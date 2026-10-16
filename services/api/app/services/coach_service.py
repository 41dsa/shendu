"""教练闭环（P5）：从历次大作文报告中聚合能力、问题本，并生成二次作答对比。"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.domain.essay import (
    ABILITY_DIMENSIONS,
    ability_for_issue_code,
    official_essay_char_count,
    issue_label_for_code,
    issue_tag_from_core_problem,
    label_to_ability,
    normalize_issue_code,
)
from app.models.entities import GradingJob, GradingJobStatus, Question, Report, Submission

# 严重程度序：用于判断「问题是否改善」（PRD §7.11）
_SEVERITY_RANK = {"severe": 3, "moderate": 2, "minor": 1}

# 首稿档次 → 允许重新批改次数（四类 4 次、三类 3 次…）
_TIER_MAX_REGRADES: dict[str, int] = {
    "t1": 1,
    "t2": 2,
    "t3": 3,
    "t4": 4,
}


def tier_max_regrade_count(tier_id: str | None) -> int:
    tid = (tier_id or "t4").strip().lower()
    return _TIER_MAX_REGRADES.get(tid, 1)


def first_pass_tier_for_root(db: Session, root_id: str) -> dict[str, Any]:
    """首稿报告上的四档判定（用于重新批改次数上限）。"""
    from app.domain.requirement_scoring import score_tier_for_total

    root_report = find_report_for_submission(db, root_id)
    if not root_report or not isinstance(root_report.payload, dict):
        return score_tier_for_total(0, 40)
    payload = root_report.payload
    try:
        total = float(payload.get("total_score") or 0)
    except (TypeError, ValueError):
        total = 0.0
    try:
        max_score = float(
            payload.get("display_max_score") or payload.get("max_score") or 40,
        )
    except (TypeError, ValueError):
        max_score = 40.0
    return score_tier_for_total(total, max_score)


def max_essay_regrade_count(db: Session, root_id: str) -> int:
    tier = first_pass_tier_for_root(db, root_id)
    return tier_max_regrade_count(str(tier.get("tier_id") or "t4"))


def essay_regrade_limit_message(db: Session, root_id: str, regrade_count: int) -> str:
    tier = first_pass_tier_for_root(db, root_id)
    label = str(tier.get("label") or "四类文")
    max_n = max_essay_regrade_count(db, root_id)
    return f"首稿为{label}，最多可重新批改 {max_n} 次（已使用 {regrade_count} 次）。"


def essay_regrade_retry_meta(db: Session, user_id: str, submission: Submission) -> dict[str, Any]:
    root_id = essay_regrade_root_id(submission)
    used = count_essay_regrades(db, user_id, root_id)
    max_n = max_essay_regrade_count(db, root_id)
    tier = first_pass_tier_for_root(db, root_id)
    return {
        "retry_submit_allowed": used < max_n,
        "retry_max_count": max_n,
        "retry_used_count": used,
        "first_pass_tier_id": tier.get("tier_id"),
        "first_pass_tier_label": tier.get("label"),
        "retry_limit_message": None if used < max_n else essay_regrade_limit_message(db, root_id, used),
    }


def essay_regrade_root_id(submission: Submission) -> str:
    return submission.parent_submission_id or submission.id


def count_essay_regrades(db: Session, user_id: str, root_id: str) -> int:
    return (
        db.query(Submission)
        .filter(
            Submission.user_id == user_id,
            Submission.parent_submission_id == root_id,
        )
        .count()
    )


def essay_regrade_allowed(db: Session, user_id: str, submission: Submission) -> bool:
    meta = essay_regrade_retry_meta(db, user_id, submission)
    return bool(meta.get("retry_submit_allowed"))


def _normalize_issue_tag(raw: str | None) -> str:
    """从「Q21 立意偏差」提取稳定键 Q21；其它短 tag 保留首词便于聚合。"""
    code = normalize_issue_code(raw)
    if code:
        return code
    if not raw:
        return ""
    token = raw.strip().split()[0]
    return token.upper() if token else raw.strip()


_A5_SEVERITY_CAP: dict[str, float] = {
    "severe": 45.0,
    "moderate": 65.0,
    "minor": 85.0,
}


def _essay_char_count(db: Session, rep: Report, payload: dict[str, Any]) -> int | None:
    meta = payload.get("essay_meta") or {}
    stored = meta.get("essay_char_count")
    if stored is not None:
        return int(stored)
    job = db.get(GradingJob, rep.grading_job_id)
    if not job:
        return None
    sub = db.get(Submission, job.submission_id)
    if not sub or not sub.content:
        return None
    return official_essay_char_count(sub.content)


def _word_compliance_percent(db: Session, rep: Report, payload: dict[str, Any]) -> float | None:
    """
    规范与字数（A5）展示分：按建议区间 word_min～word_max 计分，而非「达到下限即满分」。
    """
    meta = payload.get("essay_meta") or {}
    word_min = int(meta.get("word_min") or 0)
    word_max = int(meta.get("word_max") or word_min or 1200)
    if word_min <= 0:
        return None
    if word_max < word_min:
        word_max = word_min

    n = _essay_char_count(db, rep, payload)
    if n is None:
        return None

    if n < word_min:
        return round(max(0.0, n / word_min * 72.0), 1)
    if n <= word_max:
        span = max(word_max - word_min, 1)
        return round(72.0 + (n - word_min) / span * 28.0, 1)
    over_ratio = (n - word_max) / max(word_max, 1)
    return round(max(55.0, 100.0 - over_ratio * 40.0), 1)


def _worst_q20_severity(payload: dict[str, Any]) -> str | None:
    worst_rank = 0
    worst: str | None = None
    for item in payload.get("issues") or []:
        if _normalize_issue_tag(item.get("tag")) != "Q20":
            continue
        sev = str(item.get("severity") or "moderate")
        rank = _SEVERITY_RANK.get(sev, 2)
        if rank >= worst_rank:
            worst_rank = rank
            worst = sev
    return worst


def _a5_score_for_report(db: Session, rep: Report, payload: dict[str, Any]) -> float | None:
    base = _word_compliance_percent(db, rep, payload)
    if base is None:
        return None
    sev = _worst_q20_severity(payload)
    if sev:
        cap = _A5_SEVERITY_CAP.get(sev, 65.0)
        base = min(base, cap)
    return round(base, 1)


def _collect_issue_stats(reports: list[Report]) -> dict[str, dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = {}
    for rep in reports:
        payload = rep.payload or {}
        for item in payload.get("issues") or []:
            key = _normalize_issue_tag(item.get("tag"))
            if not key:
                continue
            named = issue_label_for_code(key) if key.startswith("Q") else None
            ability_id = ability_for_issue_code(key) if key.startswith("Q") else None
            row = stats.setdefault(
                key,
                {
                    "tag": key,
                    "label": item.get("tag") or key,
                    "issue_name": named,
                    "ability_id": ability_id,
                    "count": 0,
                    "last_severity": None,
                    "last_report_id": rep.id,
                    "reports": [],
                },
            )
            row["count"] += 1
            row["last_severity"] = item.get("severity") or row["last_severity"]
            row["label"] = item.get("tag") or row["label"]
            if named:
                row["issue_name"] = named
            if ability_id:
                row["ability_id"] = ability_id
            row["reports"].append(
                {
                    "report_id": rep.id,
                    "created_at": rep.created_at.isoformat() if rep.created_at else "",
                    "total_score": payload.get("total_score"),
                    "severity": item.get("severity"),
                }
            )
    return stats


def _related_issues_by_ability(stats: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in stats.values():
        aid = row.get("ability_id")
        if not aid:
            continue
        grouped[aid].append(
            {
                "code": row["tag"],
                "label": row.get("issue_name") or row["label"],
                "count": row["count"],
            }
        )
    for aid in grouped:
        grouped[aid].sort(key=lambda x: x["count"], reverse=True)
    return grouped


def _dimension_hit_rate(payload: dict[str, Any]) -> float:
    """维度「达标率」：按 earned/max 衡量，避免重评时 LLM 乱改 hit 标签导致对比失真。"""
    points = payload.get("scoring_points") or []
    if not points:
        return 0.0
    scored = 0
    hits = 0
    for p in points:
        if not isinstance(p, dict):
            continue
        try:
            earned = float(p.get("earned") or 0)
            mx = float(p.get("max") or p.get("max_score") or 0)
        except (TypeError, ValueError):
            continue
        if mx <= 0:
            continue
        scored += 1
        ratio = earned / mx
        tag = str(p.get("hit") or "")
        if ratio >= 0.85 or tag == "full":
            hits += 1
        elif ratio >= 0.45 or tag == "partial":
            hits += 1
    if scored <= 0:
        return 0.0
    return round(hits / scored * 100, 1)


def _issue_comparison_key(item: dict[str, Any]) -> str:
    """跨稿对齐：Q 码 + 短标题；避免仅按 Q 码合并多条同类问题。"""
    code = normalize_issue_code(item.get("tag"))
    title = str(item.get("issue_title") or "").strip()
    if not code and title:
        code = normalize_issue_code(issue_tag_from_core_problem(title, ""))
    if code and title:
        return f"{code}:{title[:28]}"
    if code:
        return code
    if title:
        return f"T:{title[:32]}"
    tag = str(item.get("tag") or "").strip()
    if tag:
        return f"R:{tag[:32]}"
    return ""


def _issues_by_comparison_key(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for item in payload.get("issues") or []:
        if not isinstance(item, dict):
            continue
        key = _issue_comparison_key(item)
        if key:
            out[key] = item
    return out


def _issue_change_label(item: dict[str, Any] | None, fallback_key: str) -> str:
    if not item:
        return fallback_key
    title = str(item.get("issue_title") or "").strip()
    if title:
        return title
    tag = str(item.get("tag") or "").strip()
    code = normalize_issue_code(tag)
    if code:
        named = issue_label_for_code(code)
        return named or tag or fallback_key
    return tag or fallback_key


def build_retry_comparison(first: dict[str, Any], second: dict[str, Any]) -> dict[str, Any]:
    """
    二次批改对比（BE-502）：分数差、维度命中率差、问题标签迁移。
    写入第二次报告 payload.comparison，供 FE-502 展示。
    """
    from app.services.grading_helpers import display_total_score, hydrate_report_display_fields

    f = dict(first)
    s = dict(second)
    hydrate_report_display_fields(f)
    hydrate_report_display_fields(s)

    s1 = display_total_score(f)
    s2 = display_total_score(s)
    r1 = _dimension_hit_rate(f)
    r2 = _dimension_hit_rate(s)

    first_issues = _issues_by_comparison_key(f)
    second_issues = _issues_by_comparison_key(s)
    all_keys = set(first_issues) | set(second_issues)

    issue_changes: list[dict[str, Any]] = []
    for key in sorted(all_keys):
        before = first_issues.get(key)
        after = second_issues.get(key)
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
                "tag": key,
                "label": _issue_change_label(after or before, key),
                "before_severity": (before or {}).get("severity"),
                "after_severity": (after or {}).get("severity"),
                "status": status,
            }
        )

    resolved = sum(1 for row in issue_changes if row.get("status") == "resolved")
    improved = sum(1 for row in issue_changes if row.get("status") == "improved")
    new_issues = sum(1 for row in issue_changes if row.get("status") == "new")
    flat = abs(s2 - s1) < 0.05
    note = ""
    if flat and (resolved or improved):
        note = (
            "部分问题标签显示已改进，但总分未变：采分引擎与主评仍按全文重新打分，"
            "且可能因新问题、未改完的中等问题或局部改动未命中采分点而未上调。"
        )
    elif flat and new_issues and not resolved:
        note = "总分未变；本次检出新的问题项，请对照「主要问题」继续修改。"

    return {
        "first_score": s1,
        "second_score": s2,
        "score_delta": round(s2 - s1, 1),
        "first_hit_rate": r1,
        "second_hit_rate": r2,
        "hit_rate_delta": round(r2 - r1, 1),
        "issue_changes": issue_changes,
        "issues_resolved": resolved,
        "issues_improved": improved,
        "issues_new": new_issues,
        "score_unchanged_note": note or None,
    }


def find_baseline_report_for_retry(db: Session, submission: Submission) -> Report | None:
    """重作对比基准：与上一稿报告比（第 2 稿比首稿，第 3 稿比第 2 稿）。"""
    root_id = submission.parent_submission_id
    if not root_id:
        return None
    prev_attempt = int(submission.attempt or 2) - 1
    if prev_attempt <= 1:
        return find_report_for_submission(db, root_id)
    prev_sub = (
        db.query(Submission)
        .filter(
            Submission.parent_submission_id == root_id,
            Submission.attempt == prev_attempt,
        )
        .order_by(Submission.submitted_at.desc())
        .first()
    )
    if prev_sub:
        return find_report_for_submission(db, prev_sub.id)
    return find_report_for_submission(db, root_id)


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

    issue_stats = _collect_issue_stats(reports)
    issues_by_ability = _related_issues_by_ability(issue_stats)

    for rep in reports:
        payload = rep.payload or {}
        if payload.get("confidence") == "low":
            low_conf_count += 1
        report_has_a5_point = False
        for point in payload.get("scoring_points") or []:
            ability = point.get("ability") or label_to_ability(point.get("label", ""))
            mx = float(point.get("max") or 10)
            earned = float(point.get("earned") or 0)
            if mx <= 0:
                continue
            if ability == "A5":
                report_has_a5_point = True
            buckets[ability].append(earned / mx * 100)
        if not report_has_a5_point:
            a5_pct = _a5_score_for_report(db, rep, payload)
            if a5_pct is not None:
                buckets["A5"].append(a5_pct)

    dimensions: list[dict[str, Any]] = []
    for meta in ABILITY_DIMENSIONS:
        aid = meta["id"]
        scores = buckets.get(aid, [])
        avg = round(sum(scores) / len(scores), 1) if scores else None
        dimensions.append(
            {
                "id": aid,
                "name": meta["name"],
                "score": avg,
                "sample_count": len(scores),
                "related_issues": issues_by_ability.get(aid, []),
            }
        )

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
    stats = _collect_issue_stats(reports)
    ordered = sorted(stats.values(), key=lambda x: x["count"], reverse=True)
    return ordered


def build_home_summary(db: Session, user_id: str) -> dict[str, Any]:
    """首页聚合（BE-507）：能力概览 + 当前重点问题 + 最近批改。"""
    abilities = compute_abilities(db, user_id)
    issues = aggregate_issue_book(db, user_id)
    focus = issues[0] if issues else None

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

    return {
        "abilities": abilities,
        "focus_issue": focus,
        "recent_reports": recent_items,
    }


def build_me_summary(db: Session, user_id: str, email: str) -> dict[str, Any]:
    """「我的」页（FE-507）：学习统计 + BYOK 用量 + 争议占位。"""
    from app.models.entities import UserAiUsage

    report_count = db.query(Report).filter(Report.user_id == user_id).count()
    usage_rows = db.query(UserAiUsage).filter(UserAiUsage.user_id == user_id).all()
    tokens_in = sum(u.tokens_in or 0 for u in usage_rows)
    tokens_out = sum(u.tokens_out or 0 for u in usage_rows)
    grading_calls = len(usage_rows)

    return {
        "email": email,
        "stats": {
            "report_count": report_count,
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
    root_id = submission.parent_submission_id or submission.id
    root = db.get(Submission, root_id) or submission
    root_report = find_report_for_submission(db, root.id)
    root_payload = (root_report.payload or {}) if root_report else {}
    regrade_count = count_essay_regrades(db, user_id, root_id)
    attempt_next = regrade_count + 2
    max_regrades = max_essay_regrade_count(db, root_id)
    retry_allowed = regrade_count < max_regrades
    tier = first_pass_tier_for_root(db, root_id)
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
        "first_content": root.content,
        "first_score": root_payload.get("total_score"),
        "issues": payload.get("issues") or [],
        "suggestions": payload.get("suggestions") or [],
        "attempt_next": attempt_next,
        "retry_allowed": retry_allowed,
        "retry_max_count": max_regrades,
        "retry_used_count": regrade_count,
        "first_pass_tier_id": tier.get("tier_id"),
        "first_pass_tier_label": tier.get("label"),
        "retry_limit_message": None
        if retry_allowed
        else essay_regrade_limit_message(db, root_id, regrade_count),
    }
