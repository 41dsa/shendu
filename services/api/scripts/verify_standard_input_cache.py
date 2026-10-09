"""标准流水线输入缓存：指纹稳定 + 缓存命中回放。"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import Question, StandardGenerationJob, StandardGenerationJobStatus, StandardJobStep
from app.services.standard_engine.input_cache import (
    build_cache_bundle,
    compute_standard_input_fingerprint,
    document_content_hashes,
    get_pipeline_cache,
    upsert_pipeline_cache,
)
from app.services.standard_engine.pipeline import run_standard_generation_job
from app.services.standard_engine.publish_service import _latest_step_payload


def main() -> None:
    os.environ["STANDARD_GEN_MODE"] = "stub"
    db = SessionLocal()
    try:
        q = db.get(Question, "demo-essay-001")
        assert q, "缺少 demo-essay-001，请先 init_db"

        job_a = StandardGenerationJob(question_id=q.id, status=StandardGenerationJobStatus.pending)
        db.add(job_a)
        db.commit()
        run_standard_generation_job(db, job_a.id)
        db.refresh(job_a)
        assert job_a.status == StandardGenerationJobStatus.validated, job_a.error_message

        doc_ids: list[str] = []
        doc_hashes = document_content_hashes(db, doc_ids)
        fp = compute_standard_input_fingerprint(
            question=q,
            document_ids=doc_ids,
            document_hashes=doc_hashes,
            gen_mode="llm",
        )
        fp2 = compute_standard_input_fingerprint(
            question=q,
            document_ids=doc_ids,
            document_hashes=doc_hashes,
            gen_mode="llm",
        )
        assert fp == fp2, "指纹应稳定"

        bundle = build_cache_bundle(
            question_std=_latest_step_payload(db, job_a.id, "question_std"),
            material_analysis=_latest_step_payload(db, job_a.id, "material_analysis"),
            rubric_candidates=_latest_step_payload(db, job_a.id, "rubric_candidates"),
            rubric_merged=_latest_step_payload(db, job_a.id, "rubric_merged"),
            validate_p05=_latest_step_payload(db, job_a.id, "validate_p05"),
        )
        upsert_pipeline_cache(
            db,
            fingerprint=fp,
            question_id=q.id,
            gen_mode="llm",
            source_job_id=job_a.id,
            bundle=bundle,
        )
        assert get_pipeline_cache(db, fp) is not None

        job_b = StandardGenerationJob(
            question_id=q.id,
            created_by_user_id="admin-cache-test",
            status=StandardGenerationJobStatus.pending,
        )
        db.add(job_b)
        db.commit()

        mock_cred = MagicMock()
        with patch("app.services.standard_engine.pipeline._use_llm", return_value=True), patch(
            "app.services.standard_engine.pipeline.get_credential", return_value=mock_cred
        ):
            os.environ["STANDARD_GEN_MODE"] = "llm"
            run_standard_generation_job(db, job_b.id)

        db.refresh(job_b)
        assert job_b.status == StandardGenerationJobStatus.validated, job_b.error_message

        ingest = _latest_step_payload(db, job_b.id, "ingest")
        assert ingest.get("cache_hit") is True, ingest

        hit_step = (
            db.query(StandardJobStep)
            .filter(StandardJobStep.job_id == job_b.id, StandardJobStep.step == "question_std")
            .order_by(StandardJobStep.created_at.desc())
            .first()
        )
        assert hit_step and hit_step.detail == "cache_hit", hit_step.detail if hit_step else None

        print("verify_standard_input_cache: ok")
    finally:
        db.close()


if __name__ == "__main__":
    main()
