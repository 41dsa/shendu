"""V0.3-E：考试级标准聚合冒烟。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import ExamStandard
from app.services.standard_engine.exam_standard_service import publish_exam_standard
from app.services.standard_engine.bank_questions import bank_essay_questions


def main() -> None:
    os.environ["STANDARD_GEN_MODE"] = "stub"
    os.environ["STANDARD_AUTO_PUBLISH"] = "0"
    db = SessionLocal()
    try:
        from app.services.standard_engine.pipeline import run_standard_generation_job
        from app.models.entities import StandardGenerationJob, StandardGenerationJobStatus
        from app.services.standard_engine.publish_service import publish_standard_from_job

        target_exam = "国考市地级"
        target_year = 2024
        qs = [
            q
            for q in bank_essay_questions(db).all()
            if (q.material_structured or {}).get("exam") == target_exam
            and (q.material_structured or {}).get("year") == target_year
        ]
        assert qs, "缺少国考市地级 2024 联调题"
        for q in qs:
            job = StandardGenerationJob(
                question_id=q.id,
                document_ids=[],
                status=StandardGenerationJobStatus.pending,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            run_standard_generation_job(db, job.id)
            db.refresh(job)
            if job.status.value == "published":
                continue
            if job.status.value != "validated":
                assert job.status.value == "failed", f"unexpected job status {job.status.value}"
            publish_standard_from_job(db, job.id, force=True)
        row = publish_exam_standard(db, exam=target_exam, year=target_year)
        assert row.is_active
        assert (row.payload or {}).get("question_count") == len(qs)
        active = db.query(ExamStandard).filter(ExamStandard.is_active.is_(True)).count()
        assert active >= 1
        print(f"verify_exam_standard: ok bundle v{row.version} questions={len(qs)}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
