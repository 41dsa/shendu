"""M7 标准发布与回滚。"""

import os
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.domain.standard_engine.confidence import (
    PUBLISH_MIN_CONFIDENCE,
    aggregate_standard_confidence,
    confidence_band,
)
from app.models.entities import (
    ExamQuestionStandard,
    ExamQuestionStandardStatus,
    Question,
    StandardGenerationJob,
    StandardGenerationJobStatus,
    StandardJobStep,
)


class PublishBlockedError(ValueError):
    pass


def auto_publish_enabled() -> bool:
    return os.environ.get("STANDARD_AUTO_PUBLISH", "0").lower() in ("1", "true", "yes")


def auto_publish_force() -> bool:
    return os.environ.get("STANDARD_AUTO_PUBLISH_FORCE", "0").lower() in ("1", "true", "yes")


def try_auto_publish_after_validation(
    db: Session,
    job_id: str,
) -> ExamQuestionStandard | None:
    """纯 AI 无人值守：validated 后自动发布（可选强制）。"""
    if not auto_publish_enabled():
        return None
    try:
        return publish_standard_from_job(db, job_id, force=auto_publish_force())
    except (PublishBlockedError, ValueError):
        return None


def _latest_step_payload(db: Session, job_id: str, step: str) -> dict[str, Any]:
    row = (
        db.query(StandardJobStep)
        .filter(StandardJobStep.job_id == job_id, StandardJobStep.step == step)
        .order_by(StandardJobStep.created_at.desc())
        .first()
    )
    return dict(row.payload) if row and row.payload else {}


def assemble_payload_from_job(db: Session, job: StandardGenerationJob) -> dict[str, Any]:
    q_std = dict(_latest_step_payload(db, job.id, "question_std"))
    consensus = _latest_step_payload(db, job.id, "standard_card_v1_consensus")
    card = dict(consensus.get("standard_card_v1") or {})
    if card:
        q_std = {**q_std, **card, "schema_version": card.get("schema_version") or "standard_card_v1"}
    return {
        "question_id": job.question_id,
        "source_job_id": job.id,
        "question_standard": q_std,
        "standard_card_v1_consensus": consensus or None,
        "material_analysis": _latest_step_payload(db, job.id, "material_analysis"),
        "rubric_standard": _latest_step_payload(db, job.id, "rubric_merged"),
        "loss_rules": (_latest_step_payload(db, job.id, "loss_rules") or {}).get("rules") or [],
        "point_pools": _latest_step_payload(db, job.id, "point_pool_build") or {},
    }


def publish_standard_from_job(db: Session, job_id: str, *, force: bool = False) -> ExamQuestionStandard:
    job = db.get(StandardGenerationJob, job_id)
    if not job:
        raise ValueError("任务不存在")
    if job.status != StandardGenerationJobStatus.validated:
        raise PublishBlockedError("任务尚未验证通过，无法发布")

    validation = _latest_step_payload(db, job.id, "validate")
    if not validation.get("overall_passed"):
        raise PublishBlockedError("验证未通过: " + ",".join(validation.get("blocking_issues") or []))

    payload = assemble_payload_from_job(db, job)
    rubric = payload.get("rubric_standard") or {}
    criteria = rubric.get("criteria") or []
    agg_conf = aggregate_standard_confidence(criteria)
    min_conf = float(getattr(settings, "standard_publish_min_confidence", PUBLISH_MIN_CONFIDENCE))
    if agg_conf < min_conf and not force:
        raise PublishBlockedError(f"标准置信度 {agg_conf:.2f} 低于发布门槛 {min_conf}")

    consensus = _latest_step_payload(db, job.id, "standard_card_v1_consensus")
    card = consensus.get("standard_card_v1") if consensus else None
    if isinstance(card, dict):
        from app.schemas.standard_card_v1 import standard_card_v1_from_legacy
        from app.services.standard_engine.standard_card_validation import standard_card_validation_errors

        q_std_step = _latest_step_payload(db, job.id, "question_std")
        v1_card = standard_card_v1_from_legacy(job.question_id, {**q_std_step, **card})
        card_errors = standard_card_validation_errors(v1_card, for_publish=True)
        blocking_card = [e for e in card_errors if "proposition_task" in e]
        if str(v1_card.review_status) == "published":
            blocking_card.extend(
                e for e in card_errors if "core_problem" in e or ("M-01:" in e and "theme" in e)
            )
        if blocking_card and not force:
            raise PublishBlockedError("标准卡字段不完整: " + "; ".join(dict.fromkeys(blocking_card)))

        review = str(card.get("review_status") or "draft")
        score = float(consensus.get("consensus_score") or 0)
        min_cons = float(getattr(settings, "standard_consensus_min_score", 0.85))
        if review != "published" and score < min_cons and not force:
            disputes = card.get("dispute_marks") or []
            raise PublishBlockedError(
                "标准卡三模型共识未达发布条件（review_status="
                f"{review}, consensus={score:.2f}）"
                + (f"；分歧：{disputes[0]}" if disputes else "")
            )

    question = db.get(Question, job.question_id)
    if not question:
        raise ValueError("题目不存在")

    latest = (
        db.query(ExamQuestionStandard)
        .filter(ExamQuestionStandard.question_id == job.question_id)
        .order_by(ExamQuestionStandard.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    for row in db.query(ExamQuestionStandard).filter(ExamQuestionStandard.question_id == job.question_id).all():
        row.is_active = False

    validation_result = {
        **validation,
        "standard_confidence": agg_conf,
        "confidence_band": confidence_band(agg_conf),
    }

    published = ExamQuestionStandard(
        question_id=job.question_id,
        version=next_version,
        status=ExamQuestionStandardStatus.published,
        is_active=True,
        payload=payload,
        validation_result=validation_result,
        published_at=datetime.now(UTC),
    )
    db.add(published)

    dims = rubric.get("dimensions") or []
    if dims:
        question.scoring_points = [
            {
                "id": d.get("id"),
                "label": d.get("label"),
                "max_score": d.get("max_score"),
                "required": d.get("required", True),
                "ability": d.get("ability"),
            }
            for d in dims
        ]

    job.status = StandardGenerationJobStatus.published
    db.commit()
    db.refresh(published)
    return published


def rollback_standard_version(db: Session, question_id: str, version: int) -> ExamQuestionStandard:
    target = (
        db.query(ExamQuestionStandard)
        .filter(ExamQuestionStandard.question_id == question_id, ExamQuestionStandard.version == version)
        .first()
    )
    if not target:
        raise ValueError("版本不存在")
    for row in db.query(ExamQuestionStandard).filter(ExamQuestionStandard.question_id == question_id).all():
        row.is_active = False
        if row.id == target.id:
            row.status = ExamQuestionStandardStatus.published
            row.is_active = True
        elif row.status == ExamQuestionStandardStatus.published:
            row.status = ExamQuestionStandardStatus.archived

    question = db.get(Question, question_id)
    if question:
        rubric = (target.payload or {}).get("rubric_standard") or {}
        dims = rubric.get("dimensions") or []
        if dims:
            question.scoring_points = [
                {
                    "id": d.get("id"),
                    "label": d.get("label"),
                    "max_score": d.get("max_score"),
                    "required": d.get("required", True),
                    "ability": d.get("ability"),
                }
                for d in dims
            ]

    db.commit()
    db.refresh(target)
    return target
