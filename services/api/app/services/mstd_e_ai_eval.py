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
    essay_published = bank_essay_questions(db).count()
    ai_gold_count = db.query(GoldSample).filter(GoldSample.note.like("%auto:ai_gold%")).count()

    self_consistency_ok = False
    if metrics:
        tm = metrics.get("targets_met") or {}
        self_consistency_ok = all(
            tm.get(k, False)
            for k in ("form_match_rate", "task_match_rate", "keyword_recall_rate")
            if metrics.get(k) is not None
        )

    checks = {
        "published_standard_questions_gte_5": published_std_count >= 5,
        "self_consistency_metrics": self_consistency_ok,
        "ai_gold_samples_gte_3": ai_gold_count >= 3,
    }
    return {
        "essay_questions_published": essay_published,
        "published_standard_questions": published_std_count,
        "ai_gold_samples": ai_gold_count,
        "metrics_targets": METRIC_TARGETS,
        "metrics": metrics,
        "checks": checks,
        "milestone_mstd_e_ai_passed": all(checks.values()),
    }
