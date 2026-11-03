"""从采分点命中结果构造 Trait 证据三元组。"""

from __future__ import annotations

from app.domain.scoring_engine.trait_definitions import TraitEvidence, TraitId
from app.domain.scoring_engine.types import PointHit, ScoringPoint


def _dim_for_point(point_id: str, points: list[ScoringPoint]) -> str:
    for p in points:
        if p.point_id == point_id:
            return p.dimension_id
    return ""


def evidence_for_trait(
    trait_id: TraitId,
    hits: list[PointHit],
    points: list[ScoringPoint],
    *,
    limit: int = 4,
) -> TraitEvidence:
    from app.domain.scoring_engine.trait_definitions import TRAIT_SPECS

    spec = TRAIT_SPECS[trait_id]
    dim_set = set(spec.dimension_ids)
    relevant = [h for h in hits if not dim_set or _dim_for_point(h.point_id, points) in dim_set]
    if not relevant and trait_id == "T1":
        relevant = [h for h in hits if any(p.is_main_point and p.point_id == h.point_id for p in points)]

    ev = TraitEvidence()
    for h in relevant:
        quote = (h.evidence or h.reason or "").strip()
        if h.status in ("hit", "partial", "borderline"):
            if quote:
                ev.positive.append(quote[:160])
        elif h.status == "missed":
            label = h.reason or h.point_id
            ev.missing.append(str(label)[:120])
        elif h.status == "miss":
            if quote:
                ev.negative.append(quote[:160])
            elif h.reason:
                ev.negative.append(h.reason[:120])
    ev.positive = ev.positive[:limit]
    ev.negative = ev.negative[:limit]
    ev.missing = ev.missing[:limit]
    return ev
