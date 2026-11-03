"""P-07：硬规则与 Trait 区间冲突时的强制下调策略（表驱动）。"""

from __future__ import annotations

from dataclasses import replace
from typing import Any, Callable

from app.domain.scoring_engine.hard_rules import HardRuleReport
from app.domain.scoring_engine.trait_interval import TraitIntervalEstimate


def _cap_off_topic(hard: HardRuleReport, interval: TraitIntervalEstimate, max_score: float) -> TraitIntervalEstimate | None:
    if not hard.severe_off_topic:
        return None
    if interval.system_center <= max_score * 0.4:
        return None
    return replace(
        interval,
        score_min=min(interval.score_min, max_score * 0.08),
        score_max=min(interval.score_max, max_score * 0.35),
        system_center=min(interval.system_center, max_score * 0.22),
        uncalibrated=True,
    )


def _cap_mechanical_copy(hard: HardRuleReport, interval: TraitIntervalEstimate, max_score: float) -> TraitIntervalEstimate | None:
    if not hard.flags.get("mechanical_copy"):
        return None
    if interval.system_center <= max_score * 0.45:
        return None
    return replace(
        interval,
        system_center=min(interval.system_center, max_score * 0.42),
        score_max=min(interval.score_max, max_score * 0.5),
        uncalibrated=True,
    )


def _cap_word_short(hard: HardRuleReport, interval: TraitIntervalEstimate, max_score: float) -> TraitIntervalEstimate | None:
    if not hard.flags.get("word_short"):
        return None
    return replace(
        interval,
        system_center=min(interval.system_center, max_score * 0.35),
        score_max=min(interval.score_max, max_score * 0.4),
        uncalibrated=True,
    )


def _cap_format_mismatch(hard: HardRuleReport, interval: TraitIntervalEstimate, max_score: float) -> TraitIntervalEstimate | None:
    if not (hard.flags.get("genre_mismatch") or hard.flags.get("identity_mismatch")):
        return None
    if interval.system_center <= max_score * 0.38:
        return None
    return replace(
        interval,
        system_center=min(interval.system_center, max_score * 0.38),
        score_max=min(interval.score_max, max_score * 0.45),
        uncalibrated=True,
    )


def _cap_scope_violation(hard: HardRuleReport, interval: TraitIntervalEstimate, max_score: float) -> TraitIntervalEstimate | None:
    if not hard.flags.get("scope_violation"):
        return None
    if interval.system_center <= max_score * 0.32:
        return None
    return replace(
        interval,
        score_min=min(interval.score_min, max_score * 0.05),
        score_max=min(interval.score_max, max_score * 0.38),
        system_center=min(interval.system_center, max_score * 0.28),
        uncalibrated=True,
    )


def _cap_word_overflow(hard: HardRuleReport, interval: TraitIntervalEstimate, max_score: float) -> TraitIntervalEstimate | None:
    if hard.word_ratio <= 1.25:
        return None
    return replace(
        interval,
        system_center=min(interval.system_center, max_score * 0.55),
        score_max=min(interval.score_max, max_score * 0.6),
        uncalibrated=True,
    )


_BOUNDARY_RULES: list[tuple[str, Callable[..., TraitIntervalEstimate | None]]] = [
    ("severe_off_topic_cap", _cap_off_topic),
    ("scope_violation_cap", _cap_scope_violation),
    ("mechanical_copy_cap", _cap_mechanical_copy),
    ("format_mismatch_cap", _cap_format_mismatch),
    ("word_short_cap", _cap_word_short),
    ("word_overflow_cap", _cap_word_overflow),
]


def apply_boundary_policy(
    hard: HardRuleReport,
    interval: TraitIntervalEstimate,
    *,
    max_score: float,
) -> tuple[TraitIntervalEstimate, list[str]]:
    notes: list[str] = []
    current = interval
    for rule_id, fn in _BOUNDARY_RULES:
        adjusted = fn(hard, current, max_score)
        if adjusted is not None:
            notes.append(f"boundary:{rule_id}")
            current = adjusted
    return current, notes
