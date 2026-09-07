from datetime import datetime, timezone
from app.extensions import db


class CircuitState:
    CLOSED = "closed"       # Healthy, traffic allowed
    OPEN = "open"           # Tripped, platform skipped immediately
    HALF_OPEN = "half_open" # Testing recovery with a single probe request

    ALL = [CLOSED, OPEN, HALF_OPEN]


class ScraperReliability(db.Model):
    """
    Tracks per-platform reliability and circuit breaker status (Gap #7).
    When failure_count_last_hour exceeds threshold (e.g. 5 consecutive/recent blocks),
    circuit_state flips to OPEN to skip further calls and save costs.
    """
    __tablename__ = "scraper_reliability"

    platform = db.Column(db.String(64), primary_key=True)
    failure_count_last_hour = db.Column(db.Integer, nullable=False, default=0)
    last_failure_at = db.Column(db.DateTime, nullable=True)
    last_failure_reason = db.Column(db.String(255), nullable=True)
    circuit_state = db.Column(db.String(16), nullable=False, default=CircuitState.CLOSED)
    circuit_opened_at = db.Column(db.DateTime, nullable=True)
    backoff_minutes = db.Column(db.Integer, nullable=False, default=15)
    last_successful_scrape_at = db.Column(db.DateTime, nullable=True)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    @property
    def platform_name(self):
        return self.platform

    @property
    def total_failures(self):
        return self.failure_count_last_hour or 0

    @property
    def total_successes(self):
        return 1 if self.last_successful_scrape_at else 0

    def to_dict(self):
        return {
            "platform": self.platform,
            "failure_count_last_hour": self.failure_count_last_hour,
            "last_failure_at": self.last_failure_at.isoformat() if self.last_failure_at else None,
            "last_failure_reason": self.last_failure_reason,
            "circuit_state": self.circuit_state,
            "circuit_opened_at": self.circuit_opened_at.isoformat() if self.circuit_opened_at else None,
            "backoff_minutes": self.backoff_minutes,
            "last_successful_scrape_at": self.last_successful_scrape_at.isoformat() if self.last_successful_scrape_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class ScraperHealthCheckLog(db.Model):
    """
    Records canary check results separately from user-triggered task history (source: 'health_check').
    """
    __tablename__ = "scraper_health_check_logs"

    id = db.Column(db.String(36), primary_key=True)
    platform = db.Column(db.String(64), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False)  # "success", "failed", "circuit_open"
    latency_ms = db.Column(db.Float, nullable=False, default=0.0)
    source = db.Column(db.String(32), nullable=False, default="health_check")
    details = db.Column(db.JSON, nullable=True)
    checked_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "platform": self.platform,
            "status": self.status,
            "latency_ms": self.latency_ms,
            "source": self.source,
            "details": self.details,
            "checked_at": self.checked_at.isoformat() if self.checked_at else None,
        }

