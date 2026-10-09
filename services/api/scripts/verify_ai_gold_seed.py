"""DEC-08：AI 金标 stub 写入冒烟。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import GoldSample
from app.services.gold_ai_service import TIERS, gold_sample_id, seed_ai_gold_for_question_sync


def main() -> None:
    db = SessionLocal()
    try:
        seed_ai_gold_for_question_sync(db, "demo-essay-001", mode="stub")
        for tier in TIERS:
            sid = gold_sample_id("demo-essay-001", tier)
            row = db.get(GoldSample, sid)
            assert row and row.reference_answer, sid
            assert row.note and "auto:ai_gold" in row.note
        print("verify_ai_gold_seed: ok")
    finally:
        db.close()


if __name__ == "__main__":
    main()
