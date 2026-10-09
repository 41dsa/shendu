"""DEC-07：validated 后自动发布。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["STANDARD_GEN_MODE"] = "stub"
os.environ["STANDARD_AUTO_PUBLISH"] = "1"
os.environ["STANDARD_AUTO_PUBLISH_FORCE"] = "1"
os.environ["STANDARD_AI_ANNOTATION"] = "1"

from app.database import SessionLocal
from app.models.entities import StandardGenerationJob, StandardGenerationJobStatus, StandardJobStep
from app.services.standard_engine.pipeline import run_standard_generation_job


def main() -> None:
    db = SessionLocal()
    job = StandardGenerationJob(question_id="demo-essay-001", status=StandardGenerationJobStatus.pending)
    db.add(job)
    db.commit()
    run_standard_generation_job(db, job.id)
    db.refresh(job)
    assert job.status == StandardGenerationJobStatus.published, (job.status, job.error_message)
    steps = db.query(StandardJobStep).filter_by(job_id=job.id).all()
    assert any(s.step == "publish" and s.detail == "auto_publish" for s in steps), [s.step for s in steps]
    print("verify_auto_publish: ok")
    db.close()


if __name__ == "__main__":
    main()
