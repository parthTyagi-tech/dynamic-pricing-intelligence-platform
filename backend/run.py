from flask import Flask

from app.config.settings import get_config

from app.extensions import init_extensions


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
# INITIALIZE EXTENSIONS
# =====================================

init_extensions(app)


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

if __name__ == "__main__":

    app.run(debug=True)