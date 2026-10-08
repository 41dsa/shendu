from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_active_license, get_current_user
from app.models.entities import ExamProfile, License, User
from app.schemas.exam import ExamProfileResponse, ExamProfileUpsert

router = APIRouter(prefix="/exam-profiles", tags=["exam"])


@router.get("", response_model=ExamProfileResponse | None)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExamProfileResponse | None:
    row = db.query(ExamProfile).filter(ExamProfile.user_id == user.id).first()
    if not row:
        return None
    return ExamProfileResponse(
        id=row.id,
        exam_type=row.exam_type,
        province=row.province,
        year=row.year,
        job_category=row.job_category,
    )


@router.put("", response_model=ExamProfileResponse)
def upsert_profile(
    body: ExamProfileUpsert,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> ExamProfileResponse:
    row = db.query(ExamProfile).filter(ExamProfile.user_id == user.id).first()
    if row:
        row.exam_type = body.exam_type
        row.province = body.province
        row.year = body.year
        row.job_category = body.job_category
    else:
        row = ExamProfile(
            user_id=user.id,
            exam_type=body.exam_type,
            province=body.province,
            year=body.year,
            job_category=body.job_category,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return ExamProfileResponse(
        id=row.id,
        exam_type=row.exam_type,
        province=row.province,
        year=row.year,
        job_category=row.job_category,
    )
