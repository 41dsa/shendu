from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models.entities import User
from app.schemas.license import PurchaseInfoResponse, RedeemRequest, RedeemResponse
from app.services import license_service

router = APIRouter(tags=["license"])


@router.get("/purchase", response_model=PurchaseInfoResponse)
def purchase_info() -> PurchaseInfoResponse:
    return PurchaseInfoResponse(
        afdian_plan_url=settings.afdian_plan_url,
        instructions="在爱发电完成「永久激活」档位购买后，使用私信中的激活码在本站兑换。AI 批改需自备模型 API Key。",
    )


@router.post("/redeem", response_model=RedeemResponse)
def redeem(
    body: RedeemRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> RedeemResponse:
    try:
        lic = license_service.redeem_code(db, user.id, body.code)
    except ValueError as exc:
        code = str(exc)
        messages = {
            "INVALID_CODE": "激活码无效",
            "CODE_REVOKED": "激活码已作废",
            "CODE_ALREADY_USED": "激活码已被使用",
            "ALREADY_LICENSED": "账号已激活，无需重复兑换",
        }
        raise HTTPException(status_code=400, detail=messages.get(code, "兑换失败")) from exc
    return RedeemResponse(ok=True, sku=lic.sku, message="激活成功")
