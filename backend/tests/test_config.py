from pathlib import Path

import pytest

from app.core.config import Settings


def test_environment_variables_override_settings(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("RFP_LENS_DATABASE_URL", "postgresql+psycopg://test:test@db/test")
    monkeypatch.setenv("RFP_LENS_STORAGE_ROOT", str(tmp_path))
    monkeypatch.setenv("RFP_LENS_MAX_UPLOAD_BYTES", "1024")

    settings = Settings(_env_file=None)

    assert settings.database_url == "postgresql+psycopg://test:test@db/test"
    assert settings.storage_root == tmp_path
    assert settings.max_upload_bytes == 1024


def test_placeholder_jwt_secret_is_rejected_outside_tests() -> None:
    settings = Settings(environment="development", jwt_secret="change-me")

    with pytest.raises(RuntimeError, match="RFP_LENS_JWT_SECRET"):
        settings.validate_runtime()


def test_placeholder_jwt_secret_is_allowed_in_tests() -> None:
    settings = Settings(environment="test", jwt_secret="change-me")

    settings.validate_runtime()
