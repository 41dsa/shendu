"""STD-703：批量创建标准生成任务（限流）。用法:
  python scripts/batch_standard_jobs.py --question-ids id1,id2 --delay 2
  python scripts/batch_standard_jobs.py --all-essay --limit 10 --delay 3
"""

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import Question, StandardGenerationJob, StandardGenerationJobStatus, User, UserRole
from app.services.standard_engine.bank_questions import bank_essay_questions
from app.services.standard_engine.pipeline import run_standard_generation_job


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--question-ids", default="", help="逗号分隔题目 ID")
    parser.add_argument("--all-essay", action="store_true", help="所有 published 大作文题")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--delay", type=float, default=2.0, help="每题间隔秒数")
    parser.add_argument("--admin-email", default="", help="任务 created_by（须 admin，用于 BYOK auto）")
    parser.add_argument("--sync", action="store_true", help="创建后立即同步跑 pipeline（无 Celery 时）")
    args = parser.parse_args()

    db = SessionLocal()
    admin_id = None
    if args.admin_email:
        u = db.query(User).filter(User.email == args.admin_email.lower()).first()
        if not u or u.role != UserRole.admin:
            print("admin-email 无效或非管理员")
            sys.exit(1)
        admin_id = u.id

    if args.question_ids.strip():
        qids = [x.strip() for x in args.question_ids.split(",") if x.strip()]
    elif args.all_essay:
        rows = bank_essay_questions(db).limit(args.limit).all()
        qids = [q.id for q in rows]
    else:
        print("指定 --question-ids 或 --all-essay")
        sys.exit(1)

    created: list[str] = []
    try:
        for qid in qids[: args.limit]:
            if not db.get(Question, qid):
                print(f"skip missing {qid}")
                continue
            job = StandardGenerationJob(
                question_id=qid,
                created_by_user_id=admin_id,
                status=StandardGenerationJobStatus.pending,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            created.append(job.id)
            print(f"job {job.id} for {qid}")
            if args.sync:
                run_standard_generation_job(db, job.id)
                db.refresh(job)
                print(f"  -> {job.status.value}")
            time.sleep(max(0, args.delay))
        print(f"created {len(created)} jobs")
    finally:
        db.close()


if __name__ == "__main__":
    main()
