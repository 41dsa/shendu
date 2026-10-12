from __future__ import annotations

from app.domain.scoring_engine.level_config import LevelConfig
from app.domain.scoring_engine.types import ScoringTier


def assign_tier(
    base_score: float,
    *,
    main_point_hit: bool,
    coverage_ratio: float,
    level_config: LevelConfig,
) -> ScoringTier:
    rules = level_config.tier_rules
    if not main_point_hit:
        r = rules[-1]
        return ScoringTier(
            tier_id=r["tier_id"],
            label=r["label"],
            score_min=float(r["score_min"]),
            score_max=float(r["score_max"]),
            reason="总论点/扣题信号不足，按跑题或偏题档处理",
        )

    chosen = rules[-1]
    for rule in rules:
        cov_min = float(rule.get("coverage_min") or 0)
        if coverage_ratio >= cov_min:
            chosen = rule
            break

    tier = ScoringTier(
        tier_id=chosen["tier_id"],
        label=chosen["label"],
        score_min=float(chosen["score_min"]),
        score_max=float(chosen["score_max"]),
        reason=f"分论点覆盖率约 {coverage_ratio:.0%}",
    )
    clamped = max(tier.score_min, min(tier.score_max, base_score))
    if clamped != base_score:
        tier = ScoringTier(
            tier_id=tier.tier_id,
            label=tier.label,
            score_min=tier.score_min,
            score_max=tier.score_max,
            reason=f"{tier.reason}；基础分 {base_score:.1f} 已钳制至档次区间 {clamped:.1f}",
        )
    return tier


def tier_clamped_total(base_score: float, tier: ScoringTier) -> float:
    return round(max(tier.score_min, min(tier.score_max, base_score)), 1)
