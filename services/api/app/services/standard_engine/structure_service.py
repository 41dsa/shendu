"""M3 大作文题结构化与 Question 关联。"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import Question, QuestionType, StandardDocument
from app.schemas.standard_engine import EssayQuestionSchema
from app.services.standard_engine.stub_generate import question_to_essay_schema

DOCUMENT_REFS_KEY = "standard_document_ids"


def get_linked_document_ids(question: Question) -> list[str]:
    meta = question.material_structured or {}
    refs = meta.get(DOCUMENT_REFS_KEY) or []
    return [str(x) for x in refs if x]


def link_documents_to_question(db: Session, question_id: str, document_ids: list[str]) -> Question:
    question = db.get(Question, question_id)
    if not question:
        raise ValueError("题目不存在")
    if question.question_type != QuestionType.essay:
        raise ValueError("仅支持大作文题目")
    for doc_id in document_ids:
        if not db.get(StandardDocument, doc_id):
            raise ValueError(f"资料不存在: {doc_id}")
    meta = dict(question.material_structured or {})
    meta[DOCUMENT_REFS_KEY] = document_ids
    question.material_structured = meta
    db.commit()
    db.refresh(question)
    return question


def build_structured_essay(db: Session, question: Question) -> EssayQuestionSchema:
    essay = question_to_essay_schema(question)
    doc_ids = get_linked_document_ids(question)
    essay.document_refs = doc_ids
    if doc_ids and not essay.material_optional.strip():
        parts: list[str] = []
        for doc_id in doc_ids[:3]:
            doc = db.get(StandardDocument, doc_id)
            if doc and doc.content:
                parts.append(doc.content[:1500])
        if parts:
            essay.material_optional = "\n\n".join(parts)[:8000]
    meta = question.material_structured or {}
    essay.exam = str(meta.get("exam") or essay.exam)
    essay.year = meta.get("year") if meta.get("year") is not None else essay.year
    return essay


def upsert_question_from_row(db: Session, row: dict[str, Any]) -> Question:
    """从 CSV/导入行创建或更新 Question（按 title+exam+year 匹配）。"""
    exam = str(row.get("exam") or "").strip()
    year_raw = row.get("year")
    year: int | None
    if year_raw is None or str(year_raw).strip() == "":
        year = None
    else:
        year = int(year_raw)
    title = str(row.get("title") or "").strip()
    if not title or not str(row.get("prompt") or "").strip():
        raise ValueError("title 与 prompt 必填")

    existing = (
        db.query(Question)
        .filter(Question.title == title)
        .all()
    )
    question = None
    for q in existing:
        meta = q.material_structured or {}
        if meta.get("exam") == exam and meta.get("year") == year:
            question = q
            break

    word_min = int(row.get("word_min") or 800)
    word_max = int(row.get("word_max") or row.get("word_limit") or 1200)
    material_structured: dict[str, Any] = {
        "genre": "essay",
        "word_min": word_min,
        "word_max": word_max,
        "exam": exam,
        "year": year,
    }
    doc_ids = row.get("document_ids") or row.get("standard_document_ids")
    if doc_ids:
        if isinstance(doc_ids, str):
            doc_ids = [x.strip() for x in doc_ids.split(",") if x.strip()]
        material_structured[DOCUMENT_REFS_KEY] = doc_ids

    if question:
        question.prompt = str(row.get("prompt") or "")
        question.material = row.get("material") or question.material
        question.score = int(row.get("score") or 40)
        question.word_limit = word_max
        question.material_structured = material_structured
        question.published = bool(row.get("published", True))
    else:
        question = Question(
            title=title,
            question_type=QuestionType.essay,
            prompt=str(row.get("prompt") or ""),
            material=row.get("material") or "",
            score=int(row.get("score") or 40),
            word_limit=word_max,
            material_structured=material_structured,
            published=bool(row.get("published", True)),
        )
        db.add(question)
    db.commit()
    db.refresh(question)
    return question
