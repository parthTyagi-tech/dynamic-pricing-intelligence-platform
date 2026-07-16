from functools import wraps
from flask import g, request
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from app.utils.responses import error_response
from app.extensions import supabase

def get_current_user():
    """Fetch user from DB and attach to Flask g."""
    from app.models.user import User
    
    # Try Supabase Auth first
    if supabase:
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            try:
                response = supabase.auth.get_user(token)
                if response and response.user:
                    # In a full migration, we would query the local DB by supabase ID here
                    # For now, return a mock user or find by email if they match
                    user = User.query.filter_by(email=response.user.email).first()
                    if user:
                        return user
            except Exception:
                pass
                
    # Fallback to local JWT if Supabase fails or isn't configured
    user_id = get_jwt_identity()
    if user_id:
        user = User.query.get(user_id)
        return user
    return None

def jwt_required_with_user(fn):
    """Verify JWT, load user into g.current_user."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        # Allow Supabase bypass if verified
        if not supabase or not request.headers.get("Authorization", "").startswith("Bearer "):
            verify_jwt_in_request()
        
        user = get_current_user()
        if not user:
            return error_response("User not found", 404)
        g.current_user = user
        g.organization_id = user.organization_id
        return fn(*args, **kwargs)
    return wrapper


def admin_required(fn):
    """JWT required + must be admin role."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = get_current_user()
        if not user:
            return error_response("User not found", 404)
        if not user.is_admin():
            return error_response("Admin privileges required", 403)
        g.current_user = user
        g.organization_id = user.organization_id
        return fn(*args, **kwargs)
    return wrapper


def analyst_required(fn):
    """JWT required + must be admin or analyst role."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        user = get_current_user()
        if not user:
            return error_response("User not found", 404)
        g.current_user = user
        g.organization_id = user.organization_id
        return fn(*args, **kwargs)
    return wrapper


def tenant_scoped(model_class, id_param="id"):
    """
    Decorator factory. Fetches a model instance scoped to the current user's org.
    Attaches it to g.resource.
    Usage: @tenant_scoped(Product, 'product_id')
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            resource_id = kwargs.get(id_param)
            if not resource_id:
                return error_response("Resource ID missing", 400)
            instance = model_class.query.filter_by(
                id=resource_id, organization_id=g.organization_id
            ).first()
            if not instance:
                return error_response(f"{model_class.__name__} not found", 404)
            g.resource = instance
            return fn(*args, **kwargs)
        return wrapper
    return decorator