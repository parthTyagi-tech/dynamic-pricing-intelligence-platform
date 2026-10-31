import os
import pytest

# Set hermetic test environment defaults BEFORE any app import
os.environ["FLASK_ENV"] = "testing"
os.environ["MOCK_SCRAPING"] = "true"
os.environ["VERCEL"] = "1"
os.environ["SECRET_KEY"] = "ci-testing-secret-key-32-chars-minimum-safe!!"
os.environ["JWT_SECRET_KEY"] = "ci-testing-jwt-secret-key-32-chars-safe!!"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from run import app
from app.extensions import db


@pytest.fixture(autouse=True)
def auto_app_context():
    """
    Autouse fixture that pushes a Flask application context for all tests,
    preventing 'Working outside of application context' errors, and ensures
    in-memory database tables exist.
    """
    with app.app_context():
        try:
            db.create_all()
        except Exception:
            pass
        yield
