#!/usr/bin/env python3
"""M-14：标准卡教研审核服务（队列 / 通过 / 发布门禁）。"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.models.entities import (
    Question,
    StandardGenerationJob,
    StandardGenerationJobStatus,
    StandardJobStep,
)
from app.services.standard_engine.publish_service import PublishBlockedError, publish_standard_from_job
from app.services.standard_engine.standard_card_review_service import (
    list_standard_card_review_queue,
    review_standard_card,
)


def _seed_job(db, question_id: str, *, review: str, score: float, disputes: list[str]) -> str:
    job_id = str(uuid.uuid4())
    qid = question_id
    job = StandardGenerationJob(
        id=job_id,
        question_id=qid,
        status=StandardGenerationJobStatus.validated,
        document_ids=[],
    )
    db.add(job)
    db.add(
        StandardJobStep(
            job_id=job_id,
            step="validate",
            detail="done",
            payload={"overall_passed": True, "blocking_issues": []},
        )
    )
    db.add(
        StandardJobStep(
            job_id=job_id,
            step="rubric_merged",
            detail="done",
            payload={"criteria": [{"id": "c1", "dimension_id": "D1", "core": "x", "confidence": 0.9}]},
        )
    )
    db.add(
        StandardJobStep(
            job_id=job_id,
            step="question_std",
            detail="done",
            payload={"question_id": qid, "proposition_task": "论证"},
        )
    )
    db.add(
        StandardJobStep(
            job_id=job_id,
            step="standard_card_v1_consensus",
            detail="done",
            payload={
                "consensus_score": score,
                "standard_card_v1": {
                    "schema_version": "standard_card_v1",
                    "question_id": qid,
                    "review_status": review,
                    "theme": "基层治理",
                    "keywords": ["基层治理"],
                    "core_problem": "如何推进基层治理现代化",
                    "dispute_marks": disputes,
                },
            },
        )
    )
    db.commit()
    return job_id


def main() -> None:
    db = SessionLocal()
    try:
        q = db.get(Question, "demo-essay-001")
        assert q, "demo-essay-001 missing"
        low_id = _seed_job(db, q.id, review="draft", score=0.5, disputes=["模型分歧"])
        try:
            publish_standard_from_job(db, low_id, force=False)
            raise AssertionError("低共识未审核应拦截发布")
        except PublishBlockedError:
            pass

        review_standard_card(db, low_id, action="approve", admin_user_id="admin-test")
        row = publish_standard_from_job(db, low_id, force=False)
        assert row.version >= 1

        draft_id = _seed_job(db, q.id, review="draft", score=0.95, disputes=[])
        queue = list_standard_card_review_queue(db)
        assert any(item["job_id"] == draft_id for item in queue)

        review_standard_card(db, draft_id, action="reject", admin_user_id="admin-test", note="需补关键词")
        steps = (
            db.query(StandardJobStep)
            .filter(StandardJobStep.job_id == draft_id, StandardJobStep.step == "standard_card_review")
            .all()
        )
        assert len(steps) >= 1

        print("verify_standard_card_review: OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
