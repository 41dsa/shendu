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
    Question,
    Submission,
    SubmissionStatus,
    User,
)
from app.schemas.submission import SubmissionResponse, SubmissionUpsert, SubmitGradingResponse
from app.services.ai_client import get_credential
from app.worker.tasks import enqueue_grading_job

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionResponse)
def upsert_submission(
    body: SubmissionUpsert,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    if not db.get(Question, body.question_id):
        raise HTTPException(status_code=404, detail="题目不存在")
    row = (
        db.query(Submission)
        .filter(
            Submission.user_id == user.id,
            Submission.question_id == body.question_id,
            Submission.status == SubmissionStatus.draft,
            Submission.attempt == 1,
        )
        .first()
    )
    status = SubmissionStatus.draft if body.status == "draft" else SubmissionStatus.submitted
    if row:
        row.content = body.content
        row.status = status
        if status == SubmissionStatus.submitted:
            row.submitted_at = datetime.now(UTC)
    else:
        row = Submission(
            user_id=user.id,
            question_id=body.question_id,
            content=body.content,
            status=status,
        )
        if status == SubmissionStatus.submitted:
            row.submitted_at = datetime.now(UTC)
        db.add(row)
    db.commit()
    db.refresh(row)
    return SubmissionResponse(
        id=row.id,
        question_id=row.question_id,
        content=row.content,
        status=row.status.value,
        attempt=row.attempt,
    )


@router.post("/{submission_id}/grade", response_model=SubmitGradingResponse)
def submit_grade(
    submission_id: str,
    user: User = Depends(get_current_user),
    lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> SubmitGradingResponse:
    _ = lic
    sub = db.get(Submission, submission_id)
    if not sub or sub.user_id != user.id:
        raise HTTPException(status_code=404, detail="提交不存在")
    if not sub.content.strip():
        raise HTTPException(status_code=400, detail="答案不能为空")
    if not get_credential(db, user.id, CredentialRole.primary):
        raise HTTPException(status_code=403, detail="AI_KEY_REQUIRED")

    sub.status = SubmissionStatus.submitted
    sub.submitted_at = datetime.now(UTC)
    job = GradingJob(user_id=user.id, submission_id=sub.id, status=GradingJobStatus.queued)
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_grading_job(job.id)
    return SubmitGradingResponse(grading_job_id=job.id, submission_id=sub.id)
