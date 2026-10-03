import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("FLASK_ENV", "testing")

from run import app
from app.extensions import db
from app.models.scraper_reliability import ScraperReliability, CircuitState
from app.services.agentic.circuit_breaker import circuit_breaker, FailureKind


def test_parse_and_no_match_errors_do_not_trip_circuit():
    """
    Validation / parsing errors and no-match results must NEVER count
    towards circuit breaker trips. Only BLOCKED and TIMEOUT trip it.
    """
    with app.app_context():
        platform = "TestPlatform_ParseErrors"
        rel = ScraperReliability.query.filter_by(platform=platform).first()
        if not rel:
            rel = ScraperReliability(platform=platform)
            db.session.add(rel)
        rel.circuit_state = CircuitState.CLOSED
        rel.failure_count_last_hour = 0
        rel.backoff_minutes = 15
        rel.circuit_opened_at = None
        db.session.commit()

        # Record 10 parse errors and 10 no-match errors
        for _ in range(10):
            circuit_breaker.record_failure(platform, kind=FailureKind.PARSE_ERROR, reason="DOM selector changed")
            circuit_breaker.record_failure(platform, kind=FailureKind.NO_MATCH, reason="Item not found")

        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel.circuit_state == CircuitState.CLOSED
        assert rel.failure_count_last_hour == 0

        allowed, state, retry_after = circuit_breaker.allow(platform)
        assert allowed is True
        assert state == CircuitState.CLOSED
        assert retry_after == 0


def test_open_circuit_concurrent_callers_yield_exactly_one_probe_lease():
    """
    When backoff period elapses, the circuit allows exactly one caller
    to execute a canary probe via probe_lease_until. Any concurrent caller
    is denied until the lease expires or succeeds/fails.
    """
    with app.app_context():
        platform = "TestPlatform_ProbeLease"
        rel = ScraperReliability.query.filter_by(platform=platform).first()
        if not rel:
            rel = ScraperReliability(platform=platform)
            db.session.add(rel)
        rel.circuit_state = CircuitState.OPEN
        rel.failure_count_last_hour = 5
        rel.backoff_minutes = 15
        # Set opened_at to 20 minutes ago (backoff of 15m has elapsed)
        rel.circuit_opened_at = datetime.now(timezone.utc) - timedelta(minutes=20)
        rel.probe_lease_until = None
        db.session.commit()

        # Caller 1 requests access: must obtain probe lease in HALF_OPEN
        allowed1, state1, retry_after1 = circuit_breaker.allow(platform)
        assert allowed1 is True
        assert state1 == CircuitState.HALF_OPEN
        assert retry_after1 == 0

        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel.circuit_state == CircuitState.HALF_OPEN
        assert rel.probe_lease_until is not None

        # Caller 2 requests access immediately while probe lease is active: must be DENIED
        allowed2, state2, retry_after2 = circuit_breaker.allow(platform)
        assert allowed2 is False
        assert state2 == CircuitState.HALF_OPEN
        assert retry_after2 > 0  # Seconds remaining on probe lease


def test_sliding_window_failure_decay_after_60_minutes():
    """
    Failures older than 60 minutes decay to 0 and do not contribute
    towards tripping the circuit.
    """
    with app.app_context():
        platform = "TestPlatform_Decay"
        rel = ScraperReliability.query.filter_by(platform=platform).first()
        if not rel:
            rel = ScraperReliability(platform=platform)
            db.session.add(rel)
        rel.circuit_state = CircuitState.CLOSED
        rel.failure_count_last_hour = 4
        rel.failure_window_started_at = datetime.now(timezone.utc) - timedelta(minutes=65)
        db.session.commit()

        # Calling allow() triggers window decay
        allowed, state, _ = circuit_breaker.allow(platform)
        assert allowed is True
        assert state == CircuitState.CLOSED

        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel.failure_count_last_hour == 0

        # Now 1 failure will not trip the breaker
        circuit_breaker.record_failure(platform, kind=FailureKind.BLOCKED, reason="HTTP 429")
        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel.circuit_state == CircuitState.CLOSED
        assert rel.failure_count_last_hour == 1


def test_skipped_platforms_do_not_double_backoff():
    """
    When a platform is skipped because the circuit is OPEN,
    its backoff time must NOT increase or double.
    """
    with app.app_context():
        platform = "TestPlatform_NoSkipDoubling"
        rel = ScraperReliability.query.filter_by(platform=platform).first()
        if not rel:
            rel = ScraperReliability(platform=platform)
            db.session.add(rel)
        rel.circuit_state = CircuitState.OPEN
        rel.failure_count_last_hour = 5
        rel.backoff_minutes = 15
        rel.circuit_opened_at = datetime.now(timezone.utc) - timedelta(minutes=5)
        rel.probe_lease_until = None
        db.session.commit()

        initial_backoff = rel.backoff_minutes

        # Check circuit multiple times (simulating skipped runs in supervisor)
        for _ in range(5):
            allowed, state, retry_after = circuit_breaker.allow(platform)
            assert allowed is False
            assert state == CircuitState.OPEN
            assert retry_after > 0

        rel = ScraperReliability.query.filter_by(platform=platform).first()
        assert rel.backoff_minutes == initial_backoff == 15
