"""批改上下文注入 ExamStandard essay_policy。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.domain.essay import DEMO_QUESTION_ID
from app.models.entities import Question, StandardGenerationJob, StandardGenerationJobStatus, Submission
from app.services.essay_context import resolve_essay_context
from app.services.standard_engine.exam_standard_service import get_active_exam_standard, publish_exam_standard
from app.services.standard_engine.pipeline import run_standard_generation_job
from app.services.standard_engine.publish_service import publish_standard_from_job
from app.services.standard_engine.standard_store import get_active_standard_row


def main() -> None:
    os.environ.setdefault("STANDARD_GEN_MODE", "stub")
    os.environ["STANDARD_AUTO_PUBLISH"] = "0"
    db = SessionLocal()
    try:
        q = db.get(Question, DEMO_QUESTION_ID)
        assert q, "missing demo essay"
        meta = dict(q.material_structured or {})
        meta["exam"] = "国考市地级"
        meta["year"] = 2024
        q.material_structured = meta
        db.commit()

        if not get_active_standard_row(db, q.id):
            job = StandardGenerationJob(question_id=q.id, document_ids=[], status=StandardGenerationJobStatus.pending)
            db.add(job)
            db.commit()
            db.refresh(job)
            run_standard_generation_job(db, job.id)
            publish_standard_from_job(db, job.id, force=True)

        if not get_active_exam_standard(db, "国考市地级", 2024):
            publish_exam_standard(db, exam="国考市地级", year=2024)

        sub = Submission(question_id=q.id, user_id=None, content="test", user_prompt="", user_material="")
        ctx = resolve_essay_context(sub, q, db)
        assert ctx.exam_policy and ctx.exam_policy.get("typical_score") == 40
        assert ctx.exam_standard_version is not None
        print("verify_essay_exam_policy: ok")
    finally:
        db.close()


if __name__ == "__main__":
    main()
