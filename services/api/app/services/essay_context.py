"""从 submission + question 解析大作文批改上下文（支持用户自备题干/材料）。"""

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.orm import Session

from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS, USER_ESSAY_QUESTION_ID, essay_word_bounds
from app.models.entities import Question, QuestionType, Submission
from app.services.standard_engine.exam_standard_service import get_active_exam_standard
from app.services.standard_engine.custom_essay_standard import get_cached_custom_payload
from app.services.standard_engine.standard_store import (
    get_active_standard_payload,
    rubric_criteria_from_payload,
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
    rubric_criteria: list[Any] = field(default_factory=list)
    score_confidence_declaration: str | None = None
    standard_version: int | None = None
    exam_policy: dict[str, Any] | None = None
    exam_standard_version: int | None = None


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
    rubric_criteria: list[Any] = []
    score_confidence_declaration: str | None = None
    standard_version: int | None = None
    exam_policy: dict[str, Any] | None = None
    exam_standard_version: int | None = None
    active: dict[str, Any] | None = None
    if custom and db is not None:
        active = get_cached_custom_payload(db, submission, question)
    if active is None and not custom and db is not None:
        active = get_active_standard_payload(db, question.id)
    if active:
        dims = rubric_dimensions_from_payload(active)
        if dims:
            scoring = dims
        q_std = active.get("question_standard") or {}
        focus_points = list(q_std.get("focus_points") or [])
        loss_rules = list(active.get("loss_rules") or [])
        rubric_criteria = rubric_criteria_from_payload(active)
        rubric_std = active.get("rubric_standard") or {}
        rules = rubric_std.get("scoring_rules") or {}
        score_confidence_declaration = rules.get("score_confidence_declaration")
        meta = active.get("_meta") or {}
        standard_version = meta.get("version")
    elif custom or question.id == USER_ESSAY_QUESTION_ID:
        scoring = DEFAULT_RUBRIC_DIMENSIONS

    if (
        db is not None
        and not custom
        and question.id != USER_ESSAY_QUESTION_ID
        and structured
    ):
        ex = structured.get("exam")
        yr = structured.get("year")
        if ex and yr is not None:
            exam_row = get_active_exam_standard(db, str(ex), int(yr))
            if exam_row and exam_row.payload:
                exam_policy = dict(exam_row.payload.get("essay_policy") or {})
                exam_standard_version = exam_row.version

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
        rubric_criteria=rubric_criteria,
        score_confidence_declaration=score_confidence_declaration,
        standard_version=standard_version,
        exam_policy=exam_policy,
        exam_standard_version=exam_standard_version,
    )


def word_bounds_for_context(ctx: EssayGradingContext) -> tuple[int, int]:
    if ctx.exam_policy:
        wr = ctx.exam_policy.get("typical_word_range")
        if isinstance(wr, (list, tuple)) and len(wr) >= 2:
            return int(wr[0]), int(wr[1])
    return essay_word_bounds(ctx.material_structured, ctx.word_limit)
