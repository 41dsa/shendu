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
        if rule_gap <= rule_high:
            return "high"
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


def normalize_llm_report_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """
    将模型返回的非标准 JSON（常见中文键、兼容模式）映射为报告页使用的英文字段。
    保留原始键，便于「评分依据」排查。
    """
    payload = dict(raw)
    summary = _payload_section(payload, "综合评分")
    if payload.get("total_score") is None and isinstance(summary, dict):
        parsed = _parse_score_value(summary.get("总分"))
        if parsed is not None and parsed >= 0:
            payload["total_score"] = parsed

    section_scores = _payload_section(payload, "分项评分", "dimensions")
    if not payload.get("scoring_points"):
        rows = _dimension_rows(section_scores)
        if not rows and isinstance(section_scores, list):
            rows = _dimension_rows(section_scores)
        points: list[dict[str, Any]] = []
        for i, row in enumerate(rows):
            earned = _to_float(row.get("earned") or row.get("得分") or row.get("score"))
            mx = _to_float(row.get("max") or row.get("满分") or row.get("max_score"), 10.0)
            label = row.get("label") or row.get("评分维度") or row.get("name") or f"维度{i + 1}"
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

    if not payload.get("review_notes") and isinstance(summary, dict):
        payload["review_notes"] = str(summary.get("总体得分原因") or summary.get("总体原因") or "")

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
    }
