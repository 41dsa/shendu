"""Q-02：题目与当前生效考试标准（标准卡版本）关联摘要。"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import ExamQuestionStandard, ExamQuestionStandardStatus
from app.services.standard_engine.standard_store import get_active_standard_row


def _review_status_from_payload(payload: dict[str, Any]) -> str:
    consensus = payload.get("standard_card_v1_consensus") or {}
    if isinstance(consensus, dict):
        card = consensus.get("standard_card_v1") or {}
        if isinstance(card, dict) and card.get("review_status"):
            return str(card["review_status"])
    q_std = payload.get("question_standard") or {}
    if isinstance(q_std, dict) and q_std.get("review_status"):
        return str(q_std["review_status"])
    return "published"


def standard_link_for_question(db: Session, question_id: str) -> dict[str, Any]:
    row = get_active_standard_row(db, question_id)
    if not row:
        return {
            "question_id": question_id,
            "has_active_standard": False,
            "standard_version": None,
            "standard_id": None,
            "published_at": None,
            "source_job_id": None,
            "review_status": None,
            "schema_version": None,
        }
    payload = dict(row.payload or {})
    q_std = payload.get("question_standard") or {}
    schema_version = None
    if isinstance(q_std, dict):
        schema_version = q_std.get("schema_version")
    return {
        "question_id": question_id,
        "has_active_standard": True,
        "standard_version": row.version,
        "standard_id": row.id,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "source_job_id": payload.get("source_job_id"),
        "review_status": _review_status_from_payload(payload),
        "schema_version": schema_version,
    }


def bulk_standard_links(db: Session, question_ids: list[str]) -> dict[str, dict[str, Any]]:
    if not question_ids:
        return {}
    rows = (
        db.query(ExamQuestionStandard)
        .filter(
            ExamQuestionStandard.question_id.in_(question_ids),
            ExamQuestionStandard.is_active.is_(True),
            ExamQuestionStandard.status == ExamQuestionStandardStatus.published,
        )
        .all()
    )
    out: dict[str, dict[str, Any]] = {
        qid: {
            "question_id": qid,
            "has_active_standard": False,
            "standard_version": None,
            "standard_id": None,
            "published_at": None,
            "source_job_id": None,
            "review_status": None,
            "schema_version": None,
        }
        for qid in question_ids
    }
    for row in rows:
        payload = dict(row.payload or {})
        q_std = payload.get("question_standard") or {}
        schema_version = q_std.get("schema_version") if isinstance(q_std, dict) else None
        out[row.question_id] = {
            "question_id": row.question_id,
            "has_active_standard": True,
            "standard_version": row.version,
            "standard_id": row.id,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "source_job_id": payload.get("source_job_id"),
            "review_status": _review_status_from_payload(payload),
            "schema_version": schema_version,
        }
    return out
