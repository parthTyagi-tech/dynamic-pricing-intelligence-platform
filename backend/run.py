from flask import Flask

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

from app.routes.approval_routes import approval_bp

from app.routes.dashboard_routes import dashboard_bp
from app.routes.chatbot_routes import chatbot_bp
from app.routes.observability_routes import observability_bp
from app.routes.simulation_routes import simulation_bp
from app.routes.startup_routes import startup_bp
from app.routes.webhook_routes import webhook_bp
from app.routes.ab_test_routes import ab_test_bp

from flask_cors import CORS
# =====================================
# CREATE FLASK APP
# =====================================

app = Flask(__name__)
CORS(app, supports_credentials=True)


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
from app.services.task_worker import init_worker
init_worker(app)

with app.app_context():
    db.create_all()

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


# =====================================
# HOME ROUTE
# =====================================

@app.route("/")
def home():

    return {
        "success": True,
        "message": "Backend running"
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
        debug=True
    )