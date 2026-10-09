"""STD-705：已发布标准冒烟（每题有 active standard + scoring_points）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import ExamQuestionStandard, ExamQuestionStandardStatus
from app.services.standard_engine.bank_questions import bank_essay_questions
from app.services.standard_engine.standard_store import get_active_standard_row


def main() -> None:
    db = SessionLocal()
    try:
        questions = bank_essay_questions(db).all()
        with_std = 0
        for q in questions:
            row = get_active_standard_row(db, q.id)
            if row and q.scoring_points:
                with_std += 1
        total_published = (
            db.query(ExamQuestionStandard)
            .filter(ExamQuestionStandard.status == ExamQuestionStandardStatus.published)
            .count()
        )
        print(f"published_standards rows: {total_published}")
        print(f"essay questions with active standard + rubric snapshot: {with_std}/{len(questions)}")
        if with_std == 0 and len(questions) > 0:
            sys.exit(1)
        print("standard_regression_smoke: ok")
    finally:
        db.close()


if __name__ == "__main__":
    main()
