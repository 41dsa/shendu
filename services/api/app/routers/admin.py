from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import require_admin
from app.models.entities import License, LicenseStatus, RedeemCode, RedeemCodeStatus, User
from app.schemas.admin import AdminGrantRequest, GenerateCodesRequest, GenerateCodesResponse
from app.services import license_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/redeem-codes/generate", response_model=GenerateCodesResponse)
def generate_codes(
    body: GenerateCodesRequest,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
) -> GenerateCodesResponse:
    batch_id = body.batch_id or license_service.generate_code(8)
    codes: list[str] = []
    for _ in range(body.count):
        while True:
            code = license_service.generate_code(16)
            if not db.get(RedeemCode, code):
                db.add(RedeemCode(code=code, sku="lifetime_web", batch_id=batch_id))
                codes.append(code)
                break
    db.commit()
    unused = db.query(RedeemCode).filter(RedeemCode.status == RedeemCodeStatus.unused).count()
    return GenerateCodesResponse(batch_id=batch_id, codes=codes, unused_total=unused)


@router.post("/licenses/grant")
def grant_license(body: AdminGrantRequest, _: User = Depends(require_admin), db: Session = Depends(get_db)) -> dict:
    user = db.query(User).filter(User.email == body.user_email.lower()).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    lic = db.query(License).filter(License.user_id == user.id).first()
    if lic:
        lic.status = LicenseStatus.active
        lic.sku = body.sku
        lic.source = "admin"
    else:
        lic = License(user_id=user.id, sku=body.sku, source="admin")
        db.add(lic)
    db.commit()
    return {"ok": True, "user_id": user.id}
