"""从 submission + question 解析大作文批改上下文（支持用户自备题干/材料）。"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Session

from app.domain.custom_exam_level import exam_level_from_profile, normalize_exam_level
from app.domain.essay import DEFAULT_RUBRIC_DIMENSIONS, USER_ESSAY_QUESTION_ID
from app.domain.essay_grading_context import EssayGradingContext, word_bounds_for_context
from app.domain.scoring_engine.level_config import ExamLevelId
from app.services.standard_engine.exam_standard_service import get_active_exam_standard
from app.services.standard_engine.custom_essay_standard import get_cached_custom_payload
from app.services.standard_engine.standard_store import (
    get_active_standard_payload,
    rubric_criteria_from_payload,
    rubric_dimensions_from_payload,
)

if TYPE_CHECKING:
    from app.models.entities import ExamProfile, Question, Submission

__all__ = ["EssayGradingContext", "word_bounds_for_context", "resolve_essay_context"]


def resolve_essay_context(
    submission: "Submission",
    question: "Question | None",
    db: Session | None = None,
) -> EssayGradingContext:
    from app.models.entities import ExamProfile

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
    standard_review_status: str | None = None
    exam_policy: dict[str, Any] | None = None
    exam_standard_version: int | None = None
    point_pools: dict[str, Any] | None = None
    question_standard: dict[str, Any] | None = None
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
        question_standard = dict(q_std) if q_std else None
        focus_points = list(q_std.get("focus_points") or [])
        loss_rules = list(active.get("loss_rules") or [])
        rubric_criteria = rubric_criteria_from_payload(active)
        rubric_std = active.get("rubric_standard") or {}
        rules = rubric_std.get("scoring_rules") or {}
        score_confidence_declaration = rules.get("score_confidence_declaration")
        meta = active.get("_meta") or {}
        standard_version = meta.get("version")
        standard_review_status = str(meta.get("status") or "published")
        from app.services.scoring_engine.pool_loader import point_pools_from_payload

        point_pools = point_pools_from_payload(active)
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

    resolved_level: ExamLevelId | None = None
    if custom:
        resolved_level = normalize_exam_level(getattr(submission, "exam_level", None))
        if resolved_level is None and db is not None:
            profile = db.query(ExamProfile).filter(ExamProfile.user_id == submission.user_id).first()
            if profile:
                resolved_level = exam_level_from_profile(
                    exam_type=profile.exam_type or "",
                    job_category=profile.job_category or "",
                )

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
        standard_review_status=standard_review_status,
        exam_policy=exam_policy,
        exam_standard_version=exam_standard_version,
        question_id=question.id,
        point_pools=point_pools,
        question_standard=question_standard,
        exam_level=resolved_level,
    )
