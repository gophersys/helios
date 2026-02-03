from functools import wraps

from flask import g, jsonify, request

from src.services.auth.jwt import verify_token


def require_auth(f):
    """Verify JWT and attach current_user to Flask g."""

    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization")
        if not auth_header or not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid authorization header"}), 401

        token = auth_header.split(" ", 1)[1]
        payload, error = verify_token(token)
        if error:
            return jsonify({"error": error}), 401

        g.current_user = payload
        return f(*args, **kwargs)

    return decorated


def require_role(*roles):
    """Check that the authenticated user has one of the given roles.
    Must be applied AFTER @require_auth."""

    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            user = getattr(g, "current_user", None)
            if not user:
                return jsonify({"error": "Unauthorized"}), 401
            if user["role"] not in roles:
                return jsonify({"error": "Forbidden"}), 403
            return f(*args, **kwargs)

        return decorated

    return decorator
