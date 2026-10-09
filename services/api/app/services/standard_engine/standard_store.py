"""已发布标准读取（M8）。"""

from sqlalchemy.orm import Session

from app.models.entities import ExamQuestionStandard, ExamQuestionStandardStatus


def get_active_standard_row(db: Session, question_id: str) -> ExamQuestionStandard | None:
    return (
        db.query(ExamQuestionStandard)
        .filter(
            ExamQuestionStandard.question_id == question_id,
            ExamQuestionStandard.is_active.is_(True),
            ExamQuestionStandard.status == ExamQuestionStandardStatus.published,
        )
        .first()
    )


def get_active_standard_payload(db: Session, question_id: str) -> dict | None:
    row = get_active_standard_row(db, question_id)
    if not row:
        return None
    payload = dict(row.payload or {})
    payload["_meta"] = {
        "version": row.version,
        "published_at": row.published_at.isoformat() if row.published_at else None,
        "standard_id": row.id,
    }
    return payload


def rubric_dimensions_from_payload(payload: dict) -> list[dict]:
    rubric = payload.get("rubric_standard") or {}
    dims = rubric.get("dimensions") or []
    out: list[dict] = []
    for d in dims:
        out.append(
            {
                "id": d.get("id"),
                "label": d.get("label"),
                "max_score": d.get("max_score"),
                "required": d.get("required", True),
                "ability": d.get("ability"),
            }
        )
    return out or []
