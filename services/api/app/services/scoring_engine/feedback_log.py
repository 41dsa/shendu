from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.scoring_engine.types import ScoringEngineResult
from app.models.entities import ScoringPointHitLog


def persist_point_hit_logs(
    db: Session,
    *,
    grading_job_id: str,
    submission_id: str,
    question_id: str,
    result: ScoringEngineResult,
) -> None:
    for hit in result.point_hits:
        db.add(
            ScoringPointHitLog(
                grading_job_id=grading_job_id,
                submission_id=submission_id,
                question_id=question_id,
                exam_level=result.exam_level,
                point_id=hit.point_id,
                status=hit.status,
                total_score=float(result.total_score),
                point_pool_version=result.point_pool_version,
                payload={
                    "match_stage": hit.match_stage,
                    "earned": hit.earned,
                    "max_score": hit.max_score,
                },
            )
        )
    try:
        db.commit()
    except Exception:
        db.rollback()
