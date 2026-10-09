"""考试级大作文标准聚合（V0.3-E / PDF M7 简版）。"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import (
    ExamQuestionStandard,
    ExamQuestionStandardStatus,
    ExamStandard,
    ExamStandardStatus,
    Question,
    QuestionType,
    StandardDocument,
)
from app.services.standard_engine.bank_questions import bank_essay_questions
from app.services.standard_engine.standard_store import get_active_standard_row
from app.services.standard_engine.structure_service import get_linked_document_ids


DEFAULT_ESSAY_POLICY: dict[str, Any] = {
    "typical_score": 40,
    "typical_word_range": [800, 1200],
    "ability_weights_hint": {"A1": 0.25, "A2": 0.25, "A3": 0.25, "A4": 0.15, "A5": 0.10},
}


def _questions_for_exam_year(db: Session, exam: str, year: int) -> list[Question]:
    exam = exam.strip()
    out: list[Question] = []
    for q in bank_essay_questions(db).all():
        meta = q.material_structured or {}
        if meta.get("exam") == exam and meta.get("year") == year:
            out.append(q)
    return out


def _collect_document_refs(db: Session, questions: list[Question]) -> list[dict[str, Any]]:
    seen: set[str] = set()
    refs: list[dict[str, Any]] = []
    for q in questions:
        for doc_id in get_linked_document_ids(q):
            if doc_id in seen:
                continue
            seen.add(doc_id)
            doc = db.get(StandardDocument, doc_id)
            if doc:
                refs.append(
                    {
                        "document_id": doc.id,
                        "title": doc.title,
                        "source_level": doc.source_level.value,
                        "doc_category": (doc.metadata_json or {}).get("doc_category"),
                    }
                )
    return refs


def publish_exam_standard(
    db: Session,
    *,
    exam: str,
    year: int,
    essay_policy: dict[str, Any] | None = None,
) -> ExamStandard:
    exam = exam.strip()
    if not exam:
        raise ValueError("exam 必填")
    questions = _questions_for_exam_year(db, exam, year)
    if not questions:
        raise ValueError(f"无大作文题库：{exam} {year}")

    bindings: list[dict[str, Any]] = []
    missing: list[str] = []
    for q in questions:
        if q.question_type != QuestionType.essay:
            continue
        row = get_active_standard_row(db, q.id)
        if not row:
            missing.append(q.title)
            continue
        bindings.append(
            {
                "question_id": q.id,
                "title": q.title,
                "standard_id": row.id,
                "standard_version": row.version,
            }
        )
    if missing:
        raise ValueError("以下题目尚无已发布标准: " + "; ".join(missing[:8]))

    latest = (
        db.query(ExamStandard)
        .filter(ExamStandard.exam == exam, ExamStandard.year == year)
        .order_by(ExamStandard.version.desc())
        .first()
    )
    next_version = (latest.version + 1) if latest else 1

    for row in db.query(ExamStandard).filter(ExamStandard.exam == exam, ExamStandard.year == year).all():
        row.is_active = False
        if row.status == ExamStandardStatus.published:
            row.status = ExamStandardStatus.archived

    payload = {
        "exam": exam,
        "year": year,
        "essay_policy": {**DEFAULT_ESSAY_POLICY, **(essay_policy or {})},
        "document_refs": _collect_document_refs(db, questions),
        "question_standards": bindings,
        "question_count": len(bindings),
    }

    published = ExamStandard(
        exam=exam,
        year=year,
        version=next_version,
        status=ExamStandardStatus.published,
        is_active=True,
        payload=payload,
        published_at=datetime.now(UTC),
    )
    db.add(published)
    db.commit()
    db.refresh(published)
    return published


def get_active_exam_standard(db: Session, exam: str, year: int) -> ExamStandard | None:
    return (
        db.query(ExamStandard)
        .filter(
            ExamStandard.exam == exam.strip(),
            ExamStandard.year == year,
            ExamStandard.is_active.is_(True),
            ExamStandard.status == ExamStandardStatus.published,
        )
        .order_by(ExamStandard.version.desc())
        .first()
    )


def list_exam_standards(db: Session, limit: int = 50) -> list[ExamStandard]:
    return db.query(ExamStandard).order_by(ExamStandard.created_at.desc()).limit(limit).all()


def list_exam_year_groups(db: Session) -> list[tuple[str, int]]:
    groups: set[tuple[str, int]] = set()
    for q in bank_essay_questions(db).all():
        meta = q.material_structured or {}
        exam = meta.get("exam")
        year = meta.get("year")
        if exam and year is not None:
            groups.add((str(exam).strip(), int(year)))
    return sorted(groups, key=lambda x: (x[0], x[1]))


def publish_complete_exam_bundles(db: Session) -> list[ExamStandard]:
    """对「卷内每题均已发布题目标准」的 exam+year 自动发布考试级标准。"""
    out: list[ExamStandard] = []
    for exam, year in list_exam_year_groups(db):
        try:
            out.append(publish_exam_standard(db, exam=exam, year=year))
        except ValueError:
            continue
    return out
