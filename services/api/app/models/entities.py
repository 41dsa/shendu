import enum
import uuid
from datetime import UTC, datetime
from typing import Any, Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.domain.question_type import QuestionType


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
    reviewer = "reviewer"
    embedding = "embedding"


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
    exam_level: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
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


class EmbeddingVectorCache(Base):
    """Embedding 向量持久化缓存（按文本 + 模型）。"""

    __tablename__ = "embedding_vector_cache"
    __table_args__ = (UniqueConstraint("cache_key", name="uq_embedding_vector_cache_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    model: Mapped[str] = mapped_column(String(128))
    vector: Mapped[list[Any]] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ScoringMatchCache(Base):
    """L3 LLM 语义仲裁结果缓存（采分点语义 + 段落哈希）。"""

    __tablename__ = "scoring_match_cache"
    __table_args__ = (UniqueConstraint("cache_key", name="uq_scoring_match_cache_key"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    cache_key: Mapped[str] = mapped_column(String(64), index=True)
    accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    reason: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ScoringPointHitLog(Base):
    """评分实践反馈（L4 自进化输入）。"""

    __tablename__ = "scoring_point_hit_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    grading_job_id: Mapped[str] = mapped_column(ForeignKey("grading_jobs.id"), index=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    exam_level: Mapped[str] = mapped_column(String(32), default="municipal")
    point_id: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(24))
    total_score: Mapped[float] = mapped_column(Float, default=0.0)
    point_pool_version: Mapped[str] = mapped_column(String(16), default="1.0.0")
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PromptPurpose(str, enum.Enum):
    essay_grading = "essay_grading"
    essay_grading_custom = "essay_grading_custom"
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


class ExamStandardStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class StandardDocumentCategory(str, enum.Enum):
    """M1 资料目录（大作文 V0.3-E）。"""

    announcement = "announcement"
    syllabus = "syllabus"
    exam_paper = "exam_paper"
    reference = "reference"
    other = "other"


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


class ExamStandard(Base):
    """考试级标准聚合（M7 简版，仅大作文）。"""

    __tablename__ = "exam_standards"
    __table_args__ = (UniqueConstraint("exam", "year", "version", name="uq_exam_standard_version"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    exam: Mapped[str] = mapped_column(String(64), index=True)
    year: Mapped[int] = mapped_column(Integer, index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[ExamStandardStatus] = mapped_column(
        Enum(ExamStandardStatus), default=ExamStandardStatus.draft
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WeakLabelType(str, enum.Enum):
    rule = "rule"
    rubric = "rubric"
    model_consensus = "model_consensus"
    self_consistency = "self_consistency"
    pair_compare = "pair_compare"
    retry_delta = "retry_delta"
    counterexample = "counterexample"


class WeakLabel(Base):
    """PRD §7.4 弱监督标签（禁止冒充真值）。"""

    __tablename__ = "weak_labels"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    grading_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("grading_jobs.id"), nullable=True, index=True)
    submission_id: Mapped[Optional[str]] = mapped_column(ForeignKey("submissions.id"), nullable=True, index=True)
    question_id: Mapped[Optional[str]] = mapped_column(ForeignKey("questions.id"), nullable=True, index=True)
    label_type: Mapped[WeakLabelType] = mapped_column(Enum(WeakLabelType), index=True)
    trait_id: Mapped[Optional[str]] = mapped_column(String(8), nullable=True, index=True)
    label_value: Mapped[str] = mapped_column(String(64), default="")
    is_weak_label: Mapped[bool] = mapped_column(Boolean, default=True)
    rubric_version: Mapped[str] = mapped_column(String(32), default="")
    standard_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ActiveLearningReason(str, enum.Enum):
    trait_vote_spread = "trait_vote_spread"
    evidence_insufficient = "evidence_insufficient"
    standard_match_low = "standard_match_low"
    level_boundary = "level_boundary"
    user_dispute = "user_dispute"
    self_consistency = "self_consistency"


class ActiveLearningPoolEntry(Base):
    """PRD §8.3 主动学习难例池。"""

    __tablename__ = "active_learning_pool"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    grading_job_id: Mapped[Optional[str]] = mapped_column(ForeignKey("grading_jobs.id"), nullable=True, index=True)
    submission_id: Mapped[Optional[str]] = mapped_column(ForeignKey("submissions.id"), nullable=True, index=True)
    question_id: Mapped[Optional[str]] = mapped_column(ForeignKey("questions.id"), nullable=True, index=True)
    reason: Mapped[ActiveLearningReason] = mapped_column(Enum(ActiveLearningReason), index=True)
    priority: Mapped[float] = mapped_column(Float, default=0.5)
    status: Mapped[str] = mapped_column(String(24), default="open", index=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TraitPairCompareStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    cancelled = "cancelled"


class EssayImportAudit(Base):
    """Q-03：EssayItem 批量导入审计。"""

    __tablename__ = "essay_import_audits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    source: Mapped[str] = mapped_column(String(32), default="csv")
    filename: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    imported_by_user_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.id"), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    created_count: Mapped[int] = mapped_column(Integer, default=0)
    updated_count: Mapped[int] = mapped_column(Integer, default=0)
    skipped_locked_count: Mapped[int] = mapped_column(Integer, default=0)
    items: Mapped[list[Any]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnchorEssay(Base):
    """PRD §6.2 锚作文（按题 L0～L4 覆盖）。"""

    __tablename__ = "anchor_essays"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    title: Mapped[str] = mapped_column(String(255), default="")
    content: Mapped[str] = mapped_column(Text)
    aggregate_level: Mapped[str] = mapped_column(String(8), default="L2")
    trait_levels: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    is_published: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AnchorTraitReview(Base):
    """PRD AN-03：多评者 Trait 标注（允许分歧）。"""

    __tablename__ = "anchor_trait_reviews"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    anchor_essay_id: Mapped[str] = mapped_column(ForeignKey("anchor_essays.id"), index=True)
    reviewer_label: Mapped[str] = mapped_column(String(32), default="reviewer_1")
    trait_id: Mapped[str] = mapped_column(String(8), index=True)
    level: Mapped[str] = mapped_column(String(4), default="L2")
    evidence_positive: Mapped[list[Any]] = mapped_column(JSON, default=list)
    reviewer_rationale: Mapped[str] = mapped_column(String(1024), default="")
    dispute_note: Mapped[str] = mapped_column(String(512), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TraitScoringRecord(Base):
    """PRD §11 Trait 评分结构化记录（与 hit_log 双写过渡期）。"""

    __tablename__ = "trait_scoring_records"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    grading_job_id: Mapped[str] = mapped_column(ForeignKey("grading_jobs.id"), index=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    trait_id: Mapped[str] = mapped_column(String(8), index=True)
    trait_level: Mapped[str] = mapped_column(String(4), default="L2")
    model_votes: Mapped[list[Any]] = mapped_column(JSON, default=list)
    vote_spread: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    evidence_payload: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    final_calibrated_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    rubric_version: Mapped[str] = mapped_column(String(32), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class TraitPairCompareTask(Base):
    """PRD §7.4 成对比较弱标签任务（A vs B）。"""

    __tablename__ = "trait_pair_compare_tasks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    question_id: Mapped[str] = mapped_column(ForeignKey("questions.id"), index=True)
    submission_a_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    submission_b_id: Mapped[str] = mapped_column(ForeignKey("submissions.id"), index=True)
    trait_id: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    status: Mapped[TraitPairCompareStatus] = mapped_column(
        Enum(TraitPairCompareStatus), default=TraitPairCompareStatus.pending
    )
    result: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
