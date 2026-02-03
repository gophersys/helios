from typing import List, Optional, Sequence, Tuple

from .types import ErrorDetail


def require_json(data) -> Optional[ErrorDetail]:
    if data is None:
        return ErrorDetail(message="Request body must contain JSON data")
    return None


def require_fields(data: dict, fields: Sequence[str]) -> Optional[ErrorDetail]:
    for f in fields:
        if not data.get(f):
            return ErrorDetail(message=f"Field '{f}' is required", field=f)
    return None


def require_fields_all(data: dict, fields: Sequence[str]) -> List[ErrorDetail]:
    errors = []
    for f in fields:
        if not data.get(f):
            errors.append(ErrorDetail(message=f"Field '{f}' is required", field=f))
    return errors


def parse_enum(value: str, allowed: Sequence[str], field_name: str) -> Optional[ErrorDetail]:
    if value not in allowed:
        return ErrorDetail(
            message=f"{field_name} must be one of: {', '.join(allowed)}",
            field=field_name,
        )
    return None
