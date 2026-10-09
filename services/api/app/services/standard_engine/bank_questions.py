"""题库侧大作文（不含用户自备题占位）。"""

from sqlalchemy.orm import Query, Session

from app.domain.essay import USER_ESSAY_QUESTION_ID
from app.models.entities import Question, QuestionType


def bank_essay_questions(db: Session) -> Query:
    return db.query(Question).filter(
        Question.question_type == QuestionType.essay,
        Question.published.is_(True),
        Question.id != USER_ESSAY_QUESTION_ID,
    )
