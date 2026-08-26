from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AnalysisSettingsRecord


def get_or_create_record(db: Session) -> AnalysisSettingsRecord:
    record = db.get(AnalysisSettingsRecord, 1)
    if record is None:
        record = AnalysisSettingsRecord(id=1, ai_provider="")
        db.add(record)
        db.flush()
    return record


def resolve_runtime_settings(db: Session, base: Settings) -> Settings:
    """Merge the stored UI overrides on top of the boot-time settings.

    Called at the start of every analysis task so changes apply without a restart.
    """
    record = db.get(AnalysisSettingsRecord, 1)
    if record is None or not record.ai_provider:
        return base

    overrides: dict[str, str] = {"ai_provider": record.ai_provider}
    if record.openai_api_key:
        overrides["openai_api_key"] = record.openai_api_key
    if record.openai_model:
        overrides["openai_model"] = record.openai_model
    if record.local_base_url:
        overrides["local_base_url"] = record.local_base_url
    if record.local_model:
        overrides["local_model"] = record.local_model
    return base.model_copy(update=overrides)


def _validation_error(code: str) -> HTTPException:
    return HTTPException(status_code=422, detail={"code": code, "message": code})


def update_analysis_settings(
    db: Session, payload, base: Settings
) -> AnalysisSettingsRecord:
    record = get_or_create_record(db)

    provider = payload.ai_provider or record.ai_provider or base.ai_provider
    openai_key = (
        payload.openai_api_key.strip()
        if payload.openai_api_key and payload.openai_api_key.strip()
        else record.openai_api_key
    )
    openai_model = (
        payload.openai_model.strip()
        if payload.openai_model and payload.openai_model.strip()
        else (record.openai_model or base.openai_model)
    )
    local_base_url = (
        payload.local_base_url.strip()
        if payload.local_base_url and payload.local_base_url.strip()
        else (record.local_base_url or base.local_base_url)
    )
    local_model = (
        payload.local_model.strip()
        if payload.local_model and payload.local_model.strip()
        else (record.local_model or "")
    )

    if provider == "fake" and base.environment not in {"test", "demo"}:
        raise _validation_error("fake_provider_not_allowed")
    if provider == "openai" and not openai_key:
        raise _validation_error("openai_api_key_required")
    if provider == "local" and not local_model:
        raise _validation_error("local_model_required")

    record.ai_provider = provider
    record.openai_api_key = openai_key
    record.openai_model = openai_model
    record.local_base_url = local_base_url
    record.local_model = local_model
    db.commit()
    db.refresh(record)
    return record


def build_response(record: AnalysisSettingsRecord, base: Settings):
    from app.settings.schemas import AnalysisSettingsResponse

    return AnalysisSettingsResponse(
        ai_provider=record.ai_provider or base.ai_provider,
        openai_model=record.openai_model or base.openai_model,
        openai_api_key_set=bool(record.openai_api_key),
        local_base_url=record.local_base_url or base.local_base_url,
        local_model=record.local_model or "",
        updated_at=record.updated_at,
    )
