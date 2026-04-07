from typing import List, Optional, Tuple

from flask import jsonify

from .types import ApiResponse, ErrorDetail


def bad_request(msg: str, field: Optional[str] = None) -> Tuple:
    """Return a 400 Bad Request JSON response.

    Args:
        msg: Human-readable error message.
        field: Optional field name that caused the error.

    Returns:
        Flask (response, 400) tuple.
    """
    resp = ApiResponse.error(ErrorDetail(message=msg, field=field))
    return jsonify(resp.to_dict()), 400


def unauthorized(msg: str) -> Tuple:
    """Return a 401 Unauthorized JSON response.

    Args:
        msg: Human-readable error message.

    Returns:
        Flask (response, 401) tuple.
    """
    resp = ApiResponse.error(ErrorDetail(message=msg))
    return jsonify(resp.to_dict()), 401


def forbidden(msg: str) -> Tuple:
    """Return a 403 Forbidden JSON response.

    Args:
        msg: Human-readable error message.

    Returns:
        Flask (response, 403) tuple.
    """
    resp = ApiResponse.error(ErrorDetail(message=msg))
    return jsonify(resp.to_dict()), 403


def not_found(msg: str) -> Tuple:
    """Return a 404 Not Found JSON response.

    Args:
        msg: Human-readable error message.

    Returns:
        Flask (response, 404) tuple.
    """
    resp = ApiResponse.error(ErrorDetail(message=msg))
    return jsonify(resp.to_dict()), 404


def conflict(msg: str) -> Tuple:
    """Return a 409 Conflict JSON response.

    Args:
        msg: Human-readable error message.

    Returns:
        Flask (response, 409) tuple.
    """
    resp = ApiResponse.error(ErrorDetail(message=msg))
    return jsonify(resp.to_dict()), 409


def internal_error(msg: str) -> Tuple:
    """Return a 500 Internal Server Error JSON response.

    Args:
        msg: Human-readable error message.

    Returns:
        Flask (response, 500) tuple.
    """
    resp = ApiResponse.error(ErrorDetail(message=msg))
    return jsonify(resp.to_dict()), 500


def validation_errors(errors: List[ErrorDetail]) -> Tuple:
    """Return a 400 Bad Request JSON response with multiple validation errors.

    Args:
        errors: List of ErrorDetail instances describing each validation failure.

    Returns:
        Flask (response, 400) tuple.
    """
    resp = ApiResponse.error(*errors)
    return jsonify(resp.to_dict()), 400
