import secrets
import string
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.models.entities import License, LicenseStatus, Order, RedeemCode, RedeemCodeStatus

CODE_ALPHABET = string.ascii_uppercase + string.digits
CODE_ALPHABET = CODE_ALPHABET.replace("O", "").replace("0", "").replace("I", "").replace("1", "")


def generate_code(length: int = 16) -> str:
    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(length))


def redeem_code(db: Session, user_id: str, code: str) -> License:
    normalized = code.strip().upper()
    row = db.get(RedeemCode, normalized)
    if not row:
        raise ValueError("INVALID_CODE")
    if row.status == RedeemCodeStatus.revoked:
        raise ValueError("CODE_REVOKED")
    if row.status == RedeemCodeStatus.used:
        if row.used_by_user_id == user_id:
            existing = db.query(License).filter(License.user_id == user_id).first()
            if existing and existing.status == LicenseStatus.active:
                return existing
        raise ValueError("CODE_ALREADY_USED")

    existing_license = db.query(License).filter(License.user_id == user_id).first()
    if existing_license and existing_license.status == LicenseStatus.active:
        # 已激活用户再次输入正确未使用码前的兜底（常见：重复点兑换）
        return existing_license

    row.status = RedeemCodeStatus.used
    row.used_by_user_id = user_id
    row.used_at = row.used_at or datetime.now(UTC)

    if existing_license:
        existing_license.status = LicenseStatus.active
        existing_license.sku = row.sku
        existing_license.source = "redeem_code"
        existing_license.source_ref = normalized
        existing_license.revoked_at = None
        license_row = existing_license
    else:
        license_row = License(user_id=user_id, sku=row.sku, source="redeem_code", source_ref=normalized)
        db.add(license_row)

    db.add(
        Order(
            user_id=user_id,
            sku=row.sku,
            channel="afdian_redeem",
            external_ref=normalized,
            status="completed",
        )
    )
    db.commit()
    db.refresh(license_row)
    return license_row
