import hashlib
import json
import re
from typing import Any

from app.domain.essay import resolve_issue_badge


def normalize_answer(text: str) -> str:
    t = re.sub(r"\s+", "", text.strip())
    return t.lower()


def answer_hash(question_id: str, content: str, rubric_version: str = "v1") -> str:
    raw = f"{question_id}:{rubric_version}:{normalize_answer(content)}"
    return hashlib.sha256(raw.encode()).hexdigest()


def compute_confidence(
    total_score: float,
    rule_score: float,
    max_score: float,
    consensus_delta: float | None,
    word_ratio: float,
    *,
    consensus_discarded: bool = False,
) -> str:
    """
    总分数置信度（非整份批改可信度）。完整维度/问题/建议来自主评，不因本字段降级。
    「low」仅保留给字数严重不足等硬条件，避免用户误以为 AI 批改无效。
    """
    if word_ratio < 0.3:
        return "low"
    rule_gap = abs(total_score - rule_score)
    rule_medium = max(3.0, max_score * 0.12)
    rule_high = max(1.5, max_score * 0.06)

    if consensus_discarded:
        return "medium"

    if consensus_delta is not None and consensus_delta > 1.5:
        return "medium"
    if rule_gap > rule_medium:
        return "medium"
    if consensus_delta is not None and consensus_delta > 0.8:
        return "medium"
    if rule_gap > rule_high:
        return "medium"
    # 双路总分一致时提高总分数置信度（完整批改 + 复核均通过）
    if consensus_delta is not None and consensus_delta <= 1.0:
        return "high"
    return "medium" if rule_gap > rule_high else "high"


def confidence_user_note(
    confidence: str,
    word_ratio: float,
    *,
    consensus_ran: bool = False,
    consensus_discarded: bool = False,
) -> str:
    if confidence == "low":
        return "作文字数明显不足，总分仅供参考；仍可根据维度与建议改进写法。"
    if consensus_ran and not consensus_discarded and confidence == "high":
        return "已完成完整批改与双路总分复核且结果接近；总分与维度、建议均可作为主要参考。"
    if consensus_discarded:
        return "已完成双路检验，但两次总分差距较大，报告采用完整批改主评；维度与建议仍可直接用于修改。"
    if consensus_ran:
        return "已完成双路总分检验；各维度得分与问题、建议可直接用于修改，总分请结合合理区间理解。"
    if confidence == "medium":
        return "总分建议在合理区间内理解；各维度得分与问题、建议可直接用于修改。"
    return "总分与维度反馈均可作为主要参考。"


def compute_consensus_rate(scores: list[float], max_score: float) -> float:
    if len(scores) < 2 or max_score <= 0:
        return 100.0
    mean = sum(scores) / len(scores)
    var = sum((s - mean) ** 2 for s in scores) / len(scores)
    std = var**0.5
    rate = max(0.0, min(100.0, (1 - std / max_score) * 100))
    return round(rate, 1)


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _infer_hit(earned: float, max_score: float) -> str:
    if max_score <= 0:
        return "miss"
    ratio = earned / max_score
    if ratio >= 0.85:
        return "full"
    if ratio >= 0.5:
        return "partial"
    return "miss"


def _parse_score_value(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        m = re.search(r"([\d]+(?:\.\d+)?)", value.replace(" ", ""))
        if m:
            return float(m.group(1))
    return _to_float(value, default=-1.0) if value is not None else None


def _payload_section(payload: dict[str, Any], *logical_names: str) -> Any:
    """按逻辑名取块：支持 `综合评分` 与 `1_综合评分` 等带序号前缀的键。"""
    for name in logical_names:
        if name in payload:
            return payload[name]
    for key, val in payload.items():
        if not isinstance(key, str):
            continue
        for name in logical_names:
            if key == name or key.endswith(f"_{name}") or name in key:
                return val
    return None


def _dimension_rows(section: Any) -> list[dict[str, Any]]:
    if isinstance(section, list):
        return [r for r in section if isinstance(r, dict)]
    if isinstance(section, dict):
        for key in ("维度", "dimensions", "items", "分项", "scoring_points"):
            block = section.get(key)
            if isinstance(block, list):
                return [r for r in block if isinstance(r, dict)]
    return []


def _issue_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    core = _payload_section(payload, "核心问题", "problems")
    if isinstance(core, list):
        return [r for r in core if isinstance(r, dict)]
    return []


_SUMMARY_REVIEW_KEYS = (
    "总体说明",
    "总体得分原因",
    "总体原因",
    "总体评价",
    "总体评述",
)


def _summary_review_text(summary: dict[str, Any]) -> str:
    for key in _SUMMARY_REVIEW_KEYS:
        val = summary.get(key)
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _looks_like_engine_tier_excerpt(text: str) -> bool:
    t = text.strip()
    if not t:
        return False
    return bool(re.match(r"^[一二三四]类文[（(]", t))


def resolve_review_notes_excerpt(payload: dict[str, Any]) -> None:
    """阅卷总评摘录：优先 LLM 综合评语文本，勿用规则引擎档位说明顶替。"""
    summary = _payload_section(payload, "综合评分")
    from_summary = _summary_review_text(summary) if isinstance(summary, dict) else ""
    existing = str(payload.get("review_notes") or "").strip()
    tier_note = str(payload.get("tier_label") or payload.get("engine_tier_note") or "").strip()

    if from_summary:
        if not existing or existing == tier_note or _looks_like_engine_tier_excerpt(existing):
            payload["review_notes"] = from_summary
        return
    if existing and not _looks_like_engine_tier_excerpt(existing):
        return
    if _looks_like_engine_tier_excerpt(existing):
        payload["review_notes"] = ""


def display_total_score(payload: dict[str, Any]) -> float:
    """报告展示用总分（兼容中文键与 total_score=0 的脏数据）。"""
    normalized = normalize_llm_report_payload(dict(payload))
    return float(normalized.get("total_score") or 0)


def resolved_primary_llm_score(payload: dict[str, Any]) -> float:
    """与「报告采用」一致的主评展示分（避免综合评分 JSON 与合并总分两套数）。"""
    total = float(payload.get("total_score") or 0)
    if total <= 0:
        total = display_total_score(payload)
    for key in ("primary_llm_score", "llm_score"):
        try:
            val = float(payload.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if val > 0 and (total <= 0 or abs(val - total) <= 2.0):
            return val
    if total > 0:
        return total
    summary = _payload_section(payload, "综合评分")
    if isinstance(summary, dict):
        parsed = _parse_score_value(summary.get("总分"))
        if parsed is not None and parsed > 0:
            return parsed
    return 0.0


def _infer_hit_from_earned(earned: float, max_score: float) -> str:
    return _infer_hit(earned, max_score)


_HOLISTIC_DIMENSION_LABELS = frozenset({"总分", "综合评分", "综合得分", "卷面总分", "总分得分"})


def _essay_max_from_payload(payload: dict[str, Any], default: float = 40.0) -> float:
    try:
        return float(payload.get("max_score") or default)
    except (TypeError, ValueError):
        return default


def is_holistic_dimension_row(label: str, max_score: float, *, essay_max: float) -> bool:
    """模型有时把卷面总分写进「分项评分」一行（label=总分、满分=40），会与顶部报告总分重复且不一致。"""
    lab = (label or "").strip()
    if not lab:
        return False
    if lab in _HOLISTIC_DIMENSION_LABELS:
        return True
    if lab.startswith("总分") and max_score >= essay_max * 0.85:
        return True
    if lab in ("综合", "整体评价") and max_score >= essay_max * 0.85:
        return True
    return False


def strip_holistic_dimension_rows(payload: dict[str, Any]) -> None:
    points = payload.get("scoring_points")
    if not isinstance(points, list) or not points:
        return
    essay_max = _essay_max_from_payload(payload)
    kept: list[dict[str, Any]] = []
    stripped = 0
    for row in points:
        if not isinstance(row, dict):
            kept.append(row)
            continue
        label = str(row.get("label") or "")
        mx = _to_float(row.get("max") or row.get("max_score"), 0.0)
        if is_holistic_dimension_row(label, mx, essay_max=essay_max):
            stripped += 1
            reason = str(row.get("reason") or row.get("说明") or "").strip()
            if reason:
                existing = str(payload.get("review_notes") or "").strip()
                if not existing:
                    payload["review_notes"] = reason
                elif reason not in existing:
                    payload["review_notes"] = f"{existing} {reason}".strip()
            continue
        kept.append(row)
    if stripped:
        payload["scoring_points"] = kept
        payload["holistic_dimension_stripped"] = True


def reconcile_scoring_points_to_total(payload: dict[str, Any], *, tolerance: float = 1.5) -> None:
    """各维度 earned 加总与 total_score 不一致时，按报告总分等比校准（仅展示层）。"""
    points = payload.get("scoring_points")
    if not isinstance(points, list) or not points:
        return
    try:
        total = float(payload.get("total_score") or 0)
    except (TypeError, ValueError):
        return
    if total <= 0:
        return
    dim_sum = 0.0
    for row in points:
        if isinstance(row, dict):
            dim_sum += float(row.get("earned") or 0)
    if dim_sum <= 0 or abs(dim_sum - total) <= tolerance:
        return
    scale = total / dim_sum
    for row in points:
        if not isinstance(row, dict):
            continue
        mx = float(row.get("max") or 0)
        earned = float(row.get("earned") or 0) * scale
        if mx > 0:
            earned = min(mx, earned)
        row["earned"] = round(earned, 1)
        row["hit"] = row.get("hit") or _infer_hit_from_earned(row["earned"], mx if mx > 0 else 10.0)
    payload["dimension_sum_before_reconcile"] = round(dim_sum, 1)
    payload["score_reconcile_note"] = (
        f"各维度原始加总约 {round(dim_sum, 1)} 分，已与报告采用总分 {total} 分校准一致。"
    )


def sanitize_evidence_chain(payload: dict[str, Any], *, essay_max: float = 40.0) -> None:
    """证据链单项分值不应误用整卷满分（避免展示成「总分 29/40」）。"""
    cap = max(3.0, essay_max * 0.3)
    chain = payload.get("evidence_chain")
    if not isinstance(chain, list):
        return
    for row in chain:
        if not isinstance(row, dict):
            continue
        try:
            mx = float(row.get("max") or 0)
            er = float(row.get("earned") or 0)
        except (TypeError, ValueError):
            continue
        if mx <= 0:
            continue
        if mx >= essay_max * 0.45:
            scale = cap / mx
            row["max"] = round(cap, 1)
            row["earned"] = round(min(er * scale, cap), 1)
        elif mx > cap:
            row["max"] = round(cap, 1)
            row["earned"] = round(min(er, cap), 1)
        else:
            row["earned"] = round(min(er, mx), 1)


def refresh_evidence_chain(payload: dict[str, Any]) -> None:
    from app.services.scoring_engine.report_adapter import evidence_chain_from_hit_dicts

    eng = payload.get("scoring_engine")
    if not isinstance(eng, dict):
        return
    hits = eng.get("point_hits")
    if not isinstance(hits, list) or not hits:
        return
    rebuilt = evidence_chain_from_hit_dicts(hits)
    if rebuilt:
        payload["evidence_chain"] = rebuilt


def refresh_scoring_basis_fields(payload: dict[str, Any]) -> None:
    """同步 scoring_basis 与顶层 rule/llm 分，供「查看评分依据」展示。"""
    total = display_total_score(payload)
    if total > 0:
        payload["total_score"] = total

    primary = resolved_primary_llm_score(payload)
    if primary > 0:
        payload["primary_llm_score"] = primary
        try:
            llm = float(payload.get("llm_score") or 0)
        except (TypeError, ValueError):
            llm = 0.0
        if llm <= 0:
            payload["llm_score"] = primary

    try:
        rule = float(payload.get("rule_score") or payload.get("deterministic_score") or 0)
    except (TypeError, ValueError):
        rule = 0.0
    payload["rule_score"] = rule

    stored = dict(payload.get("scoring_basis") or {})
    stored["rule_score"] = rule
    if primary > 0:
        stored["primary_llm_score"] = primary
        stored["llm_score"] = payload.get("llm_score", primary)
    for key in (
        "consensus_scores",
        "consensus_delta",
        "consensus_discarded",
        "consensus_rate",
        "confidence",
        "confidence_note",
        "confidence_scope",
        "evidence_chain",
        "engine_total_discarded",
        "score_confidence_declaration",
        "standard_version",
        "exam_standard_version",
        "grading_standard_mode",
        "scoring_points_rubric",
    ):
        if payload.get(key) is not None:
            stored[key] = payload.get(key)
        elif stored.get(key) is not None:
            payload[key] = stored[key]
    payload["scoring_basis"] = stored
    refresh_evidence_chain(payload)
    try:
        essay_max = float(payload.get("max_score") or 40)
    except (TypeError, ValueError):
        essay_max = 40.0
    strip_holistic_dimension_rows(payload)
    reconcile_scoring_points_to_total(payload)
    sanitize_evidence_chain(payload, essay_max=essay_max)
    if primary > 0:
        payload["primary_llm_score"] = primary
        payload["llm_score"] = payload.get("llm_score") or primary
        stored["primary_llm_score"] = primary
        stored["llm_score"] = payload["llm_score"]
        payload["scoring_basis"] = stored


def refresh_retry_comparison_scores(
    payload: dict[str, Any],
    *,
    baseline_payload: dict[str, Any] | None = None,
) -> None:
    """重作对比中的分数与涨幅与当前解析后的总分对齐。"""
    comp = payload.get("comparison")
    if not isinstance(comp, dict):
        return
    second = display_total_score(payload)
    if baseline_payload is not None:
        first = display_total_score(baseline_payload)
        comp["first_score"] = first
    else:
        first = float(comp.get("first_score") or 0)
    comp["second_score"] = second
    comp["score_delta"] = round(second - first, 1)


def normalize_llm_report_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """
    将模型返回的非标准 JSON（常见中文键、兼容模式）映射为报告页使用的英文字段。
    保留原始键，便于「评分依据」排查。
    """
    payload = dict(raw)
    summary = _payload_section(payload, "综合评分")
    if isinstance(summary, dict):
        parsed = _parse_score_value(summary.get("总分"))
        if parsed is not None and parsed >= 0:
            current = payload.get("total_score")
            try:
                current_num = float(current) if current is not None else None
            except (TypeError, ValueError):
                current_num = None
            if current_num is None or (current_num <= 0 and parsed > 0):
                payload["total_score"] = parsed

    section_scores = _payload_section(payload, "分项评分", "dimensions")
    if not payload.get("scoring_points"):
        rows = _dimension_rows(section_scores)
        if not rows and isinstance(section_scores, list):
            rows = _dimension_rows(section_scores)
        points: list[dict[str, Any]] = []
        essay_max = _essay_max_from_payload(payload)
        for i, row in enumerate(rows):
            earned = _to_float(row.get("earned") or row.get("得分") or row.get("score"))
            mx = _to_float(row.get("max") or row.get("满分") or row.get("max_score"), 10.0)
            label = row.get("label") or row.get("评分维度") or row.get("name") or f"维度{i + 1}"
            if is_holistic_dimension_row(str(label), mx, essay_max=essay_max) and len(rows) > 1:
                continue
            points.append(
                {
                    "id": row.get("id") or f"D{i + 1:02d}",
                    "label": str(label),
                    "earned": earned,
                    "max": mx,
                    "hit": row.get("hit") or _infer_hit(earned, mx),
                    "reason": row.get("reason") or row.get("主要原因") or row.get("说明") or "",
                    "evidence_ref": row.get("evidence_ref") or row.get("material_ref"),
                }
            )
        payload["scoring_points"] = points

    if not payload.get("issues"):
        issues: list[dict[str, Any]] = []
        for row in _issue_rows(payload)[:5]:
            problem = str(row.get("问题") or row.get("explanation") or "").strip()
            raw_tag = str(row.get("tag") or "").strip()
            if raw_tag and re.match(r"^问题\s*\d+$", raw_tag):
                raw_tag = ""
            why = str(row.get("为什么扣分") or "").strip()
            explanation = str(row.get("explanation") or problem).strip()
            if why and why not in explanation:
                explanation = f"{explanation} {why}".strip() if explanation else why
            issues.append(
                {
                    "tag": resolve_issue_badge(problem, raw_tag or None),
                    "severity": row.get("severity") or "moderate",
                    "explanation": explanation,
                    "user_quote": row.get("user_quote") or row.get("原文表现") or "",
                }
            )
        payload["issues"] = issues

    if not payload.get("suggestions"):
        suggestions: list[str] = []
        prio = _payload_section(payload, "修改优先级")
        if isinstance(prio, dict):
            for key, block in prio.items():
                if isinstance(block, list) and ("改" in key or "建议" in key or key in ("items", "优先修改")):
                    suggestions.extend(str(x) for x in block)
        for row in _issue_rows(payload):
            fix = row.get("如何改") or row.get("修改建议") or row.get("修改方向")
            if fix:
                suggestions.append(str(fix))
        payload["suggestions"] = suggestions[:8]

    if isinstance(summary, dict):
        excerpt = _summary_review_text(summary)
        if excerpt and not payload.get("review_notes"):
            payload["review_notes"] = excerpt

    resolve_review_notes_excerpt(payload)

    for issue in payload.get("issues") or []:
        if not isinstance(issue, dict):
            continue
        exp = str(issue.get("explanation") or "").strip()
        tag = str(issue.get("tag") or "").strip()
        if not exp and not tag:
            continue
        if len(tag) > 18 or re.match(r"^问题\s*\d+$", tag) or not re.match(r"^Q\d+\s", tag, re.I):
            issue["tag"] = resolve_issue_badge(exp or tag, tag if re.match(r"^Q\d+", tag, re.I) else None)

    return payload


def build_scoring_basis(payload: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    essay_meta = payload.get("essay_meta") or {}
    return {
        "rule_score": payload.get("rule_score"),
        "llm_score": payload.get("llm_score"),
        "consensus_scores": payload.get("consensus_scores"),
        "consensus_rate": payload.get("consensus_rate"),
        "confidence": payload.get("confidence"),
        "scoring_points_rubric": question.get("scoring_points"),
        "steps_summary": payload.get("review_notes"),
        "standard_version": payload.get("standard_version") or essay_meta.get("standard_version"),
        "exam_standard_version": payload.get("exam_standard_version") or essay_meta.get("exam_standard_version"),
        "grading_standard_mode": essay_meta.get("grading_standard_mode"),
        "consensus_discarded": payload.get("consensus_discarded"),
        "consensus_delta": payload.get("consensus_delta"),
        "primary_llm_score": payload.get("primary_llm_score"),
        "confidence_note": payload.get("confidence_note"),
        "confidence_scope": payload.get("confidence_scope"),
        "evidence_chain": payload.get("evidence_chain"),
        "engine_total_discarded": payload.get("engine_total_discarded"),
        "score_confidence_declaration": (payload.get("essay_meta") or {}).get("score_confidence_declaration"),
    }
