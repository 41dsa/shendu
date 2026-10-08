from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.domain.essay import essay_word_bounds
from app.models.entities import Question, QuestionType, User
from app.schemas.question import QuestionDetail, QuestionListItem, RubricDimensionSchema

router = APIRouter(prefix="/questions", tags=["questions"])

QUESTION_TYPE_LABEL = {"essay": "申论大作文"}


def _word_min(row: Question) -> int:
    lo, _ = essay_word_bounds(row.material_structured, row.word_limit)
    return lo


@router.get("", response_model=list[QuestionListItem])
def list_questions(
    question_type: str | None = None,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[QuestionListItem]:
    q = db.query(Question).filter(Question.published.is_(True))
    if question_type:
        try:
            q = q.filter(Question.question_type == QuestionType(question_type))
        except ValueError:
            return []
    rows = q.order_by(Question.title).all()
    return [
        QuestionListItem(
            id=r.id,
            title=r.title,
            question_type=r.question_type.value,
            question_type_label=QUESTION_TYPE_LABEL.get(r.question_type.value, "申论大作文"),
            score=r.score,
            word_limit=r.word_limit,
            word_min=_word_min(r),
        )
        for r in rows
    ]


@router.get("/{question_id}", response_model=QuestionDetail)
def get_question(
    question_id: str,
    _: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> QuestionDetail:
    row = db.get(Question, question_id)
    if not row:
        raise HTTPException(status_code=404, detail="题目不存在")
    prompt = (row.prompt or "").strip() or (row.material or "")
    dimensions = [RubricDimensionSchema(**p) for p in (row.scoring_points or [])]
    return QuestionDetail(
        id=row.id,
        title=row.title,
        question_type=row.question_type.value,
        question_type_label=QUESTION_TYPE_LABEL.get(row.question_type.value, "申论大作文"),
        score=row.score,
        word_limit=row.word_limit,
        word_min=_word_min(row),
        prompt=prompt,
        reference_material=row.material,
        scoring_points=dimensions,
    )
