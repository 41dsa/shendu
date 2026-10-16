"""首稿档次 → 重新批改次数上限 smoke test。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.requirement_scoring import score_tier_for_total

_TIER_MAX = {"t1": 1, "t2": 2, "t3": 3, "t4": 4}


def tier_max_regrade_count(tier_id: str) -> int:
    return _TIER_MAX.get(tier_id, 1)


def test_tier_to_max_regrades() -> None:
    assert tier_max_regrade_count("t4") == 4
    assert tier_max_regrade_count("t3") == 3
    assert tier_max_regrade_count("t2") == 2
    assert tier_max_regrade_count("t1") == 1
    t4 = score_tier_for_total(10, 40)
    assert t4["tier_id"] == "t4"
    assert tier_max_regrade_count(t4["tier_id"]) == 4
    t1 = score_tier_for_total(35, 40)
    assert t1["tier_id"] == "t1"
    assert tier_max_regrade_count(t1["tier_id"]) == 1
    print("ok: tier_max_regrade_count matches 四类→4 … 一类→1")


if __name__ == "__main__":
    test_tier_to_max_regrades()
