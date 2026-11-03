"""S-03 / S-04：分数展示模式与低置信人工复核策略。"""

from __future__ import annotations

from typing import Any, Literal

ScoreDisplayMode = Literal["tier_only", "interval", "center"]

HUMAN_REVIEW_NOTE = "引擎置信度偏低或模型分歧较大，建议人工复核后再采信分数。"


def resolve_score_display_mode(
    *,
    suppress_absolute_score: bool,
    trait_confidence: float,
    score_uncalibrated: bool,
    anchor_count: int,
    diagnostic_only_mode: bool,
    trait_vote_max_spread: float = 0.0,
) -> ScoreDisplayMode:
    if diagnostic_only_mode or suppress_absolute_score:
        return "tier_only"
    if trait_confidence < 0.58 or trait_vote_max_spread >= 0.5:
        return "tier_only"
    from app.config import settings

    if anchor_count <= 0 and score_uncalibrated:
        return "interval"
    if trait_confidence < 0.68:
        return "interval"
    if (
        anchor_count >= int(settings.anchor_min_for_center_score)
        and trait_confidence >= 0.68
        and not score_uncalibrated
    ):
        return "center"
    if anchor_count >= int(settings.anchor_min_for_center_score) and trait_confidence >= 0.72:
        return "center"
    return "interval" if score_uncalibrated else "center"


def human_review_recommended(
    *,
    score_display_mode: ScoreDisplayMode,
    trait_confidence: float,
    trait_vote_max_spread: float,
) -> bool:
    if score_display_mode == "tier_only":
        return True
    return trait_confidence < 0.62 or trait_vote_max_spread >= 0.35


def apply_score_display_to_payload(
    payload: dict[str, Any],
    *,
    score_display_mode: ScoreDisplayMode,
    human_review: bool,
    score_interval: tuple[float, float] | None,
) -> None:
    payload["score_display_mode"] = score_display_mode
    payload["human_review_recommended"] = human_review
    if human_review:
        note = HUMAN_REVIEW_NOTE
        existing = str(payload.get("confidence_note") or "").strip()
        payload["confidence_note"] = f"{existing} {note}".strip() if existing else note

    if score_display_mode == "tier_only":
        payload["display_mode"] = "reference_only"
        payload["trait_low_confidence"] = True
        payload["total_score"] = 0.0
        payload["merged_total"] = 0.0
        payload["score_range"] = [0, 0]
    elif score_display_mode == "interval":
        payload["display_mode"] = "interval_only"
        payload["trait_low_confidence"] = False
        if score_interval:
            payload["score_range"] = [score_interval[0], score_interval[1]]
        payload["total_score"] = 0.0
        payload["merged_total"] = 0.0
    else:
        payload.setdefault("display_mode", "normal")
        payload["trait_low_confidence"] = False
