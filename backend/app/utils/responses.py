from flask import jsonify
from typing import Any, Optional


def success_response(message: str = "Success", data: Any = None, status_code: int = 200):
    response = {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
    }
    return jsonify(response), status_code


def error_response(message: str = "Error", status_code: int = 400, errors: Any = None):
    response = {
        "success": False,
        "message": message,
        "data": {},
    }
    if errors:
        response["errors"] = errors
    return jsonify(response), status_code


def paginated_response(
    message: str,
    items: list,
    total: int,
    page: int,
    per_page: int,
    status_code: int = 200,
):
    return jsonify({
        "success": True,
        "message": message,
        "data": {
            "items": items,
            "pagination": {
                "total": total,
                "page": page,
                "per_page": per_page,
                "pages": (total + per_page - 1) // per_page,
                "has_next": (page * per_page) < total,
                "has_prev": page > 1,
            },
        },
    }), status_code