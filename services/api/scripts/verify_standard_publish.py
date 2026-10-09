"""STD-P5：发布 + 批改上下文集成冒烟（stub 流水线）。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["STANDARD_GEN_MODE"] = "stub"

from app.database import SessionLocal
from app.models.entities import Question, StandardGenerationJob, StandardGenerationJobStatus, Submission, SubmissionStatus, User
from app.services.standard_engine.pipeline import run_standard_generation_job
from app.services.standard_engine.publish_service import publish_standard_from_job
from app.services.essay_context import resolve_essay_context


def main() -> None:
    db = SessionLocal()
    q = db.get(Question, "demo-essay-001")
    assert q, "demo-essay-001 missing"

    job = StandardGenerationJob(question_id=q.id, status=StandardGenerationJobStatus.pending)
    db.add(job)
    db.commit()
    db.refresh(job)
    run_standard_generation_job(db, job.id)
    db.refresh(job)
    assert job.status == StandardGenerationJobStatus.validated, job.error_message

    published = publish_standard_from_job(db, job.id)
    assert published.is_active

    user = db.query(User).first()
    assert user, "need at least one user in db"
    sub = Submission(
        user_id=user.id,
        question_id=q.id,
        content="测试作文内容" * 50,
        status=SubmissionStatus.submitted,
    )
    ctx = resolve_essay_context(sub, q, db)
    assert ctx.standard_version == published.version
    assert ctx.scoring_points
    print("verify_standard_publish: ok", "version", ctx.standard_version)
    db.close()


if __name__ == "__main__":
    main()
