from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AnalysisSettingsResponse(BaseModel):
    ai_provider: Literal["openai", "fake", "local"]
    openai_model: str
    openai_api_key_set: bool
    local_base_url: str
    local_model: str
    updated_at: datetime


class AnalysisSettingsPatch(BaseModel):
    ai_provider: Literal["openai", "fake", "local"] | None = None
    openai_api_key: str | None = Field(default=None, max_length=512)
    openai_model: str | None = Field(default=None, min_length=1, max_length=120)
    local_base_url: str | None = Field(default=None, min_length=1, max_length=500)
    local_model: str | None = Field(default=None, min_length=1, max_length=120)


class ConnectionTestResponse(BaseModel):
    ok: bool
    detail: str
    models: list[str] = Field(default_factory=list)
