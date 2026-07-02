from functools import wraps
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request
from flask import jsonify
from app.models.user import User, UserRole


def admin_required():
    """
    Flask decorator that ensures the authenticated JWT user possesses
    admin role status. Returns 403 Forbidden otherwise.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            verify_jwt_in_request()
            current_user_id = get_jwt_identity()
            user = User.query.get(current_user_id)
            
            if not user or user.role != UserRole.ADMIN:
                return jsonify({
                    "success": False,
                    "message": "Admin authorization privileges required for this action."
                }), 403
                
            return fn(*args, **kwargs)
        return wrapper
    return decorator
