"""纯 AI：从已生成标准反写标注 CSV（自洽基线，无需人工教研）。"""

import csv
import os
import re
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.entities import Question
from app.schemas.standard_engine import QuestionStandardSchema, RubricStandardSchema
from app.services.standard_engine.metrics_eval import latest_job_payload

ANNOTATION_FILENAME = "questions_for_labeling.csv"
FIELDNAMES = [
    "question_id",
    "title",
    "expected_essay_form",
    "expected_proposition_task",
    "core_criteria_keywords",
    "notes",
]
AUTO_NOTE = "auto:ai_self_consistency"


def ai_annotation_enabled() -> bool:
    return os.environ.get("STANDARD_AI_ANNOTATION", "1").lower() not in ("0", "false", "no")


def default_annotation_path() -> Path:
    return settings.standards_annotation_path / ANNOTATION_FILENAME


def _extract_keywords(rubric: dict[str, Any] | RubricStandardSchema, *, max_keywords: int = 6) -> list[str]:
    if isinstance(rubric, RubricStandardSchema):
        criteria = rubric.criteria
    else:
        criteria = rubric.get("criteria") or []
    keywords: list[str] = []
    seen: set[str] = set()
    for c in criteria:
        core = str(c.get("core") if isinstance(c, dict) else c.core or "").strip()
        if not core:
            continue
        chunk = re.sub(r"\s+", "", core)
        token = chunk[:8] if len(chunk) > 8 else chunk
        if token and token not in seen:
            seen.add(token)
            keywords.append(token)
        if len(keywords) >= max_keywords:
            break
    return keywords


def row_from_generated_standard(
    *,
    question_id: str,
    title: str,
    question_standard: dict[str, Any] | QuestionStandardSchema,
    rubric: dict[str, Any] | RubricStandardSchema,
) -> dict[str, str]:
    if isinstance(question_standard, QuestionStandardSchema):
        qd = question_standard.model_dump()
    else:
        qd = question_standard
    keywords = _extract_keywords(rubric)
    return {
        "question_id": question_id,
        "title": title,
        "expected_essay_form": str(qd.get("essay_form") or ""),
        "expected_proposition_task": str(qd.get("proposition_task") or ""),
        "core_criteria_keywords": "|".join(keywords),
        "notes": AUTO_NOTE,
    }


def load_annotation_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.is_file():
        return {}
    out: dict[str, dict[str, str]] = {}
    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            qid = (row.get("question_id") or "").strip()
            if qid:
                out[qid] = {k: (row.get(k) or "").strip() for k in FIELDNAMES}
    return out


def write_annotation_rows(path: Path, rows_by_id: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = sorted(rows_by_id.values(), key=lambda r: (r.get("title") or "", r.get("question_id") or ""))
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for row in ordered:
            w.writerow({k: row.get(k, "") for k in FIELDNAMES})


def merge_annotation_row(
    existing: dict[str, str] | None,
    generated: dict[str, str],
    *,
    overwrite: bool = False,
) -> dict[str, str]:
    """合并一行：默认仅填空；overwrite 时整行用 AI 生成（仍保留非 auto 的 notes 可选）。"""
    base = dict(existing) if existing else {k: "" for k in FIELDNAMES}
    if not base.get("question_id"):
        base["question_id"] = generated["question_id"]
    if not base.get("title"):
        base["title"] = generated["title"]
    for key in ("expected_essay_form", "expected_proposition_task", "core_criteria_keywords"):
        if overwrite or not (base.get(key) or "").strip():
            base[key] = generated.get(key, "")
    if overwrite or not (base.get("notes") or "").strip() or base.get("notes") == AUTO_NOTE:
        base["notes"] = generated.get("notes", AUTO_NOTE)
    return base


def upsert_annotation_row_file(generated: dict[str, str], *, overwrite: bool = False) -> Path:
    path = default_annotation_path()
    rows = load_annotation_rows(path)
    qid = generated["question_id"]
    rows[qid] = merge_annotation_row(rows.get(qid), generated, overwrite=overwrite)
    write_annotation_rows(path, rows)
    return path


def bootstrap_question_from_db(db: Session, question_id: str, *, overwrite: bool = False) -> bool:
    question = db.get(Question, question_id)
    if not question:
        return False
    q_std = latest_job_payload(db, question_id, "question_std")
    rubric = latest_job_payload(db, question_id, "rubric_merged")
    if not q_std or not rubric:
        return False
    generated = row_from_generated_standard(
        question_id=question_id,
        title=question.title,
        question_standard=q_std,
        rubric=rubric,
    )
    upsert_annotation_row_file(generated, overwrite=overwrite)
    return True


def sync_annotation_after_job(
    db: Session,
    *,
    question_id: str,
    question_standard: dict[str, Any],
    rubric: dict[str, Any],
    title: str,
) -> None:
    if not ai_annotation_enabled():
        return
    generated = row_from_generated_standard(
        question_id=question_id,
        title=title,
        question_standard=question_standard,
        rubric=rubric,
    )
    upsert_annotation_row_file(generated, overwrite=True)
