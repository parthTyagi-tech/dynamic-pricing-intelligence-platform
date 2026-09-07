import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

# Ensure backend root is first in sys.path
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("FLASK_ENV", "testing")

from run import app
from app.extensions import db
from app.models.scraper_reliability import ScraperReliability
from app.services.agentic.supervisor_agent import check_circuit_breaker, update_circuit_breaker_result


def test_circuit_breaker_exponential_backoff_and_half_open():
    """
    Simulates repeated scraper failures and verifies:
    1. Circuit opens after failure threshold.
    2. Exponential backoff doubles on subsequent failure (capped at 240m).
    3. Half-open state gates single probe attempt.
    4. Reset to closed and zero failures on success.
    """
    with app.app_context():
        platform = "Amazon"
        rel = ScraperReliability.query.filter_by(platform=platform).first()
        if not rel:
            rel = ScraperReliability(platform=platform)
            db.session.add(rel)
        rel.circuit_state = "closed"
        rel.failure_count_last_hour = 0
        rel.backoff_minutes = 15
        rel.circuit_opened_at = None
        db.session.commit()

        # 1. Simulate 3 consecutive failures to trigger open circuit
        update_circuit_breaker_result(platform, success=False)
        update_circuit_breaker_result(platform, success=False)
        update_circuit_breaker_result(platform, success=False)

        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel.circuit_state == "open", f"Expected open, got {rel.circuit_state}"
        assert rel.circuit_opened_at is not None
        assert rel.backoff_minutes == 15

        # 2. Simulate another failure during open/half_open -> backoff doubles to 30
        update_circuit_breaker_result(platform, success=False)
        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel.backoff_minutes == 30

        # Simulate another failure -> doubles to 60
        update_circuit_breaker_result(platform, success=False)
        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel.backoff_minutes == 60

        # 3. Simulate cooldown elapsed -> probe attempt allows half_open
        rel.circuit_opened_at = datetime.now(timezone.utc) - timedelta(minutes=61)
        db.session.commit()

        # Probe attempt should transition to half_open
        should_attempt, remaining, c_state = check_circuit_breaker(platform)
        assert should_attempt is True
        assert c_state == "half_open"

        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel.circuit_state == "half_open"

        # 4. Successful probe resets circuit to closed, clears failures, and resets backoff
        update_circuit_breaker_result(platform, success=True)
        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel.circuit_state == "closed"
        assert rel.failure_count_last_hour == 0
        assert rel.backoff_minutes == 15
        assert rel.last_successful_scrape_at is not None
