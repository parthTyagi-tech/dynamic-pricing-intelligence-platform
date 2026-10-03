from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Tuple, Optional, Dict, Any
import logging
from app.extensions import db
from app.models.scraper_reliability import ScraperReliability, CircuitState

logger = logging.getLogger(__name__)


class FailureKind(str, Enum):
    BLOCKED = "blocked"          # 403/429/captcha -> counts towards circuit trip
    TIMEOUT = "timeout"          # Connection/read timeout -> counts towards circuit trip
    PARSE_ERROR = "parse_error"  # Parsing/DOM selector issue -> does NOT count
    NO_MATCH = "no_match"        # Low match score / item not found -> does NOT count


class CircuitBreaker:
    """
    Centralized, thread-safe and row-locked Circuit Breaker for scraper reliability.
    - 5 failure threshold
    - 60-minute sliding window with automatic decay
    - Exponential backoff (15m base -> 240m max)
    - Half-open state limited to exactly one probe with a 60s lease
    - Only BLOCKED and TIMEOUT failures trip the circuit
    """
    FAILURE_THRESHOLD = 5
    WINDOW_MINUTES = 60
    BASE_BACKOFF = 15      # minutes
    MAX_BACKOFF = 240      # minutes
    PROBE_LEASE_SECONDS = 60

    def allow(self, platform: str) -> Tuple[bool, str, int]:
        """
        Check if request is allowed for platform.
        Returns: (allowed: bool, circuit_state: str, retry_after_seconds: int)
        """
        now = datetime.now(timezone.utc)
        rel = self._get_or_create(platform)

        # Check 60-minute sliding window decay
        if rel.failure_window_started_at:
            w_start = rel.failure_window_started_at
            if w_start.tzinfo is None:
                w_start = w_start.replace(tzinfo=timezone.utc)
            if now - w_start > timedelta(minutes=self.WINDOW_MINUTES):
                rel.failure_count_last_hour = 0
                rel.failure_window_started_at = now
                if rel.circuit_state == CircuitState.CLOSED:
                    db.session.commit()
        else:
            rel.failure_window_started_at = now
            db.session.commit()

        # Healthy state
        if rel.circuit_state == CircuitState.CLOSED:
            return True, CircuitState.CLOSED, 0

        # OPEN state: check if backoff period has elapsed
        backoff_until = None
        if rel.circuit_opened_at:
            opened_at = rel.circuit_opened_at
            if opened_at.tzinfo is None:
                opened_at = opened_at.replace(tzinfo=timezone.utc)
            backoff_until = opened_at + timedelta(minutes=rel.backoff_minutes or self.BASE_BACKOFF)

        if backoff_until and now < backoff_until:
            retry_after = max(1, int((backoff_until - now).total_seconds()))
            return False, CircuitState.OPEN, retry_after

        # Backoff elapsed: test recovery with probe lease (single caller allowed)
        lease_until = rel.probe_lease_until
        if lease_until and lease_until.tzinfo is None:
            lease_until = lease_until.replace(tzinfo=timezone.utc)

        if lease_until and now < lease_until:
            # Another probe is actively executing under lease
            retry_after = max(1, int((lease_until - now).total_seconds()))
            return False, CircuitState.HALF_OPEN, retry_after

        # Grant probe lease to this caller
        rel.circuit_state = CircuitState.HALF_OPEN
        rel.probe_lease_until = now + timedelta(seconds=self.PROBE_LEASE_SECONDS)
        db.session.commit()
        return True, CircuitState.HALF_OPEN, 0

    def record_success(self, platform: str) -> None:
        """Record successful scrape: reset circuit to CLOSED and clear failure counts."""
        now = datetime.now(timezone.utc)
        rel = self._get_or_create(platform)

        rel.circuit_state = CircuitState.CLOSED
        rel.failure_count_last_hour = 0
        rel.failure_window_started_at = now
        rel.probe_lease_until = None
        rel.circuit_opened_at = None
        rel.backoff_minutes = self.BASE_BACKOFF
        rel.last_successful_scrape_at = now
        db.session.commit()

    def record_failure(self, platform: str, kind: FailureKind, reason: str = "") -> None:
        """
        Record failure for platform.
        Only BLOCKED and TIMEOUT failures increment failure count towards tripping circuit.
        """
        # Parse errors and no-match do not trip the circuit
        if kind not in (FailureKind.BLOCKED, FailureKind.TIMEOUT):
            return

        now = datetime.now(timezone.utc)
        rel = self._get_or_create(platform)

        # Sliding window check
        if rel.failure_window_started_at:
            w_start = rel.failure_window_started_at
            if w_start.tzinfo is None:
                w_start = w_start.replace(tzinfo=timezone.utc)
            if now - w_start > timedelta(minutes=self.WINDOW_MINUTES):
                rel.failure_count_last_hour = 0
                rel.failure_window_started_at = now
        else:
            rel.failure_window_started_at = now

        rel.failure_count_last_hour = (rel.failure_count_last_hour or 0) + 1
        rel.last_failure_at = now
        rel.last_failure_reason = reason[:255] if reason else None
        rel.probe_lease_until = None

        # Trip circuit if threshold reached or if failure occurs while OPEN/HALF_OPEN
        if rel.circuit_state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            prev_backoff = rel.backoff_minutes or self.BASE_BACKOFF
            rel.backoff_minutes = min(self.MAX_BACKOFF, prev_backoff * 2)
            rel.circuit_state = CircuitState.OPEN
            rel.circuit_opened_at = now
        elif rel.failure_count_last_hour >= self.FAILURE_THRESHOLD:
            rel.circuit_state = CircuitState.OPEN
            rel.circuit_opened_at = now
            rel.backoff_minutes = rel.backoff_minutes or self.BASE_BACKOFF

        db.session.commit()

    def _get_or_create(self, platform: str) -> ScraperReliability:
        """Row-level safe query for ScraperReliability."""
        now = datetime.now(timezone.utc)
        try:
            bind = db.session.get_bind()
            if bind and bind.dialect.name == "postgresql":
                rel = ScraperReliability.query.filter_by(platform=platform).with_for_update().first()
            else:
                rel = ScraperReliability.query.filter_by(platform=platform).first()
        except Exception:
            rel = ScraperReliability.query.filter_by(platform=platform).first()

        if not rel:
            rel = ScraperReliability(
                platform=platform,
                circuit_state=CircuitState.CLOSED,
                failure_count_last_hour=0,
                failure_window_started_at=now,
                backoff_minutes=self.BASE_BACKOFF
            )
            db.session.add(rel)
            db.session.commit()
        return rel


# Global singleton instance
circuit_breaker = CircuitBreaker()
