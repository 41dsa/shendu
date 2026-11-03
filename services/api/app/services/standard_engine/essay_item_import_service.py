"""Q-01/Q-03：EssayItem 统一导入、A 类字段锁定与审计。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.orm import Session

from app.models.entities import EssayImportAudit, Question, QuestionType
from app.schemas.essay_item_v1 import ESSAY_ITEM_A_CLASS_FIELDS, EssayItemV1Schema
from app.services.standard_engine.structure_service import DOCUMENT_REFS_KEY

ESSAY_ITEM_V1_KEY = "essay_item_v1"
ESSAY_ITEM_LOCKED_KEY = "essay_item_v1_locked"
ESSAY_ITEM_IMPORTED_AT_KEY = "essay_item_v1_imported_at"


@dataclass
class EssayItemImportLineResult:
    question_id: str
    action: Literal["created", "updated", "skipped_locked", "unchanged"]
    note: str = ""


@dataclass
class EssayItemImportResult:
    source: str
    filename: str | None
    item_count: int
    created_count: int = 0
    updated_count: int = 0
    skipped_locked_count: int = 0
    lines: list[EssayItemImportLineResult] = field(default_factory=list)


def row_to_essay_item(row: dict[str, Any], *, source: str = "csv") -> EssayItemV1Schema:
    exam = str(row.get("exam") or "").strip()
    year_raw = row.get("year")
    year: int | None
    if year_raw is None or str(year_raw).strip() == "":
        year = None
    else:
        year = int(year_raw)
    qno_raw = row.get("question_no")
    question_no: int | None = None
    if qno_raw is not None and str(qno_raw).strip() != "":
        question_no = int(qno_raw)
    title = str(row.get("title") or "").strip()
    prompt = str(row.get("prompt") or "").strip()
    if not title or not prompt:
        raise ValueError("title 与 prompt 必填")
    word_min = int(row.get("word_min") or 800)
    word_max = int(row.get("word_max") or row.get("word_limit") or 1200)
    doc_ids = row.get("document_ids") or row.get("standard_document_ids")
    document_ids: list[str] = []
    if doc_ids:
        if isinstance(doc_ids, str):
            document_ids = [x.strip() for x in doc_ids.split(",") if x.strip()]
        else:
            document_ids = [str(x).strip() for x in doc_ids if str(x).strip()]
    return EssayItemV1Schema(
        exam=exam,
        year=year,
        question_no=question_no,
        title=title,
        prompt=prompt,
        material=str(row.get("material") or ""),
        exam_instructions=str(row.get("exam_instructions") or row.get("requirements") or ""),
        word_min=word_min,
        word_max=word_max,
        score=int(row.get("score") or 40),
        document_ids=document_ids,
        published=bool(row.get("published", True)),
        source=source,
    )


def _find_question(db: Session, item: EssayItemV1Schema) -> Question | None:
    existing = db.query(Question).filter(Question.title == item.title).all()
    for q in existing:
        meta = q.material_structured or {}
        if meta.get("exam") == item.exam and meta.get("year") == item.year:
            if item.question_no is not None and meta.get("question_no") != item.question_no:
                continue
            return q
    return None


def _stored_a_class(question: Question) -> dict[str, Any] | None:
    meta = question.material_structured or {}
    raw = meta.get(ESSAY_ITEM_V1_KEY)
    if isinstance(raw, dict):
        return raw
    return None


def is_essay_item_locked(question: Question) -> bool:
    meta = question.material_structured or {}
    return bool(meta.get(ESSAY_ITEM_LOCKED_KEY))


def locked_field_violations(question: Question, patch: dict[str, Any]) -> list[str]:
    """Admin 更新时检测是否篡改 A 类字段。"""
    if not is_essay_item_locked(question):
        return []
    stored = _stored_a_class(question) or {}
    violations: list[str] = []
    if "title" in patch and str(patch["title"]) != str(stored.get("title") or question.title):
        violations.append("title")
    if "prompt" in patch and str(patch["prompt"]) != str(stored.get("prompt") or question.prompt):
        violations.append("prompt")
    if "material" in patch and str(patch.get("material") or "") != str(stored.get("material") or question.material or ""):
        violations.append("material")
    if "score" in patch and int(patch["score"]) != int(stored.get("score") or question.score):
        violations.append("score")
    ms = patch.get("material_structured")
    if isinstance(ms, dict):
        for key in ("exam", "year", "question_no", "word_min", "word_max"):
            if key in ms and stored.get(key) is not None and ms.get(key) != stored.get(key):
                violations.append(key)
    return violations


def _apply_item(
    question: Question,
    item: EssayItemV1Schema,
    *,
    lock_a_fields: bool,
    respect_existing_lock: bool,
) -> Literal["updated", "skipped_locked", "unchanged"]:
    locked = respect_existing_lock and is_essay_item_locked(question)
    stored = _stored_a_class(question) or {}

    if locked:
        snap = item.a_class_snapshot()
        changed = any(str(stored.get(k, "")) != str(snap.get(k, "")) for k in ESSAY_ITEM_A_CLASS_FIELDS if k in snap)
        if changed:
            return "skipped_locked"
        return "unchanged"

    question.title = item.title
    question.prompt = item.prompt
    question.material = item.material
    question.score = item.score
    question.word_limit = item.word_max
    question.published = item.published

    meta = dict(question.material_structured or {})
    meta.update(
        {
            "genre": "essay",
            "word_min": item.word_min,
            "word_max": item.word_max,
            "exam": item.exam,
            "year": item.year,
            "question_no": item.question_no,
            "exam_instructions": item.exam_instructions,
        }
    )
    if item.document_ids:
        meta[DOCUMENT_REFS_KEY] = item.document_ids
    meta[ESSAY_ITEM_V1_KEY] = item.a_class_snapshot()
    if lock_a_fields:
        meta[ESSAY_ITEM_LOCKED_KEY] = True
    meta[ESSAY_ITEM_IMPORTED_AT_KEY] = meta.get(ESSAY_ITEM_IMPORTED_AT_KEY) or datetime.now(UTC).isoformat()
    question.material_structured = meta
    return "updated"


def import_essay_items(
    db: Session,
    rows: list[dict[str, Any]],
    *,
    source: str = "csv",
    filename: str | None = None,
    admin_user_id: str | None = None,
    lock_a_fields: bool = True,
) -> EssayItemImportResult:
    result = EssayItemImportResult(source=source, filename=filename, item_count=len(rows))
    for row in rows:
        item = row_to_essay_item(row, source=source)
        question = _find_question(db, item)
        if question is None:
            question = Question(
                title=item.title,
                question_type=QuestionType.essay,
                prompt=item.prompt,
                material=item.material,
                score=item.score,
                word_limit=item.word_max,
                material_structured={},
                published=item.published,
            )
            db.add(question)
            db.flush()
            action = _apply_item(question, item, lock_a_fields=lock_a_fields, respect_existing_lock=False)
            result.created_count += 1
            result.lines.append(
                EssayItemImportLineResult(question_id=question.id, action="created", note=action)
            )
        else:
            action = _apply_item(question, item, lock_a_fields=lock_a_fields, respect_existing_lock=True)
            if action == "skipped_locked":
                result.skipped_locked_count += 1
            elif action == "updated":
                result.updated_count += 1
            else:
                pass
            result.lines.append(
                EssayItemImportLineResult(question_id=question.id, action=action, note="")
            )
    audit = EssayImportAudit(
        source=source,
        filename=filename,
        imported_by_user_id=admin_user_id,
        item_count=result.item_count,
        created_count=result.created_count,
        updated_count=result.updated_count,
        skipped_locked_count=result.skipped_locked_count,
        items=[{"question_id": ln.question_id, "action": ln.action, "note": ln.note} for ln in result.lines],
    )
    db.add(audit)
    db.commit()
    return result


def import_essay_items_from_json_document(
    db: Session,
    doc: dict[str, Any],
    *,
    admin_user_id: str | None = None,
    lock_a_fields: bool = True,
) -> EssayItemImportResult:
    items_raw = doc.get("items") or doc.get("questions") or []
    if not isinstance(items_raw, list):
        raise ValueError("JSON 需包含 items 数组")
    rows = [x for x in items_raw if isinstance(x, dict)]
    return import_essay_items(
        db,
        rows,
        source=str(doc.get("source") or "json"),
        filename=str(doc.get("filename") or "") or None,
        admin_user_id=admin_user_id,
        lock_a_fields=lock_a_fields if doc.get("lock_a_fields", True) else False,
    )
