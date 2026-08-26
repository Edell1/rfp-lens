from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="RFP_LENS_",
        extra="ignore",
    )

    database_url: str = "postgresql+psycopg://rfp_lens:rfp_lens@localhost:5432/rfp_lens"
    redis_url: str = "redis://localhost:6379/0"
    storage_root: Path = Path("storage")
    jwt_secret: str = "change-me"
    openai_api_key: str | None = None
    openai_model: str = "gpt-5-mini"
    ai_provider: Literal["openai", "fake"] = "openai"
    celery_task_always_eager: bool = False
    frontend_origins: list[str] = ["http://localhost:5173"]
    max_upload_bytes: int = 26_214_400
    environment: Literal["development", "test", "demo", "production"] = "development"

    def validate_runtime(self) -> None:
        if self.environment != "test" and self.jwt_secret == "change-me":
            raise RuntimeError(
                "RFP_LENS_JWT_SECRET must be changed outside the test environment"
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()
