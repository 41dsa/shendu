#!/usr/bin/env python3
"""Q-02：题目 ↔ 生效标准版本关联。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import Question
from app.services.standard_engine.question_standard_link import bulk_standard_links, standard_link_for_question
from app.services.standard_engine.standard_store import get_active_standard_row


def main() -> None:
    db = SessionLocal()
    try:
        q = db.get(Question, "demo-essay-001")
        assert q, "demo-essay-001 missing"
        link = standard_link_for_question(db, q.id)
        row = get_active_standard_row(db, q.id)
        if row:
            assert link["has_active_standard"]
            assert link["standard_version"] == row.version
            assert link["review_status"] in ("draft", "published", "in_review", "archived")
        else:
            assert not link["has_active_standard"]

        bulk = bulk_standard_links(db, [q.id, "nonexistent-q"])
        assert q.id in bulk
        assert bulk["nonexistent-q"]["has_active_standard"] is False
        print("verify_question_standard_link: OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
