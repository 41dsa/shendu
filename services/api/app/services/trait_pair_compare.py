"""PRD W-04：Trait 成对比较弱标签任务。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.entities import TraitPairCompareStatus, TraitPairCompareTask, WeakLabel, WeakLabelType


def create_pair_compare_task(
    db: Session,
    *,
    question_id: str,
    submission_a_id: str,
    submission_b_id: str,
    trait_id: str | None = None,
) -> TraitPairCompareTask:
    if submission_a_id == submission_b_id:
        raise ValueError("submissions must differ")
    row = TraitPairCompareTask(
        question_id=question_id,
        submission_a_id=submission_a_id,
        submission_b_id=submission_b_id,
        trait_id=trait_id,
        status=TraitPairCompareStatus.pending,
    )
    db.add(row)
    db.flush()
    return row


def complete_pair_compare(
    db: Session,
    task_id: str,
    *,
    preferred_submission_id: str,
    trait_id: str | None,
    note: str = "",
) -> TraitPairCompareTask:
    task = db.get(TraitPairCompareTask, task_id)
    if not task or task.status != TraitPairCompareStatus.pending:
        raise ValueError("task not found or not pending")
    if preferred_submission_id not in (task.submission_a_id, task.submission_b_id):
        raise ValueError("preferred_submission_id must be a or b")
    task.status = TraitPairCompareStatus.completed
    task.result = {
        "preferred_submission_id": preferred_submission_id,
        "trait_id": trait_id or task.trait_id,
        "note": note[:500],
    }
    db.add(
        WeakLabel(
            question_id=task.question_id,
            submission_id=preferred_submission_id,
            label_type=WeakLabelType.pair_compare,
            trait_id=trait_id or task.trait_id,
            label_value="preferred",
            is_weak_label=True,
            payload={
                "task_id": task.id,
                "submission_a_id": task.submission_a_id,
                "submission_b_id": task.submission_b_id,
                "preferred_submission_id": preferred_submission_id,
                "note": note[:500],
            },
        )
    )
    db.flush()
    return task
