"""⑥ 评分校准：导出金标跑分 + 争议记录为 Benchmark CSV。"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.entities import GoldRun, GoldSample, ScoreDispute


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("calibration_export.csv")
    db = SessionLocal()
    rows: list[dict[str, str | float | None]] = []
    try:
        for run in db.query(GoldRun).order_by(GoldRun.created_at.desc()).limit(500).all():
            sample = db.get(GoldSample, run.gold_sample_id)
            expected = run.expected_mid
            ai = run.ai_score
            delta = run.score_delta
            rows.append(
                {
                    "source": "gold_regression",
                    "question_id": sample.question_id if sample else "",
                    "sample_title": sample.title if sample else "",
                    "expected_mid": expected,
                    "ai_score": ai,
                    "error": (ai - expected) if ai is not None and expected is not None else None,
                    "abs_delta": delta,
                    "standard_version": run.standard_version,
                }
            )
        for d in db.query(ScoreDispute).order_by(ScoreDispute.created_at.desc()).limit(200).all():
            rows.append(
                {
                    "source": "user_dispute",
                    "question_id": "",
                    "sample_title": (d.reason or "")[:80],
                    "expected_mid": None,
                    "ai_score": None,
                    "error": None,
                    "abs_delta": None,
                    "standard_version": None,
                }
            )
    finally:
        db.close()

    if not rows:
        print("no calibration rows")
        return
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {len(rows)} rows -> {out}")


if __name__ == "__main__":
    main()
