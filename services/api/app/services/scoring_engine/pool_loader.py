from __future__ import annotations

from typing import Any

from app.domain.scoring_engine.level_config import ExamLevelId
from app.domain.scoring_engine.types import ScoringPoint
from app.schemas.point_pool import AtomicPointSchema, PointPoolSchema


class PointPoolLevelMismatchError(ValueError):
    pass


def point_pools_from_payload(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    pools = payload.get("point_pools")
    return dict(pools) if isinstance(pools, dict) else None


def load_point_pool_for_level(
    payload: dict[str, Any] | None,
    level_id: ExamLevelId,
    *,
    question_id: str | None = None,
) -> PointPoolSchema | None:
    pools = point_pools_from_payload(payload)
    if not pools:
        return None
    raw = pools.get(level_id)
    if not raw:
        return None
    pool = PointPoolSchema.model_validate(raw)
    if pool.level_id != level_id:
        raise PointPoolLevelMismatchError(f"点池 level_id={pool.level_id} 与请求 {level_id} 不一致")
    if question_id and pool.question_id not in (question_id, "sys-user-essay"):
        # 自备题占位 ID 与缓存 question_id 可能不同，仅严格校验题库题
        if question_id != "sys-user-essay":
            raise PointPoolLevelMismatchError("点池 question_id 与题目不匹配")
    return pool


def atomic_points_to_scoring_points(pool: PointPoolSchema, level_id: ExamLevelId) -> list[ScoringPoint]:
    points: list[ScoringPoint] = []
    for atom in pool.points:
        points.append(_atomic_to_scoring(atom, level_id))
    return points


def _atomic_to_scoring(atom: AtomicPointSchema, level_id: ExamLevelId) -> ScoringPoint:
    la = atom.level_applicability
    lw = getattr(la, level_id)
    weight = float(lw.weight or 1.0)
    required = bool(lw.required)
    band = "high" if atom.confidence >= 0.85 else "medium" if atom.confidence >= 0.7 else "low"
    max_score = max(1.0, weight)
    return ScoringPoint(
        point_id=atom.point_id,
        text=atom.text,
        dimension_id="D01" if atom.is_main_point else "D03",
        keywords=list(atom.keywords),
        semantic_variants=list(atom.semantic_variants),
        weight=weight,
        max_score=max_score,
        is_main_point=atom.is_main_point,
        usage_band=band,
        level_weight=weight,
        required=required,
        confidence=float(atom.confidence),
        source="point_pool",
    )
