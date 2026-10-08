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
