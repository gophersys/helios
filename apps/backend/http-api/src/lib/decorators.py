import hashlib
import threading
import time
from datetime import datetime, timezone
from functools import wraps

from flask import g, request

from src.lib.errors import forbidden, unauthorized
from src.services.auth.jwt import verify_token
from src.services.database.prisma import get_db_client

# In-memory permission set cache: {permissionSetId: (permissions_list, fetched_at)}
_permission_set_cache: dict[str, tuple[list[str], float]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL_SECONDS = 60


def invalidate_permission_set_cache(permission_set_id: str | None = None):
    """Invalidate cached permission set(s). Call on update/delete."""
    with _cache_lock:
        if permission_set_id:
            _permission_set_cache.pop(permission_set_id, None)
        else:
            _permission_set_cache.clear()


def _get_permissions_for_set(permission_set_id: str) -> list[str] | None:
    """Load permission set permissions from cache or DB."""
    now = time.time()
    with _cache_lock:
        cached = _permission_set_cache.get(permission_set_id)
        if cached and (now - cached[1]) < _CACHE_TTL_SECONDS:
            return cached[0]

    db = get_db_client()
    perm_set = db.permissionset.find_unique(where={"id": permission_set_id})
    if not perm_set:
        return None

    with _cache_lock:
        _permission_set_cache[permission_set_id] = (perm_set.permissions, now)
    return perm_set.permissions


def require_auth(f):
    """Verify JWT or API key and attach current_user to Flask g.
    When AUTH_ENABLED is false, all requests get a default admin identity."""

    @wraps(f)
    def decorated(*args, **kwargs):
        from config import env_config

        if not env_config.AUTH_ENABLED:
            g.current_user = {
                "sub": "00000000-0000-0000-0000-000000000000",
                "email": "admin@concord.local",
                "name": "Admin (auth disabled)",
                "permissionSetId": None,
            }
            return f(*args, **kwargs)

        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return unauthorized("Missing authorization header")

        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ", 1)[1]
            payload, error = verify_token(token)
            if error:
                return unauthorized(error)
            g.current_user = payload

        elif auth_header.startswith("ApiKey "):
            raw_key = auth_header.split(" ", 1)[1]
            key_hash = hashlib.sha256(raw_key.encode()).hexdigest()

            db = get_db_client()
            api_key = db.apikey.find_unique(
                where={"keyHash": key_hash},
                include={"user": {"include": {"permissionSet": True}}},
            )

            if not api_key:
                return unauthorized("Invalid API key")

            if api_key.expiresAt and api_key.expiresAt.timestamp() < time.time():
                return unauthorized("API key expired")

            if not api_key.user.active:
                return forbidden("User account deactivated")

            # Update lastUsedAt
            db.apikey.update(
                where={"id": api_key.id},
                data={"lastUsedAt": datetime.now(timezone.utc)},
            )

            g.current_user = {
                "sub": api_key.user.id,
                "email": api_key.user.email,
                "name": api_key.user.name,
                "permissionSetId": api_key.user.permissionSetId,
            }

        else:
            return unauthorized("Invalid authorization header format")

        return f(*args, **kwargs)

    return decorated


def require_permissions(*permission_strings):
    """Check that the authenticated user's permission set includes the required permissions.
    Must be applied AFTER @require_auth (or wraps it automatically)."""

    def decorator(f):
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            from config import env_config

            if not env_config.AUTH_ENABLED:
                return f(*args, **kwargs)

            user = getattr(g, "current_user", None)
            if not user:
                return unauthorized("Unauthorized")

            perm_set_id = user.get("permissionSetId")
            if not perm_set_id:
                return forbidden("No permission set assigned")

            permissions = _get_permissions_for_set(perm_set_id)
            if permissions is None:
                return forbidden("Permission set not found")

            for perm in permission_strings:
                if perm not in permissions:
                    return forbidden("Forbidden")

            return f(*args, **kwargs)

        return decorated

    return decorator
