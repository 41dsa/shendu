"""STD-309：标准生成流水线（stub 模式）集成冒烟。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["STANDARD_GEN_MODE"] = "stub"
os.environ["STANDARD_AUTO_PUBLISH"] = "0"

from app.database import SessionLocal
from app.models.entities import StandardGenerationJob, StandardGenerationJobStatus, StandardJobStep
from app.services.standard_engine.pipeline import run_standard_generation_job


def main() -> None:
    db = SessionLocal()
    job = StandardGenerationJob(question_id="demo-essay-001", status=StandardGenerationJobStatus.pending)
    db.add(job)
    db.commit()
    db.refresh(job)
    run_standard_generation_job(db, job.id)
    db.refresh(job)
    assert job.status == StandardGenerationJobStatus.validated, (job.status, job.error_message)
    names = [s.step for s in db.query(StandardJobStep).filter_by(job_id=job.id).all()]
    for required in ("ingest", "question_std", "rubric_merged", "loss_rules", "validate"):
        assert required in names, names
    print("verify_standard_pipeline_stub: ok")
    db.close()


if __name__ == "__main__":
    main()
