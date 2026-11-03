"""多模型 Trait 等级投票合并（弱标签，非 Ground Truth）。"""

from __future__ import annotations

from statistics import median

from app.domain.scoring_engine.trait_definitions import LEVEL_ORDER, TraitLevel, level_to_numeric


def _level_from_median(nums: list[int]) -> TraitLevel:
    if not nums:
        return "L2"
    m = int(round(median(nums)))
    m = max(0, min(4, m))
    return LEVEL_ORDER[m]


def merge_trait_level_votes(votes: list[TraitLevel]) -> tuple[TraitLevel, float]:
    """返回 (合并等级, 分歧度 0~1)。"""
    if not votes:
        return "L2", 0.0
    nums = [level_to_numeric(v) for v in votes]
    spread = (max(nums) - min(nums)) / 4.0 if len(nums) > 1 else 0.0
    return _level_from_median(nums), round(spread, 3)


def apply_vote_levels(
    diagnostics: list[dict],
    voted: dict[str, tuple[TraitLevel, float, list[dict]]],
) -> list[dict]:
    """将投票结果写入 trait 行，并更新 level / model_votes。"""
    out: list[dict] = []
    for row in diagnostics:
        tid = str(row.get("trait_id") or "")
        copy = dict(row)
        if tid in voted:
            level, spread, vote_rows = voted[tid]
            copy["level"] = level
            copy["model_votes"] = vote_rows
            copy["vote_spread"] = spread
            conf = float(copy.get("confidence") or 0.75)
            copy["confidence"] = round(max(0.45, conf - spread * 0.15), 2)
        out.append(copy)
    return out
