import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException
from sqlalchemy.exc import OperationalError

from app.config.settings import get_config

from app.extensions import init_extensions , db


# =====================================
# IMPORT MODELS
# =====================================

from app.models import *


# =====================================
# IMPORT BLUEPRINTS
# =====================================

from app.routes.auth_routes import auth_bp

from app.routes.product_routes import product_bp

from app.routes.recommendation_routes import recommendation_bp
from app.routes.alert_routes import alert_bp

from app.routes.approval_routes import approval_bp

from app.routes.dashboard_routes import dashboard_bp
from app.routes.chatbot_routes import chatbot_bp
from app.routes.observability_routes import observability_bp
from app.routes.simulation_routes import simulation_bp
from app.routes.startup_routes import startup_bp
from app.routes.webhook_routes import webhook_bp
from app.routes.ab_test_routes import ab_test_bp
from app.routes.agentic_routes import agentic_bp

# =====================================
# CREATE FLASK APP
# =====================================

app = Flask(__name__)


# =====================================
# LOAD CONFIG
# =====================================

app.config.from_object(
    get_config()
)


# =====================================
# INITIALIZE EXTENSIONS & TASK WORKER
# =====================================

init_extensions(app)
if os.environ.get("VERCEL") != "1" or os.environ.get("FLASK_ENV") == "testing":
    from app.services.task_worker import init_worker
    init_worker(app)

from app.services.db_schema_sync import auto_patch_database_schema

if os.environ.get("VERCEL") != "1":
    with app.app_context():
        auto_patch_database_schema(db)

@app.before_request
def ensure_db_schema_ready():
    from flask import request
    if request.path in ("/health", "/"):
        return
    auto_patch_database_schema(db)

# =====================================
# CLEAN JSON ERROR HANDLERS
# =====================================
@app.errorhandler(HTTPException)
def handle_http_error(error):
    return jsonify({"success": False, "message": error.description}), error.code


@app.errorhandler(OperationalError)
def handle_database_error(error):
    app.logger.error("Database connection unavailable for request: %s", error.__class__.__name__)
    return jsonify({"success": False, "message": "Database temporarily unavailable. Please retry shortly."}), 503


@app.errorhandler(Exception)
def handle_unexpected_error(error):
    app.logger.exception("Unhandled application error")
    return jsonify({"success": False, "message": "Internal server error"}), 500


# =====================================
# REGISTER BLUEPRINTS
# =====================================

app.register_blueprint(
    auth_bp,
    url_prefix="/api/auth"
)

app.register_blueprint(
    product_bp,
    url_prefix="/api/products"
)

app.register_blueprint(
    recommendation_bp,
    url_prefix="/api/recommendations"
)

app.register_blueprint(
    alert_bp,
    url_prefix="/api/alerts"
)

app.register_blueprint(
    approval_bp,
    url_prefix="/api/approvals"
)

app.register_blueprint(
    dashboard_bp,
    url_prefix="/api/dashboard"
)

app.register_blueprint(
    chatbot_bp,
    url_prefix="/api/chatbot"
)

app.register_blueprint(
    observability_bp,
    url_prefix="/api/observability"
)

app.register_blueprint(
    simulation_bp,
    url_prefix="/api/simulation"
)

app.register_blueprint(
    startup_bp,
    url_prefix="/api/startup"
)

app.register_blueprint(
    webhook_bp,
    url_prefix="/api/webhooks"
)

app.register_blueprint(
    ab_test_bp,
    url_prefix="/api/ab-test"
)

app.register_blueprint(
    agentic_bp
)


# =====================================
# HOME ROUTE
# =====================================

@app.route("/")
def home():

    return {
        "success": True,
        "message": "Backend running"
    }


@app.route("/health")
def health():
    """Lightweight liveness probe that does not require a database round trip."""
    return {
        "success": True,
        "status": "healthy",
        "database_configured": bool(app.config.get("SQLALCHEMY_DATABASE_URI")),
    }


@app.route("/api/system/sync-schema", methods=["GET", "POST"])
def sync_schema_endpoint():
    """Explicit endpoint to force database schema patch across all tables."""
    import app.services.db_schema_sync as sync_mod
    sync_mod._SCHEMA_PATCHED = False
    auto_patch_database_schema(db)
    return {
        "success": True,
        "message": "Database schema verified and patched successfully."
    }


# =====================================
# RUN SERVER
# =====================================

import os

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    app.run(
        host="0.0.0.0",
        port=port,
        debug=bool(app.config.get("DEBUG", False))
    )