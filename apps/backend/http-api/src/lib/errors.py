from typing import List, Optional, Tuple

from flask import jsonify

from .types import ApiResponse, ErrorDetail


def bad_request(msg: str, field: Optional[str] = None) -> Tuple:
    resp = ApiResponse.error(ErrorDetail(message=msg, field=field))
    return jsonify(resp.to_dict()), 400


def unauthorized(msg: str) -> Tuple:
    resp = ApiResponse.error(ErrorDetail(message=msg))
    return jsonify(resp.to_dict()), 401


def forbidden(msg: str) -> Tuple:
    resp = ApiResponse.error(ErrorDetail(message=msg))
    return jsonify(resp.to_dict()), 403


def not_found(msg: str) -> Tuple:
    resp = ApiResponse.error(ErrorDetail(message=msg))
    return jsonify(resp.to_dict()), 404


def conflict(msg: str) -> Tuple:
    resp = ApiResponse.error(ErrorDetail(message=msg))
    return jsonify(resp.to_dict()), 409


def internal_error(msg: str) -> Tuple:
    resp = ApiResponse.error(ErrorDetail(message=msg))
    return jsonify(resp.to_dict()), 500


def validation_errors(errors: List[ErrorDetail]) -> Tuple:
    resp = ApiResponse.error(*errors)
    return jsonify(resp.to_dict()), 400
