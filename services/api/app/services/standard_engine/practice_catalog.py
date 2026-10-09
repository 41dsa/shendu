"""学员端大作文练习目录（产品级：ExamProfile + 已发布标准）。"""

from typing import Any

from sqlalchemy.orm import Session

from app.domain.essay import USER_ESSAY_QUESTION_ID, essay_word_bounds
from app.domain.exam_catalog import resolve_bank_exam_label
from app.models.entities import ExamProfile, Question
from app.services.standard_engine.bank_questions import bank_essay_questions
from app.services.standard_engine.standard_store import get_active_standard_row


def _normalize_year(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    return int(value)


def profile_to_bank_exam(profile: ExamProfile | None) -> tuple[str | None, int | None]:
    """将用户考试目标映射到题库 `material_structured.exam` / year。"""
    if not profile:
        return None, None
    bank = resolve_bank_exam_label(
        exam_type=profile.exam_type or "",
        province=profile.province or "",
        job_category=profile.job_category or "",
    )
    return bank, profile.year


def question_matches_exam_filter(question: Question, exam: str | None, year: int | None) -> bool:
    meta = question.material_structured or {}
    q_exam = str(meta.get("exam") or "").strip()
    q_year = _normalize_year(meta.get("year"))
    if exam and q_exam != exam:
        return False
    if year is not None and q_year is not None and q_year != year:
        return False
    return True


def list_practice_questions(
    db: Session,
    *,
    exam: str | None = None,
    year: int | None = None,
    require_published_standard: bool = True,
    limit: int = 50,
) -> list[Question]:
    rows = bank_essay_questions(db).all()
    out: list[Question] = []
    for q in rows:
        if q.id == USER_ESSAY_QUESTION_ID:
            continue
        if require_published_standard and not get_active_standard_row(db, q.id):
            continue
        if exam or year is not None:
            if not question_matches_exam_filter(q, exam, year):
                continue
        out.append(q)
    out.sort(key=lambda q: (_normalize_year((q.material_structured or {}).get("year")) or 0, q.title), reverse=True)
    return out[: max(1, limit)]


def list_recommended_for_profile(
    db: Session,
    profile: ExamProfile | None,
    *,
    limit: int = 8,
) -> list[Question]:
    exam, year = profile_to_bank_exam(profile)
    primary = list_practice_questions(db, exam=exam, year=year, limit=limit)
    if len(primary) >= limit:
        return primary
    seen = {q.id for q in primary}
    fallback = list_practice_questions(db, exam=exam, year=None, limit=limit)
    for q in fallback:
        if q.id not in seen:
            primary.append(q)
            seen.add(q.id)
        if len(primary) >= limit:
            break
    if len(primary) >= limit:
        return primary[:limit]
    for q in list_practice_questions(db, exam=None, year=None, limit=limit):
        if q.id not in seen:
            primary.append(q)
        if len(primary) >= limit:
            break
    return primary[:limit]


def question_list_meta(question: Question) -> dict[str, Any]:
    meta = question.material_structured or {}
    lo, hi = essay_word_bounds(meta, question.word_limit)
    return {
        "exam": meta.get("exam") or "",
        "year": _normalize_year(meta.get("year")),
        "word_min": lo,
        "word_max": hi,
    }
