from typing import Annotated

from fastapi import APIRouter, Depends

from app.auth.dependencies import CurrentUser, DatabaseSession
from app.core.config import Settings, get_settings
from app.settings.schemas import AnalysisSettingsPatch, AnalysisSettingsResponse
from app.settings.service import build_response, get_or_create_record, update_analysis_settings


router = APIRouter(prefix="/api/settings", tags=["settings"])


@router.get("/analysis", response_model=AnalysisSettingsResponse)
def read_analysis_settings(
    db: DatabaseSession,
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisSettingsResponse:
    record = get_or_create_record(db)
    db.commit()
    return build_response(record, settings)


@router.patch("/analysis", response_model=AnalysisSettingsResponse)
def patch_analysis_settings(
    payload: AnalysisSettingsPatch,
    db: DatabaseSession,
    user: CurrentUser,
    settings: Annotated[Settings, Depends(get_settings)],
) -> AnalysisSettingsResponse:
    record = update_analysis_settings(db, payload, settings)
    return build_response(record, settings)
