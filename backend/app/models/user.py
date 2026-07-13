import uuid
import bcrypt
from datetime import datetime, timezone
from app.extensions import db


class UserRole:
    ADMIN = "admin"
    ANALYST = "analyst"

    ALL = [ADMIN, ANALYST]


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=True)
    oauth_provider = db.Column(db.String(64), nullable=True)
    oauth_id = db.Column(db.String(255), nullable=True)
    role = db.Column(db.String(32), nullable=False, default=UserRole.ANALYST)
    organization_id = db.Column(
        db.String(36), db.ForeignKey("organizations.id"), nullable=False, index=True
    )
    phone_number = db.Column(db.String(20), nullable=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Relationships
    organization = db.relationship("Organization", back_populates="users")
    approval_actions = db.relationship("ApprovalAction", back_populates="approver", lazy="dynamic")
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")

    def set_password(self, password: str):
        salt = bcrypt.gensalt()
        self.password_hash = bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")

    def check_password(self, password: str) -> bool:
        if not self.password_hash:
            return False
        return bcrypt.checkpw(password.encode("utf-8"), self.password_hash.encode("utf-8"))

    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    def is_analyst(self) -> bool:
        return self.role == UserRole.ANALYST

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone_number": self.phone_number,
            "role": self.role,
            "organization_id": self.organization_id,
            "organization_name": self.organization.name if self.organization else None,
            "onboarding_completed": self.organization.onboarding_completed if self.organization else True,
            "store_platform": self.organization.store_platform if self.organization else None,
            "store_domain": self.organization.store_domain if self.organization else None,
            "oauth_provider": self.oauth_provider,
            "created_at": self.created_at.isoformat(),
        }