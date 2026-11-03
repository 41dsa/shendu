"""PRD V1 诊断报告生成器：以 Trait 引擎 payload 为唯一脊柱，LLM 仅润色叙事。"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.domain.scoring_engine.trait_definitions import SCORABLE_TRAIT_WEIGHTS, level_to_numeric
from app.domain.scoring_engine.types import ScoringEngineResult
from app.domain.essay_grading_context import EssayGradingContext

REPORT_SCHEMA_VERSION = "prd_v1_diagnostic_v1"

PRD_SCORE_DISCLAIMER = (
    "本报告由 AI 诊断引擎生成，非官方阅卷分数；区间与能力等级未经命题方校准，"
    "请勿作为估分依据或对外宣称准确。"
)

NO_ANCHOR_CALIBRATION_SUFFIX = "本题尚无足够锚作文校准，请勿将区间当作精确估分。"

NON_OFFICIAL_NOTICE = "AI 辅助诊断，非官方评分结果。"

TRAIT_V1_LLM_APPEND = """

【Trait V1 锁定模式】输入 JSON 中 deterministic_scoring.engine 为 diagnostic_trait_v1 时：
- 禁止修改 total_score、score_range、scoring_points 的分项等级与 earned；
- 勿输出 trait_evidence 或与引擎冲突的维度分；
- issues 每条必须含 trait_id（T1～T8），最多 5 条，仅可润色 explanation（不得改变失分维度排序）；
- suggestions 为 3～5 条，每条为 {"trait_id":"T?","text":"..."} 或字符串（字符串须以 T? 开头）；
- 可选 diagnostic_polish：{"q7_next_steps":[string]} 润色第七问，不得改写 Trait 等级；
- review_notes 可写总体评语，勿重新定档总分。
"""


def _standard_from_ctx(ctx: EssayGradingContext):
    from app.domain.scoring_engine.question_standard_card import build_question_standard_card

    return build_question_standard_card(ctx)


def build_diagnostic_header(
    engine: ScoringEngineResult,
    ctx: EssayGradingContext,
    *,
    suggestion_texts: list[str] | None = None,
) -> dict[str, Any]:
    traits = engine.trait_diagnostics or []
    pos = []
    miss = []
    for row in traits:
        pos.extend(row.get("evidence_positive") or [])
        miss.extend(row.get("evidence_missing") or [])
    disputes = list(engine.trait_dispute_notes or [])
    for row in traits:
        if row.get("dispute_hint"):
            disputes.append(str(row["dispute_hint"]))
    base = dict(engine.diagnostic_header or {})
    return {
        "q1_task": base.get("q1_task") or (ctx.prompt[:500] if ctx.prompt else ""),
        "q2_met": base.get("q2_met")
        or [
            f"{row.get('name')}（{row.get('level')}）"
            for row in traits
            if row.get("level") in ("L3", "L4")
        ],
        "q3_evidence": (base.get("q3_evidence") or pos)[:8],
        "q4_unmet": (base.get("q4_unmet") or miss)[:8],
        "q5_loss_sources": base.get("q5_loss_sources") or list(engine.primary_loss_traits or []),
        "q6_disputes": (base.get("q6_disputes") or disputes)[:6],
        "q7_next_steps": base.get("q7_next_steps") or list(suggestion_texts or [])[:5],
    }


def _severity_for_level(level: str | None) -> str:
    lv = str(level or "L2").upper()
    if lv == "L0":
        return "severe"
    if lv in ("L1", "L2"):
        return "moderate"
    return "minor"


def _loss_rank(row: dict[str, Any]) -> float:
    tid = str(row.get("trait_id") or "")
    w = float(SCORABLE_TRAIT_WEIGHTS.get(tid, 0.08))
    lv = row.get("level")
    if not lv:
        return 0.0
    gap = (4 - level_to_numeric(lv)) / 4.0
    missing = len(row.get("evidence_missing") or [])
    return w * gap + missing * 0.02


def build_issues_from_traits(trait_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = [r for r in trait_rows if r.get("participates_in_score")]
    candidates.sort(key=_loss_rank, reverse=True)
    issues: list[dict[str, Any]] = []
    for row in candidates:
        if _loss_rank(row) <= 0.01 and not (row.get("evidence_missing") or row.get("evidence_negative")):
            continue
        tid = str(row.get("trait_id") or "")
        name = str(row.get("name") or tid)
        quote = ""
        neg = row.get("evidence_negative") or []
        pos = row.get("evidence_positive") or []
        if neg:
            quote = str(neg[0])[:120]
        elif pos:
            quote = str(pos[0])[:120]
        miss = row.get("evidence_missing") or []
        explanation = str(row.get("conclusion") or "").strip()
        if miss and not explanation:
            explanation = str(miss[0])
        issues.append(
            {
                "tag": f"{tid} {name}",
                "trait_id": tid,
                "weight": round(float(SCORABLE_TRAIT_WEIGHTS.get(tid, 0.08)), 3),
                "severity": _severity_for_level(row.get("level")),
                "explanation": explanation or f"{name} 维度表现偏弱（{row.get('level')}）",
                "user_quote": quote,
                "evidence_ref": tid,
            }
        )
        if len(issues) >= 5:
            break
    return issues


def build_structured_suggestions(trait_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    ranked = sorted(trait_rows, key=_loss_rank, reverse=True)
    for row in ranked:
        tid = str(row.get("trait_id") or "")
        name = str(row.get("name") or tid)
        for miss in row.get("evidence_missing") or []:
            text = str(miss).strip()
            if not text:
                continue
            out.append(
                {
                    "trait_id": tid,
                    "trait_name": name,
                    "text": f"针对{name}：补全「{text[:80]}」所对应的论述或材料转化。",
                    "evidence_missing": text[:160],
                }
            )
            if len(out) >= 6:
                return out
    for row in ranked:
        if row.get("level") not in ("L0", "L1", "L2"):
            continue
        tid = str(row.get("trait_id") or "")
        name = str(row.get("name") or tid)
        out.append(
            {
                "trait_id": tid,
                "trait_name": name,
                "text": f"提升 {name}：由 {row.get('level')} 向 L3 推进，增加可核验的原文论据与层次推进。",
                "evidence_missing": "",
            }
        )
        if len(out) >= 5:
            break
    return out[:5]


def _parse_trait_id_from_suggestion(item: Any) -> tuple[str, str]:
    if isinstance(item, dict):
        tid = str(item.get("trait_id") or "").strip().upper()
        text = str(item.get("text") or "").strip()
        return tid, text
    s = str(item or "").strip()
    if len(s) >= 2 and s[0].upper() == "T" and s[1].isdigit():
        tid = s[:2].upper()
        rest = s[2:].lstrip(" ：:")
        return tid, rest or s
    return "", s


def _merge_llm_issues(spine: list[dict[str, Any]], llm_issues: list[Any]) -> list[dict[str, Any]]:
    by_trait: dict[str, dict[str, Any]] = {str(i.get("trait_id")): dict(i) for i in spine if i.get("trait_id")}
    for raw in llm_issues or []:
        if not isinstance(raw, dict):
            continue
        tid = str(raw.get("trait_id") or "").strip().upper()
        if not tid:
            tag = str(raw.get("tag") or "")
            if tag.upper().startswith("T") and len(tag) >= 2:
                tid = tag[:2].upper()
        if tid not in by_trait:
            continue
        expl = str(raw.get("explanation") or raw.get("problem") or "").strip()
        quote = str(raw.get("user_quote") or "").strip()
        if expl:
            by_trait[tid]["explanation"] = expl[:500]
        if quote:
            by_trait[tid]["user_quote"] = quote[:120]
    merged = list(by_trait.values())
    merged.sort(key=lambda x: float(x.get("weight") or 0), reverse=True)
    return merged[:5]


def _merge_llm_suggestions(
    spine: list[dict[str, Any]],
    llm_suggestions: list[Any],
) -> list[dict[str, Any]]:
    out = list(spine)
    seen = {(s.get("trait_id"), s.get("text")) for s in out}
    for item in llm_suggestions or []:
        tid, text = _parse_trait_id_from_suggestion(item)
        if not text:
            continue
        key = (tid, text)
        if key in seen:
            continue
        seen.add(key)
        out.append({"trait_id": tid or "T1", "trait_name": "", "text": text[:400], "evidence_missing": ""})
        if len(out) >= 5:
            break
    return out[:5]


def _mark_evidence_gaps(trait_rows: list[dict[str, Any]]) -> None:
    for row in trait_rows:
        has = bool(row.get("evidence_positive") or row.get("evidence_negative"))
        row["evidence_insufficient"] = bool(row.get("participates_in_score")) and not has


def _apply_scoring_point_withhold(payload: dict[str, Any]) -> None:
    traits = {str(t.get("trait_id")): t for t in (payload.get("trait_diagnostics") or [])}
    for pt in payload.get("scoring_points") or []:
        if not isinstance(pt, dict):
            continue
        tid = str(pt.get("id") or "")
        tr = traits.get(tid) or {}
        if tr.get("evidence_insufficient"):
            pt["earned"] = None
            pt["hit"] = "withheld"
            pt["reason"] = (pt.get("reason") or "") + "（证据不足，不展示维度估分）"


def finalize_trait_v1_report(
    payload: dict[str, Any],
    engine: ScoringEngineResult,
    ctx: EssayGradingContext,
    *,
    llm_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """合并 LLM 叙事后强制回写 Trait 脊柱字段。"""
    llm = llm_snapshot or {}
    traits = [dict(r) for r in (engine.trait_diagnostics or [])]
    _mark_evidence_gaps(traits)
    payload["trait_diagnostics"] = traits
    if payload.get("scoring_engine") and isinstance(payload["scoring_engine"], dict):
        payload["scoring_engine"]["trait_diagnostics"] = traits

    suggestions = build_structured_suggestions(traits)
    suggestions = _merge_llm_suggestions(suggestions, llm.get("suggestions") or payload.get("suggestions"))
    payload["structured_suggestions"] = suggestions
    payload["suggestions"] = [s["text"] for s in suggestions if s.get("text")]

    issues = build_issues_from_traits(traits)
    issues = _merge_llm_issues(issues, llm.get("issues") or payload.get("issues"))
    payload["issues"] = issues[:5]

    polish = llm.get("diagnostic_polish") if isinstance(llm.get("diagnostic_polish"), dict) else {}
    header = build_diagnostic_header(engine, ctx, suggestion_texts=payload["suggestions"])
    if isinstance(polish.get("q7_next_steps"), list) and polish["q7_next_steps"]:
        header["q7_next_steps"] = [str(x) for x in polish["q7_next_steps"][:5]]
    payload["diagnostic_header"] = header

    payload["report_schema"] = REPORT_SCHEMA_VERSION
    disclaimer = PRD_SCORE_DISCLAIMER
    if int(engine.anchor_count or 0) <= 0:
        disclaimer = f"{disclaimer} {NO_ANCHOR_CALIBRATION_SUFFIX}"
    payload["score_disclaimer"] = disclaimer
    payload["non_official_notice"] = NON_OFFICIAL_NOTICE
    std_marks = list(_standard_from_ctx(ctx).dispute_marks or [])
    if std_marks:
        payload["standard_dispute_marks"] = std_marks
        header["q6_disputes"] = list(dict.fromkeys(list(header.get("q6_disputes") or []) + std_marks))[:8]
        payload["diagnostic_header"] = header
    payload["ability_level"] = engine.ability_level or payload.get("ability_level")
    payload["trait_confidence"] = engine.trait_confidence
    payload["standard_match_confidence"] = engine.standard_match_confidence
    payload["multi_standard_views"] = engine.multi_standard_views or payload.get("multi_standard_views")
    payload["score_display_mode"] = engine.score_display_mode
    payload["human_review_recommended"] = engine.human_review_recommended
    if engine.human_review_recommended:
        from app.domain.scoring_engine.score_display_policy import HUMAN_REVIEW_NOTE

        payload["human_review_note"] = HUMAN_REVIEW_NOTE
    payload["diagnostic_only_mode"] = bool(settings.diagnostic_only_mode)
    if settings.diagnostic_only_mode:
        payload["score_display_mode"] = "tier_only"
        payload["score_range"] = [0, 0]
        payload["total_score"] = 0.0
        payload["merged_total"] = 0.0
        payload["display_mode"] = "reference_only"
    payload["anchor_count"] = engine.anchor_count
    if engine.anchor_relative_scale:
        payload["anchor_relative_scale"] = engine.anchor_relative_scale

    dispute_block = (engine.multi_standard_views or {}).get("dependency") or {}
    dep_traits = dispute_block.get("traits") or []
    payload["standard_dependency_traits"] = dep_traits
    payload["trait_dispute_notes"] = list(
        dict.fromkeys(
            list(engine.trait_dispute_notes or [])
            + [str(t.get("dispute_hint") or "") for t in traits if t.get("dispute_hint")]
        )
    )

    _apply_scoring_point_withhold(payload)
    if engine.evidence_chain:
        payload["evidence_chain"] = list(engine.evidence_chain)
    return payload
