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
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc), nullable=False)

    def to_dict(self):
        return {
            "platform": self.platform,
            "failure_count_last_hour": self.failure_count_last_hour,
            "last_failure_at": self.last_failure_at.isoformat() if self.last_failure_at else None,
            "last_failure_reason": self.last_failure_reason,
            "circuit_state": self.circuit_state,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
