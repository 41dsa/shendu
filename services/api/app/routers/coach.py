from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_active_license, get_current_user
from app.models.entities import (
    CredentialRole,
    GradingJob,
    GradingJobStatus,
    License,
    Report,
    Submission,
    SubmissionStatus,
    User,
)
from app.schemas.coach import RetryContextResponse, RetrySubmitBody, RetrySubmitResponse
from app.services.ai_client import get_credential
from app.services.coach_service import (
    aggregate_issue_book,
    build_home_summary,
    compute_abilities,
    get_retry_context,
)
from app.worker.tasks import enqueue_grading_job

router = APIRouter(prefix="/coach", tags=["coach"])


@router.get("/home")
def home_summary(
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> dict:
    """首页聚合：能力、重点问题、今日训练推荐、最近批改。"""
    return build_home_summary(db, user.id)


@router.get("/abilities")
def abilities(
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> dict:
    return compute_abilities(db, user.id)


@router.get("/issues")
def issue_book(
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> list[dict]:
    return aggregate_issue_book(db, user.id)


@router.get("/reports/{report_id}/retry-context", response_model=RetryContextResponse)
def retry_context(
    report_id: str,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> RetryContextResponse:
    try:
        ctx = get_retry_context(db, user.id, report_id)
    except ValueError as exc:
        if str(exc) == "REPORT_NOT_FOUND":
            raise HTTPException(status_code=404, detail="报告不存在") from exc
        raise HTTPException(status_code=400, detail="无法加载二次作答上下文") from exc
    return RetryContextResponse(**ctx)


@router.post("/reports/{report_id}/retry", response_model=RetrySubmitResponse)
def submit_retry(
    report_id: str,
    body: RetrySubmitBody,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> RetrySubmitResponse:
    """
    二次作答（BE-501）：新建 attempt>1 的 submission，parent 指向首次提交，并入队批改。
    对比结果在 grading 完成后写入新报告 payload.comparison。
    """
    if not get_credential(db, user.id, CredentialRole.primary):
        raise HTTPException(status_code=403, detail="AI_KEY_REQUIRED")

    report = db.get(Report, report_id)
    if not report or report.user_id != user.id:
        raise HTTPException(status_code=404, detail="报告不存在")
    job = db.get(GradingJob, report.grading_job_id)
    if not job:
        raise HTTPException(status_code=400, detail="批改任务不存在")

    first_sub = db.get(Submission, job.submission_id)
    if not first_sub:
        raise HTTPException(status_code=400, detail="首次提交不存在")

    # 链式 parent：始终指向「第一次」作答，便于多次重写对比到首稿
    root_id = first_sub.parent_submission_id or first_sub.id
    root = db.get(Submission, root_id)
    attempt = (
        db.query(Submission)
        .filter(Submission.user_id == user.id, Submission.parent_submission_id == root_id)
        .count()
        + 2
    )

    row = Submission(
        user_id=user.id,
        question_id=first_sub.question_id,
        content=body.content.strip(),
        status=SubmissionStatus.submitted,
        attempt=attempt,
        parent_submission_id=root_id,
        submitted_at=datetime.now(UTC),
    )
    db.add(row)
    db.flush()

    new_job = GradingJob(user_id=user.id, submission_id=row.id, status=GradingJobStatus.queued)
    db.add(new_job)
    db.commit()
    db.refresh(new_job)
    enqueue_grading_job(new_job.id)

    return RetrySubmitResponse(
        grading_job_id=new_job.id,
        submission_id=row.id,
        attempt=attempt,
    )
