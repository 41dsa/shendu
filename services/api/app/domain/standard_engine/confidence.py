"""标准引擎置信度加权（V0.1-E 规则版）。"""

from typing import Any

CONFIDENCE_WEIGHTS: dict[str, float] = {
    "source_trust": 0.30,
    "prompt_trace": 0.25,
    "reference_support": 0.20,
    "model_agreement": 0.15,
    "ability_alignment": 0.10,
}

CONFIDENCE_BANDS: tuple[tuple[float, str], ...] = (
    (0.95, "high"),
    (0.85, "medium_high"),
    (0.70, "review"),
    (0.0, "low"),
)

PUBLISH_MIN_CONFIDENCE = 0.85


def compute_confidence_score(components: dict[str, float]) -> float:
    total = 0.0
    for key, weight in CONFIDENCE_WEIGHTS.items():
        total += float(components.get(key, 0.0)) * weight
    return round(min(1.0, max(0.0, total)), 4)


def confidence_band(score: float) -> str:
    for threshold, name in CONFIDENCE_BANDS:
        if score >= threshold:
            return name
    return "low"


def aggregate_standard_confidence(criteria: list[dict[str, Any]]) -> float:
    if not criteria:
        return 0.0
    scores = [float(c.get("confidence", 0.0)) for c in criteria]
    return round(sum(scores) / len(scores), 4)
