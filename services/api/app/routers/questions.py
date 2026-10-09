from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.domain.essay import USER_ESSAY_QUESTION_ID, essay_word_bounds
from app.models.entities import ExamProfile, Question, QuestionType, User
from app.schemas.question import QuestionDetail, QuestionListItem, RubricDimensionSchema
from app.services.standard_engine.practice_catalog import (
    list_practice_questions,
    list_recommended_for_profile,
    question_list_meta,
    profile_to_bank_exam,
)
from app.services.standard_engine.standard_store import get_active_standard_row

router = APIRouter(prefix="/questions", tags=["questions"])

QUESTION_TYPE_LABEL = {"essay": "申论大作文"}


def _to_list_item(db: Session, row: Question) -> QuestionListItem:
    meta = question_list_meta(row)
    _, hi = essay_word_bounds(row.material_structured, row.word_limit)
    return QuestionListItem(
        id=row.id,
        title=row.title,
        question_type=row.question_type.value,
        question_type_label=QUESTION_TYPE_LABEL.get(row.question_type.value, "申论大作文"),
        score=row.score,
        word_limit=row.word_limit,
        word_min=meta["word_min"],
        word_max=hi,
        exam=meta["exam"] or None,
        year=meta["year"],
        has_published_standard=get_active_standard_row(db, row.id) is not None,
    )


@router.get("", response_model=list[QuestionListItem])
def list_questions(
    question_type: str | None = None,
    exam: str | None = None,
    year: int | None = None,
    practice_only: bool = Query(True, description="仅返回已发布考试标准的联调/真题题"),
    limit: int = Query(50, ge=1, le=100),
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuestionListItem]:
    if question_type and question_type != "essay":
        return []
    rows = list_practice_questions(
        db,
        exam=exam,
        year=year,
        require_published_standard=practice_only,
        limit=limit,
    )
    return [_to_list_item(db, r) for r in rows]


@router.get("/recommended", response_model=list[QuestionListItem])
def list_recommended_questions(
    limit: int = Query(8, ge=1, le=20),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuestionListItem]:
    profile = db.query(ExamProfile).filter(ExamProfile.user_id == user.id).first()
    rows = list_recommended_for_profile(db, profile, limit=limit)
    return [_to_list_item(db, r) for r in rows]


@router.get("/catalog-context")
def get_catalog_context(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    profile = db.query(ExamProfile).filter(ExamProfile.user_id == user.id).first()
    exam, year = profile_to_bank_exam(profile)
    total = len(
        list_practice_questions(db, exam=None, year=None, require_published_standard=True, limit=200)
    )
    matched = len(list_practice_questions(db, exam=exam, year=year, require_published_standard=True, limit=200))
    return {
        "exam_profile_set": profile is not None,
        "mapped_exam": exam,
        "mapped_year": year,
        "practice_total_with_standard": total,
        "practice_matched_exam_year": matched,
    }


@router.get("/{question_id}", response_model=QuestionDetail)
def get_question(
    question_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionDetail:
    if question_id == USER_ESSAY_QUESTION_ID:
        raise HTTPException(status_code=404, detail="题目不存在")
    row = db.get(Question, question_id)
    if not row or not row.published or row.question_type != QuestionType.essay:
        raise HTTPException(status_code=404, detail="题目不存在")
    if not get_active_standard_row(db, question_id):
        raise HTTPException(status_code=404, detail="该题尚无可用批改标准")
    prompt = (row.prompt or "").strip() or (row.material or "")
    dimensions = [RubricDimensionSchema(**p) for p in (row.scoring_points or [])]
    item = _to_list_item(db, row)
    return QuestionDetail(
        **item.model_dump(),
        prompt=prompt,
        reference_material=row.material,
        scoring_points=dimensions,
    )
