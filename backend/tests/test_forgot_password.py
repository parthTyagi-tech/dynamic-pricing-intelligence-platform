import pytest
import os
os.environ["FLASK_ENV"] = "testing"
os.environ["VERCEL"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from itsdangerous import URLSafeTimedSerializer
from run import app
from app.extensions import db
from app.models.user import User
from app.models.organization import Organization


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key-321"
    
    with app.app_context():
        db.create_all()
        # Seed test org and user
        org = Organization(name="Test Org", invite_code="TESTINV12345")
        db.session.add(org)
        db.session.commit()

        user = User(
            name="Test User",
            email="testuser@example.com",
            organization_id=org.id,
            role="analyst"
        )
        user.set_password("initialpassword123")
        db.session.add(user)
        db.session.commit()

        yield app.test_client()

        db.session.remove()
        db.drop_all()


def test_forgot_password_success(client):
    res = client.post("/api/auth/forgot-password", json={"email": "testuser@example.com"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True
    assert "password reset instructions" in data["message"].lower()


def test_forgot_password_nonexistent_email_returns_safe_success(client):
    # Prevents account enumeration
    res = client.post("/api/auth/forgot-password", json={"email": "ghost@example.com"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["success"] is True


def test_forgot_password_missing_email(client):
    res = client.post("/api/auth/forgot-password", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False


def test_reset_password_success(client):
    with app.app_context():
        user = User.query.filter_by(email="testuser@example.com").first()
        serializer = URLSafeTimedSerializer("test-secret-key-321")
        token = serializer.dumps({"user_id": user.id, "email": user.email}, salt="password-reset")

    res = client.post("/api/auth/reset-password", json={
        "token": token,
        "new_password": "brandnewpassword456"
    })
    assert res.status_code == 200
    assert res.get_json()["success"] is True

    # Verify user can now log in with the new password
    login_res = client.post("/api/auth/login", json={
        "email": "testuser@example.com",
        "password": "brandnewpassword456"
    })
    assert login_res.status_code == 200
    assert "token" in login_res.get_json()


def test_reset_password_short_password(client):
    with app.app_context():
        user = User.query.filter_by(email="testuser@example.com").first()
        serializer = URLSafeTimedSerializer("test-secret-key-321")
        token = serializer.dumps({"user_id": user.id, "email": user.email}, salt="password-reset")

    res = client.post("/api/auth/reset-password", json={
        "token": token,
        "new_password": "123"
    })
    assert res.status_code == 400
    assert "at least 6 characters" in res.get_json()["message"]


def test_reset_password_tampered_token(client):
    res = client.post("/api/auth/reset-password", json={
        "token": "invalid.tampered.token",
        "new_password": "validpassword123"
    })
    assert res.status_code == 400
    assert "invalid or corrupted" in res.get_json()["message"]
