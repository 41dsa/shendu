"""M-STD-E（纯 AI）：工程冒烟 + 自洽指标 + 发布计数 → Markdown 报告。"""

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.gold_service import regression_summary
from app.services.mstd_e_ai_eval import evaluate_mstd_e_ai_milestone

API_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = API_ROOT / "scripts"


def run_suite() -> str:
    proc = subprocess.run(
        [sys.executable, str(SCRIPTS / "verify_std_e_suite.py")],
        cwd=API_ROOT,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else API_ROOT / "mstd_e_ai_report.md"
    suite_log = run_suite()

    db = SessionLocal()
    try:
        milestone = evaluate_mstd_e_ai_milestone(db)
        metrics = milestone.get("metrics")
        gold_reg = regression_summary(db)
    finally:
        db.close()

    lines = [
        "# M-STD-E 纯 AI 验收报告",
        "",
        f"- 生成时间: {datetime.now(UTC).isoformat()}",
        "- 模式: **纯 AI（DEC-06～08）**；标注反写、自动发布、AI 金标；指标为 **自洽率**",
        "",
        "## 1. 工程冒烟",
        "",
        "```",
        suite_log,
        "```",
        "",
        "## 2. 题库与发布",
        "",
        f"- 已发布 essay 题: {milestone['essay_questions_published']}",
        f"- 至少一版 published standard 的题数: {milestone['published_standard_questions']}",
        f"- AI 金标条数: {milestone['ai_gold_samples']}",
        "",
        "## 3. 自洽指标（STD-704）",
        "",
    ]
    if metrics:
        lines.append(f"- 标注文件: `{metrics['annotation_file']}`")
        lines.append(f"- 行数: {metrics['rows_evaluated']}")
        for key, label in (
            ("form_match_rate", "命题形式自洽"),
            ("task_match_rate", "审题任务自洽"),
            ("keyword_recall_rate", "准则关键词自洽"),
        ):
            val = metrics.get(key)
            met = metrics.get("targets_met", {}).get(key)
            if val is not None:
                lines.append(f"- {label}: {val:.1%} ({'达标' if met else '未达目标'})")
            else:
                lines.append(f"- {label}: N/A")
        lines.append("")
        lines.append("<details><summary>JSON</summary>")
        lines.append("")
        lines.append("```json")
        lines.append(json.dumps(metrics, ensure_ascii=False, indent=2))
        lines.append("```")
        lines.append("</details>")
    else:
        lines.append("- 无标注文件，请先跑标准生成或 `bootstrap_annotation_from_jobs.py`")

    lines.extend(
        [
            "",
            "## 4. 金标回归（近期）",
            "",
            f"- 跑分次数: {gold_reg.get('run_count', 0)}",
            f"- 通过率 Δ≤2: {gold_reg.get('pass_rate')}%",
            f"- 涉及标准版本: {gold_reg.get('standard_versions') or []}",
            "",
            "## 5. 里程碑 M-STD-E-AI",
            "",
        ]
    )
    for name, ok in milestone["checks"].items():
        lines.append(f"- [{('x' if ok else ' ')}] {name}")
    lines.append("")
    lines.append(
        f"**总判定**: {'通过' if milestone['milestone_mstd_e_ai_passed'] else '未通过'}"
    )
    lines.extend(
        [
            "",
            "> 不代表与官方阅卷对齐；仅证明 AI 闭环与内部一致性。",
            "",
        ]
    )
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"mstd_e_ai_report: wrote {out_path}")


if __name__ == "__main__":
    main()
