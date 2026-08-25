"""Vercel Python runtime entrypoint for the Flask API."""

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Vercel provides the production environment and database URL at deploy time.
os.environ.setdefault("FLASK_ENV", "production")

from run import app  # noqa: E402,F401

__all__ = ["app"]
