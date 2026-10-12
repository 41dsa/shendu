"""点池数据契约（评分引擎技术设计 §6.1）。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ExamLevelId = Literal["provincial", "municipal", "enforcement"]
PointType = Literal["main", "sub", "evidence", "theme"]


class LevelWeightSchema(BaseModel):
    weight: float = 1.0
    required: bool = False


class LevelApplicabilitySchema(BaseModel):
    provincial: LevelWeightSchema = Field(default_factory=LevelWeightSchema)
    municipal: LevelWeightSchema = Field(default_factory=LevelWeightSchema)
    enforcement: LevelWeightSchema = Field(default_factory=LevelWeightSchema)


class AtomicPointSchema(BaseModel):
    point_id: str
    text: str
    keywords: list[str] = Field(default_factory=list)
    semantic_variants: list[str] = Field(default_factory=list)
    source_para: list[int] = Field(default_factory=list)
    level_applicability: LevelApplicabilitySchema = Field(default_factory=LevelApplicabilitySchema)
    is_main_point: bool = False
    point_type: PointType = "sub"
    confidence: float = 0.75
    extraction_method: str = "heuristic"
    consensus_votes: int = 0
    consensus_total: int = 0


class PointPoolSchema(BaseModel):
    question_id: str
    level_id: ExamLevelId
    points: list[AtomicPointSchema] = Field(default_factory=list)
    version: str = "1.0.0"
    level_config_version: str = "1.0.0"
    metadata: dict[str, Any] = Field(default_factory=dict)


class PointPoolBundleSchema(BaseModel):
    """按级别独立存储的点池包。"""

    provincial: PointPoolSchema | None = None
    municipal: PointPoolSchema | None = None
    enforcement: PointPoolSchema | None = None
    pipeline_version: str = "1.0.0"
    built_at: str | None = None
