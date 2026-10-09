"""从题库导出/补全标注 CSV（保留已有 AI/人工列，仅新增题目行）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import Question
from app.services.standard_engine.bank_questions import bank_essay_questions
from app.services.standard_engine.annotation_bootstrap import (
    FIELDNAMES,
    default_annotation_path,
    load_annotation_rows,
    write_annotation_rows,
)


def main() -> None:
    db = SessionLocal()
    try:
        rows = bank_essay_questions(db).order_by(Question.title).all()
        out = default_annotation_path()
        existing = load_annotation_rows(out)
        for q in rows:
            if q.id not in existing:
                existing[q.id] = {k: "" for k in FIELDNAMES}
                existing[q.id]["question_id"] = q.id
                existing[q.id]["title"] = q.title
            elif not existing[q.id].get("title"):
                existing[q.id]["title"] = q.title
        write_annotation_rows(out, existing)
        print(f"wrote {len(existing)} rows to {out}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
