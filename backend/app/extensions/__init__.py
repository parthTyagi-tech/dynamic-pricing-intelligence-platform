from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from flask_migrate import Migrate
from flask_cors import CORS

db = SQLAlchemy()

jwt = JWTManager()

migrate = Migrate()

cors = CORS()

# Temporary in-memory token blacklist
# (Use Redis in production)
token_blocklist = set()


def init_extensions(app):

    # Initialize database
    db.init_app(app)

    # Initialize JWT
    jwt.init_app(app)

    # Initialize migrations
    migrate.init_app(app, db)

    # Initialize CORS
    cors.init_app(
        app,
        resources={
    r"/api/*": {
        "origins": [
            "http://localhost:5173"
        ]
    }
},
        supports_credentials=True,
    )

    # JWT token blacklist check
   # @jwt.token_in_blocklist_loader
    #def check_if_token_revoked(jwt_header, jwt_payload):

      #  jti = jwt_payload["jti"]

       # return jti in token_blocklist

    # Revoked token handler
    @jwt.revoked_token_loader
    def revoked_token_callback(jwt_header, jwt_payload):

        from app.utils.responses import error_response

        return error_response(
            "Token has been revoked",
            401
        )

    # Expired token handler
    @jwt.expired_token_loader
    def expired_token_callback(jwt_header, jwt_payload):

        from app.utils.responses import error_response

        return error_response(
            "Token has expired",
            401
        )

    # Invalid token handler
    @jwt.invalid_token_loader
    def invalid_token_callback(error):

        from app.utils.responses import error_response

        return error_response(
            "Invalid token",
            401
        )

    # Missing token handler
    @jwt.unauthorized_loader
    def missing_token_callback(error):

        from app.utils.responses import error_response

        return error_response(
            "Authorization token is required",
            401
        )