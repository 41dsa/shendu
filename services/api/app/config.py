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
    grading_llm_stuck_minutes: int = 4
    # 双路复核：分差超过此值则丢弃复核分，仅保留完整批改主评（避免用户看到 29/34 等撕裂感）
    grading_consensus_max_delta: float = 1.5
    standards_upload_dir: str = "uploads/standards"
    standard_publish_min_confidence: float = 0.85
    standards_annotation_dir: str = ""
    # 自备批改：注入写作技巧参考（见 data/guides/essay_writing_technique.txt）
    essay_writing_guide_enabled: bool = False
    essay_writing_guide_path: str = ""
    essay_writing_guide_max_chars: int = 10000

    @property
    def standards_annotation_path(self) -> Path:
        if self.standards_annotation_dir.strip():
            return Path(self.standards_annotation_dir)
        return _API_ROOT.parent.parent / "data" / "standards" / "annotation"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
