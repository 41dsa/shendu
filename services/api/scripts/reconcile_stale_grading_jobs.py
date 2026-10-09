"""手动释放僵尸批改任务。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.grading_limits import reconcile_stale_grading_jobs


def main() -> None:
    db = SessionLocal()
    try:
        n = reconcile_stale_grading_jobs(db)
        print(f"reconcile_stale_grading_jobs: released {n}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
