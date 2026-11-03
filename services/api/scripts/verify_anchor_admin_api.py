#!/usr/bin/env python3
"""锚作文运营 API：summary + seed-demo + patch。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import AnchorEssay, Question
from app.services.anchor_essay_admin import anchor_essays_summary_by_question, seed_demo_anchors_for_question


def main() -> None:
    db = SessionLocal()
    try:
        q = db.get(Question, "demo-essay-001")
        assert q, "demo-essay-001 missing"
        before = (
            db.query(AnchorEssay).filter(AnchorEssay.question_id == q.id, AnchorEssay.is_published.is_(True)).count()
        )
        seed_demo_anchors_for_question(db, q.id)
        after = (
            db.query(AnchorEssay).filter(AnchorEssay.question_id == q.id, AnchorEssay.is_published.is_(True)).count()
        )
        assert after >= before

        summary = anchor_essays_summary_by_question(db)
        row = next((s for s in summary if s["question_id"] == q.id), None)
        assert row is not None
        assert row["published_count"] == after
        assert row["relative_scale_ready"] == (after >= 3)

        one = (
            db.query(AnchorEssay)
            .filter(AnchorEssay.question_id == q.id)
            .order_by(AnchorEssay.created_at.desc())
            .first()
        )
        assert one
        one.is_published = False
        db.commit()
        row2 = next(s for s in anchor_essays_summary_by_question(db) if s["question_id"] == q.id)
        assert row2["published_count"] == after - 1
        one.is_published = True
        db.commit()

        print("verify_anchor_admin_api: OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
