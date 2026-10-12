from __future__ import annotations

from typing import Any

from app.domain.scoring_engine.level_config import LevelConfig
from app.domain.scoring_engine.tiers import assign_tier, tier_clamped_total
from app.domain.scoring_engine.types import DeterministicScoreResult, EngineLayerTrace, PointHit, ScoringPoint
from app.services.scoring_engine.deterministic import _is_main, _point_dim


def recompute_from_hits(
    hits: list[PointHit],
    points: list[ScoringPoint],
    level_config: LevelConfig,
    *,
    max_score: float,
    scoring_dimensions: list[Any],
) -> DeterministicScoreResult:
    main_hits = [h for h in hits if _is_main(h, points)]
    sub_hits = [h for h in hits if h not in main_hits and h.max_score > 0]
    main_point_hit = any(h.status in ("hit", "borderline", "partial") for h in main_hits) or not main_hits

    if sub_hits:
        earned_sub = sum(h.earned for h in sub_hits)
        max_sub = sum(h.max_score for h in sub_hits)
        coverage_ratio = earned_sub / max_sub if max_sub > 0 else 0.0
    else:
        coverage_ratio = sum(1 for h in hits if h.status == "hit") / max(len(hits), 1)

    dim_scores: dict[str, dict[str, float]] = {}
    for dim in scoring_dimensions or []:
        if not isinstance(dim, dict):
            continue
        did = str(dim.get("id") or "")
        dmax = float(dim.get("max_score") or 0)
        if not did or dmax <= 0:
            continue
        dim_hits = [h for h in hits if _point_dim(h.point_id, points) == did]
        if dim_hits:
            earned = sum(h.earned for h in dim_hits)
            cap = sum(h.max_score for h in dim_hits) or dmax
            earned = min(dmax, earned * (dmax / cap) if cap else earned)
        else:
            earned = dmax * coverage_ratio * 0.85
        dim_scores[did] = {"score": round(earned, 2), "max": dmax}

    weights = level_config.dimension_weights
    if dim_scores:
        weighted = 0.0
        weight_sum = 0.0
        for did, row in dim_scores.items():
            w = weights.get(did, weights.get("D01", 0.25))
            weighted += row["score"] * w
            weight_sum += w * row["max"]
        base_score = (weighted / weight_sum * max_score) if weight_sum else sum(r["score"] for r in dim_scores.values())
    else:
        base_score = sum(h.earned for h in hits)

    base_score = round(min(max_score, max(0.0, base_score)), 1)
    tier = assign_tier(
        base_score,
        main_point_hit=main_point_hit,
        coverage_ratio=coverage_ratio,
        level_config=level_config,
    )
    clamped = tier_clamped_total(base_score, tier)
    return DeterministicScoreResult(
        base_score=clamped,
        dimension_scores=dim_scores,
        point_hits=hits,
        main_point_hit=main_point_hit,
        coverage_ratio=coverage_ratio,
        tier=tier,
        traces=[EngineLayerTrace(layer="deterministic", detail="recomputed", data={})],
    )
