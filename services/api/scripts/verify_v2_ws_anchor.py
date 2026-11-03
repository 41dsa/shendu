#!/usr/bin/env python3
"""V2-WS / V2-ANCHOR：Bradley-Terry + 弱监督 v2 导出包。"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import Question, Submission, SubmissionStatus, User
from app.services.anchor_bradley_terry import anchor_calibration_summary, bradley_terry_strengths
from app.services.trait_pair_compare import complete_pair_compare, create_pair_compare_task
from app.services.weak_supervision_v2_export import export_weak_supervision_bundle


def main() -> None:
    db = SessionLocal()
    try:
        edges = [
            ("a", "b", "T5"),
            ("a", "c", "T5"),
            ("b", "c", "T5"),
        ]
        scores = bradley_terry_strengths(edges)
        assert scores["a"] > scores["b"] > scores["c"]

        q = db.get(Question, "demo-essay-001")
        assert q
        user = db.query(User).first()
        assert user, "need a user"
        sa, sb = str(uuid.uuid4()), str(uuid.uuid4())
        db.add(
            Submission(
                id=sa,
                user_id=user.id,
                question_id=q.id,
                content="验证作文 A " * 50,
                status=SubmissionStatus.submitted,
            )
        )
        db.add(
            Submission(
                id=sb,
                user_id=user.id,
                question_id=q.id,
                content="验证作文 B " * 50,
                status=SubmissionStatus.submitted,
            )
        )
        db.flush()
        t1 = create_pair_compare_task(
            db, question_id=q.id, submission_a_id=sa, submission_b_id=sb, trait_id="T5"
        )
        complete_pair_compare(db, t1.id, preferred_submission_id=sa, trait_id="T5")
        db.commit()

        summary = anchor_calibration_summary(db, q.id)
        assert summary["pair_count"] >= 1

        bundle = export_weak_supervision_bundle(db, question_id=q.id, label_limit=100)
        assert bundle["schema_version"] == "weak-supervision-v2"
        assert bundle["pair_edge_count"] >= 1
        assert bundle["counterexample_templates"]

        print("verify_v2_ws_anchor: OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
