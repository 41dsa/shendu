"""从 submission + question 解析大作文批改上下文（支持用户自备题干/材料）。"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS, USER_ESSAY_QUESTION_ID, essay_word_bounds
from app.models.entities import Question, QuestionType, Submission
from app.services.standard_engine.standard_store import (
    get_active_standard_payload,
    rubric_dimensions_from_payload,
)


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
    standard_version: int | None = None


def resolve_essay_context(
    submission: Submission,
    question: Question | None,
    db: Session | None = None,
) -> EssayGradingContext:
    if not question:
        raise ValueError("QUESTION_NOT_FOUND")

    custom = bool((submission.user_prompt or "").strip())
    prompt = (submission.user_prompt or question.prompt or "").strip()
    material = (
        submission.user_material
        if submission.user_material is not None
        else question.material
    )
    title = "用户自备题目" if custom else (question.title or "申论大作文")
    structured = question.material_structured
    scoring = question.scoring_points or DEFAULT_RUBRIC_DIMENSIONS
    focus_points: list[str] = []
    loss_rules: list[Any] = []
    standard_version: int | None = None
    if custom or question.id == USER_ESSAY_QUESTION_ID:
        scoring = DEFAULT_RUBRIC_DIMENSIONS
    elif db is not None:
        active = get_active_standard_payload(db, question.id)
        if active:
            dims = rubric_dimensions_from_payload(active)
            if dims:
                scoring = dims
            q_std = active.get("question_standard") or {}
            focus_points = list(q_std.get("focus_points") or [])
            loss_rules = list(active.get("loss_rules") or [])
            meta = active.get("_meta") or {}
            standard_version = meta.get("version")

    cache_key = question.id
    if custom:
        cache_key = f"custom:{prompt[:400]}|{(material or '')[:400]}"

    return EssayGradingContext(
        title=title,
        prompt=prompt or (material or ""),
        reference_material=material,
        material_structured=structured,
        scoring_points=scoring,
        score=int(question.score),
        word_limit=int(question.word_limit),
        question_type=question.question_type,
        cache_context_key=cache_key,
        focus_points=focus_points,
        loss_rules=loss_rules,
        standard_version=standard_version,
    )


def word_bounds_for_context(ctx: EssayGradingContext) -> tuple[int, int]:
    return essay_word_bounds(ctx.material_structured, ctx.word_limit)
