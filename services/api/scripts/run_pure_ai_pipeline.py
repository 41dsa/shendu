#!/usr/bin/env python3
"""纯 AI 总入口：标准批量 → 金标 → 验收报告 →（可选）金标回归。

示例:
  cd services/api && source .venv/bin/activate
  python scripts/run_pure_ai_pipeline.py --limit 21
  python scripts/run_pure_ai_pipeline.py --limit 5 --admin-email admin@example.com --run-gold-regression
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = API_ROOT / "scripts"


def main() -> None:
    parser = argparse.ArgumentParser(description="DEC-06/07/08 纯 AI 一条龙")
    parser.add_argument("--limit", type=int, default=21)
    parser.add_argument("--admin-email", default="", help="LLM 标准/金标与回归")
    parser.add_argument("--mode", choices=("stub", "llm", "auto"), default="stub")
    parser.add_argument("--run-gold-regression", action="store_true")
    parser.add_argument("--report", type=Path, default=API_ROOT / "mstd_e_ai_report.md")
    parser.add_argument("--skip-batch", action="store_true", help="仅报告/回归")
    args = parser.parse_args()

    os.environ.setdefault("STANDARD_AI_ANNOTATION", "1")
    os.environ.setdefault("STANDARD_AUTO_PUBLISH", "1")
    os.environ.setdefault("STANDARD_AUTO_PUBLISH_FORCE", "1")
    if args.mode == "stub":
        os.environ["STANDARD_GEN_MODE"] = "stub"
    elif args.mode == "llm":
        os.environ["STANDARD_GEN_MODE"] = "llm"

    if not args.skip_batch:
        cmd = [
            sys.executable,
            str(SCRIPTS / "run_ai_standard_batch.py"),
            "--all-essay",
            "--limit",
            str(args.limit),
            "--report",
            str(args.report),
        ]
        if args.admin_email:
            cmd.extend(["--admin-email", args.admin_email])
        subprocess.run(cmd, cwd=API_ROOT, check=True)
    else:
        subprocess.run(
            [sys.executable, str(SCRIPTS / "mstd_e_ai_report.py"), str(args.report)],
            cwd=API_ROOT,
            check=True,
        )

    if args.run_gold_regression:
        if not args.admin_email:
            print("run_gold_regression 需要 --admin-email（BYOK）")
            sys.exit(1)
        subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "run_ai_gold_regression.py"),
                "--admin-email",
                args.admin_email,
                "--limit",
                str(args.limit * 3),
            ],
            cwd=API_ROOT,
            check=False,
        )

    print(f"run_pure_ai_pipeline: done -> {args.report}")


if __name__ == "__main__":
    main()
