from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

MatchStage = Literal["keyword", "semantic", "borderline", "miss"]
PointStatus = Literal["hit", "partial", "missed", "borderline", "advisory"]


@dataclass
class ScoringPoint:
    point_id: str
    text: str
    dimension_id: str
    keywords: list[str] = field(default_factory=list)
    semantic_variants: list[str] = field(default_factory=list)
    weight: float = 1.0
    max_score: float = 0.0
    is_main_point: bool = False
    usage_band: Literal["high", "medium", "low"] | None = None
    level_weight: float = 1.0
    required: bool = False
    confidence: float = 0.85
    source: str = "rubric_criterion"


@dataclass
class PointHit:
    point_id: str
    status: PointStatus
    match_stage: MatchStage
    weight: float
    earned: float
    max_score: float
    evidence: str = ""
    evidence_para: int | None = None
    reason: str = ""
    suggestion: str = ""


@dataclass
class ScoringTier:
    tier_id: str
    label: str
    score_min: float
    score_max: float
    reason: str = ""


@dataclass
class EngineLayerTrace:
    layer: str
    detail: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeterministicScoreResult:
    base_score: float
    dimension_scores: dict[str, dict[str, float]]
    point_hits: list[PointHit]
    main_point_hit: bool
    coverage_ratio: float
    tier: ScoringTier
    traces: list[EngineLayerTrace] = field(default_factory=list)


@dataclass
class CalibrationResult:
    penalties: dict[str, float]
    tier_adjusted: ScoringTier | None
    total_penalty: float
    traces: list[EngineLayerTrace] = field(default_factory=list)


@dataclass
class ScoringEngineResult:
    exam_level: str
    level_inferred: bool
    level_config_version: str
    point_pool_version: str
    total_score: float
    max_score: float
    tier: ScoringTier
    dimension_rows: list[dict[str, Any]]
    point_hits: list[PointHit]
    penalties: dict[str, float]
    confidence: float
    level_specific_feedback: str
    evidence_chain: list[dict[str, Any]]
    engine_traces: list[EngineLayerTrace]
    deliberation_triggered: bool = False
    deliberation_note: str = ""
    pool_points: list[ScoringPoint] = field(default_factory=list)
