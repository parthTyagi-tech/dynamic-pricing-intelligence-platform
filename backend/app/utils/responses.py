"""
Standardized response helpers used across the app.
Keeps API responses consistent.
"""

from typing import Any, Optional
from flask import jsonify


def success_response(
    arg1: Any = None,
    arg2: Any = None,
    status_code: int = 200,
    **kwargs,
):
    """
    Consolidated success response helper.
    Supports both signatures:
      - success_response(message="Success", data={...}, status_code=200)
      - success_response(data={...}, message="Success", status=200)
    """
    message = "Success"
    data = None
    status = kwargs.get("status", status_code)

    if isinstance(arg1, str) and (arg2 is None or not isinstance(arg2, str)):
        message = arg1
        data = arg2
    elif isinstance(arg1, (dict, list)) or (arg1 is not None and isinstance(arg2, str)):
        data = arg1
        if isinstance(arg2, str):
            message = arg2
    elif arg1 is not None:
        message = str(arg1)
        data = arg2

    if "message" in kwargs:
        message = kwargs["message"]
    if "data" in kwargs:
        data = kwargs["data"]

    response = {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
    }
    return jsonify(response), status


def error_response(
    message: str = "Error",
    status_code: int = 400,
    errors: Any = None,
    **kwargs,
):
    """
    Consolidated error response helper.
    Supports:
      - error_response(message="Error", status_code=400, errors=None)
      - error_response("Not found", 404)
      - error_response("Not found", status=404)
    """
    status = kwargs.get("status", status_code)
    response = {
        "success": False,
        "message": message,
        "data": {},
    }
    if errors:
        response["errors"] = errors
    elif "errors" in kwargs:
        response["errors"] = kwargs["errors"]

    return jsonify(response), status


def paginated_response(
    message: str,
    items: list,
    total: int,
    page: int,
    per_page: int,
    status_code: int = 200,
):
    pages = (total + per_page - 1) // per_page if per_page > 0 else 1
    return jsonify({
        "success": True,
        "message": message,
        "data": {
            "items": items,
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": pages,
                "has_next": (page * per_page) < total,
                "has_prev": page > 1,
            },
        },
    }), status_code