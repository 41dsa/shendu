"""STD-704：对比教研标注表与已生成标准，输出简易指标。

用法:
  python scripts/eval_standard_metrics.py ../../data/standards/annotation/questions_for_labeling.csv
  python scripts/eval_standard_metrics.py ../../data/standards/annotation/questions_for_labeling.csv --output /tmp/std_metrics.json
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.services.standard_engine.metrics_eval import evaluate_annotation_csv


def main() -> None:
    parser = argparse.ArgumentParser(description="STD-704 标注 vs 标准指标")
    parser.add_argument("annotation_csv", type=Path)
    parser.add_argument("--output", "-o", type=Path, help="写入 JSON 报告")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        report = evaluate_annotation_csv(db, args.annotation_csv)
    except FileNotFoundError as exc:
        print(f"文件不存在: {exc}")
        sys.exit(1)
    finally:
        db.close()

    print("=== STD 指标（简易） ===")
    print(f"标注行（含 question_id）: {report['rows_evaluated']}")
    if report["rows_evaluated"] and report["form_match_rate"] is not None:
        print(
            f"命题形式一致率: {report['form_match_rate']:.1%} "
            f"({report['form_match_count']}/{report['rows_evaluated']}) "
            f"目标 ≥{report['targets']['form_match_rate']:.0%} "
            f"{'✓' if report['targets_met']['form_match_rate'] else '✗'}"
        )
        if report["task_match_rate"] is not None:
            print(
                f"审题任务一致率: {report['task_match_rate']:.1%} "
                f"({report['task_match_count']}/{report['rows_evaluated']}) "
                f"目标 ≥{report['targets']['task_match_rate']:.0%} "
                f"{'✓' if report['targets_met']['task_match_rate'] else '✗'}"
            )
    if report["keyword_recall_total"]:
        print(
            f"核心准则关键词召回: {report['keyword_recall_rate']:.1%} "
            f"({report['keyword_recall_hits']}/{report['keyword_recall_total']}) "
            f"目标 ≥{report['targets']['keyword_recall_rate']:.0%} "
            f"{'✓' if report['targets_met']['keyword_recall_rate'] else '✗'}"
        )
    else:
        print("核心准则关键词召回: N/A（标注 core_criteria_keywords 为空）")

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"JSON 报告: {args.output}")


if __name__ == "__main__":
    main()
