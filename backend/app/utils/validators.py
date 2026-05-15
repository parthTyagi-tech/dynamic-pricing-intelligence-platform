import re
from typing import Dict, List, Tuple, Any


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
    return bool(re.match(pattern, email))


def validate_password(password: str) -> Tuple[bool, str]:
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    return True, ""


def validate_required_fields(data: Dict[str, Any], required: List[str]) -> Tuple[bool, List[str]]:
    missing = [field for field in required if not data.get(field)]
    return len(missing) == 0, missing


def validate_positive_number(value: Any, field_name: str) -> Tuple[bool, str]:
    try:
        num = float(value)
        if num <= 0:
            return False, f"{field_name} must be a positive number"
        return True, ""
    except (TypeError, ValueError):
        return False, f"{field_name} must be a valid number"