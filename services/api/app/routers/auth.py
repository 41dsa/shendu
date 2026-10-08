from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.config import settings
from app.core.security import create_access_token, hash_password, verify_password
from app.database import get_db
from app.deps import get_current_user
from app.models.entities import CredentialRole, License, LicenseStatus, User, UserProviderCredential, UserRole
from app.schemas.auth import EntitlementResponse, LoginRequest, RegisterRequest, TokenResponse, UserMeResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
def register(body: RegisterRequest, db: Session = Depends(get_db)) -> TokenResponse:
    if db.query(User).filter(User.email == body.email.lower()).first():
        raise HTTPException(status_code=400, detail="邮箱已注册")
    role = UserRole.user
    if settings.bootstrap_admin_email and body.email.lower() == settings.bootstrap_admin_email.lower():
        role = UserRole.admin
    user = User(email=body.email.lower(), password_hash=hash_password(body.password), role=role)
    db.add(user)
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id))


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = db.query(User).filter(User.email == body.email.lower()).first()
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="邮箱或密码错误")
    return TokenResponse(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserMeResponse)
def me(user: User = Depends(get_current_user)) -> UserMeResponse:
    return UserMeResponse(id=user.id, email=user.email, role=user.role.value)


@router.get("/me/entitlement", response_model=EntitlementResponse)
def entitlement(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> EntitlementResponse:
    lic = db.query(License).filter(License.user_id == user.id, License.status == LicenseStatus.active).first()
    has_key = (
        db.query(UserProviderCredential)
        .filter(
            UserProviderCredential.user_id == user.id,
            UserProviderCredential.role == CredentialRole.primary,
        )
        .first()
        is not None
    )
    return EntitlementResponse(
        licensed=lic is not None,
        sku=lic.sku if lic else None,
        activated_at=lic.activated_at.isoformat() if lic else None,
        has_primary_ai_key=has_key,
    )
