"""重作批改：在可验证改进时，总分至少升入上一档（用户信任与产品承诺）。"""

from __future__ import annotations

import difflib
from typing import Any

from app.domain.requirement_scoring import score_tier_for_total

_TIER_ORDER = ("t1", "t2", "t3", "t4")


def _tiers_for_max(max_score: float) -> list[dict[str, Any]]:
    from app.domain.scoring_engine.level_config import _base_tiers

    return _base_tiers(max_score)


def next_tier_floor_score(total: float, max_score: float) -> float:
    """当前总分所在档的「上一档」最低分；已在最高档则至少 +0.5（不超过满分）。"""
    if max_score <= 0:
        return total
    tier = score_tier_for_total(total, max_score)
    tid = str(tier.get("tier_id") or "t4")
    idx = _TIER_ORDER.index(tid) if tid in _TIER_ORDER else len(_TIER_ORDER) - 1
    if idx <= 0:
        bump = max(0.5, max_score * 0.0125)
        return min(max_score, total + bump)
    upper_id = _TIER_ORDER[idx - 1]
    for rule in _tiers_for_max(max_score):
        if str(rule.get("tier_id")) == upper_id:
            return float(rule["score_min"])
    return total


def essay_changed_enough(baseline_text: str, new_text: str, *, min_delta: float = 0.015) -> bool:
    a = (baseline_text or "").strip()
    b = (new_text or "").strip()
    if not a or not b:
        return bool(b)
    if a == b:
        return False
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    return ratio < (1.0 - min_delta)


def retry_shows_improvement(comparison: dict[str, Any] | None, payload: dict[str, Any]) -> bool:
    if not comparison:
        return False
    resolved = int(comparison.get("issues_resolved") or 0)
    improved = int(comparison.get("issues_improved") or 0)
    worse = sum(
        1
        for row in comparison.get("issue_changes") or []
        if isinstance(row, dict) and row.get("status") == "worse"
    )
    if worse > 0 and resolved + improved == 0:
        return False
    if payload.get("retry_issue_policy_ok") is True:
        return True
    if resolved + improved >= 1 and worse == 0:
        return True
    if resolved >= 2:
        return True
    return False


def apply_retry_tier_lift(
    payload: dict[str, Any],
    *,
    baseline_payload: dict[str, Any],
    comparison: dict[str, Any] | None,
    display_max: float,
    baseline_essay: str = "",
    current_essay: str = "",
) -> None:
    """
    改进后总分至少进入上一档区间（按作答要求满分缩放的四档）。
    仅当对比显示改进且正文确有修改时生效。
    """
    if int(payload.get("attempt") or 1) < 2:
        return
    if not retry_shows_improvement(comparison, payload):
        payload["retry_tier_lift_skipped"] = "no_verified_improvement"
        return
    if baseline_essay and current_essay and not essay_changed_enough(baseline_essay, current_essay):
        payload["retry_tier_lift_skipped"] = "essay_unchanged"
        return

    from app.services.grading_helpers import display_total_score, reconcile_scoring_points_to_total

    baseline_total = display_total_score(baseline_payload)
    current_total = display_total_score(payload)
    if baseline_total <= 0 or display_max <= 0:
        return

    before_tier = score_tier_for_total(baseline_total, display_max)
    floor = next_tier_floor_score(baseline_total, display_max)
    # 已高于上一档下限则保持；否则抬到升档下限
    target = current_total
    if current_total < floor:
        target = floor
    # 至少不低于基线（改进不应降分）
    target = max(target, baseline_total)
    target = min(display_max, round(target, 1))

    after_tier = score_tier_for_total(target, display_max)
    if target <= current_total + 0.04 and before_tier.get("tier_id") == after_tier.get("tier_id"):
        if current_total >= baseline_total:
            payload.pop("retry_tier_lift", None)
            return

    payload["total_score"] = target
    payload["primary_llm_score"] = target
    payload["llm_score"] = target
    reconcile_scoring_points_to_total(payload)
    payload["retry_tier_lift"] = {
        "baseline_score": baseline_total,
        "before_merge_score": current_total,
        "applied_score": target,
        "display_max_score": display_max,
        "tier_before": before_tier.get("full_label") or before_tier.get("label"),
        "tier_after": after_tier.get("full_label") or after_tier.get("label"),
        "floor_for_next_tier": floor,
    }
    if comparison and isinstance(comparison, dict):
        comparison["second_score"] = target
        comparison["score_delta"] = round(target - baseline_total, 1)
        comparison.pop("score_unchanged_note", None)
