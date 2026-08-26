from fastapi import HTTPException
from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.db.models import AnalysisSettingsRecord
from app.settings.schemas import ConnectionTestResponse


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


def _effective_values(
    db: Session, payload, base: Settings
) -> dict[str, str | None]:
    record = db.get(AnalysisSettingsRecord, 1)
    stored = (
        {}
        if record is None
        else {
            "ai_provider": record.ai_provider,
            "openai_api_key": record.openai_api_key,
            "openai_model": record.openai_model,
            "local_base_url": record.local_base_url,
            "local_model": record.local_model,
        }
    )

    def pick(field: str) -> str | None:
        candidate = getattr(payload, field, None)
        if candidate is not None and str(candidate).strip():
            return str(candidate).strip()
        if stored.get(field):
            return stored[field]
        return getattr(base, field, None)

    provider = pick("ai_provider") or base.ai_provider
    openai_key = pick("openai_api_key")
    if not openai_key:
        # The stored key is write-only from the UI; fall back to boot settings.
        openai_key = base.openai_api_key or None
    return {
        "ai_provider": provider,
        "openai_api_key": openai_key,
        "openai_model": pick("openai_model"),
        "local_base_url": pick("local_base_url"),
        "local_model": pick("local_model"),
    }


def test_connection(
    db: Session,
    payload,
    base: Settings,
    *,
    client_factory=None,
) -> ConnectionTestResponse:
    values = _effective_values(db, payload, base)
    provider = values["ai_provider"]

    if provider == "fake":
        return ConnectionTestResponse(
            ok=True,
            detail="합성 테스트 모드는 네트워크 없이 동작합니다.",
        )

    def default_factory(**kwargs):
        kwargs.setdefault("timeout", 10.0)
        return OpenAI(**kwargs)

    factory = client_factory or default_factory

    if provider == "local":
        base_url = values["local_base_url"]
        model = values["local_model"] or ""
        if not base_url:
            return ConnectionTestResponse(ok=False, detail="로컬 서버 주소가 필요합니다.")
        try:
            models = [
                item.id for item in factory(api_key="local", base_url=base_url).models.list().data
            ]
        except Exception as error:  # noqa: BLE001 - surfaced to the UI verbatim
            return ConnectionTestResponse(
                ok=False,
                detail=f"연결 실패: {_error_summary(error)}",
            )
        if model and model not in models:
            return ConnectionTestResponse(
                ok=False,
                detail=f"모델을 찾을 수 없습니다: {model}",
                models=models[:20],
            )
        return ConnectionTestResponse(
            ok=True,
            detail=f"연결 성공 · 모델 {len(models)}개",
            models=models[:20],
        )

    api_key = values["openai_api_key"]
    if not api_key:
        return ConnectionTestResponse(ok=False, detail="OpenAI API 키가 필요합니다.")
    try:
        models = [
            item.id
            for item in factory(api_key=api_key).models.list().data
        ]
    except Exception as error:  # noqa: BLE001 - surfaced to the UI verbatim
        return ConnectionTestResponse(
            ok=False,
            detail=f"연결 실패: {_error_summary(error)}",
        )
    return ConnectionTestResponse(
        ok=True,
        detail=f"연결 성공 · 모델 {len(models)}개",
        models=models[:20],
    )


def _error_summary(error: Exception, limit: int = 200) -> str:
    message = str(error).strip().replace("\n", " ")
    return message[:limit] if message else error.__class__.__name__
