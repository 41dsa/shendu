"""批量：从 DB 最新 validated 标准反写 questions_for_labeling.csv（纯 AI 自洽）。"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import StandardGenerationJob, StandardGenerationJobStatus
from app.services.standard_engine.bank_questions import bank_essay_questions
from app.services.standard_engine.annotation_bootstrap import bootstrap_question_from_db, default_annotation_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--overwrite", action="store_true", help="覆盖已有标注列")
    parser.add_argument("--all-essay", action="store_true", help="所有已发布 essay 题")
    args = parser.parse_args()

    db = SessionLocal()
    updated = 0
    try:
        if args.all_essay:
            qids = [q.id for q in bank_essay_questions(db).all()]
        else:
            qids = [
                r[0]
                for r in db.query(StandardGenerationJob.question_id)
                .filter(
                    StandardGenerationJob.status.in_(
                        [
                            StandardGenerationJobStatus.validated,
                            StandardGenerationJobStatus.published,
                        ]
                    )
                )
                .distinct()
                .all()
            ]
        for qid in qids:
            if bootstrap_question_from_db(db, qid, overwrite=args.overwrite):
                updated += 1
        print(f"bootstrap_annotation_from_jobs: updated {updated} rows -> {default_annotation_path()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
