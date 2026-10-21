import os
from app import create_app
from app.models import *  # noqa: F401, F403
from app.extensions import db  # noqa: F401

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=bool(app.config.get("DEBUG", False)),
        use_reloader=False
    )