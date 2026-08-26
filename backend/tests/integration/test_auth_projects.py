from fastapi.testclient import TestClient
import pytest


PASSWORD = "Correct-Horse-2026"


def register_and_login(client: TestClient, email: str) -> dict[str, str]:
    registration = client.post(
        "/api/auth/register", json={"email": email, "password": PASSWORD}
    )
    assert registration.status_code == 201
    token = client.post(
        "/api/auth/token", data={"username": email, "password": PASSWORD}
    )
    assert token.status_code == 200
    return {"Authorization": f"Bearer {token.json()['access_token']}"}


def test_registration_normalizes_email_and_me_returns_user(client: TestClient) -> None:
    headers = register_and_login(client, "  Owner@Example.COM ")

    response = client.get("/api/auth/me", headers=headers)

    assert response.status_code == 200
    assert response.json()["email"] == "owner@example.com"


def test_duplicate_email_returns_conflict(client: TestClient) -> None:
    register_and_login(client, "duplicate@example.com")

    response = client.post(
        "/api/auth/register",
        json={"email": "DUPLICATE@example.com", "password": PASSWORD},
    )

    assert response.status_code == 409


def test_wrong_password_returns_unauthorized(client: TestClient) -> None:
    register_and_login(client, "login@example.com")

    response = client.post(
        "/api/auth/token",
        data={"username": "login@example.com", "password": "Wrong-Password-2026"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password"


@pytest.mark.parametrize("name", ["   ", "가" * 121])
def test_project_name_validation(client: TestClient, name: str) -> None:
    headers = register_and_login(client, f"name-{len(name)}@example.com")

    response = client.post("/api/projects", headers=headers, json={"name": name})

    assert response.status_code == 422


def test_second_user_cannot_read_first_users_project(client: TestClient) -> None:
    alice = register_and_login(client, "alice@example.com")
    project = client.post(
        "/api/projects", headers=alice, json={"name": "Alice RFP"}
    ).json()
    bob = register_and_login(client, "bob@example.com")

    response = client.get(f"/api/projects/{project['id']}", headers=bob)

    assert response.status_code == 404


def test_project_crud_is_scoped_to_current_user(client: TestClient) -> None:
    headers = register_and_login(client, "project-owner@example.com")
    created = client.post(
        "/api/projects", headers=headers, json={"name": "  2027 RFP  "}
    )
    project_id = created.json()["id"]

    assert created.status_code == 201
    assert created.json()["name"] == "2027 RFP"
    assert client.get("/api/projects", headers=headers).json()[0]["id"] == project_id

    updated = client.patch(
        f"/api/projects/{project_id}",
        headers=headers,
        json={"name": "수정된 프로젝트"},
    )
    assert updated.status_code == 200
    assert updated.json()["name"] == "수정된 프로젝트"

    deleted = client.delete(f"/api/projects/{project_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/projects/{project_id}", headers=headers).status_code == 404
