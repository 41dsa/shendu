"""教研标注 CSV 与已生成标准对比（STD-704）。"""

import csv
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import StandardGenerationJob, StandardGenerationJobStatus, StandardJobStep

METRIC_TARGETS = {
    "form_match_rate": 0.95,
    "task_match_rate": 0.90,
    "keyword_recall_rate": 0.90,
}


def latest_job_payload(db: Session, question_id: str, step: str) -> dict[str, Any]:
    job = (
        db.query(StandardGenerationJob)
        .filter(
            StandardGenerationJob.question_id == question_id,
            StandardGenerationJob.status.in_(
                [
                    StandardGenerationJobStatus.validated,
                    StandardGenerationJobStatus.published,
                ]
            ),
        )
        .order_by(StandardGenerationJob.created_at.desc())
        .first()
    )
    if not job:
        return {}
    row = (
        db.query(StandardJobStep)
        .filter(StandardJobStep.job_id == job.id, StandardJobStep.step == step)
        .order_by(StandardJobStep.created_at.desc())
        .first()
    )
    return dict(row.payload) if row and row.payload else {}


def evaluate_annotation_csv(db: Session, path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(str(path))

    rows_evaluated = 0
    form_ok = 0
    task_ok = 0
    recall_hits = 0
    recall_total = 0
    per_question: list[dict[str, Any]] = []

    with path.open(encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            qid = (row.get("question_id") or "").strip()
            if not qid:
                continue
            rows_evaluated += 1
            q_std = latest_job_payload(db, qid, "question_std")
            rubric = latest_job_payload(db, qid, "rubric_merged")
            validation = latest_job_payload(db, qid, "validate")

            entry: dict[str, Any] = {
                "question_id": qid,
                "title": (row.get("title") or "").strip(),
                "has_job": bool(q_std),
            }
            if not q_std:
                entry["skip_reason"] = "无 validated/published job"
                per_question.append(entry)
                continue

            exp_form = (row.get("expected_essay_form") or "").strip()
            form_match = bool(exp_form and q_std.get("essay_form") == exp_form)
            if form_match:
                form_ok += 1
            entry["essay_form_match"] = form_match if exp_form else None

            exp_task = (row.get("expected_proposition_task") or "").strip()
            task_match = bool(exp_task and q_std.get("proposition_task") == exp_task)
            if task_match:
                task_ok += 1
            entry["proposition_task_match"] = task_match if exp_task else None

            keywords = [k.strip() for k in (row.get("core_criteria_keywords") or "").split("|") if k.strip()]
            criteria = rubric.get("criteria") or []
            blob = " ".join(
                str(c.get("core") or "") + " ".join(c.get("observable_signals") or []) for c in criteria
            )
            kw_hits = [kw for kw in keywords if kw in blob]
            recall_total += len(keywords)
            recall_hits += len(kw_hits)
            entry["keyword_recall"] = (
                round(len(kw_hits) / len(keywords), 4) if keywords else None
            )
            entry["keywords_missed"] = [kw for kw in keywords if kw not in blob]

            checks = {c.get("id"): c for c in (validation.get("checks") or []) if c.get("id")}
            dup = checks.get("duplicate_criteria") or {}
            entry["duplicate_rate"] = dup.get("duplicate_rate")
            entry["standard_confidence"] = validation.get("standard_confidence")
            per_question.append(entry)

    form_rate = form_ok / rows_evaluated if rows_evaluated else None
    task_rate = task_ok / rows_evaluated if rows_evaluated else None
    kw_rate = recall_hits / recall_total if recall_total else None

    return {
        "annotation_file": str(path),
        "rows_evaluated": rows_evaluated,
        "form_match_rate": round(form_rate, 4) if form_rate is not None else None,
        "form_match_count": form_ok,
        "task_match_rate": round(task_rate, 4) if task_rate is not None else None,
        "task_match_count": task_ok,
        "keyword_recall_rate": round(kw_rate, 4) if kw_rate is not None else None,
        "keyword_recall_hits": recall_hits,
        "keyword_recall_total": recall_total,
        "targets": METRIC_TARGETS,
        "targets_met": {
            "form_match_rate": form_rate is not None and form_rate >= METRIC_TARGETS["form_match_rate"],
            "task_match_rate": task_rate is not None and task_rate >= METRIC_TARGETS["task_match_rate"],
            "keyword_recall_rate": kw_rate is not None and kw_rate >= METRIC_TARGETS["keyword_recall_rate"],
        },
        "per_question": per_question,
    }
