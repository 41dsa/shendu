#!/usr/bin/env python3
"""Q-01/Q-03：EssayItem 导入、A 类锁定与审计。"""

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, SessionLocal, engine
from app.models.entities import EssayImportAudit, Question
from app.services.standard_engine.essay_item_import_service import (
    import_essay_items,
    is_essay_item_locked,
    locked_field_violations,
)


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        row = {
            "exam": "验证卷",
            "year": 2099,
            "title": f"EssayItem验证题-{suffix}",
            "prompt": "围绕测试主题写一篇文章。",
            "material": "给定材料段落。",
            "exam_instructions": "不得抄袭。",
            "word_min": 800,
            "word_max": 1200,
        }
        r1 = import_essay_items(db, [row], source="verify", lock_a_fields=True)
        assert r1.created_count == 1
        qid = r1.lines[0].question_id
        q = db.get(Question, qid)
        assert q and is_essay_item_locked(q)

        row2 = dict(row)
        row2["prompt"] = "篡改后的题干"
        r2 = import_essay_items(db, [row2], source="verify", lock_a_fields=True)
        assert r2.skipped_locked_count == 1

        violations = locked_field_violations(q, {"prompt": "篡改后的题干"})
        assert "prompt" in violations

        audits = db.query(EssayImportAudit).order_by(EssayImportAudit.created_at.desc()).limit(5).all()
        assert len(audits) >= 2
        print("verify_essay_item_import: OK")
    finally:
        db.close()


if __name__ == "__main__":
    main()
