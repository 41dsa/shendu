"""DEC-08：为题目生成 AI 金标（高/中/低三档）。"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import User, UserRole
from app.services.standard_engine.bank_questions import bank_essay_questions
from app.services.gold_ai_service import seed_ai_gold_for_question_sync


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question-id", default="demo-essay-001")
    parser.add_argument("--all-published", action="store_true", help="每题 3 条金标（慎用题量）")
    parser.add_argument("--limit", type=int, default=5)
    parser.add_argument("--mode", choices=("auto", "stub", "llm"), default="auto")
    parser.add_argument("--admin-email", default="")
    args = parser.parse_args()

    db = SessionLocal()
    admin_id = None
    if args.admin_email:
        u = db.query(User).filter(User.email == args.admin_email.lower()).first()
        if u and u.role == UserRole.admin:
            admin_id = u.id
    try:
        qids = [args.question_id]
        if args.all_published:
            qids = [q.id for q in bank_essay_questions(db).limit(args.limit).all()]
        total = 0
        for qid in qids:
            rows = seed_ai_gold_for_question_sync(
                db, qid, admin_user_id=admin_id, mode=args.mode
            )
            total += len(rows)
            print(f"{qid}: seeded {len(rows)} ai gold samples")
        print(f"seed_ai_gold: {total} samples")
    finally:
        db.close()


if __name__ == "__main__":
    main()
