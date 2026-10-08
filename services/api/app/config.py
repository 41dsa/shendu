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

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
