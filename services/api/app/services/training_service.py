"""训练推荐与记录（BE-506）：L1～L3 难度与 PRD §12 简化升级规则。"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.domain.essay import ABILITY_DIMENSIONS
from app.models.entities import (
    TrainingKind,
    TrainingLevel,
    TrainingRecord,
    TrainingRecordStatus,
)
from app.services.coach_service import aggregate_issue_book, compute_abilities

# 能力分 → 推荐难度（V1 简版：低分从 L1 练起）
_LEVEL_BY_SCORE = (
    (60, TrainingLevel.L1),
    (80, TrainingLevel.L2),
    (101, TrainingLevel.L3),
)


def suggest_level(ability_score: float | None) -> TrainingLevel:
    if ability_score is None:
        return TrainingLevel.L1
    for threshold, level in _LEVEL_BY_SCORE:
        if ability_score < threshold:
            return level
    return TrainingLevel.L3


def _level_after_completion(recent_hit_rates: list[float]) -> TrainingLevel | None:
    """
    PRD §12 升级简版：连续 2 次完成且命中率 ≥80% → 升一级；<60% → 降一级。
    返回建议的下一任务难度（供前端展示，不自动改历史记录）。
    """
    if len(recent_hit_rates) < 2:
        return None
    last_two = recent_hit_rates[-2:]
    if all(r >= 80 for r in last_two):
        return TrainingLevel.L2  # 示意：实际应相对当前 level +1
    if all(r < 60 for r in last_two):
        return TrainingLevel.L1
    return None


def _today_window() -> datetime:
    """UTC 日界；V1 不做时区个性化。"""
    now = datetime.now(UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def count_today_completed(db: Session, user_id: str) -> int:
    start = _today_window()
    return (
        db.query(TrainingRecord)
        .filter(
            TrainingRecord.user_id == user_id,
            TrainingRecord.kind == TrainingKind.today,
            TrainingRecord.status == TrainingRecordStatus.completed,
            TrainingRecord.completed_at >= start,
        )
        .count()
    )


def build_training_plan(db: Session, user_id: str) -> dict[str, Any]:
    """生成今日/专项推荐任务（可不落库，开始训练时再 POST record）。"""
    abilities = compute_abilities(db, user_id)
    issues = aggregate_issue_book(db, user_id)
    weakest = None
    for dim in abilities["dimensions"]:
        if dim["score"] is not None and (weakest is None or dim["score"] < weakest["score"]):
            weakest = dim

    w_level = suggest_level(weakest["score"] if weakest else None)
    focus = issues[0] if issues else None

    today_tasks: list[dict[str, Any]] = [
        {
            "task_key": "today-essay-1",
            "kind": "today",
            "title": "大作文完整写作 · 1 篇",
            "level": w_level.value,
            "ability_id": weakest["id"] if weakest else "A1",
            "ability_name": weakest["name"] if weakest else "立意与审题",
            "instructions": "在「批改」页上传或粘贴你的题干、材料与作文全文后提交 AI 批改。",
            "question_id": None,
            "estimated_minutes": 45,
        },
    ]
    if focus:
        today_tasks.append(
            {
                "task_key": f"today-issue-{focus['tag']}",
                "kind": "today",
                "title": f"针对「{focus['label']}」重写一段",
                "level": w_level.value,
                "ability_id": weakest["id"] if weakest else "A2",
                "focus_tag": focus["tag"],
                "instructions": "用同一套题干材料，只重写分论点段落约 300 字，再合并进全文重新批改。",
                "question_id": None,
                "estimated_minutes": 20,
            }
        )

    special_tasks: list[dict[str, Any]] = []
    for dim in abilities["dimensions"]:
        if dim["score"] is None:
            continue
        lv = suggest_level(dim["score"])
        special_tasks.append(
            {
                "task_key": f"special-{dim['id']}",
                "kind": "special",
                "title": f"{dim['name']} · {'基础' if lv == TrainingLevel.L1 else '提高' if lv == TrainingLevel.L2 else '综合'}",
                "level": lv.value,
                "ability_id": dim["id"],
                "ability_name": dim["name"],
                "instructions": f"专项练 {dim['name']}，自备题干与作文完成 1 次批改。",
                "question_id": None,
                "estimated_minutes": 40,
            }
        )

    records = (
        db.query(TrainingRecord)
        .filter(TrainingRecord.user_id == user_id)
        .order_by(TrainingRecord.created_at.desc())
        .limit(50)
        .all()
    )
    record_items = [_record_to_dict(r) for r in records]

    done_today = count_today_completed(db, user_id)
    return {
        "today_tasks": today_tasks,
        "special_tasks": special_tasks,
        "today_progress": {"done": done_today, "target": 3},
        "records": record_items,
    }


def _record_to_dict(r: TrainingRecord) -> dict[str, Any]:
    return {
        "id": r.id,
        "kind": r.kind.value,
        "title": r.title,
        "ability_id": r.ability_id,
        "level": r.level.value,
        "focus_tag": r.focus_tag,
        "status": r.status.value,
        "instructions": r.instructions,
        "result_note": r.result_note,
        "linked_report_id": r.linked_report_id,
        "question_id": r.question_id,
        "created_at": r.created_at.isoformat(),
        "completed_at": r.completed_at.isoformat() if r.completed_at else None,
    }


def start_training_record(db: Session, user_id: str, body: dict[str, Any]) -> TrainingRecord:
    """开始一项训练：写入 pending 记录。"""
    level = TrainingLevel(body.get("level", "L1"))
    kind = TrainingKind(body["kind"])
    row = TrainingRecord(
        user_id=user_id,
        kind=kind,
        title=body["title"],
        ability_id=body.get("ability_id"),
        level=level,
        focus_tag=body.get("focus_tag"),
        instructions=body.get("instructions"),
        question_id=body.get("question_id"),
        status=TrainingRecordStatus.pending,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def complete_training_record(
    db: Session,
    user_id: str,
    record_id: str,
    result_note: str | None,
    linked_report_id: str | None,
) -> TrainingRecord:
    row = db.get(TrainingRecord, record_id)
    if not row or row.user_id != user_id:
        raise ValueError("NOT_FOUND")
    row.status = TrainingRecordStatus.completed
    row.result_note = result_note
    row.linked_report_id = linked_report_id
    row.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return row


def skip_training_record(db: Session, user_id: str, record_id: str) -> TrainingRecord:
    row = db.get(TrainingRecord, record_id)
    if not row or row.user_id != user_id:
        raise ValueError("NOT_FOUND")
    row.status = TrainingRecordStatus.skipped
    row.completed_at = datetime.now(UTC)
    db.commit()
    db.refresh(row)
    return row


def build_me_summary(db: Session, user_id: str, email: str) -> dict[str, Any]:
    """「我的」页（FE-507）：学习统计 + BYOK 用量 + 争议占位。"""
    from app.models.entities import Report, UserAiUsage

    report_count = db.query(Report).filter(Report.user_id == user_id).count()
    training_done = (
        db.query(TrainingRecord)
        .filter(TrainingRecord.user_id == user_id, TrainingRecord.status == TrainingRecordStatus.completed)
        .count()
    )
    usage_rows = db.query(UserAiUsage).filter(UserAiUsage.user_id == user_id).all()
    tokens_in = sum(u.tokens_in or 0 for u in usage_rows)
    tokens_out = sum(u.tokens_out or 0 for u in usage_rows)
    grading_calls = len(usage_rows)

    return {
        "email": email,
        "stats": {
            "report_count": report_count,
            "training_completed": training_done,
            "ai_calls": grading_calls,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
        },
        "dispute": {
            "enabled": False,
            "message": "评分争议入口（P6）即将开放，可先通过客服邮箱反馈。",
        },
        "ability_labels": [d["name"] for d in ABILITY_DIMENSIONS],
    }
