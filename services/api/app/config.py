from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_API_ROOT = Path(__file__).resolve().parents[1]
_ENV_FILES = (_API_ROOT / ".env", _API_ROOT.parent.parent / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=[str(p) for p in _ENV_FILES if p.exists()],
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///./shendu_dev.db"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "dev-jwt-secret-change-in-production-min-32"
    jwt_expire_minutes: int = 60 * 24 * 7
    master_key: str = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    cors_origins: str = "http://localhost:5173"
    app_env: str = "development"
    bootstrap_admin_email: str | None = None
    afdian_plan_url: str = "https://afdian.net"
    max_concurrent_grading_jobs_per_user: int = 2
    grading_stale_queued_minutes: int = 5
    grading_stale_running_minutes: int = 25
    grading_llm_timeout_seconds: float = 120.0
    # 模型 HTTP：默认不读 HTTP_PROXY（IDE/沙箱本地代理常对厂商 API 返回 403，导致批改 INTERNAL 失败）
    ai_http_trust_env: bool = False
    grading_llm_stuck_minutes: int = 4
    # 双路复核：分差超过此值则丢弃复核分，仅保留完整批改主评（避免用户看到 29/34 等撕裂感）
    grading_consensus_max_delta: float = 1.5
    standards_upload_dir: str = "uploads/standards"
    standard_publish_min_confidence: float = 0.85
    standard_consensus_3model_enabled: bool = False
    standard_consensus_min_score: float = 0.85
    standards_annotation_dir: str = ""
    # 自备批改：注入写作技巧参考（见 data/guides/essay_writing_technique.txt）
    essay_writing_guide_enabled: bool = False
    essay_writing_guide_path: str = ""
    essay_writing_guide_max_chars: int = 10000
    # 自备批改：提交时按题干/材料走标准生产（stub/llm），结果缓存复用
    custom_essay_standard_engine_enabled: bool = True
    custom_essay_standard_mode: str = "auto"  # auto | stub | llm
    # 自备批改主评：trait_v1（PRD 诊断）| traditional_marking（四档阅卷 Prompt）
    custom_essay_grading_mode: str = "trait_v1"
    # 分层评分引擎 = PRD V1 Trait 诊断引擎（非采分点池五层）
    layered_scoring_engine_enabled: bool = True
    layered_scoring_max_llm_delta: float = 4.0
    # 采分点池管线仅用于标准生产后台，批改路径已切换为 Trait V1 引擎
    point_pool_pipeline_enabled: bool = False
    # 批改/read path 禁止回退采分点池引擎（§0 Done-6）
    grading_point_pool_engine_allowed: bool = False
    scoring_llm_arbitration_enabled: bool = False
    scoring_deliberation_enabled: bool = False
    trait_llm_evidence_enabled: bool = True
    trait_llm_voting_enabled: bool = True
    trait_llm_voting_min_models: int = 3
    trait_anchor_count: int = 0
    anchor_min_for_relative_scale: int = 3
    anchor_min_for_center_score: int = 10
    diagnostic_only_mode: bool = False
    active_learning_vote_spread_threshold: float = 0.35
    active_learning_standard_match_threshold: float = 0.6
    active_learning_retry_min_level_changes: int = 2
    active_learning_boundary_confidence_max: float = 0.62
    weak_supervision_enabled: bool = True
    # V3-CAL 门禁（样本不足时跳过，不阻塞 CI）
    v3_calibration_min_qwk: float = 0.55
    v3_calibration_min_gold_runs: int = 5
    v3_calibration_min_anchor_pairs: int = 5
    v3_calibration_enabled: bool = False
    # V3-MODEL：专用 Trait 模型（未部署时为 stub，不改变 V1 分值）
    v3_trait_model_enabled: bool = False
    v3_trait_model_id: str = "trait-v3-stub"
    # E-05：证据 grounding 准确率门禁（合成金标集）
    evidence_accuracy_min_rate: float = 0.9
    # OpenAI 兼容 Embedding（BGE 网关 / vLLM / 云厂商）
    embedding_enabled: bool = True
    embedding_api_url: str = ""
    embedding_model: str = "bge-base-zh"
    embedding_use_primary_base: bool = True
    embedding_timeout_seconds: float = 45.0
    embedding_batch_size: int = 32
    embedding_max_chars_per_text: int = 2048

    @property
    def standards_annotation_path(self) -> Path:
        if self.standards_annotation_dir.strip():
            return Path(self.standards_annotation_dir)
        return _API_ROOT.parent.parent / "data" / "standards" / "annotation"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
