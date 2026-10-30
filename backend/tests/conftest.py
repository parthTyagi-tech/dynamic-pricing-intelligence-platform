import os
import pytest

# Set hermetic test environment defaults BEFORE any app import
os.environ.setdefault("FLASK_ENV", "testing")
os.environ.setdefault("MOCK_SCRAPING", "true")
os.environ.setdefault("VERCEL", "1")
os.environ.setdefault("SECRET_KEY", "ci-testing-secret-key-32-chars-minimum-safe!!")
os.environ.setdefault("JWT_SECRET_KEY", "ci-testing-jwt-secret-key-32-chars-safe!!")

# Ensure DATABASE_URL is SQLite in-memory unless an explicit PostgreSQL test URL is provided
db_url = os.environ.get("DATABASE_URL", "")
if not db_url or "pooler.supabase.com" in db_url or db_url == "sqlite:///pricing_dashboard.db":
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
