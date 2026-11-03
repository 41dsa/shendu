"""STD-210：从 CSV 批量导入大作文题库。用法: python scripts/import_standard_questions_csv.py <csv_path>"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.standard_engine.essay_item_import_service import import_essay_items


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python scripts/import_standard_questions_csv.py <csv_path>")
        sys.exit(1)
    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File not found: {path}")
        sys.exit(1)

    db = SessionLocal()
    try:
        with path.open(encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        result = import_essay_items(db, rows, source="csv_cli", filename=str(path), lock_a_fields=True)
        print(
            f"imported {result.item_count} from {path}: "
            f"created={result.created_count} updated={result.updated_count} "
            f"skipped_locked={result.skipped_locked_count}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
