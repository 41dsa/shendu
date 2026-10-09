"""金标回归（BE-604/605）：用管理员 BYOK 对金标答案跑真实批改并统计偏差。"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.entities import (
    GoldRun,
    GoldSample,
    GradingJob,
    GradingJobStatus,
    Report,
    Submission,
    SubmissionStatus,
)
from app.services.grading_service import run_grading_job
import asyncio


async def run_gold_sample(db: Session, sample: GoldSample, admin_user_id: str) -> GoldRun:
    """
    为金标创建独立 submission + grading_job，复用大作文批改管线。
    管理员账号需已配置 BYOK 且有效 License。
    """
    sub = Submission(
        user_id=admin_user_id,
        question_id=sample.question_id,
        content=sample.reference_answer,
        status=SubmissionStatus.submitted,
        submitted_at=datetime.now(UTC),
    )
    db.add(sub)
    db.flush()

    job = GradingJob(user_id=admin_user_id, submission_id=sub.id, status=GradingJobStatus.queued)
    db.add(job)
    db.commit()
    db.refresh(job)

    await run_grading_job(db, job.id)

    report = db.query(Report).filter(Report.grading_job_id == job.id).first()
    payload = report.payload if report else {}
    ai_score = float(payload.get("total_score") or 0)
    standard_version = payload.get("standard_version")
    if standard_version is None:
        essay_meta = payload.get("essay_meta") or {}
        if isinstance(essay_meta, dict):
            standard_version = essay_meta.get("standard_version")
    if standard_version is not None:
        try:
            standard_version = int(standard_version)
        except (TypeError, ValueError):
            standard_version = None
    expected_mid = None
    if sample.expected_score_min is not None and sample.expected_score_max is not None:
        expected_mid = (sample.expected_score_min + sample.expected_score_max) / 2
    delta = abs(ai_score - expected_mid) if expected_mid is not None else None

    run = GoldRun(
        gold_sample_id=sample.id,
        ai_score=ai_score,
        expected_mid=expected_mid,
        score_delta=delta,
        consensus_rate=float(payload.get("consensus_rate") or 0),
        standard_version=standard_version,
        report_id=report.id if report else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def run_gold_sample_sync(db: Session, sample: GoldSample, admin_user_id: str) -> GoldRun:
    """供 FastAPI 路由调用的同步包装。"""
    return asyncio.run(run_gold_sample(db, sample, admin_user_id))


def _run_stats(runs: list[GoldRun]) -> dict:
    with_delta = [r for r in runs if r.score_delta is not None]
    passed = sum(1 for r in with_delta if r.score_delta <= 2.0)
    avg_delta = sum(r.score_delta for r in with_delta) / len(with_delta) if with_delta else None
    return {
        "run_count": len(runs),
        "pass_rate": round(passed / len(with_delta) * 100, 1) if with_delta else None,
        "avg_delta": round(avg_delta, 2) if avg_delta is not None else None,
    }


def regression_summary(db: Session) -> dict:
    """金标一致率：|delta|<=2 分视为通过（V1 简版）。"""
    runs = db.query(GoldRun).order_by(GoldRun.created_at.desc()).limit(100).all()
    if not runs:
        return {
            "run_count": 0,
            "pass_rate": None,
            "avg_delta": None,
            "standard_versions": [],
            "by_standard_version": [],
        }
    versions = sorted({r.standard_version for r in runs if r.standard_version is not None})
    by_version: list[dict] = []
    grouped: dict[int | None, list[GoldRun]] = {}
    for r in runs:
        grouped.setdefault(r.standard_version, []).append(r)
    for ver in sorted((k for k in grouped if k is not None), reverse=True):
        stats = _run_stats(grouped[ver])
        by_version.append({"standard_version": ver, **stats})
    if None in grouped:
        by_version.append({"standard_version": None, **_run_stats(grouped[None])})
    return {
        **_run_stats(runs),
        "standard_versions": versions,
        "by_standard_version": by_version,
    }
