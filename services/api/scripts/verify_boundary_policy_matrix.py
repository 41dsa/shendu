#!/usr/bin/env python3
"""P-07：边界策略表矩阵样例 100% 通过。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.boundary_policy import apply_boundary_policy
from app.domain.scoring_engine.hard_rules import HardRuleReport
from app.domain.scoring_engine.trait_interval import TraitIntervalEstimate

MAX = 40.0


def _interval(center: float) -> TraitIntervalEstimate:
    return TraitIntervalEstimate(
        ability_level="一般",
        score_min=center - 5,
        score_max=center + 5,
        system_center=center,
        uncalibrated=False,
        primary_loss_traits=[],
    )


def _hard(**flags) -> HardRuleReport:
    word_ratio = float(flags.pop("_word_ratio", 0.9))
    base = {
        "word_short": False,
        "mechanical_copy": False,
        "severe_off_topic": False,
        "genre_mismatch": False,
        "identity_mismatch": False,
        "scope_violation": False,
    }
    base.update(flags)
    return HardRuleReport(
        word_count=900,
        word_ratio=word_ratio,
        paragraph_count=5,
        has_title_line=False,
        main_thesis_signal=not base.get("severe_off_topic"),
        severe_off_topic=bool(base.get("severe_off_topic")),
        mechanical_copy_ratio=0.4 if base.get("mechanical_copy") else 0.0,
        flags={k: bool(v) for k, v in base.items()},
        format_issues=[],
    )


CASES: list[tuple[str, HardRuleReport, float, str]] = [
    ("severe_off_topic", _hard(severe_off_topic=True), 30.0, "severe_off_topic_cap"),
    ("mechanical_copy", _hard(mechanical_copy=True), 30.0, "mechanical_copy_cap"),
    ("word_short", _hard(word_short=True, _word_ratio=0.5), 30.0, "word_short_cap"),
    ("genre", _hard(genre_mismatch=True), 30.0, "format_mismatch_cap"),
    ("scope", _hard(scope_violation=True), 28.0, "scope_violation_cap"),
    ("word_overflow", _hard(_word_ratio=1.4), 30.0, "word_overflow_cap"),
]


def main() -> None:
    for name, hard, center, expect_rule in CASES:
        adjusted, notes = apply_boundary_policy(hard, _interval(center), max_score=MAX)
        assert any(expect_rule in n for n in notes), f"{name}: {notes}"
        assert adjusted.system_center <= center + 0.01, f"{name} did not cap center"
    print(f"verify_boundary_policy_matrix: OK ({len(CASES)} cases)")


if __name__ == "__main__":
    main()
