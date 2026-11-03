"""Trait 投票合并单元冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.scoring_engine.trait_vote_merge import apply_vote_levels, merge_trait_level_votes


def main() -> None:
    level, spread = merge_trait_level_votes(["L2", "L3", "L3"])
    assert level == "L3", level
    assert spread > 0, spread
    level3, spread3 = merge_trait_level_votes(["L1", "L2", "L4"])
    assert spread3 == 0.75, spread3
    assert level3 == "L2", level3
    rows = apply_vote_levels(
        [{"trait_id": "T1", "level": "L2", "name": "审题", "confidence": 0.8, "participates_in_score": True}],
        {"T1": ("L3", 0.25, [{"model": "a", "level": "L3"}, {"model": "b", "level": "L2"}])},
    )
    assert rows[0]["level"] == "L3"
    assert rows[0].get("model_votes")
    print("verify_trait_vote_merge: ok")


if __name__ == "__main__":
    main()
