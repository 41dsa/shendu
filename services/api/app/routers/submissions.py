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
from app.domain.essay import USER_ESSAY_QUESTION_ID
from app.schemas.submission import SubmissionResponse, SubmissionUpsert, SubmitGradingResponse
from app.services.ai_client import get_credential
from app.services.events_service import track_event
from app.worker.tasks import enqueue_grading_job

router = APIRouter(prefix="/submissions", tags=["submissions"])


@router.post("", response_model=SubmissionResponse)
def upsert_submission(
    body: SubmissionUpsert,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> SubmissionResponse:
    status = SubmissionStatus.draft if body.status == "draft" else SubmissionStatus.submitted

    if body.question_id:
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
    else:
        prompt = (body.user_prompt or "").strip()
        if not prompt:
            raise HTTPException(status_code=400, detail="请填写题干与作答要求")
        if not db.get(Question, USER_ESSAY_QUESTION_ID):
            raise HTTPException(status_code=503, detail="服务未初始化，请联系管理员运行 init_db")
        material = (body.user_material or "").strip() or None
        row = Submission(
            user_id=user.id,
            question_id=USER_ESSAY_QUESTION_ID,
            user_prompt=prompt,
            user_material=material,
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
        user_prompt=row.user_prompt,
        user_material=row.user_material,
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
    track_event(db, "grading_submit", user.id, job_id=job.id, question_id=sub.question_id)
    return SubmitGradingResponse(grading_job_id=job.id, submission_id=sub.id)
