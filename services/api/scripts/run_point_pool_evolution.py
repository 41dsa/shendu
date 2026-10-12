"""L4 点池自进化审计：读取 scoring_point_hit_logs，输出 JSON 建议。"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, engine
from app.models.entities import Base, ScoringPointHitLog
from app.services.point_pool_pipeline.l4_evolution import audit_point_pool_from_logs


def main() -> None:
    out_path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("/tmp/point_pool_evolution.json")
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        rows = db.query(ScoringPointHitLog).order_by(ScoringPointHitLog.created_at.desc()).limit(5000).all()
        logs = [
            {
                "point_id": r.point_id,
                "status": r.status,
                "total_score": r.total_score,
                "submission_id": r.submission_id,
                "grading_job_id": r.grading_job_id,
            }
            for r in rows
        ]
        point_ids = sorted({r.point_id for r in rows})
        report = audit_point_pool_from_logs(point_ids=point_ids, hit_logs=logs)
        out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"run_point_pool_evolution: wrote {out_path} samples={report.get('sample_size')}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
