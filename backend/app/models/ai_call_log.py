import uuid
from datetime import datetime
from app.extensions import db


class AICallLog(db.Model):
    __tablename__ = "ai_call_logs"

    id = db.Column(
        db.String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4())
    )
    timestamp = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        index=True
    )
    user_id = db.Column(
        db.String(36),
        db.ForeignKey("users.id"),
        nullable=True
    )
    organization_id = db.Column(
        db.String(36),
        db.ForeignKey("organizations.id"),
        nullable=True
    )
    agent_name = db.Column(
        db.String(100),
        nullable=False
    )
    model_name = db.Column(
        db.String(100),
        nullable=False
    )
    prompt_tokens = db.Column(
        db.Integer,
        default=0
    )
    completion_tokens = db.Column(
        db.Integer,
        default=0
    )
    total_tokens = db.Column(
        db.Integer,
        default=0
    )
    latency_ms = db.Column(
        db.Integer,
        default=0
    )
    cost = db.Column(
        db.Float,
        default=0.0
    )
    status = db.Column(
        db.String(20),
        default="success"
    )
    error_message = db.Column(
        db.Text,
        nullable=True
    )

    def to_dict(self):
        return {
            "id": self.id,
            "timestamp": self.timestamp.isoformat(),
            "user_id": self.user_id,
            "organization_id": self.organization_id,
            "agent_name": self.agent_name,
            "model_name": self.model_name,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "latency_ms": self.latency_ms,
            "cost": self.cost,
            "status": self.status,
            "error_message": self.error_message
        }
