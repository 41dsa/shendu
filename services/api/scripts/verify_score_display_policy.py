"""Phase 3：S-03 / S-04 分数展示策略。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.score_display_policy import (
    HUMAN_REVIEW_NOTE,
    apply_score_display_to_payload,
    human_review_recommended,
    resolve_score_display_mode,
)


def main() -> None:
    assert resolve_score_display_mode(
        suppress_absolute_score=True,
        trait_confidence=0.9,
        score_uncalibrated=False,
        anchor_count=10,
        diagnostic_only_mode=False,
    ) == "tier_only"
    assert resolve_score_display_mode(
        suppress_absolute_score=False,
        trait_confidence=0.8,
        score_uncalibrated=True,
        anchor_count=0,
        diagnostic_only_mode=False,
    ) == "interval"
    assert human_review_recommended(
        score_display_mode="interval",
        trait_confidence=0.5,
        trait_vote_max_spread=0.1,
    )
    payload: dict = {"confidence_note": "已有说明"}
    apply_score_display_to_payload(
        payload,
        score_display_mode="tier_only",
        human_review=True,
        score_interval=(10.0, 20.0),
    )
    assert payload["display_mode"] == "reference_only"
    assert payload["total_score"] == 0.0
    assert HUMAN_REVIEW_NOTE in payload["confidence_note"]
    assert (
        resolve_score_display_mode(
            suppress_absolute_score=False,
            trait_confidence=0.95,
            score_uncalibrated=False,
            anchor_count=20,
            diagnostic_only_mode=True,
        )
        == "tier_only"
    )
    print("verify_score_display_policy: ok")


if __name__ == "__main__":
    main()
