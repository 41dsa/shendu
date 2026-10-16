"""重作升档策略 smoke test。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.retry_tier_lift import (
    apply_retry_tier_lift,
    next_tier_floor_score,
    retry_shows_improvement,
)
from app.domain.requirement_scoring import score_tier_for_total


def main() -> None:
    assert next_tier_floor_score(16, 40) == 24.0
    assert next_tier_floor_score(32, 40) >= 32.5

    comp = {"issues_resolved": 2, "issues_improved": 0, "issue_changes": []}
    assert retry_shows_improvement(comp, {"retry_issue_policy_ok": False})

    baseline = {"total_score": 16, "max_score": 40, "scoring_points": [{"earned": 4, "max": 10}] * 4}
    payload = {
        "attempt": 2,
        "total_score": 16,
        "max_score": 40,
        "scoring_points": [{"earned": 4, "max": 10, "hit": "partial"}] * 4,
        "retry_issue_policy_ok": True,
    }
    apply_retry_tier_lift(
        payload,
        baseline_payload=baseline,
        comparison=comp,
        display_max=40,
        baseline_essay="原文段落A。",
        current_essay="原文段落A，已补充分析。",
    )
    assert payload["total_score"] >= 24, payload
    tier = score_tier_for_total(payload["total_score"], 40)
    tier_base = score_tier_for_total(16, 40)
    assert tier["tier_id"] != tier_base["tier_id"] or payload["total_score"] > 16
    assert payload.get("retry_tier_lift")
    print("verify_retry_tier_lift: ok")


if __name__ == "__main__":
    main()
