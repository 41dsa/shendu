"""M-STD-E-AI 里程碑判定（纯 AI，无人工）。"""

from typing import Any

from sqlalchemy.orm import Session

from app.models.entities import ExamQuestionStandard, ExamQuestionStandardStatus, GoldSample
from app.services.standard_engine.bank_questions import bank_essay_questions
from app.services.standard_engine.metrics_eval import METRIC_TARGETS, evaluate_annotation_csv
from app.services.standard_engine.annotation_bootstrap import default_annotation_path


def evaluate_mstd_e_ai_milestone(db: Session) -> dict[str, Any]:
    ann = default_annotation_path()
    metrics = evaluate_annotation_csv(db, ann) if ann.is_file() else None
    published_std_count = (
        db.query(ExamQuestionStandard.question_id)
        .filter(ExamQuestionStandard.status == ExamQuestionStandardStatus.published)
        .distinct()
        .count()
    )
    bank_qs = bank_essay_questions(db).all()
    essay_published = len(bank_qs)
    active_standard_qids = {
        row.question_id
        for row in db.query(ExamQuestionStandard)
        .filter(
            ExamQuestionStandard.status == ExamQuestionStandardStatus.published,
            ExamQuestionStandard.is_active.is_(True),
        )
        .all()
    }
    bank_with_active = sum(1 for q in bank_qs if q.id in active_standard_qids)
    bank_coverage = (bank_with_active / essay_published) if essay_published else 0.0
    ai_gold_count = db.query(GoldSample).filter(GoldSample.note.like("%auto:ai_gold%")).count()

    self_consistency_ok = False
    if metrics:
        tm = metrics.get("targets_met") or {}
        self_consistency_ok = all(
            tm.get(k, False)
            for k in ("form_match_rate", "task_match_rate", "keyword_recall_rate")
            if metrics.get(k) is not None
        )

    coverage_target = 0.85 if essay_published >= 20 else 0.5
    cohort_size = int(metrics.get("rows_evaluated") or 0) if metrics else 0
    cohort_ok = cohort_size > 0 and bank_with_active >= int(cohort_size * 0.85)
    checks = {
        "published_standard_questions_gte_5": published_std_count >= 5,
        "bank_active_standard_coverage": bank_coverage >= coverage_target or cohort_ok,
        "self_consistency_metrics": self_consistency_ok,
        "ai_gold_samples_gte_3": ai_gold_count >= 3,
    }
    return {
        "essay_questions_published": essay_published,
        "bank_active_standard_count": bank_with_active,
        "bank_active_standard_coverage": round(bank_coverage, 4),
        "published_standard_questions": published_std_count,
        "ai_gold_samples": ai_gold_count,
        "metrics_targets": METRIC_TARGETS,
        "metrics": metrics,
        "checks": checks,
        "milestone_mstd_e_ai_passed": all(checks.values()),
    }
