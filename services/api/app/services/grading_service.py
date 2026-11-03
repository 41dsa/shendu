import asyncio
import copy
import json
from datetime import UTC, datetime
from typing import Any

from app.config import settings
from app.database import SessionLocal
from sqlalchemy.orm import Session

from app.models.entities import (
    CredentialRole,
    GradingAnswerCache,
    GradingJob,
    GradingJobStatus,
    Question,
    Report,
    Submission,
    UserAiUsage,
    UserProviderCredential,
)
from app.services.ai_client import AiCallError, ai_error_storage_message, chat_completion_json, get_credential
from app.domain.essay import essay_length_ratio, issue_tag_prompt_hint, official_essay_char_count
from app.services.coach_service import (
    build_retry_comparison,
    find_baseline_report_for_retry,
    find_report_for_submission,
)
from app.services.essay_context import EssayGradingContext, resolve_essay_context, word_bounds_for_context
from app.services.standard_engine.custom_essay_standard import ensure_custom_essay_standard
from app.services.essay_writing_guide import writing_guide_for_submission
from app.services.prompt_service import (
    get_active_custom_traditional_grading_prompt,
    get_active_grading_system_prompt,
)
from app.services.custom_traditional_grader import (
    fill_traditional_grading_prompt,
    load_default_custom_traditional_prompt,
    normalize_traditional_marking_payload,
)
from app.domain.scoring_engine.types import ScoringEngineResult
from app.services.grading_helpers import (
    answer_hash,
    build_scoring_basis,
    compute_confidence,
    confidence_user_note,
    compute_consensus_rate,
    normalize_llm_report_payload,
    reconcile_scoring_points_to_total,
    refresh_scoring_basis_fields,
    sanitize_evidence_chain,
    strip_holistic_dimension_rows,
)
from app.services.scoring_engine.merge import merge_engine_with_llm_payload
from app.services.scoring_engine.trait_report_builder import TRAIT_V1_LLM_APPEND
from app.services.scoring_engine.orchestrator import (
    engine_result_to_payload_meta,
    run_scoring_engine,
    run_scoring_engine_online,
)

GRADING_STEPS = [
    "parse_prompt",
    "check_requirements",
    "analyze_structure",
    "analyze_thesis",
    "analyze_argumentation",
    "rule_score",
    "llm_score",
    "review",
    "generate_report",
]

_SYSTEM_PROMPT_TEMPLATE = """你是申论大作文阅卷专家（不是小题概括/分析/对策题阅卷）。
评价对象是一篇完整议论文：自拟或给定主题的立意、结构、论证、语言与字数规范。
仅输出 JSON：
{
  "total_score": number,
  "score_range": [min, max],
  "trait_evidence": [
    {"trait_id": "T1"|"T2"|...|"T8", "level": "L0"|..|"L4",
     "evidence_positive": [string], "evidence_negative": [string], "evidence_missing": [string],
     "conclusion": string}
  ],
  "scoring_points": [
    {"id": string, "label": string, "earned": number, "max": number,
     "hit": "full"|"partial"|"miss", "reason": string, "evidence_ref": string}
  ],
  "issues": [
    {"tag": string, "severity": "severe"|"moderate"|"minor",
     "explanation": string, "user_quote": string, "evidence_ref": string}
  ],
  "suggestions": [string],
  "review_notes": string,
  "evidence_chain": [
    {"criterion_id": string, "label": string, "hit": "full"|"partial"|"miss",
     "user_quote": string, "material_ref": string, "earned": number, "max": number, "reason": string}
  ]
}
scoring_points 对应题目给出的维度（如立意、结构、论证、语言）。勿按「从材料摘抄要点」方式评分。
若输入含 rubric_criteria，须按 semantic 匹配（acceptable_expressions / typical_gaps），禁止纯关键词匹配。
usage_band=low 的准则仅作建议，不得作为强制扣分唯一依据。
evidence_chain 0～5 条，追溯「维度/准则→作文片段→材料依据（若有）」；无准则可省略该数组。
若 user JSON 含 deterministic_scoring（Trait V1 引擎），须以其 system_center_score / score_interval 为基准；
禁止自行给出与引擎区间冲突的精确总分；total_score 仅可填引擎中心值或 0（低置信时）。
issues / suggestions 须与 trait_evidence 及八大 Trait 诊断一致，不得另立评分标准。
issues 最多 3 条；每条 issues.user_quote 必填，须为用户作文原文连续摘录（约 15～80 字），不得写评语或概括。
suggestions 3～5 条。tag 必须使用 PRD 编号+名称，例如：
review_notes 若写「一类/二类/三类/四类文」及分数区间，须按用户作答要求里声明的题目满分（如满分35分则按35分四档）定档，勿按 rubric 维度满分（如40分）定档。"""

SYSTEM_PROMPT = (
    _SYSTEM_PROMPT_TEMPLATE
    + issue_tag_prompt_hint()
    + "。JSON 顶层键名必须使用英文：total_score, score_range, scoring_points, issues, suggestions, review_notes（勿改用中文键）。"
)

CONSENSUS_PROMPT = """你是申论大作文严格阅卷人。根据题干与用户作文，仅输出 JSON：{"score": number}。"""

_WRITING_GUIDE_SYSTEM_APPEND = (
    "\n\n用户 JSON 中若含 writing_technique_reference，表示内部写作技巧参考。"
    "给分仍以 rubric_dimensions 为准；issues/suggestions/review_notes 应对照该参考"
    "（如论点鲜明、结构、论证、语言等要求）给出可操作的改进建议，勿照搬参考原文。"
)


def append_step(job: GradingJob, step: str, detail: str = "done") -> None:
    steps = list(job.steps or [])
    steps.append({"step": step, "detail": detail, "at": datetime.now(UTC).isoformat()})
    job.steps = steps
    job.current_step = step


def rule_score_fallback(ctx: EssayGradingContext, answer: str) -> float:
    points = ctx.scoring_points or []
    max_score = float(ctx.score)
    if not points:
        return 0.0
    word_min, word_max = word_bounds_for_context(ctx)
    n = official_essay_char_count(answer)
    per = max_score / len(points)
    paragraphs = [p for p in answer.replace("\r", "").split("\n") if p.strip()]
    structure_ok = len(paragraphs) >= 4
    length_ok = word_min <= n <= word_max
    earned = 0.0
    for p in points:
        label = p.get("label", "")
        if "结构" in label:
            earned += per * (0.85 if structure_ok else 0.35)
        elif "立意" in label or "观点" in label:
            earned += per * (0.5 if n >= word_min * 0.5 else 0.2)
        elif "论证" in label:
            earned += per * (0.7 if structure_ok and n >= word_min * 0.6 else 0.25)
        elif "语言" in label:
            earned += per * (0.65 if length_ok else 0.4)
        else:
            earned += per * (0.75 if length_ok else 0.3)
    return min(max_score, round(earned, 1))


def log_usage(
    db: Session,
    user_id: str,
    job_id: str,
    cred: UserProviderCredential,
    usage: dict[str, Any] | None,
    call_type: str,
) -> None:
    """记录 token 用量；单独提交，避免 schema 漂移导致整单批改无法落库。"""
    tokens_in = usage.get("prompt_tokens") if usage else None
    tokens_out = usage.get("completion_tokens") if usage else None
    row = UserAiUsage(
        user_id=user_id,
        grading_job_id=job_id,
        model=cred.model,
        provider_base_url=cred.base_url,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        call_type=call_type,
    )
    usage_db = SessionLocal()
    try:
        usage_db.add(row)
        usage_db.commit()
    except Exception:
        usage_db.rollback()
    finally:
        usage_db.close()


def _custom_traditional_marking_enabled(custom_prompt: bool) -> bool:
    if not custom_prompt:
        return False
    mode = (settings.custom_essay_grading_mode or "trait_v1").strip().lower()
    return mode == "traditional_marking"


def short_circuit_payload(_ctx: EssayGradingContext, reason: str, word_ratio: float) -> dict[str, Any]:
    return {
        "total_score": 0,
        "score_range": [0, 0],
        "confidence": "low",
        "consensus_rate": 0,
        "display_mode": "reference_only",
        "short_circuit_reason": reason,
        "word_ratio": word_ratio,
        "scoring_points": [],
        "issues": [],
        "suggestions": ["请按大作文字数与结构要求重写后再提交批改。"],
        "rule_score": 0,
        "llm_score": 0,
    }


async def run_grading_job(db: Session, job_id: str) -> None:
    job = db.get(GradingJob, job_id)
    if not job:
        return
    submission = db.get(Submission, job.submission_id)
    if not submission:
        job.status = GradingJobStatus.failed
        job.error_message = "提交不存在"
        db.commit()
        return
    question = db.get(Question, submission.question_id)
    if not question:
        job.status = GradingJobStatus.failed
        job.error_message = "题目不存在"
        db.commit()
        return
    custom_prompt = bool((submission.user_prompt or "").strip())
    use_traditional_custom = _custom_traditional_marking_enabled(custom_prompt)
    job.status = GradingJobStatus.running
    db.commit()

    try:
        if custom_prompt and not use_traditional_custom:
            append_step(job, "custom_standard", "generating")
            db.commit()
            await ensure_custom_essay_standard(
                db,
                submission,
                question,
                user_id=job.user_id,
                grading_job_id=job.id,
            )
            append_step(job, "custom_standard", "done")
            db.commit()

        ctx = resolve_essay_context(submission, question, db)
        content = submission.content.strip()
        essay_chars = official_essay_char_count(content)
        word_min, word_max = word_bounds_for_context(ctx)

        engine_result: ScoringEngineResult | None = None
        word_ratio = 1.0
        if use_traditional_custom:
            word_ratio = essay_length_ratio(essay_chars, word_min)
            if essay_chars < 10 or word_ratio < 0.3:
                reason = "作文过短" if essay_chars < 10 else f"字数不足（低于建议字数 {word_min} 字的约 30%）"
                payload = short_circuit_payload(ctx, reason, word_ratio)
                append_step(job, "parse_prompt", "gate_reject")
                append_step(job, "generate_report", "short_circuit")
                report = Report(grading_job_id=job.id, user_id=job.user_id, payload=payload)
                db.add(report)
                job.status = GradingJobStatus.succeeded
                job.finished_at = datetime.now(UTC)
                job.current_step = "done"
                db.commit()
                return
            append_step(job, "parse_prompt", "gate_ok:traditional_marking")
            append_step(job, "analyze_structure", "traditional_marking")
        elif settings.layered_scoring_engine_enabled:
            engine_out = await run_scoring_engine_online(
                db,
                ctx,
                content,
                user_id=job.user_id,
                job_id=job.id,
                submission_id=submission.id,
            )
            if isinstance(engine_out, dict):
                word_ratio = float(engine_out.get("word_ratio") or 0)
                append_step(job, "parse_prompt", "gate_reject")
                append_step(job, "generate_report", "short_circuit")
                report = Report(grading_job_id=job.id, user_id=job.user_id, payload=engine_out)
                db.add(report)
                job.status = GradingJobStatus.succeeded
                job.finished_at = datetime.now(UTC)
                job.current_step = "done"
                db.commit()
                return
            engine_result = engine_out
            word_ratio = essay_length_ratio(essay_chars, word_min)
            append_step(job, "parse_prompt", f"gate_ok:{engine_result.exam_level}")
            append_step(job, "check_requirements", "level_adapter")
            append_step(job, "analyze_structure", "trait_v1")
            append_step(job, "analyze_thesis", engine_result.tier.tier_id)
            append_step(
                job,
                "analyze_argumentation",
                f"traits:{len(engine_result.trait_diagnostics)}",
            )
        else:
            # DEPRECATED：layered_scoring_engine_enabled=false 时走旧 LLM 主评（非 PRD V1 Trait 脊柱）
            if not settings.layered_scoring_engine_enabled and not settings.grading_point_pool_engine_allowed:
                append_step(job, "parse_prompt", "legacy_llm_only")
            word_ratio = essay_length_ratio(essay_chars, word_min)
            for step in GRADING_STEPS[:5]:
                append_step(job, step)
            if essay_chars < 10 or word_ratio < 0.3:
                reason = "作文过短" if essay_chars < 10 else f"字数不足（低于建议字数 {word_min} 字的约 30%）"
                payload = short_circuit_payload(ctx, reason, word_ratio)
                append_step(job, "generate_report", "short_circuit")
                report = Report(grading_job_id=job.id, user_id=job.user_id, payload=payload)
                db.add(report)
                job.status = GradingJobStatus.succeeded
                job.finished_at = datetime.now(UTC)
                job.current_step = "done"
                db.commit()
                return
        db.commit()

        essay_prompt = ctx.prompt.strip() or (ctx.reference_material or "")
        h = answer_hash(ctx.cache_context_key, content)
        cached = (
            db.query(GradingAnswerCache)
            .filter(GradingAnswerCache.question_id == question.id, GradingAnswerCache.answer_hash == h)
            .first()
        )
        if cached:
            if submission.parent_submission_id:
                raise AiCallError(
                    "DUPLICATE_ANSWER",
                    "重作正文与已批改过的内容完全相同，请修改后再提交。",
                )
            cached_payload = cached.report_payload
            if not isinstance(cached_payload, dict) or not cached_payload:
                raise AiCallError("DUPLICATE_ANSWER", "请修改正文后再提交")
            payload = copy.deepcopy(cached_payload)
            append_step(job, "llm_score", "cache_reuse")
            append_step(job, "generate_report", "from_cache")
            payload["attempt"] = int(submission.attempt or 1)
            payload["grading_cache_reused"] = True
            from app.services.grading_helpers import (
                compact_display_issues,
                enrich_report_essay_quotes,
                hydrate_report_display_fields,
                refresh_requirement_scoring_summary,
            )

            hydrate_report_display_fields(payload)
            enrich_report_essay_quotes(payload, content)
            compact_display_issues(payload, max_items=8 if int(payload["attempt"]) <= 1 else 4)
            refresh_requirement_scoring_summary(payload, essay_prompt)
            report = Report(grading_job_id=job.id, user_id=job.user_id, payload=payload)
            db.add(report)
            job.status = GradingJobStatus.succeeded
            job.finished_at = datetime.now(UTC)
            job.current_step = "done"
            db.commit()
            return

        cred = get_credential(db, job.user_id, CredentialRole.primary)
        if not cred:
            raise AiCallError("NO_KEY", "未配置主模型 API Key")
        guide_excerpt = writing_guide_for_submission(submission, question)
        payload_in: dict[str, Any] = {
            "task": "essay",
            "question_type": ctx.question_type.value,
            "title": ctx.title,
            "prompt": essay_prompt,
            "reference_material": ctx.reference_material,
            "rubric_dimensions": ctx.scoring_points,
            "focus_points": ctx.focus_points,
            "loss_rules": ctx.loss_rules,
            "rubric_criteria": ctx.rubric_criteria,
            "score_confidence_declaration": ctx.score_confidence_declaration,
            "standard_version": ctx.standard_version,
            "exam_policy": ctx.exam_policy,
            "exam_standard_version": ctx.exam_standard_version,
            "max_score": ctx.score,
            "word_min": word_min,
            "word_max": word_max,
            "user_essay": content,
        }
        if guide_excerpt:
            payload_in["writing_technique_reference"] = guide_excerpt
        if engine_result is not None:
            payload_in["deterministic_scoring"] = engine_result_to_payload_meta(engine_result)
            payload_in["deterministic_scoring"]["total_score"] = engine_result.total_score
            payload_in["deterministic_scoring"]["system_center_score"] = engine_result.system_center_score
            payload_in["deterministic_scoring"]["score_interval"] = (
                list(engine_result.score_interval) if engine_result.score_interval else None
            )
            payload_in["deterministic_scoring"]["trait_diagnostics"] = engine_result.trait_diagnostics
            payload_in["deterministic_scoring"]["dimension_rows"] = engine_result.dimension_rows
        if submission.parent_submission_id:
            baseline_for_prompt = find_baseline_report_for_retry(db, submission)
            if baseline_for_prompt and baseline_for_prompt.payload:
                from app.services.grading_helpers import prior_core_problems_for_retry

                prior_items = prior_core_problems_for_retry(baseline_for_prompt.payload)
                if prior_items:
                    from app.services.grading_helpers import display_total_score

                    prior_total = display_total_score(baseline_for_prompt.payload)
                    payload_in["retry_grading"] = {
                        "attempt": int(submission.attempt or 2),
                        "prior_total_score": prior_total,
                        "prior_core_problems": prior_items,
                        "instructions": (
                            "本次为重新作答批改。请先对照 prior_core_problems 判断上次问题是否已改进；"
                            "已消除的问题勿再列入 core_problems/issues。"
                            "重新作答时 core_problems 只能包含 level=轻微 的残留问题（最多 4 条）；"
                            "仍属中等或严重的问题不要写入 core_problems（系统会单独判定并要求继续修改）。"
                            "新发现的轻微问题最多 1～2 条。"
                            "若多处 prior 问题已在文中实质改进且未新增同等严重问题，"
                            f"total_score 应高于 prior_total_score（{prior_total:g}），"
                            "通常上调 1～4 分并体现在 dimension_scores；"
                            "勿在明显改进后仍给出与上次相同总分。"
                        ),
                    }
        else:
            payload_in["first_grading"] = {
                "instructions": (
                    "首次批改：core_problems 须尽量覆盖文中问题，每条必填 level（严重/中等/轻微），"
                    "严重、中等、轻微各档均要如实列出，不要只写最严重几条。"
                ),
            }
        if use_traditional_custom:
            template = get_active_custom_traditional_grading_prompt(
                db, load_default_custom_traditional_prompt()
            )
            system_prompt = fill_traditional_grading_prompt(
                template,
                ctx=ctx,
                essay=content,
                word_min=word_min,
                word_max=word_max,
                essay_char_count=essay_chars,
                submission=submission,
            )
            user_prompt = "请开始评分。"
        else:
            user_prompt = json.dumps(payload_in, ensure_ascii=False)
            system_prompt = get_active_grading_system_prompt(db, SYSTEM_PROMPT)
            if engine_result is not None and engine_result.trait_diagnostics:
                system_prompt = system_prompt + TRAIT_V1_LLM_APPEND
            if guide_excerpt:
                system_prompt = system_prompt + _WRITING_GUIDE_SYSTEM_APPEND

        append_step(job, "rule_score")
        rule = float(engine_result.total_score) if engine_result else rule_score_fallback(ctx, content)
        db.commit()

        append_step(job, "llm_score", "calling")
        db.commit()
        try:
            raw, usage = await asyncio.wait_for(
                chat_completion_json(cred, system_prompt, user_prompt),
                timeout=settings.grading_llm_timeout_seconds,
            )
        except TimeoutError as exc:
            raise AiCallError(
                "TIMEOUT",
                f"模型调用超过 {int(settings.grading_llm_timeout_seconds)} 秒，请检查网络与 AI 设置",
            ) from exc
        log_usage(db, job.user_id, job.id, cred, usage, "primary")
        parsed_llm = json.loads(raw)
        if use_traditional_custom:
            parsed_llm = normalize_traditional_marking_payload(parsed_llm)
        payload = normalize_llm_report_payload(parsed_llm)

        if engine_result is not None and not use_traditional_custom:
            payload = merge_engine_with_llm_payload(
                engine_result,
                payload,
                max_llm_delta=settings.layered_scoring_max_llm_delta,
                max_score=float(ctx.score),
                grading_ctx=ctx,
            )
        llm_score = float(payload.get("total_score", rule))
        if engine_result is None:
            payload["rule_score"] = rule

        # 为维度条目补上 ability 字段，供 coach 能力聚合（与题库 rubric 对齐）
        rubric_by_id = {p.get("id"): p for p in (ctx.scoring_points or []) if p.get("id")}
        for point in payload.get("scoring_points") or []:
            if point.get("ability"):
                continue
            ref = rubric_by_id.get(point.get("id")) or {}
            if ref.get("ability"):
                point["ability"] = ref["ability"]
            elif ref.get("label"):
                from app.domain.essay import label_to_ability

                point["ability"] = label_to_ability(str(ref.get("label")))

        primary_llm_score = float(
            payload.get("merged_total") or payload.get("total_score") or llm_score
        )
        consensus_scores = [primary_llm_score]
        consensus_delta: float | None = None
        consensus_discarded = False

        # 双路复核：字数达标且未开省流时必跑第二次总分检验（与主评/规则是否接近无关）
        use_consensus = (
            not use_traditional_custom and not cred.save_tokens_mode and word_ratio >= 0.3
        )
        if use_consensus:
            append_step(job, "review", "consensus")
            db.commit()
            cred2 = get_credential(db, job.user_id, CredentialRole.consensus) or cred
            try:
                raw2, usage2 = await chat_completion_json(cred2, CONSENSUS_PROMPT, user_prompt)
                log_usage(db, job.user_id, job.id, cred2, usage2, "consensus")
                score2 = float(json.loads(raw2).get("score", primary_llm_score))
                consensus_scores.append(score2)
                consensus_delta = abs(primary_llm_score - score2)
                max_delta = settings.grading_consensus_max_delta
                if consensus_delta > max_delta:
                    consensus_discarded = True
                    llm_score = primary_llm_score
                elif consensus_delta > 1.0:
                    llm_score = round((primary_llm_score + score2) / 2, 1)
            except AiCallError:
                consensus_scores.append(llm_score)

        payload["max_score"] = float(ctx.score)
        payload["consensus_scores"] = consensus_scores
        payload["primary_llm_score"] = primary_llm_score
        if len(consensus_scores) > 1:
            payload["consensus_review_score"] = consensus_scores[1]
        payload["consensus_delta"] = consensus_delta
        payload["consensus_discarded"] = consensus_discarded
        payload["consensus_ran"] = len(consensus_scores) >= 2
        payload["consensus_rate"] = compute_consensus_rate(consensus_scores, float(ctx.score))
        payload["llm_score"] = llm_score
        if engine_result is not None and engine_result.trait_diagnostics:
            if engine_result.suppress_absolute_score:
                payload["total_score"] = 0.0
            else:
                payload["total_score"] = float(
                    engine_result.system_center_score or engine_result.total_score or 0
                )
            payload["merged_total"] = payload["total_score"]
        else:
            payload["total_score"] = llm_score
        payload["attempt"] = int(submission.attempt or 1)
        from app.services.grading_helpers import (
            compact_display_issues,
            enforce_retry_issue_severity_policy,
            hydrate_report_display_fields,
        )

        hydrate_report_display_fields(payload)
        from app.services.grading_helpers import enrich_report_essay_quotes

        enrich_report_essay_quotes(payload, submission.content or "")
        attempt_n = int(payload["attempt"])
        compact_display_issues(payload, max_items=8 if attempt_n <= 1 else 4)
        strip_holistic_dimension_rows(payload)
        reconcile_scoring_points_to_total(payload)
        sanitize_evidence_chain(payload, essay_max=float(ctx.score))

        conf = compute_confidence(
            llm_score,
            rule,
            float(ctx.score),
            consensus_delta,
            word_ratio,
            consensus_discarded=consensus_discarded,
        )
        if payload.get("engine_total_discarded"):
            conf = "medium"
        payload["confidence"] = conf
        payload["confidence_scope"] = "total_score"
        payload["confidence_note"] = confidence_user_note(
            conf,
            word_ratio,
            consensus_ran=payload["consensus_ran"],
            consensus_discarded=consensus_discarded,
        )

        payload["display_mode"] = "normal"

        if ctx.standard_version is not None and custom_prompt:
            grading_standard_mode = "custom_engine"
        elif ctx.standard_version is not None:
            grading_standard_mode = "published"
        else:
            grading_standard_mode = "default_rubric"
        payload["essay_meta"] = {
            "word_min": word_min,
            "word_max": word_max,
            "word_ratio": round(word_ratio, 3),
            "essay_char_count": essay_chars,
            "title": ctx.title,
            "prompt_excerpt": essay_prompt[:200],
            "has_user_material": bool(ctx.reference_material),
            "standard_version": ctx.standard_version,
            "exam_standard_version": ctx.exam_standard_version,
            "grading_standard_mode": grading_standard_mode,
            "writing_guide_applied": bool(guide_excerpt),
            "score_confidence_declaration": ctx.score_confidence_declaration,
            "scoring_engine_mode": (
                "custom_traditional_marking"
                if use_traditional_custom
                else (
                    "diagnostic_trait_v1"
                    if engine_result is not None and engine_result.trait_diagnostics
                    else ("layered" if engine_result is not None else "legacy")
                )
            ),
            "custom_grading_mode": (
                "traditional_marking" if use_traditional_custom else settings.custom_essay_grading_mode
            ),
            "exam_level": engine_result.exam_level if engine_result else None,
            "level_inferred": engine_result.level_inferred if engine_result else None,
        }
        if ctx.standard_version is not None:
            payload["standard_version"] = ctx.standard_version
        if ctx.exam_standard_version is not None:
            payload["exam_standard_version"] = ctx.exam_standard_version
        from app.services.grading_helpers import flag_review_tier_mismatch, refresh_requirement_scoring_summary

        refresh_requirement_scoring_summary(payload, essay_prompt)
        display_max = float(payload.get("display_max_score") or ctx.score)
        flag_review_tier_mismatch(payload, max_score=display_max)

        payload["scoring_basis"] = build_scoring_basis(
            payload,
            {
                "scoring_points": ctx.scoring_points,
                "max_score": ctx.score,
                "prompt_excerpt": essay_prompt[:200],
            },
        )
        refresh_scoring_basis_fields(payload)

        # 二次作答：与上一稿对比后再执行「仅接受轻微残留」策略（P5 / BE-502）
        if submission.parent_submission_id:
            baseline_report = find_baseline_report_for_retry(db, submission)
            comparison: dict | None = None
            if baseline_report and baseline_report.payload:
                comparison = build_retry_comparison(baseline_report.payload, payload)
                payload["comparison"] = comparison
                payload["parent_report_id"] = baseline_report.id
            enforce_retry_issue_severity_policy(payload, comparison=comparison)
            if baseline_report and baseline_report.payload and comparison:
                from app.domain.retry_tier_lift import apply_retry_tier_lift

                baseline_content = ""
                if baseline_report.grading_job_id:
                    prev_job = db.get(GradingJob, baseline_report.grading_job_id)
                    if prev_job:
                        prev_sub = db.get(Submission, prev_job.submission_id)
                        if prev_sub:
                            baseline_content = prev_sub.content or ""
                apply_retry_tier_lift(
                    payload,
                    baseline_payload=dict(baseline_report.payload or {}),
                    comparison=comparison,
                    display_max=float(payload.get("display_max_score") or ctx.score),
                    baseline_essay=baseline_content,
                    current_essay=content or "",
                )
                refresh_requirement_scoring_summary(payload, essay_prompt)
            if payload.get("retry_issue_policy_ok") is False:
                payload["confidence"] = "medium"
                note = str(payload.get("confidence_note") or "").strip()
                extra = "改写后仍有中等及以上问题，总分仅供参考，请优先处理「待继续改进」列表。"
                payload["confidence_note"] = f"{note} {extra}".strip() if note else extra

        if (
            submission.parent_submission_id
            and baseline_report
            and baseline_report.payload
            and engine_result
            and settings.weak_supervision_enabled
        ):
            from app.services.weak_supervision_factory import persist_retry_trait_delta

            prior_traits = list(baseline_report.payload.get("trait_diagnostics") or [])
            current_traits = list(payload.get("trait_diagnostics") or [])
            persist_retry_trait_delta(
                db,
                grading_job_id=job.id,
                submission_id=submission.id,
                question_id=question.id,
                prior_traits=prior_traits,
                current_traits=current_traits,
                rubric_version=str(engine_result.rubric_version or engine_result.point_pool_version or ""),
            )
            if settings.weak_supervision_enabled:
                from app.services.active_learning_pool import enqueue_retry_trait_volatility

                enqueue_retry_trait_volatility(
                    db,
                    grading_job_id=job.id,
                    submission_id=submission.id,
                    question_id=question.id,
                    prior_traits=prior_traits,
                    current_traits=current_traits,
                )

        append_step(job, "generate_report")
        report = Report(grading_job_id=job.id, user_id=job.user_id, payload=payload)
        db.add(report)
        db.flush()

        cache_row = (
            db.query(GradingAnswerCache)
            .filter(GradingAnswerCache.question_id == question.id, GradingAnswerCache.answer_hash == h)
            .first()
        )
        if cache_row:
            cache_row.report_payload = payload
        else:
            db.add(
                GradingAnswerCache(
                    question_id=question.id,
                    answer_hash=h,
                    report_payload=payload,
                )
            )

        job.status = GradingJobStatus.succeeded
        job.finished_at = datetime.now(UTC)
        job.current_step = "done"
        db.commit()
    except AiCallError as exc:
        job.status = GradingJobStatus.failed
        job.error_message = ai_error_storage_message(exc)
        job.finished_at = datetime.now(UTC)
        fail_step = "llm_score"
        steps = job.steps or []
        if not any(s.get("step") == "parse_prompt" for s in steps):
            # custom_standard 已 done 但未到 gate_ok → Trait 在线引擎 / 证据 LLM
            if custom_prompt and any(s.get("step") == "custom_standard" for s in steps):
                fail_step = "analyze_structure"
            elif custom_prompt:
                fail_step = "custom_standard"
            else:
                fail_step = "analyze_structure"
        append_step(job, fail_step, f"failed:{exc.code}")
        job.current_step = "done"
        db.commit()
    except json.JSONDecodeError:
        job.status = GradingJobStatus.failed
        job.error_message = "UPSTREAM: 模型返回非 JSON"
        job.finished_at = datetime.now(UTC)
        job.current_step = "done"
        db.commit()
    except Exception as exc:  # noqa: BLE001
        job.status = GradingJobStatus.failed
        detail = str(exc).strip() or type(exc).__name__
        job.error_message = f"INTERNAL: {detail[:400]}"
        job.finished_at = datetime.now(UTC)
        job.current_step = "done"
        db.commit()
