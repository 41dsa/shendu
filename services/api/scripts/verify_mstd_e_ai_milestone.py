"""M-STD-E-AI 里程碑（不重复跑全量 suite，适合 CI 在 pipeline 之后）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.mstd_e_ai_eval import evaluate_mstd_e_ai_milestone


def main() -> None:
    db = SessionLocal()
    try:
        m = evaluate_mstd_e_ai_milestone(db)
    finally:
        db.close()
    print("checks:", m["checks"])
    if not m["milestone_mstd_e_ai_passed"]:
        print("verify_mstd_e_ai_milestone: FAIL")
        print("hint: python scripts/run_pure_ai_pipeline.py --limit 40 --mode stub")
        sys.exit(1)
    print("verify_mstd_e_ai_milestone: ok")


if __name__ == "__main__":
    main()
