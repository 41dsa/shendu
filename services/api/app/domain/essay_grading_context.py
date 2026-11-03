"""大作文批改上下文（无 ORM 依赖，供评分引擎与冒烟脚本使用）。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.domain.essay import essay_word_bounds
from app.domain.question_type import QuestionType
from app.domain.scoring_engine.level_config import ExamLevelId


@dataclass
class EssayGradingContext:
    title: str
    prompt: str
    reference_material: str | None
    material_structured: dict[str, Any] | None
    scoring_points: list[Any]
    score: int
    word_limit: int
    question_type: QuestionType
    cache_context_key: str
    focus_points: list[str] = field(default_factory=list)
    loss_rules: list[Any] = field(default_factory=list)
    rubric_criteria: list[Any] = field(default_factory=list)
    score_confidence_declaration: str | None = None
    standard_version: int | None = None
    standard_review_status: str | None = None
    exam_policy: dict[str, Any] | None = None
    exam_standard_version: int | None = None
    question_id: str = ""
    anchor_count: int | None = None
    point_pools: dict[str, Any] | None = None
    question_standard: dict[str, Any] | None = None
    exam_level: ExamLevelId | None = None


def word_bounds_for_context(ctx: EssayGradingContext) -> tuple[int, int]:
    if ctx.exam_policy:
        wr = ctx.exam_policy.get("typical_word_range")
        if isinstance(wr, (list, tuple)) and len(wr) >= 2:
            return int(wr[0]), int(wr[1])
    return essay_word_bounds(ctx.material_structured, ctx.word_limit)
