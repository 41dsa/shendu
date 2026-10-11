import asyncio
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
from app.services.ai_client import AiCallError, chat_completion_json, get_credential
from app.domain.essay import essay_length_ratio, issue_tag_prompt_hint
from app.services.coach_service import build_retry_comparison, find_report_for_submission
from app.services.essay_context import EssayGradingContext, resolve_essay_context, word_bounds_for_context
from app.services.essay_writing_guide import writing_guide_for_submission
from app.services.prompt_service import get_active_grading_system_prompt
from app.services.grading_helpers import (
    answer_hash,
    build_scoring_basis,
    compute_confidence,
    confidence_user_note,
    compute_consensus_rate,
    normalize_llm_report_payload,
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
issues 最多 3 条；suggestions 3～5 条。tag 必须使用 PRD 编号+名称，例如："""

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
    n = len(answer.strip())
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
    ctx = resolve_essay_context(submission, question, db)

    job.status = GradingJobStatus.running
    db.commit()

    try:
        content = submission.content.strip()
        word_min, word_max = word_bounds_for_context(ctx)
        word_ratio = essay_length_ratio(len(content), word_min)

        for step in GRADING_STEPS[:5]:
            append_step(job, step)
            db.commit()

        if len(content) < 10 or word_ratio < 0.3:
            reason = "作文过短" if len(content) < 10 else f"字数不足（低于建议字数 {word_min} 字的约 30%）"
            payload = short_circuit_payload(ctx, reason, word_ratio)
            append_step(job, "generate_report", "short_circuit")
            report = Report(grading_job_id=job.id, user_id=job.user_id, payload=payload)
            db.add(report)
            job.status = GradingJobStatus.succeeded
            job.finished_at = datetime.now(UTC)
            job.current_step = "done"
            db.commit()
            return

        h = answer_hash(ctx.cache_context_key, content)
        cached = (
            db.query(GradingAnswerCache)
            .filter(GradingAnswerCache.question_id == question.id, GradingAnswerCache.answer_hash == h)
            .first()
        )
        if cached:
            payload = dict(cached.report_payload)
            payload["from_cache"] = True
            append_step(job, "llm_score", "cache_hit")
            append_step(job, "review")
            append_step(job, "generate_report")
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

        essay_prompt = ctx.prompt.strip() or (ctx.reference_material or "")
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
        user_prompt = json.dumps(payload_in, ensure_ascii=False)

        append_step(job, "rule_score")
        rule = rule_score_fallback(ctx, content)
        db.commit()

        append_step(job, "llm_score", "calling")
        db.commit()

        system_prompt = get_active_grading_system_prompt(db, SYSTEM_PROMPT)
        if guide_excerpt:
            system_prompt = system_prompt + _WRITING_GUIDE_SYSTEM_APPEND
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
        payload = normalize_llm_report_payload(json.loads(raw))

        llm_score = float(payload.get("total_score", rule))
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

        primary_llm_score = llm_score
        consensus_scores = [llm_score]
        consensus_delta: float | None = None
        consensus_discarded = False

        # 双路复核：字数达标且未开省流时必跑第二次总分检验（与主评/规则是否接近无关）
        use_consensus = not cred.save_tokens_mode and word_ratio >= 0.3
        if use_consensus:
            append_step(job, "review", "consensus")
            db.commit()
            cred2 = get_credential(db, job.user_id, CredentialRole.consensus) or cred
            try:
                raw2, usage2 = await chat_completion_json(cred2, CONSENSUS_PROMPT, user_prompt)
                log_usage(db, job.user_id, job.id, cred2, usage2, "consensus")
                score2 = float(json.loads(raw2).get("score", llm_score))
                consensus_scores.append(score2)
                consensus_delta = abs(llm_score - score2)
                max_delta = settings.grading_consensus_max_delta
                if consensus_delta > max_delta:
                    consensus_discarded = True
                    llm_score = primary_llm_score
                elif consensus_delta > 1.0:
                    llm_score = round((llm_score + score2) / 2, 1)
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
        payload["total_score"] = llm_score

        conf = compute_confidence(
            llm_score,
            rule,
            float(ctx.score),
            consensus_delta,
            word_ratio,
            consensus_discarded=consensus_discarded,
        )
        payload["confidence"] = conf
        payload["confidence_scope"] = "total_score"
        payload["confidence_note"] = confidence_user_note(
            conf,
            word_ratio,
            consensus_ran=payload["consensus_ran"],
            consensus_discarded=consensus_discarded,
        )

        span = 1.0 if conf == "high" else 2.0 if conf == "medium" else 2.5
        payload["score_range"] = [
            max(0, round(llm_score - span, 1)),
            min(float(ctx.score), round(llm_score + span, 1)),
        ]

        payload["display_mode"] = "normal"

        grading_standard_mode = "published" if ctx.standard_version is not None else "default_rubric"
        payload["essay_meta"] = {
            "word_min": word_min,
            "word_max": word_max,
            "title": ctx.title,
            "prompt_excerpt": essay_prompt[:200],
            "has_user_material": bool(ctx.reference_material),
            "standard_version": ctx.standard_version,
            "exam_standard_version": ctx.exam_standard_version,
            "grading_standard_mode": grading_standard_mode,
            "writing_guide_applied": bool(guide_excerpt),
            "score_confidence_declaration": ctx.score_confidence_declaration,
        }
        if ctx.standard_version is not None:
            payload["standard_version"] = ctx.standard_version
        if ctx.exam_standard_version is not None:
            payload["exam_standard_version"] = ctx.exam_standard_version
        payload["scoring_basis"] = build_scoring_basis(
            payload,
            {
                "scoring_points": ctx.scoring_points,
                "max_score": ctx.score,
                "prompt_excerpt": essay_prompt[:200],
            },
        )

        # 二次作答：与首次报告对比（P5 / BE-502）
        if submission.parent_submission_id:
            payload["attempt"] = submission.attempt
            parent_report = find_report_for_submission(db, submission.parent_submission_id)
            if parent_report and parent_report.payload:
                payload["comparison"] = build_retry_comparison(parent_report.payload, payload)
                payload["parent_report_id"] = parent_report.id

        append_step(job, "generate_report")
        report = Report(grading_job_id=job.id, user_id=job.user_id, payload=payload)
        db.add(report)

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
        job.error_message = f"{exc.code}: {exc}"
        job.finished_at = datetime.now(UTC)
        append_step(job, "llm_score", f"failed:{exc.code}")
        db.commit()
    except json.JSONDecodeError:
        job.status = GradingJobStatus.failed
        job.error_message = "UPSTREAM: 模型返回非 JSON"
        job.finished_at = datetime.now(UTC)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        job.status = GradingJobStatus.failed
        job.error_message = "INTERNAL"
        job.finished_at = datetime.now(UTC)
        db.commit()
        raise exc
