import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent / "backend"
sys.path.insert(0, str(backend_dir))

from run import app  # noqa: E402,F401

__all__ = ["app"]
