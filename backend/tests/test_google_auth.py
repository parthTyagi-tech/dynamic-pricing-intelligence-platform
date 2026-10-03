import pytest
import os
from unittest.mock import patch

os.environ["FLASK_ENV"] = "testing"
os.environ["VERCEL"] = "1"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from run import app
from app.extensions import db
from app.models.user import User
from app.models.organization import Organization


@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["GOOGLE_OAUTH_CLIENT_ID"] = "mock-google-client-id.apps.googleusercontent.com"
    app.config["GOOGLE_OAUTH_CLIENT_SECRET"] = "mock-google-client-secret"

    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_google_auth_missing_token(client):
    res = client.post("/api/auth/google", json={})
    assert res.status_code == 400
    data = res.get_json()
    assert data["success"] is False
    assert "required" in data["message"].lower()


def test_google_auth_invalid_token(client):
    res = client.post("/api/auth/google", json={"credential": "invalid_fake_token_12345"})
    assert res.status_code == 401
    data = res.get_json()
    assert data["success"] is False


def test_google_auth_success_new_user(client):
    mock_payload = {
        "sub": "google-user-id-998877",
        "email": "testgoogleuser@klypup.ai",
        "name": "Test Google User",
        "email_verified": True,
        "aud": "mock-google-client-id.apps.googleusercontent.com",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_payload):
        res = client.post("/api/auth/google", json={"credential": "valid_mock_token"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert "token" in data
        assert data["user"]["email"] == "testgoogleuser@klypup.ai"
        assert data["user"]["oauth_provider"] == "google"


def test_google_auth_existing_user_linking(client):
    with app.app_context():
        org = Organization(name="Existing Org", invite_code="ex1234")
        db.session.add(org)
        db.session.flush()
        u = User(
            name="Existing User",
            email="existing@klypup.ai",
            role="admin",
            organization_id=org.id,
        )
        u.set_password("existingpass123")
        db.session.add(u)
        db.session.commit()

    mock_payload = {
        "sub": "google-sub-555",
        "email": "existing@klypup.ai",
        "name": "Existing User Google",
        "email_verified": True,
        "aud": "mock-google-client-id.apps.googleusercontent.com",
    }

    with patch("google.oauth2.id_token.verify_oauth2_token", return_value=mock_payload):
        res = client.post("/api/auth/google", json={"credential": "valid_mock_token_existing"})
        assert res.status_code == 200
        data = res.get_json()
        assert data["success"] is True
        assert data["user"]["email"] == "existing@klypup.ai"
        assert data["user"]["oauth_provider"] == "google"
