from __future__ import annotations

from sqlalchemy.orm import Session

from app.domain.scoring_engine.types import ScoringEngineResult
from app.models.entities import ScoringPointHitLog, TraitScoringRecord


def persist_trait_scoring_records(
    db: Session,
    *,
    grading_job_id: str,
    submission_id: str,
    question_id: str,
    result: ScoringEngineResult,
) -> None:
    """PRD §11：按 Trait 维度写入弱监督结构化记录（复用 hit_log 表）。"""
    for row in result.trait_diagnostics:
        tid = str(row.get("trait_id") or "")
        if not tid:
            continue
        db.add(
            TraitScoringRecord(
                grading_job_id=grading_job_id,
                submission_id=submission_id,
                question_id=question_id,
                trait_id=tid,
                trait_level=str(row.get("level") or "L2"),
                model_votes=list(row.get("model_votes") or []),
                vote_spread=float(row["vote_spread"]) if row.get("vote_spread") is not None else None,
                confidence=float(row.get("confidence") or 0.0) if row.get("confidence") is not None else None,
                evidence_payload={
                    "evidence_positive": row.get("evidence_positive"),
                    "evidence_negative": row.get("evidence_negative"),
                    "evidence_missing": row.get("evidence_missing"),
                    "human_review_recommended": bool(result.human_review_recommended),
                    "model_votes": list(row.get("model_votes") or []),
                },
                final_calibrated_score=None,
                rubric_version=result.rubric_version or result.point_pool_version,
            )
        )
        db.add(
            ScoringPointHitLog(
                grading_job_id=grading_job_id,
                submission_id=submission_id,
                question_id=question_id,
                exam_level=result.exam_level,
                point_id=tid,
                status=str(row.get("level") or "L2"),
                total_score=float(result.system_center_score or result.total_score or 0),
                point_pool_version=result.rubric_version or result.point_pool_version,
                payload={
                    "record_type": "trait_v1",
                    "trait_level": row.get("level"),
                    "confidence": row.get("confidence"),
                    "evidence_positive": row.get("evidence_positive"),
                    "evidence_negative": row.get("evidence_negative"),
                    "evidence_missing": row.get("evidence_missing"),
                    "participates_in_score": row.get("participates_in_score"),
                    "final_calibrated_score": None,
                },
            )
        )
    from app.config import settings

    if settings.weak_supervision_enabled:
        from app.services.weak_supervision_factory import persist_weak_labels_from_engine

        persist_weak_labels_from_engine(
            db,
            grading_job_id=grading_job_id,
            submission_id=submission_id,
            question_id=question_id,
            result=result,
        )
    try:
        db.commit()
    except Exception:
        db.rollback()


def persist_point_hit_logs(*args, **kwargs) -> None:
    """已废弃：采分点命中日志。保留符号兼容旧 import。"""
    persist_trait_scoring_records(*args, **kwargs)
