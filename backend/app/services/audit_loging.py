from typing import Optional, Any, Dict
from app.extensions import db
from app.models.audit import AuditLog


def log_action(
    organization_id: str,
    action: str,
    user_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
):
    """Create an audit log entry. Call within an active app context."""
    try:
        entry = AuditLog(
            user_id=user_id,
            organization_id=organization_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            metadata=metadata or {},
        )
        db.session.add(entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"[AuditLog] Failed to write audit log: {e}")