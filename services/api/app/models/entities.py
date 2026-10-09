import enum
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
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
    user_prompt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    user_material: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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


class TrainingLevel(str, enum.Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"


class TrainingKind(str, enum.Enum):
    today = "today"
    special = "special"
    issue = "issue"


class TrainingRecordStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    skipped = "skipped"


class TrainingRecord(Base):
    """用户训练记录（BE-506）：今日/专项/问题训练的可追踪单元。"""

    __tablename__ = "training_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    kind: Mapped[TrainingKind] = mapped_column(Enum(TrainingKind))
    title: Mapped[str] = mapped_column(String(255))
    ability_id: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    level: Mapped[TrainingLevel] = mapped_column(Enum(TrainingLevel), default=TrainingLevel.L1)
    focus_tag: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    status: Mapped[TrainingRecordStatus] = mapped_column(
        Enum(TrainingRecordStatus), default=TrainingRecordStatus.pending
    )
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    result_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    linked_report_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reports.id"), nullable=True)
    question_id: Mapped[Optional[str]] = mapped_column(ForeignKey("questions.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class PromptPurpose(str, enum.Enum):
    essay_grading = "essay_grading"
    essay_consensus = "essay_consensus"
    standard_p01 = "standard_p01"
    standard_p02 = "standard_p02"
    standard_p03 = "standard_p03"
    standard_p04 = "standard_p04"
    standard_p05 = "standard_p05"
    standard_p06 = "standard_p06"
    standard_p07 = "standard_p07"


class SourceLevel(str, enum.Enum):
    S = "S"
    A = "A"
    B = "B"
    C = "C"


class StandardGenerationJobStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    validated = "validated"
    published = "published"
    failed = "failed"


class ExamQuestionStandardStatus(str, enum.Enum):
    draft = "draft"
    in_review = "in_review"
    published = "published"
    archived = "archived"


class PromptVersion(Base):
    """批改 Prompt 版本（BE-603）；仅一条 is_active=true 生效。"""

    __tablename__ = "prompt_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(128))
    purpose: Mapped[PromptPurpose] = mapped_column(Enum(PromptPurpose), default=PromptPurpose.essay_grading)
    content: Mapped[str] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GoldSample(Base):
    """金标答案样本（BE-604）。"""

    __tablename__ = "gold_samples"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    reference_answer: Mapped[str] = mapped_column(Text)
    expected_score_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    expected_score_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class GoldRun(Base):
    """金标回归跑分结果（BE-605）。"""

    __tablename__ = "gold_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    gold_sample_id: Mapped[str] = mapped_column(ForeignKey("gold_samples.id"), index=True)
    ai_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    expected_mid: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_delta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    consensus_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    standard_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    report_id: Mapped[Optional[str]] = mapped_column(ForeignKey("reports.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DisputeStatus(str, enum.Enum):
    pending = "pending"
    ai_reviewed = "ai_reviewed"
    closed = "closed"


class ScoreDispute(Base):
    """用户评分争议（BE-606/607）。"""

    __tablename__ = "score_disputes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    report_id: Mapped[str] = mapped_column(ForeignKey("reports.id"), index=True)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[DisputeStatus] = mapped_column(Enum(DisputeStatus), default=DisputeStatus.pending)
    ai_review_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class AnalyticsEvent(Base):
    """关键埋点（BE-608）。"""

    __tablename__ = "analytics_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    event_name: Mapped[str] = mapped_column(String(64), index=True)
    properties: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class UserAiUsage(Base):
    __tablename__ = "user_ai_usage"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    grading_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("grading_jobs.id"), nullable=True)
    standard_generation_job_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    model: Mapped[str] = mapped_column(String(128))
    provider_base_url: Mapped[str] = mapped_column(String(512))
    tokens_in: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    tokens_out: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    call_type: Mapped[str] = mapped_column(String(32), default="primary")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StandardDocument(Base):
    """考试标准引擎 — 资料（M1）。"""

    __tablename__ = "standard_documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255))
    source: Mapped[str] = mapped_column(String(32), default="manual_upload")
    source_level: Mapped[SourceLevel] = mapped_column(Enum(SourceLevel), default=SourceLevel.B)
    exam: Mapped[str] = mapped_column(String(64), default="")
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content: Mapped[str] = mapped_column(Text, default="")
    storage_uri: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StandardGenerationJob(Base):
    """标准生成任务（Celery 步骤机）。"""

    __tablename__ = "standard_generation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    created_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    status: Mapped[StandardGenerationJobStatus] = mapped_column(
        Enum(StandardGenerationJobStatus), default=StandardGenerationJobStatus.pending
    )
    current_step: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    document_ids: Mapped[list[Any]] = mapped_column(JSON, default=list)
    error_message: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class StandardJobStep(Base):
    __tablename__ = "standard_job_steps"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    job_id: Mapped[str] = mapped_column(ForeignKey("standard_generation_jobs.id"), index=True)
    step: Mapped[str] = mapped_column(String(64))
    detail: Mapped[str] = mapped_column(String(128), default="done")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class StandardPipelineCache(Base):
    """同题 + 同资料内容 + LLM 模式下的流水线结果缓存（跳过 P01～P05 调用）。"""

    __tablename__ = "standard_pipeline_cache"

    input_fingerprint: Mapped[str] = mapped_column(String(64), primary_key=True)
    question_id: Mapped[str] = mapped_column(String(36), index=True)
    gen_mode: Mapped[str] = mapped_column(String(16), default="llm")
    source_job_id: Mapped[str] = mapped_column(String(36))
    bundle: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ExamQuestionStandard(Base):
    """题目级考试标准发布包（M7）。"""

    __tablename__ = "exam_question_standards"
    __table_args__ = (UniqueConstraint("question_id", "version", name="uq_question_standard_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ExamQuestionStandardStatus] = mapped_column(
        Enum(ExamQuestionStandardStatus), default=ExamQuestionStandardStatus.draft
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    validation_result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
