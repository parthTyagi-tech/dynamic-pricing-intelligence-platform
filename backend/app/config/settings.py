from dotenv import load_dotenv
load_dotenv()
import os
import secrets
from datetime import timedelta
from dotenv import load_dotenv
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def _secret_value(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value
    if os.environ.get("FLASK_ENV", "development") == "production":
        raise RuntimeError(f"{name} must be configured in production")
    return secrets.token_urlsafe(32)


class BaseConfig:
    SECRET_KEY = _secret_value("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
    }

    # JWT
    JWT_SECRET_KEY = _secret_value("JWT_SECRET_KEY")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRES", 3600))
    )
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(
        seconds=int(os.environ.get("JWT_REFRESH_TOKEN_EXPIRES", 2592000))
    )
    JWT_BLACKLIST_ENABLED = True
    JWT_BLACKLIST_TOKEN_CHECKS = ["access", "refresh"]

    # CORS
    CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

    # AI
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")
    AI_PROVIDER = os.environ.get("AI_PROVIDER", "groq")

    # OAuth
    GOOGLE_OAUTH_CLIENT_ID = os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET", "")

    # Twilio / WhatsApp
    TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN", "")
    TWILIO_WHATSAPP_FROM = os.environ.get("TWILIO_WHATSAPP_FROM", "whatsapp:+14155238886")

    # Mock platform
    MOCK_PLATFORM_FAILURE_RATE = float(
        os.environ.get("MOCK_PLATFORM_FAILURE_RATE", 0.1)
    )


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    
    _dev_db_url = os.environ.get(
        "DATABASE_URL", "sqlite:///pricing_dashboard.db"
    )
    if _dev_db_url:
        if _dev_db_url.startswith("postgres://"):
            _dev_db_url = _dev_db_url.replace("postgres://", "postgresql://", 1)
        _dev_db_url = _dev_db_url.replace("?pgbouncer=true", "")
        _dev_db_url = _dev_db_url.replace("&pgbouncer=true", "")
        
    SQLALCHEMY_DATABASE_URI = _dev_db_url
    SQLALCHEMY_ECHO = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SECRET_KEY = _secret_value("SECRET_KEY")
    JWT_SECRET_KEY = _secret_value("JWT_SECRET_KEY")
    
    _db_url = os.environ.get("DATABASE_URL")
    if _db_url:
        if _db_url.startswith("postgres://"):
            _db_url = _db_url.replace("postgres://", "postgresql://", 1)
        _db_url = _db_url.replace("?pgbouncer=true", "")
        _db_url = _db_url.replace("&pgbouncer=true", "")
        
    SQLALCHEMY_DATABASE_URI = _db_url
    SQLALCHEMY_ECHO = False


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}


def get_config():
    env = os.environ.get("FLASK_ENV", "development")
    return config_map.get(env, DevelopmentConfig)