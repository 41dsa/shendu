import hashlib
import json
import re
from typing import Any


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
) -> str:
    if word_ratio < 0.3:
        return "low"
    if consensus_delta is not None and consensus_delta > 1.5:
        return "low"
    if abs(total_score - rule_score) > max(2.0, max_score * 0.2):
        return "medium"
    if consensus_delta is not None and consensus_delta > 0.5:
        return "medium"
    return "high"


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


def normalize_llm_report_payload(raw: dict[str, Any]) -> dict[str, Any]:
    """
    将模型返回的非标准 JSON（常见中文键、兼容模式）映射为报告页使用的英文字段。
    保留原始键，便于「评分依据」排查。
    """
    payload = dict(raw)
    if payload.get("total_score") is None:
        summary = payload.get("综合评分")
        if isinstance(summary, dict) and summary.get("总分") is not None:
            payload["total_score"] = _to_float(summary["总分"])

    if not payload.get("scoring_points"):
        rows = payload.get("分项评分") or payload.get("dimensions") or payload.get("scoring_points")
        points: list[dict[str, Any]] = []
        if isinstance(rows, list):
            for i, row in enumerate(rows):
                if not isinstance(row, dict):
                    continue
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
        core = payload.get("核心问题") or payload.get("problems")
        issues: list[dict[str, Any]] = []
        if isinstance(core, list):
            for i, row in enumerate(core[:5]):
                if not isinstance(row, dict):
                    continue
                issues.append(
                    {
                        "tag": row.get("tag") or f"问题{i + 1}",
                        "severity": row.get("severity") or "moderate",
                        "explanation": row.get("explanation") or row.get("问题") or "",
                        "user_quote": row.get("user_quote") or row.get("原文表现") or "",
                    }
                )
        payload["issues"] = issues

    if not payload.get("suggestions"):
        suggestions: list[str] = []
        prio = payload.get("修改优先级")
        if isinstance(prio, dict):
            for key in ("如果只能改3个地方", "优先修改", "建议", "items"):
                block = prio.get(key)
                if isinstance(block, list):
                    suggestions.extend(str(x) for x in block)
        for row in payload.get("核心问题") or []:
            if isinstance(row, dict):
                fix = row.get("如何改") or row.get("修改建议")
                if fix:
                    suggestions.append(str(fix))
        payload["suggestions"] = suggestions[:8]

    if not payload.get("review_notes") and isinstance(payload.get("综合评分"), dict):
        payload["review_notes"] = str(payload["综合评分"].get("总体得分原因") or "")

    return payload


def build_scoring_basis(payload: dict[str, Any], question: dict[str, Any]) -> dict[str, Any]:
    return {
        "rule_score": payload.get("rule_score"),
        "llm_score": payload.get("llm_score"),
        "consensus_scores": payload.get("consensus_scores"),
        "consensus_rate": payload.get("consensus_rate"),
        "confidence": payload.get("confidence"),
        "scoring_points_rubric": question.get("scoring_points"),
        "steps_summary": payload.get("review_notes"),
    }
