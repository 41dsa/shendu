from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_active_license, get_current_user
from app.domain.exam_catalog import exam_profile_display, get_exam_profile_form_options
from app.models.entities import ExamProfile, License, User
from app.schemas.exam import ExamProfileResponse, ExamProfileUpsert

router = APIRouter(prefix="/exam-profiles", tags=["exam"])


def _to_response(row: ExamProfile) -> ExamProfileResponse:
    meta = exam_profile_display(
        exam_type=row.exam_type,
        province=row.province,
        year=row.year,
        job_category=row.job_category,
    )
    return ExamProfileResponse(
        id=row.id,
        exam_type=meta["exam_type"],
        province=row.province,
        year=row.year,
        job_category=meta["job_category"],
        summary=meta["summary"],
        mapped_bank_exam=meta["mapped_bank_exam"],
        mapped_bank_year=meta["mapped_bank_year"],
    )


@router.get("/options")
def get_profile_options(
    _: User = Depends(get_current_user),
) -> dict:
    return get_exam_profile_form_options().model_dump()


@router.get("", response_model=ExamProfileResponse | None)
def get_profile(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ExamProfileResponse | None:
    row = db.query(ExamProfile).filter(ExamProfile.user_id == user.id).first()
    if not row:
        return None
    return _to_response(row)


@router.put("", response_model=ExamProfileResponse)
def upsert_profile(
    body: ExamProfileUpsert,
    user: User = Depends(get_current_user),
    _lic: License = Depends(get_active_license),
    db: Session = Depends(get_db),
) -> ExamProfileResponse:
    meta = exam_profile_display(
        exam_type=body.exam_type,
        province=body.province,
        year=body.year,
        job_category=body.job_category,
    )
    row = db.query(ExamProfile).filter(ExamProfile.user_id == user.id).first()
    if row:
        row.exam_type = str(meta["exam_type"])
        row.province = body.province.strip()
        row.year = body.year
        row.job_category = str(meta["job_category"])
    else:
        row = ExamProfile(
            user_id=user.id,
            exam_type=str(meta["exam_type"]),
            province=body.province.strip(),
            year=body.year,
            job_category=str(meta["job_category"]),
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return _to_response(row)
