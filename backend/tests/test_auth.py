from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.deps import require_staff
from app.models import User, UserSession


@pytest.fixture(autouse=True)
def enable_registration_for_account_tests(monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "signup_enabled", True)


def test_registration_can_be_closed(client, monkeypatch):
    from app.config import get_settings
    monkeypatch.setattr(get_settings(), "signup_enabled", False)
    assert client.get("/api/auth/available-roles").json() == {"roles": []}
    result = client.post("/api/auth/signup", json={"name": "Closed", "email": "closed@account.test", "password": "Closed-password-42", "role": "admin"})
    assert result.status_code == 403
    assert result.json()["detail"]["code"] == "registration_closed"


@pytest.mark.parametrize("role", ["patient", "receptionist", "admin"])
def test_signup_sets_cookie_and_returns_user(client: TestClient, role: str) -> None:
    response = client.post("/api/auth/signup", json={"name": "Account", "email": f"{role}@account.test", "password": "Account-password-42", "role": role})

    assert response.status_code == 201
    body = response.json()
    assert body["role"] == role
    assert set(body) == {"id", "name", "email", "role"}
    assert client.cookies.get("session")


def test_me_returns_logged_in_user(login) -> None:
    client = login("patient")

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.json()["name"] == "Maya Patel"
    assert response.json()["role"] == "patient"


def test_me_without_cookie_is_401(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthenticated"


def test_logout_then_me_is_401(login) -> None:
    client = login("receptionist")

    logout = client.post("/api/auth/logout")

    assert logout.status_code == 204
    assert client.get("/api/auth/me").status_code == 401


def test_invalid_role_is_422(client: TestClient) -> None:
    response = client.post("/api/auth/signup", json={"name": "Account", "email": "account@example.test", "password": "Account-password-42", "role": "doctor"})

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"


def test_expired_session_is_401(login, db: Session) -> None:
    client = login("patient")
    token = client.cookies.get("session")
    db.execute(
        update(UserSession)
        .where(UserSession.token == token)
        .values(expires_at=datetime.now(UTC) - timedelta(hours=1))
    )
    db.commit()

    assert client.get("/api/auth/me").status_code == 401


def test_session_lasts_eight_hours(login, db: Session) -> None:
    client = login("admin")
    row = db.scalar(select(UserSession).where(UserSession.token == client.cookies.get("session")))

    assert row.expires_at - row.created_at == timedelta(hours=8)


def test_require_staff_forbids_patient_and_allows_staff() -> None:
    patient = User(id=1, name="P", email="p@x.test", role="patient")
    receptionist = User(id=2, name="R", email="r@x.test", role="receptionist")

    with pytest.raises(HTTPException) as excinfo:
        require_staff(patient)
    assert excinfo.value.status_code == 403
    assert excinfo.value.detail["code"] == "forbidden"

    assert require_staff(receptionist) is receptionist


def test_role_claim_and_normalized_email(client, db):
    payload = {"name": " Owner ", "email": " OWNER@account.test ", "password": "Owner-password-42", "role": "admin"}
    assert client.post("/api/auth/signup", json=payload).status_code == 201
    assert "admin" not in client.get("/api/auth/available-roles").json()["roles"]
    row = db.scalar(select(User).where(User.email == "owner@account.test"))
    assert row.password_hash != payload["password"]
    assert row.password_hash.startswith("scrypt$")
    assert row.name == "Owner"
    second = {**payload, "email": "another@account.test"}
    assert client.post("/api/auth/signup", json=second).status_code == 409
    assert client.post("/api/auth/signup", json={**payload, "role": "patient"}).status_code == 409
    client.post("/api/auth/logout")
    assert client.post("/api/auth/login", json={"email": "OWNER@account.test", "password": payload["password"]}).status_code == 200
    assert client.get("/api/auth/me").json()["role"] == "admin"


def test_password_required_and_role_bypass_removed(client):
    assert client.post("/api/auth/demo-login", json={"role": "admin"}).status_code == 404
    for email in ("missing@account.test", "maya.patel@terra.example"):
        response = client.post("/api/auth/login", json={"email": email, "password": "Incorrect-password"})
        assert response.status_code == 401
        assert response.json()["detail"]["code"] == "invalid_credentials"
    assert client.post("/api/auth/signup", json={"name": "X", "email": "x@account.test", "password": "short", "role": "patient"}).status_code == 422
    assert client.post("/api/auth/login", json={"email": "x@account.test", "password": "Long-password-42", "role": "admin"}).status_code == 422


def test_session_rotates_and_wrong_password_fails(client):
    payload = {"name": "Patient", "email": "new@account.test", "password": "Patient-password-42", "role": "patient"}
    assert client.post("/api/auth/signup", json=payload).status_code == 201
    old = client.cookies.get("session")
    assert client.post("/api/auth/login", json={"email": payload["email"], "password": "Incorrect-password"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": payload["email"], "password": payload["password"]}).status_code == 200
    assert client.cookies.get("session") != old
    other = TestClient(client.app)
    other.cookies.set("session", old)
    assert other.get("/api/auth/me").status_code == 401
    assert client.get("/api/retention").status_code == 403
