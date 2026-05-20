"""Application settings loaded from environment variables."""

from functools import lru_cache

from pydantic import Field, RedisDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration; all secrets come from the environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = Field(default="taskforge", validation_alias="APP_NAME")
    app_env: str = Field(default="development", validation_alias="APP_ENV")
    debug: bool = Field(default=False, validation_alias="DEBUG")
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")

    api_host: str = Field(default="0.0.0.0", validation_alias="API_HOST")
    api_port: int = Field(default=8000, validation_alias="API_PORT")

    # asyncpg driver prefix added in Step 2 when SQLAlchemy is wired
    database_url: str = Field(
        default="postgresql+asyncpg://taskforge:taskforge@localhost:5432/taskforge",
        validation_alias="DATABASE_URL",
    )
    redis_url: RedisDsn = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
    )
    task_queue_key: str = Field(
        default="taskforge:tasks:queue",
        validation_alias="TASK_QUEUE_KEY",
    )
    worker_brpop_timeout: int = Field(
        default=5,
        ge=1,
        le=60,
        validation_alias="WORKER_BRPOP_TIMEOUT",
    )

    @property
    def is_development(self) -> bool:
        return self.app_env.lower() in {"development", "dev", "local"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance for FastAPI Depends (added in later phases)."""
    return Settings()
