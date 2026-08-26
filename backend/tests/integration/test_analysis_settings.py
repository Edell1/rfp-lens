from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.models import AnalysisSettingsRecord
from app.settings.service import resolve_runtime_settings


PASSWORD = "Correct-Horse-2026"


def register_and_login(client: TestClient, email: str) -> dict[str, str]:
    assert (
        client.post(
            "/api/auth/register", json={"email": email, "password": PASSWORD}
        ).status_code
        == 201
    )
    token = client.post(
        "/api/auth/token", data={"username": email, "password": PASSWORD}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_get_returns_defaults_without_exposing_key(client: TestClient) -> None:
    headers = register_and_login(client, "cfg-reader@example.com")

    response = client.get("/api/settings/analysis", headers=headers)

    assert response.status_code == 200
    body = response.json()
    assert body["ai_provider"] == "openai"
    assert body["openai_api_key_set"] is False
    assert body["openai_model"] == "gpt-5-mini"
    assert body["local_base_url"] == "http://localhost:11434/v1"
    assert body["local_model"] == ""
    assert "openai_api_key" not in body


def test_patch_local_settings_round_trip(client: TestClient) -> None:
    headers = register_and_login(client, "cfg-local@example.com")

    patched = client.patch(
        "/api/settings/analysis",
        headers=headers,
        json={
            "ai_provider": "local",
            "local_base_url": "http://host.docker.internal:11434/v1",
            "local_model": "qwen2.5:7b",
        },
    )
    fetched = client.get("/api/settings/analysis", headers=headers)

    assert patched.status_code == 200
    assert patched.json()["ai_provider"] == "local"
    assert fetched.json()["local_model"] == "qwen2.5:7b"
    assert fetched.json()["local_base_url"] == "http://host.docker.internal:11434/v1"


def test_patch_openai_stores_key_without_exposing_it(client: TestClient) -> None:
    headers = register_and_login(client, "cfg-openai@example.com")

    patched = client.patch(
        "/api/settings/analysis",
        headers=headers,
        json={"ai_provider": "openai", "openai_api_key": "sk-secret-demo-key"},
    )

    assert patched.status_code == 200
    assert patched.json()["openai_api_key_set"] is True
    assert "sk-secret-demo-key" not in patched.text


def test_patch_openai_without_any_key_is_rejected(client: TestClient) -> None:
    headers = register_and_login(client, "cfg-nokey@example.com")

    response = client.patch(
        "/api/settings/analysis",
        headers=headers,
        json={"ai_provider": "openai"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "openai_api_key_required"


def test_patch_local_without_model_is_rejected(client: TestClient) -> None:
    headers = register_and_login(client, "cfg-nomodel@example.com")

    response = client.patch(
        "/api/settings/analysis",
        headers=headers,
        json={"ai_provider": "local"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "local_model_required"


def test_unauthenticated_access_is_rejected(client: TestClient) -> None:
    assert client.get("/api/settings/analysis").status_code == 401
    assert client.patch("/api/settings/analysis", json={}).status_code == 401


def test_runtime_resolution_merges_stored_overrides(
    client: TestClient, db_session, tmp_path
) -> None:
    base = Settings(
        environment="test",
        jwt_secret="runtime-resolution-secret-enough",
        storage_root=tmp_path,
    )
    headers = register_and_login(client, "cfg-runtime@example.com")

    assert resolve_runtime_settings(db_session, base).ai_provider == "openai"

    client.patch(
        "/api/settings/analysis",
        headers=headers,
        json={"ai_provider": "local", "local_model": "qwen2.5:7b"},
    )
    first = resolve_runtime_settings(db_session, base)
    assert first is not base
    assert first.ai_provider == "local"
    assert first.local_model == "qwen2.5:7b"
    assert first.environment == base.environment

    record = db_session.get(AnalysisSettingsRecord, 1)
    record.local_model = "llama3.1:8b"
    db_session.commit()

    second = resolve_runtime_settings(db_session, base)
    assert second.local_model == "llama3.1:8b"


def test_connection_test_accepts_fake_without_network(client: TestClient) -> None:
    headers = register_and_login(client, "cfg-test-fake@example.com")

    response = client.post(
        "/api/settings/analysis/test",
        headers=headers,
        json={"ai_provider": "fake"},
    )

    assert response.status_code == 200
    assert response.json()["ok"] is True


def test_connection_test_reports_unreachable_local_server(
    client: TestClient,
) -> None:
    headers = register_and_login(client, "cfg-test-local@example.com")

    response = client.post(
        "/api/settings/analysis/test",
        headers=headers,
        json={
            "ai_provider": "local",
            "local_base_url": "http://127.0.0.1:9/v1",
            "local_model": "m",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert body["detail"].startswith("연결 실패")


def test_connection_test_detects_missing_model(db_session, tmp_path) -> None:
    from types import SimpleNamespace

    from app.settings.schemas import AnalysisSettingsPatch
    from app.settings.service import test_connection

    base = Settings(
        environment="test",
        jwt_secret="connection-stub-secret-enough",
        storage_root=tmp_path,
    )
    payload = AnalysisSettingsPatch(
        ai_provider="local",
        local_base_url="http://stub:1234/v1",
        local_model="missing-model",
    )
    captured = {}

    def stub_factory(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            models=SimpleNamespace(
                list=lambda: SimpleNamespace(
                    data=[SimpleNamespace(id="present-a"), SimpleNamespace(id="present-b")]
                )
            )
        )

    missing = test_connection(db_session, payload, base, client_factory=stub_factory)

    assert missing.ok is False
    assert "missing-model" in missing.detail
    assert missing.models == ["present-a", "present-b"]
    assert captured["base_url"] == "http://stub:1234/v1"

    found = test_connection(
        db_session,
        AnalysisSettingsPatch(
            ai_provider="local",
            local_base_url="http://stub:1234/v1",
            local_model="present-a",
        ),
        base,
        client_factory=stub_factory,
    )
    assert found.ok is True
    assert found.detail.startswith("연결 성공")


def test_connection_test_requires_openai_key_when_none_stored(
    client: TestClient,
) -> None:
    headers = register_and_login(client, "cfg-test-openai@example.com")

    response = client.post(
        "/api/settings/analysis/test",
        headers=headers,
        json={"ai_provider": "openai"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is False
    assert "API 키" in body["detail"]
