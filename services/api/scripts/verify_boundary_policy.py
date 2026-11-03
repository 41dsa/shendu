"""P-07 边界策略表冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.boundary_policy import apply_boundary_policy
from app.domain.scoring_engine.hard_rules import HardRuleReport
from app.domain.scoring_engine.trait_interval import TraitIntervalEstimate


def main() -> None:
    hard = HardRuleReport(
        word_count=900,
        word_ratio=0.9,
        paragraph_count=5,
        has_title_line=False,
        main_thesis_signal=False,
        severe_off_topic=True,
        mechanical_copy_ratio=0.0,
        flags={"severe_off_topic": True},
    )
    interval = TraitIntervalEstimate(
        ability_level="一般",
        score_min=20.0,
        score_max=30.0,
        system_center=25.0,
        uncalibrated=True,
        primary_loss_traits=[],
    )
    adjusted, notes = apply_boundary_policy(hard, interval, max_score=40.0)
    assert adjusted.system_center <= 40 * 0.22 + 0.1, adjusted.system_center
    assert notes
    print("verify_boundary_policy: ok")


if __name__ == "__main__":
    main()
