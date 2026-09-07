import os
import sys
from pathlib import Path
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.agentic.scrapers.platform_scrapers import (
    UnknownPlatformError,
    get_scraper_for_platform,
    PLATFORM_SCRAPERS,
)
from app.services.agentic.supervisor_agent import SupervisorAgent


def test_unknown_platform_raises_error_not_silent_fallback():
    """
    Problem 2: Unrecognized platform names must fail loudly with UnknownPlatformError.
    Never silently fallback or auto-register Amazon.
    """
    invalid_names = ["UnknownShop", "random_marketplace", "amazn_typo", "ebay_unsupported"]

    for name in invalid_names:
        with pytest.raises(UnknownPlatformError) as excinfo:
            get_scraper_for_platform(name)
        assert "is not a registered scraper platform" in str(excinfo.value)
        assert "Valid platforms" in str(excinfo.value)


def test_supervisor_rejects_unknown_target_platforms():
    """
    SupervisorAgent must reject target_platforms containing unknown platforms.
    """
    supervisor = SupervisorAgent()
    with pytest.raises(UnknownPlatformError) as excinfo:
        supervisor._validate_platforms(["Amazon", "invalid_store"])
    assert "invalid_store" in str(excinfo.value)
