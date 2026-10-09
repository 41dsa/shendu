"""纯 AI：对 AI 金标样本批量跑批改并输出回归摘要。"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import GoldSample, User, UserRole
from app.services.gold_service import regression_summary, run_gold_sample_sync


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--admin-email", required=True, help="须已配置 BYOK 与 License")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--question-id", default="", help="仅跑绑定该题的金标")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        admin = db.query(User).filter(User.email == args.admin_email.lower()).first()
        if not admin or admin.role != UserRole.admin:
            print("invalid admin-email")
            sys.exit(1)
        q = db.query(GoldSample).filter(GoldSample.note.like("%auto:ai_gold%"))
        if args.question_id:
            q = q.filter(GoldSample.question_id == args.question_id)
        samples = q.order_by(GoldSample.created_at.desc()).limit(args.limit).all()
        if not samples:
            print("no AI gold samples; run seed_ai_gold.py first")
            sys.exit(1)
        for s in samples:
            try:
                run = run_gold_sample_sync(db, s, admin.id)
                print(
                    f"{s.id[:20]}… ai={run.ai_score} delta={run.score_delta} std_v={run.standard_version}"
                )
            except Exception as exc:
                print(f"{s.id}: FAIL {exc}")
        summary = regression_summary(db)
        print("regression:", summary)
    finally:
        db.close()


if __name__ == "__main__":
    main()
