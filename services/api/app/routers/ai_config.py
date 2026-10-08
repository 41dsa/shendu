from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.crypto import encrypt_secret, mask_api_key
from app.database import get_db
from app.deps import get_current_user
from app.models.entities import CredentialRole, User, UserProviderCredential
from app.schemas.ai_config import AiCredentialUpsert, AiCredentialView, AiTestConnectionRequest
from app.services.ai_client import AiCallError, get_credential, test_connection

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/credentials", response_model=list[AiCredentialView])
def list_credentials(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[AiCredentialView]:
    rows = db.query(UserProviderCredential).filter(UserProviderCredential.user_id == user.id).all()
    by_role = {r.role: r for r in rows}
    result: list[AiCredentialView] = []
    for role in (CredentialRole.primary, CredentialRole.consensus):
        row = by_role.get(role)
        if not row:
            result.append(
                AiCredentialView(role=role.value, base_url="", model="", api_key_masked="", configured=False)
            )
        else:
            from app.services.ai_client import decrypt_api_key

            masked = mask_api_key(decrypt_api_key(row))
            result.append(
                AiCredentialView(
                    role=role.value,
                    base_url=row.base_url,
                    model=row.model,
                    api_key_masked=masked,
                    configured=True,
                )
            )
    return result


@router.put("/credentials/{role}", response_model=AiCredentialView)
def upsert_credential(
    role: str,
    body: AiCredentialUpsert,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AiCredentialView:
    try:
        role_enum = CredentialRole(role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="无效 role") from exc
    nonce, ct = encrypt_secret(body.api_key)
    row = get_credential(db, user.id, role_enum)
    if row:
        row.base_url = body.base_url.rstrip("/")
        row.model = body.model
        row.api_key_nonce = nonce
        row.api_key_ciphertext = ct
        row.save_tokens_mode = body.save_tokens_mode
    else:
        row = UserProviderCredential(
            user_id=user.id,
            role=role_enum,
            base_url=body.base_url.rstrip("/"),
            model=body.model,
            api_key_nonce=nonce,
            api_key_ciphertext=ct,
            save_tokens_mode=body.save_tokens_mode,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return AiCredentialView(
        role=role_enum.value,
        base_url=row.base_url,
        model=row.model,
        api_key_masked=mask_api_key(body.api_key),
        configured=True,
    )


@router.post("/test-connection")
async def test_conn(
    body: AiTestConnectionRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    try:
        role_enum = CredentialRole(body.role)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="无效 role") from exc
    cred = get_credential(db, user.id, role_enum)
    if not cred:
        raise HTTPException(status_code=400, detail="请先保存 API 配置")
    try:
        return await test_connection(cred)
    except AiCallError as exc:
        raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)}) from exc
