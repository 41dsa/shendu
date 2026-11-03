"""L0–L4 → 能力等级与分数区间（确定性映射，非 LLM 总分）。"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.scoring_engine.rubric_loader import merged_scorable_weights
from app.domain.scoring_engine.trait_definitions import (
    ABILITY_BY_LEVEL,
    TraitDiagnostic,
    TraitLevel,
    level_to_numeric,
)
from app.domain.scoring_engine.question_standard_card import QuestionStandardCard


@dataclass
class TraitIntervalEstimate:
    ability_level: str
    score_min: float
    score_max: float
    system_center: float
    uncalibrated: bool
    primary_loss_traits: list[str]


def _aggregate_level(
    diagnostics: list[TraitDiagnostic],
    weights: dict[str, float] | None = None,
    *,
    aggregate: str = "weighted",
) -> TraitLevel:
    from app.domain.scoring_engine.trait_definitions import LEVEL_ORDER

    nums: list[int] = []
    wmap = weights or merged_scorable_weights(None)
    weighted = 0.0
    weight_sum = 0.0
    for d in diagnostics:
        if not d.participates_in_score or d.level is None:
            continue
        n = level_to_numeric(d.level)
        nums.append(n)
        w = wmap.get(d.trait_id, 0.0)
        if w <= 0:
            continue
        weighted += n * w
        weight_sum += w
    if not nums:
        return "L2"
    if aggregate == "min":
        idx = min(nums)
    elif aggregate == "max":
        idx = max(nums)
    else:
        if weight_sum <= 0:
            return "L2"
        avg = weighted / weight_sum
        idx = max(0, min(4, int(round(avg))))
    return LEVEL_ORDER[idx]


def estimate_score_interval(
    diagnostics: list[TraitDiagnostic],
    *,
    max_score: float,
    severe_off_topic: bool,
    standard: QuestionStandardCard | None = None,
    aggregate: str = "weighted",
) -> TraitIntervalEstimate:
    weights = merged_scorable_weights(
        standard.trait_rubric_adjustments if standard else None
    )
    agg = _aggregate_level(diagnostics, weights=weights, aggregate=aggregate)
    if severe_off_topic:
        agg = "L0" if agg != "L4" else "L1"

    center_ratio = level_to_numeric(agg) / 4.0
    center = round(max_score * (0.12 + 0.88 * center_ratio), 1)
    span_factor = 1.0
    if standard and standard.trait_rubric_adjustments:
        for adj in standard.trait_rubric_adjustments:
            f = adj.get("interval_span_factor")
            if f is not None:
                span_factor = max(span_factor, float(f))
    span = max(2.0, max_score * 0.08 * span_factor)
    if agg in ("L0", "L1"):
        span = max(span, max_score * 0.12 * span_factor)
    score_min = round(max(0.0, center - span), 1)
    score_max = round(min(max_score, center + span), 1)

    scorable = [d for d in diagnostics if d.participates_in_score and d.level in ("L0", "L1", "L2")]
    scorable.sort(key=lambda x: level_to_numeric(x.level or "L2"))
    loss_ids = [f"{d.trait_id} {d.name}" for d in scorable[:3]]

    return TraitIntervalEstimate(
        ability_level=ABILITY_BY_LEVEL[agg],
        score_min=score_min,
        score_max=score_max,
        system_center=center,
        uncalibrated=True,
        primary_loss_traits=loss_ids,
    )
