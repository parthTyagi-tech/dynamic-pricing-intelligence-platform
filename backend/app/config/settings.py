from dotenv import load_dotenv
load_dotenv()
import os
import secrets
from datetime import timedelta
from urllib.parse import quote, unquote, urlsplit, urlunsplit
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


def _normalize_database_url(raw_url: str | None) -> str | None:
    """Normalize hosted PostgreSQL URLs for short-lived Vercel functions.

    Supabase's direct `db.<project>.supabase.co` hostname can resolve only to
    IPv6 in some regions. Vercel functions need the IPv4-compatible pooler.
    The password remains entirely in the URL and is never logged.
    """
    if not raw_url:
        return raw_url
    url = raw_url.replace("postgres://", "postgresql://", 1)
    url = url.replace("?pgbouncer=true", "").replace("&pgbouncer=true", "")
    parsed = urlsplit(url)
    host = parsed.hostname or ""
    if host.startswith("db.") and host.endswith(".supabase.co"):
        project_ref = host[3:].split(".", 1)[0]
        region = os.environ.get("SUPABASE_POOLER_REGION", "ap-southeast-2")
        pooler_host = os.environ.get("SUPABASE_POOLER_HOST", f"aws-0-{region}.pooler.supabase.com")
        pooler_port = int(os.environ.get("SUPABASE_POOLER_PORT", "6543"))
        username = parsed.username or "postgres"
        if username == "postgres":
            username = f"postgres.{project_ref}"
        password = unquote(parsed.password or "")
        auth = quote(username, safe="")
        if password:
            auth = f"{auth}:{quote(password, safe='')}"
        netloc = f"{auth}@{pooler_host}:{pooler_port}"
        return urlunsplit((parsed.scheme, netloc, parsed.path or "/postgres", parsed.query, parsed.fragment))
    return url


class ProductionConfig(BaseConfig):
    DEBUG = False
    SECRET_KEY = _secret_value("SECRET_KEY")
    JWT_SECRET_KEY = _secret_value("JWT_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_ENGINE_OPTIONS = {
        **BaseConfig.SQLALCHEMY_ENGINE_OPTIONS,
        # Vercel may overlap status polling, task callbacks, and auth queries
        # within one warm instance. A single connection with no overflow causes
        # QueuePool timeout errors during normal asynchronous polling.
        "pool_size": int(os.environ.get("DB_POOL_SIZE", "2")),
        "max_overflow": int(os.environ.get("DB_MAX_OVERFLOW", "4")),
        "pool_timeout": int(os.environ.get("DB_POOL_TIMEOUT", "30")),
        "connect_args": {"sslmode": "require"},
    }
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