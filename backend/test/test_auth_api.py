from fastapi.testclient import TestClient

from app.api import auth
from app.main import app


client = TestClient(app)


def test_forgot_password_hint_returns_relative_path(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "PASSWORD_FILE", tmp_path / "workspace" / "password.txt")

    response = client.get("/api/auth/forgot-password-hint")

    assert response.status_code == 200
    assert response.json()["file_path"] == "workspace/password.txt"


def test_password_setup_validation_failure_does_not_create_password_file(monkeypatch, tmp_path):
    password_file = tmp_path / "workspace" / "password.txt"
    monkeypatch.setattr(auth, "PASSWORD_FILE", password_file)

    response = client.post("/api/auth/setup", json={"password": "short"})

    assert response.status_code == 422
    assert not password_file.exists()


def test_password_hash_save_failure_does_not_leave_password_file(monkeypatch, tmp_path):
    password_file = tmp_path / "workspace" / "password.txt"
    monkeypatch.setattr(auth, "PASSWORD_FILE", password_file)

    def fail_replace(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(auth.os, "replace", fail_replace)

    try:
        auth._save_password_hash("Aa123456")
    except OSError:
        pass

    assert not password_file.exists()


def test_auth_status_exposes_demo_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "PASSWORD_FILE", tmp_path / "workspace" / "password.txt")
    monkeypatch.setattr(auth.settings, "demo_mode", True)

    response = client.get("/api/auth/status")

    assert response.status_code == 200
    assert response.json() == {"password_set": False, "demo_mode": True}


def test_demo_login_requires_demo_mode(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "PASSWORD_FILE", tmp_path / "workspace" / "password.txt")
    monkeypatch.setattr(auth.settings, "demo_mode", False)

    response = client.post("/api/auth/demo-login")

    assert response.status_code == 403
    assert response.json()["detail"] == "演示模式未开启"


def test_demo_login_issues_expiring_admin_token(monkeypatch, tmp_path):
    monkeypatch.setattr(auth, "PASSWORD_FILE", tmp_path / "workspace" / "password.txt")
    monkeypatch.setattr(auth.settings, "demo_mode", True)
    auth._save_password_hash("Aa123456")

    response = client.post("/api/auth/demo-login")

    assert response.status_code == 200
    token = response.json()["token"]
    payload = auth.decode_jwt_payload(token)
    assert payload is not None
    assert payload["sub"] == "lui-admin"
    assert payload["demo_mode"] is True
    assert auth.verify_jwt_token(token)

    monkeypatch.setattr(auth.settings, "demo_mode", False)
    assert not auth.verify_jwt_token(token)
