"""合并重复大作文题库（同 title+exam+year 保留最新一条）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.domain.essay import USER_ESSAY_QUESTION_ID
from app.models.entities import ExamQuestionStandard, Question, QuestionType, Submission


def _key(q: Question) -> tuple:
    meta = q.material_structured or {}
    return (q.title, str(meta.get("exam") or ""), int(meta.get("year") or 0))


def main() -> None:
    db: Session = SessionLocal()
    removed = 0
    try:
        rows = (
            db.query(Question)
            .filter(Question.question_type == QuestionType.essay, Question.id != USER_ESSAY_QUESTION_ID)
            .order_by(Question.title)
            .all()
        )
        groups: dict[tuple, list[Question]] = {}
        for q in rows:
            groups.setdefault(_key(q), []).append(q)
        for _k, qs in groups.items():
            if len(qs) <= 1:
                continue
            keep = qs[-1]
            for dup in qs[:-1]:
                subs = db.query(Submission).filter(Submission.question_id == dup.id).count()
                if subs:
                    continue
                db.query(ExamQuestionStandard).filter(ExamQuestionStandard.question_id == dup.id).delete()
                db.delete(dup)
                removed += 1
        db.commit()
        print(f"dedupe_essay_bank: removed {removed} duplicates")
    finally:
        db.close()


if __name__ == "__main__":
    main()
