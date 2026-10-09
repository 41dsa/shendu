"""STD-210：从 CSV 批量导入大作文题库。用法: python scripts/import_standard_questions_csv.py <csv_path>"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.standard_engine.structure_service import upsert_question_from_row


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_standard_questions_csv.py <csv_path>")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}")
        sys.exit(1)

    db = SessionLocal()
    count = 0
    try:
        with path.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                upsert_question_from_row(db, row)
                count += 1
        print(f"imported/updated {count} questions from {path}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
