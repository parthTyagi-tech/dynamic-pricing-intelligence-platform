from flask import request


def get_pagination_params(default_per_page: int = 20, max_per_page: int = 100):
    """Extract and validate pagination params from request args."""
    try:
        page = max(1, int(request.args.get("page", 1)))
    except (ValueError, TypeError):
        page = 1

    try:
        per_page = min(max_per_page, max(1, int(request.args.get("per_page", default_per_page))))
    except (ValueError, TypeError):
        per_page = default_per_page

    return page, per_page


def paginate_query(query, page: int, per_page: int):
    """Apply pagination to a SQLAlchemy query. Returns (items, total)."""
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return items, total