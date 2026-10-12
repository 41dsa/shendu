"""将 RubricCriterion / 维度 / focus_points 适配为评分引擎采分点池。"""

from __future__ import annotations

from typing import Any

from app.domain.scoring_engine.types import ScoringPoint
from app.domain.standard_engine.criterion_confidence import criterion_usage_band

POINT_POOL_VERSION = "1.0.0"


def _level_weight_for_point(level_id: str, criterion: dict[str, Any]) -> float:
    # 大作文 V1：准则级权重由 rubric weight；级别系数后续可扩展 level_applicability
    _ = level_id
    w = float(criterion.get("weight") or 1.0)
    return max(0.2, min(2.0, w))


def build_point_pool(
    *,
    rubric_criteria: list[Any],
    scoring_dimensions: list[Any],
    focus_points: list[str],
    level_id: str,
    max_score: float,
) -> list[ScoringPoint]:
    points: list[ScoringPoint] = []
    dim_max: dict[str, float] = {}
    for dim in scoring_dimensions or []:
        if isinstance(dim, dict) and dim.get("id"):
            dim_max[str(dim["id"])] = float(dim.get("max_score") or 0)

    criteria_dicts = [c for c in (rubric_criteria or []) if isinstance(c, dict)]
    if criteria_dicts:
        for c in criteria_dicts:
            cid = str(c.get("id") or "")
            if not cid:
                continue
            conf = float(c.get("confidence") or 0.85)
            band = c.get("usage_band") or criterion_usage_band(conf)
            dim_id = str(c.get("dimension_id") or "D01")
            mx = float(c.get("max_score") or dim_max.get(dim_id) or max_score / 4)
            keywords = list(c.get("observable_signals") or []) + list(c.get("acceptable_expressions") or [])
            variants = list(c.get("acceptable_expressions") or []) + [str(c.get("core") or "")]
            points.append(
                ScoringPoint(
                    point_id=cid,
                    text=str(c.get("core") or cid),
                    dimension_id=dim_id,
                    keywords=[str(k) for k in keywords if k],
                    semantic_variants=[str(v) for v in variants if v],
                    weight=float(c.get("weight") or 1.0),
                    max_score=mx,
                    is_main_point=dim_id == "D01" or "立意" in str(c.get("core") or ""),
                    usage_band=band,
                    level_weight=_level_weight_for_point(level_id, c),
                    required=band == "high",
                    confidence=conf,
                    source="rubric_criterion",
                )
            )
    else:
        for dim in scoring_dimensions or []:
            if not isinstance(dim, dict):
                continue
            did = str(dim.get("id") or "")
            label = str(dim.get("label") or did)
            if not did:
                continue
            mx = float(dim.get("max_score") or max_score / max(len(scoring_dimensions), 1))
            points.append(
                ScoringPoint(
                    point_id=did,
                    text=label,
                    dimension_id=did,
                    keywords=[label],
                    semantic_variants=[label],
                    weight=1.0,
                    max_score=mx,
                    is_main_point="立意" in label or did == "D01",
                    usage_band="medium",
                    level_weight=1.0,
                    required=bool(dim.get("required", True)),
                    confidence=0.75,
                    source="rubric_dimension",
                )
            )

    for i, fp in enumerate(focus_points or []):
        fp_text = str(fp).strip()
        if not fp_text:
            continue
        points.append(
            ScoringPoint(
                point_id=f"FP{i + 1:03d}",
                text=fp_text,
                dimension_id="D01",
                keywords=[fp_text],
                semantic_variants=[fp_text],
                weight=0.6,
                max_score=0.0,
                is_main_point=i == 0,
                usage_band="medium",
                level_weight=0.8,
                required=False,
                confidence=0.7,
                source="focus_point",
            )
        )

    return points
