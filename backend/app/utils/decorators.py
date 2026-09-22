"""
backend/app/utils/decorators.py

Re-exports authorization decorators from app.middleware.auth_middleware
to maintain a single source of truth for authorization and tenant context.
"""

from app.middleware.auth_middleware import admin_required

__all__ = ["admin_required"]
