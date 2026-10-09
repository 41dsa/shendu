"""从 submission + question 解析大作文批改上下文（支持用户自备题干/材料）。"""

from dataclasses import dataclass
from typing import Any

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS, USER_ESSAY_QUESTION_ID, essay_word_bounds
from app.models.entities import Question, QuestionType, Submission


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


def resolve_essay_context(submission: Submission, question: Question | None) -> EssayGradingContext:
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
    if custom or question.id == USER_ESSAY_QUESTION_ID:
        scoring = DEFAULT_RUBRIC_DIMENSIONS

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
    )


def word_bounds_for_context(ctx: EssayGradingContext) -> tuple[int, int]:
    return essay_word_bounds(ctx.material_structured, ctx.word_limit)
