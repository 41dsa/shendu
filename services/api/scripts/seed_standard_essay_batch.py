"""STD-207：导入 demo 批次（5 题国考大作文 CSV）。"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.standard_engine.structure_service import upsert_question_from_row

REPO_CSV = Path(__file__).resolve().parents[3] / "data/standards/国考/2024/demo_essay_batch.csv"


def main() -> None:
    if not REPO_CSV.is_file():
        print(f"Missing {REPO_CSV}")
        sys.exit(1)
    db = SessionLocal()
    count = 0
    try:
        with REPO_CSV.open(encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                upsert_question_from_row(db, row)
                count += 1
        print(f"seed_standard_essay_batch: {count} questions from {REPO_CSV}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
