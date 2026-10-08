import enum
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class UserRole(str, enum.Enum):
    user = "user"
    admin = "admin"


class RedeemCodeStatus(str, enum.Enum):
    unused = "unused"
    used = "used"
    revoked = "revoked"


class LicenseStatus(str, enum.Enum):
    active = "active"
    revoked = "revoked"


class QuestionType(str, enum.Enum):
    """V1 仅批改申论大作文；小题（概括/分析/对策）不在产品范围内。"""

    essay = "essay"


class SubmissionStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"


class GradingJobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"


class CredentialRole(str, enum.Enum):
    primary = "primary"
    consensus = "consensus"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.user)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    license: Mapped[Optional["License"]] = relationship(back_populates="user", uselist=False)
    credentials: Mapped[list["UserProviderCredential"]] = relationship(back_populates="user")


class RedeemCode(Base):
    __tablename__ = "redeem_codes"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), default="lifetime_web")
    status: Mapped[RedeemCodeStatus] = mapped_column(Enum(RedeemCodeStatus), default=RedeemCodeStatus.unused)
    batch_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    used_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    sku: Mapped[str] = mapped_column(String(64), default="lifetime_web")
    status: Mapped[LicenseStatus] = mapped_column(Enum(LicenseStatus), default=LicenseStatus.active)
    source: Mapped[str] = mapped_column(String(32), default="redeem_code")
    source_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    valid_until: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["User"] = relationship(back_populates="license")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    sku: Mapped[str] = mapped_column(String(64))
    channel: Mapped[str] = mapped_column(String(32))
    external_ref: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserProviderCredential(Base):
    __tablename__ = "user_provider_credentials"
    __table_args__ = (UniqueConstraint("user_id", "role", name="uq_user_credential_role"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[CredentialRole] = mapped_column(Enum(CredentialRole))
    base_url: Mapped[str] = mapped_column(String(512))
    model: Mapped[str] = mapped_column(String(128))
    api_key_nonce: Mapped[str] = mapped_column(String(64))
    api_key_ciphertext: Mapped[str] = mapped_column(Text)
    save_tokens_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship(back_populates="credentials")


class ExamProfile(Base):
    __tablename__ = "exam_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    exam_type: Mapped[str] = mapped_column(String(64))
    province: Mapped[str] = mapped_column(String(64))
    year: Mapped[int] = mapped_column(Integer)
    job_category: Mapped[str] = mapped_column(String(64))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Question(Base):
    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255))
    question_type: Mapped[QuestionType] = mapped_column(Enum(QuestionType), default=QuestionType.essay)
    score: Mapped[int] = mapped_column(Integer, default=40)
    word_limit: Mapped[int] = mapped_column(Integer, default=1200)
    prompt: Mapped[str] = mapped_column(Text, default="")
    material: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    material_structured: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, nullable=True)
    scoring_points: Mapped[list[Any]] = mapped_column(JSON, default=list)
    published: Mapped[bool] = mapped_column(Boolean, default=True)


class Submission(Base):
    __tablename__ = "submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    content: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[SubmissionStatus] = mapped_column(Enum(SubmissionStatus), default=SubmissionStatus.draft)
    attempt: Mapped[int] = mapped_column(Integer, default=1)
    parent_submission_id: Mapped[Optional[str]] = mapped_column(ForeignKey("submissions.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class GradingJob(Base):
    __tablename__ = "grading_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    status: Mapped[GradingJobStatus] = mapped_column(Enum(GradingJobStatus), default=GradingJobStatus.queued)
    current_step: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    steps: Mapped[list[Any]] = mapped_column(JSON, default=list)
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    grading_job_id: Mapped[str] = mapped_column(ForeignKey("grading_jobs.id"), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GradingAnswerCache(Base):
    __tablename__ = "grading_answer_cache"
    __table_args__ = (UniqueConstraint("question_id", "answer_hash", name="uq_question_answer_hash"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    answer_hash: Mapped[str] = mapped_column(String(64))
    rubric_version: Mapped[str] = mapped_column(String(16), default="v1")
    report_payload: Mapped[dict] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserAiUsage(Base):
    __tablename__ = "user_ai_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    grading_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("grading_jobs.id"), nullable=True)
    model: Mapped[str] = mapped_column(String(128))
    provider_base_url: Mapped[str] = mapped_column(String(512))
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    call_type: Mapped[str] = mapped_column(String(32), default="primary")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
