"""纯 AI 一键：批量生成 → 自洽标注 → 可选自动发布 → 指标报告。

  STANDARD_GEN_MODE=stub STANDARD_AUTO_PUBLISH=1 STANDARD_AUTO_PUBLISH_FORCE=1 \\
    python scripts/run_ai_standard_batch.py --all-essay --limit 21
"""

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import StandardGenerationJob, StandardGenerationJobStatus, User, UserRole
from app.services.standard_engine.bank_questions import bank_essay_questions
from app.services.standard_engine.pipeline import run_standard_generation_job

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = API_ROOT / "scripts"


def main() -> None:
    parser = argparse.ArgumentParser(description="DEC-06 纯 AI 批量标准流水线")
    parser.add_argument("--all-essay", action="store_true")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--delay", type=float, default=0.0)
    parser.add_argument("--admin-email", default="")
    parser.add_argument("--report", type=Path, default=None, help="mstd_e_ai_report 输出路径")
    args = parser.parse_args()

    os.environ.setdefault("STANDARD_AI_ANNOTATION", "1")
    os.environ.setdefault("STANDARD_AUTO_PUBLISH", "1")
    os.environ.setdefault("STANDARD_AUTO_PUBLISH_FORCE", "1")

    db = SessionLocal()
    admin_id = None
    if args.admin_email:
        u = db.query(User).filter(User.email == args.admin_email.lower()).first()
        if u and u.role == UserRole.admin:
            admin_id = u.id

    rows = bank_essay_questions(db).limit(args.limit).all()
    ok = 0
    pub = 0
    try:
        for q in rows:
            job = StandardGenerationJob(
                question_id=q.id,
                created_by_user_id=admin_id,
                status=StandardGenerationJobStatus.pending,
            )
            db.add(job)
            db.commit()
            db.refresh(job)
            run_standard_generation_job(db, job.id)
            db.refresh(job)
            if job.status == StandardGenerationJobStatus.published:
                pub += 1
                ok += 1
            elif job.status == StandardGenerationJobStatus.validated:
                ok += 1
            print(f"{q.id[:8]}… -> {job.status.value}")
            time.sleep(max(0, args.delay))
        print(f"run_ai_standard_batch: validated+ {ok}/{len(rows)}, published {pub}/{len(rows)}")
    finally:
        db.close()

    subprocess.run(
        [sys.executable, str(SCRIPTS / "bootstrap_annotation_from_jobs.py"), "--all-essay", "--overwrite"],
        cwd=API_ROOT,
        check=False,
    )
    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS / "seed_ai_gold.py"),
            "--all-published",
            "--limit",
            str(args.limit),
            "--mode",
            "stub" if os.environ.get("STANDARD_GEN_MODE", "stub") == "stub" else "auto",
            *(
                ["--admin-email", args.admin_email]
                if args.admin_email
                else []
            ),
        ],
        cwd=API_ROOT,
        check=False,
    )
    report = args.report or API_ROOT / "mstd_e_ai_report.md"
    subprocess.run([sys.executable, str(SCRIPTS / "mstd_e_ai_report.py"), str(report)], cwd=API_ROOT, check=True)


if __name__ == "__main__":
    main()
