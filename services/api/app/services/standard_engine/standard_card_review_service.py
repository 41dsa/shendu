"""M-14 标准卡教研审核：共识卡 review_status 与审计步。"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import StandardGenerationJob, StandardGenerationJobStatus, StandardJobStep
from app.services.standard_engine.pipeline import append_job_step

CONSENSUS_STEP = "standard_card_v1_consensus"
REVIEW_AUDIT_STEP = "standard_card_review"


def _latest_step_payload(db: Session, job_id: str, step: str) -> dict[str, Any]:
    row = (
        db.query(StandardJobStep)
        .filter(StandardJobStep.job_id == job_id, StandardJobStep.step == step)
        .order_by(StandardJobStep.created_at.desc())
        .first()
    )
    return dict(row.payload) if row and row.payload else {}


def get_job_standard_card_v1(db: Session, job_id: str) -> dict[str, Any]:
    consensus = _latest_step_payload(db, job_id, CONSENSUS_STEP)
    if not consensus:
        return {"job_id": job_id, "has_consensus": False}
    card = dict(consensus.get("standard_card_v1") or {})
    return {
        "job_id": job_id,
        "has_consensus": True,
        "consensus_score": consensus.get("consensus_score"),
        "three_model": consensus.get("three_model"),
        "standard_card_v1": card,
        "review_status": str(card.get("review_status") or "draft"),
        "dispute_marks": list(card.get("dispute_marks") or []),
    }


def list_standard_card_review_queue(db: Session, *, limit: int = 100) -> list[dict[str, Any]]:
    jobs = (
        db.query(StandardGenerationJob)
        .filter(StandardGenerationJob.status == StandardGenerationJobStatus.validated)
        .order_by(StandardGenerationJob.created_at.desc())
        .limit(limit)
        .all()
    )
    min_cons = float(getattr(settings, "standard_consensus_min_score", 0.85))
    out: list[dict[str, Any]] = []
    for job in jobs:
        consensus = _latest_step_payload(db, job.id, CONSENSUS_STEP)
        if not consensus:
            continue
        card = dict(consensus.get("standard_card_v1") or {})
        review = str(card.get("review_status") or "draft")
        if review == "published":
            continue
        score = float(consensus.get("consensus_score") or 0)
        disputes = list(card.get("dispute_marks") or [])
        blocked = score < min_cons or bool(disputes)
        out.append(
            {
                "job_id": job.id,
                "question_id": job.question_id,
                "created_at": job.created_at.isoformat() if job.created_at else None,
                "consensus_score": score,
                "review_status": review,
                "dispute_marks": disputes,
                "publish_blocked": blocked,
                "min_consensus_score": min_cons,
            }
        )
    return out


def review_standard_card(
    db: Session,
    job_id: str,
    *,
    action: Literal["approve", "reject"],
    admin_user_id: str,
    note: str = "",
    dispute_marks: list[str] | None = None,
) -> dict[str, Any]:
    job = db.get(StandardGenerationJob, job_id)
    if not job:
        raise ValueError("任务不存在")
    if job.status != StandardGenerationJobStatus.validated:
        raise ValueError("仅已验证通过的任务可审核标准卡")

    consensus = _latest_step_payload(db, job_id, CONSENSUS_STEP)
    if not consensus or not consensus.get("standard_card_v1"):
        raise ValueError("任务缺少 standard_card_v1_consensus 步骤")

    new_consensus = deepcopy(consensus)
    card = dict(new_consensus.get("standard_card_v1") or {})

    if action == "approve":
        card["review_status"] = "published"
        if dispute_marks is not None:
            card["dispute_marks"] = dispute_marks
        detail = "admin_approved"
    else:
        card["review_status"] = "draft"
        marks = list(card.get("dispute_marks") or [])
        if note.strip():
            marks.append(f"教研驳回: {note.strip()}")
        card["dispute_marks"] = marks
        detail = "admin_rejected"

    new_consensus["standard_card_v1"] = card
    append_job_step(db, job, CONSENSUS_STEP, new_consensus, detail=detail)
    append_job_step(
        db,
        job,
        REVIEW_AUDIT_STEP,
        {
            "action": action,
            "admin_user_id": admin_user_id,
            "note": note,
            "review_status": card.get("review_status"),
        },
        detail=detail,
    )

    return {
        "job_id": job_id,
        "action": action,
        "review_status": card.get("review_status"),
        "dispute_marks": card.get("dispute_marks") or [],
    }
