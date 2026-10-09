"""教练闭环（P5）：从历次大作文报告中聚合能力、问题本，并生成二次作答对比。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.domain.essay import ABILITY_DIMENSIONS, ESSAY_ISSUE_TAGS, label_to_ability
from app.models.entities import GradingJob, GradingJobStatus, Question, Report, Submission

# 严重程度序：用于判断「问题是否改善」（PRD §7.11）
_SEVERITY_RANK = {"severe": 3, "moderate": 2, "minor": 1}


def _normalize_issue_tag(raw: str | None) -> str:
    """从「Q21 立意偏差」提取稳定键 Q21，便于跨报告聚合。"""
    if not raw:
        return ""
    token = raw.strip().split()[0]
    return token.upper() if token else raw.strip()


def _dimension_hit_rate(payload: dict[str, Any]) -> float:
    """维度「命中率」= 全命中 + 半命中维度数 / 总维度数。"""
    points = payload.get("scoring_points") or []
    if not points:
        return 0.0
    hits = sum(1 for p in points if p.get("hit") in ("full", "partial"))
    return round(hits / len(points) * 100, 1)


def _issues_by_tag(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in payload.get("issues") or []:
        key = _normalize_issue_tag(item.get("tag"))
        if key:
            out[key] = item
    return out


def build_retry_comparison(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """
    二次批改对比（BE-502）：分数差、维度命中率差、问题标签迁移。
    写入第二次报告 payload.comparison，供 FE-502 展示。
    """
    s1 = float(first.get("total_score") or 0)
    s2 = float(second.get("total_score") or 0)
    r1 = _dimension_hit_rate(first)
    r2 = _dimension_hit_rate(second)

    first_issues = _issues_by_tag(first)
    second_issues = _issues_by_tag(second)
    all_tags = set(first_issues) | set(second_issues)

    issue_changes: list[dict[str, Any]] = []
    for tag in sorted(all_tags):
        before = first_issues.get(tag)
        after = second_issues.get(tag)
        if before and not after:
            status = "resolved"
        elif not before and after:
            status = "new"
        elif before and after:
            b_rank = _SEVERITY_RANK.get(str(before.get("severity")), 2)
            a_rank = _SEVERITY_RANK.get(str(after.get("severity")), 2)
            if a_rank < b_rank:
                status = "improved"
            elif a_rank > b_rank:
                status = "worse"
            else:
                status = "unchanged"
        else:
            continue
        issue_changes.append(
            {
                "tag": tag,
                "label": (after or before or {}).get("tag") or tag,
                "before_severity": (before or {}).get("severity"),
                "after_severity": (after or {}).get("severity"),
                "status": status,
            }
        )

    return {
        "first_score": s1,
        "second_score": s2,
        "score_delta": round(s2 - s1, 1),
        "first_hit_rate": r1,
        "second_hit_rate": r2,
        "hit_rate_delta": round(r2 - r1, 1),
        "issue_changes": issue_changes,
    }


def find_report_for_submission(db: Session, submission_id: str) -> Report | None:
    """通过 submission 找到最近一次成功批改的报告。"""
    job = (
        db.query(GradingJob)
        .filter(
            GradingJob.submission_id == submission_id,
            GradingJob.status == GradingJobStatus.succeeded,
        )
        .order_by(GradingJob.finished_at.desc())
        .first()
    )
    if not job:
        return None
    return db.query(Report).filter(Report.grading_job_id == job.id).first()


def compute_abilities(db: Session, user_id: str, limit: int = 20) -> dict[str, Any]:
    """
    大作文五维能力（BE-503）：近 N 篇报告维度均分 → 0～100 展示分。
    低置信报告仍计入，但 overall 附带 data_confidence 提示。
    """
    reports = (
        db.query(Report)
        .filter(Report.user_id == user_id)
        .order_by(Report.created_at.desc())
        .limit(limit)
        .all()
    )
    # ability_id -> list of percent scores
    buckets: dict[str, list[float]] = defaultdict(list)
    low_conf_count = 0

    for rep in reports:
        payload = rep.payload or {}
        if payload.get("confidence") == "low":
            low_conf_count += 1
        for point in payload.get("scoring_points") or []:
            ability = point.get("ability") or label_to_ability(point.get("label", ""))
            mx = float(point.get("max") or 10)
            earned = float(point.get("earned") or 0)
            if mx <= 0:
                continue
            buckets[ability].append(earned / mx * 100)

    dimensions: list[dict[str, Any]] = []
    for meta in ABILITY_DIMENSIONS:
        aid = meta["id"]
        scores = buckets.get(aid, [])
        avg = round(sum(scores) / len(scores), 1) if scores else None
        dimensions.append({"id": aid, "name": meta["name"], "score": avg, "sample_count": len(scores)})

    scored = [d for d in dimensions if d["score"] is not None]
    overall = round(sum(d["score"] for d in scored) / len(scored), 1) if scored else None
    data_confidence = "high"
    if not reports:
        data_confidence = "none"
    elif low_conf_count > len(reports) / 2:
        data_confidence = "low"
    elif low_conf_count > 0:
        data_confidence = "medium"

    return {
        "overall": overall,
        "dimensions": dimensions,
        "report_count": len(reports),
        "data_confidence": data_confidence,
    }


def aggregate_issue_book(db: Session, user_id: str, limit: int = 80) -> list[dict[str, Any]]:
    """问题本（BE-504）：按标签聚合出现次数、严重程度与关联报告列表。"""
    reports = (
        db.query(Report)
        .filter(Report.user_id == user_id)
        .order_by(Report.created_at.desc())
        .limit(limit)
        .all()
    )
    stats: dict[str, dict[str, Any]] = {}
    for rep in reports:
        payload = rep.payload or {}
        for item in payload.get("issues") or []:
            key = _normalize_issue_tag(item.get("tag"))
            if not key:
                continue
            row = stats.setdefault(
                key,
                {
                    "tag": key,
                    "label": item.get("tag") or key,
                    "count": 0,
                    "last_severity": None,
                    "last_report_id": rep.id,
                    "reports": [],
                },
            )
            row["count"] += 1
            row["last_severity"] = item.get("severity") or row["last_severity"]
            row["label"] = item.get("tag") or row["label"]
            row["reports"].append(
                {
                    "report_id": rep.id,
                    "created_at": rep.created_at.isoformat() if rep.created_at else "",
                    "total_score": payload.get("total_score"),
                    "severity": item.get("severity"),
                }
            )

    ordered = sorted(stats.values(), key=lambda x: x["count"], reverse=True)
    return ordered


def build_home_summary(db: Session, user_id: str) -> dict[str, Any]:
    """首页聚合（BE-507）：能力概览 + 当前重点问题 + 训练推荐占位。"""
    abilities = compute_abilities(db, user_id)
    issues = aggregate_issue_book(db, user_id)
    focus = issues[0] if issues else None

    # 训练推荐（BE-505 简版）：最低能力维 + 最高频问题
    weakest = None
    for dim in abilities["dimensions"]:
        if dim["score"] is not None and (weakest is None or dim["score"] < weakest["score"]):
            weakest = dim

    training_title = "大作文专项"
    training_reason = "完成更多批改后，系统将推荐针对性训练。"
    if weakest and focus:
        training_title = f"{weakest['name']} · 基础巩固"
        training_reason = (
            f"「{focus['label']}」近 {focus['count']} 次报告出现；"
            f"建议优先练 {weakest['name']}（当前约 {weakest['score']} 分）。"
        )
    elif weakest:
        training_title = f"{weakest['name']} · 基础巩固"
        training_reason = f"当前短板维度：{weakest['name']}（约 {weakest['score']} 分）。"

    recent = (
        db.query(Report)
        .filter(Report.user_id == user_id)
        .order_by(Report.created_at.desc())
        .limit(3)
        .all()
    )
    recent_items = [
        {
            "id": r.id,
            "total_score": (r.payload or {}).get("total_score"),
            "confidence": (r.payload or {}).get("confidence"),
            "created_at": r.created_at.isoformat(),
        }
        for r in recent
    ]

    from app.services.training_service import count_today_completed, suggest_level

    return {
        "abilities": abilities,
        "focus_issue": focus,
        "today_training": {
            "title": training_title,
            "reason": training_reason,
            "level": (
                suggest_level(weakest["score"] if weakest else None).value if weakest else "L1"
            ),
            "progress_done": count_today_completed(db, user_id),
            "progress_target": 3,
        },
        "recent_reports": recent_items,
    }


def get_retry_context(db: Session, user_id: str, report_id: str) -> dict[str, Any]:
    """二次作答页上下文（FE-501）：首次正文 + 题目 + 待改进问题。"""
    report = db.get(Report, report_id)
    if not report or report.user_id != user_id:
        raise ValueError("REPORT_NOT_FOUND")
    job = db.get(GradingJob, report.grading_job_id)
    if not job:
        raise ValueError("JOB_NOT_FOUND")
    submission = db.get(Submission, job.submission_id)
    if not submission:
        raise ValueError("SUBMISSION_NOT_FOUND")
    question = db.get(Question, submission.question_id)
    payload = report.payload or {}
    custom = bool((submission.user_prompt or "").strip())
    prompt = (submission.user_prompt or (question.prompt if question else "") or "").strip()
    material = submission.user_material if submission.user_material is not None else (question.material if question else None)
    title = "用户自备题目" if custom else (question.title if question else "")
    return {
        "report_id": report.id,
        "question_id": submission.question_id,
        "question_title": title,
        "prompt": prompt,
        "reference_material": material,
        "first_content": submission.content,
        "first_score": payload.get("total_score"),
        "issues": payload.get("issues") or [],
        "suggestions": payload.get("suggestions") or [],
        "attempt_next": submission.attempt + 1,
    }
