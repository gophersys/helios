import hashlib
import logging
import threading
import time
from datetime import datetime, timezone
from functools import wraps

from flask import g, jsonify, request

from config.env import env_config
from src.lib.errors import forbidden, unauthorized
from src.services.auth.jwt import verify_token
from src.services.database.prisma import get_db_client

logger = logging.getLogger(__name__)

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
    """Verify JWT or API key and attach current_user to Flask g."""

    @wraps(f)
    def decorated(*args, **kwargs):
        """Authenticate via JWT or API key, injecting current_user into g."""
        if not env_config.AUTH_ENABLED:
            # If a Bearer token is present, decode it (dev login flow).
            # Otherwise fall back to the default admin identity.
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ", 1)[1]
                payload, err = verify_token(token)
                if payload and not err:
                    g.current_user = payload
                    return f(*args, **kwargs)

            g.current_user = {
                "sub": "00000000-0000-0000-0000-000000000000",
                "email": "admin@concord.local",
                "name": "Admin (auth disabled)",
                "role": "ADMIN",
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
            # Ensure role is present (tokens created before RBAC won't have it)
            if "role" not in payload:
                payload["role"] = "DEVELOPER"
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
                "role": getattr(api_key.user, "role", "DEVELOPER"),
                "permissionSetId": api_key.user.permissionSetId,
            }

        else:
            return unauthorized("Invalid authorization header format")

        return f(*args, **kwargs)

    return decorated


def require_permissions(*permission_strings):
    """Check that the authenticated user's permission set includes the required permissions.
    Must be applied AFTER @require_auth (or wraps it automatically).

    Admin/Maintainer roles bypass permission set checks entirely (they have implicit
    full access). This provides backward compat: endpoints using @require_permissions
    work with both the old permission-set model and the new role model.
    """

    def decorator(f):
        """Wrap the handler with auth and permission checks."""
        @wraps(f)
        @require_auth
        def decorated(*args, **kwargs):
            """Check permissions after authentication.

            Permission enforcement runs even when AUTH_ENABLED=false so that
            dev-login as Operator/Developer accurately reflects what each role
            can and cannot do.  Only the anonymous fallback (no JWT) gets the
            legacy all-access admin bypass.
            """
            user = getattr(g, "current_user", None)
            if not user:
                return unauthorized("Unauthorized")

            # When auth is disabled and no real JWT was provided, the default
            # admin identity (sub=00000000-...) gets full access — preserving
            # the old behaviour for unauthenticated dev requests (curl, etc.).
            if not env_config.AUTH_ENABLED and user.get("sub") == "00000000-0000-0000-0000-000000000000":
                g.effective_role = "ADMIN"
                return f(*args, **kwargs)

            # Resolve effective role (supports X-View-As-Role for Admin/Maintainer)
            effective_role = _resolve_effective_role(user)
            g.effective_role = effective_role

            # New role system: Admin and Maintainer bypass permission set checks
            if effective_role in ("ADMIN", "MAINTAINER"):
                return f(*args, **kwargs)

            # Permission set check for Developer/Operator
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


# ---------------------------------------------------------------------------
# Role-based access control decorators
# ---------------------------------------------------------------------------

ROLE_HIERARCHY = {
    "ADMIN": 4,
    "MAINTAINER": 3,
    "DEVELOPER": 2,
    "OPERATOR": 1,
}


def _resolve_effective_role(user: dict) -> str:
    """Resolve effective role, applying X-View-As-Role header for Admin/Maintainer."""
    actual_role = user.get("role", "DEVELOPER")
    view_as = request.headers.get("X-View-As-Role")
    if view_as and actual_role in ("ADMIN", "MAINTAINER") and view_as in ROLE_HIERARCHY:
        return view_as
    return actual_role


def require_role(min_role: str):
    """Require minimum role level. Admin > Maintainer > Developer > Operator.

    Supports X-View-As-Role header: Admin/Maintainer can send this header to
    have the backend treat them as a lower role for permission checks and
    UI filtering. The effective role is stored on g for downstream use.
    """

    def decorator(f):
        """Wrap the handler with auth and role-level checks."""
        @wraps(f)
        @require_auth
        def wrapper(*args, **kwargs):
            """Enforce minimum role level after authentication."""
            if not env_config.AUTH_ENABLED:
                g.effective_role = "ADMIN"
                return f(*args, **kwargs)

            user = g.current_user
            effective_role = _resolve_effective_role(user)
            g.effective_role = effective_role

            if ROLE_HIERARCHY.get(effective_role, 0) < ROLE_HIERARCHY.get(min_role, 0):
                return jsonify({"data": None, "errors": [{"message": f"Requires {min_role} role or higher"}]}), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator


def require_product_access(min_level: str, product_param: str = "product_id"):
    """Require product-level access. Admin/Maintainer bypass the check.

    Args:
        min_level: Minimum access level required ("view", "operate", "develop", "admin").
        product_param: Name of the route parameter or query param containing the product ID.
    """
    LEVEL_HIERARCHY = {"admin": 4, "develop": 3, "operate": 2, "view": 1}

    def decorator(f):
        """Wrap the handler with auth and product-level access checks."""
        @wraps(f)
        @require_auth
        def wrapper(*args, **kwargs):
            """Enforce product-level access after authentication."""
            if not env_config.AUTH_ENABLED:
                g.effective_role = "ADMIN"
                return f(*args, **kwargs)

            user = g.current_user
            effective_role = _resolve_effective_role(user)
            g.effective_role = effective_role

            # Admin and Maintainer bypass product access checks
            # (unless using View As to simulate a lower role)
            if effective_role in ("ADMIN", "MAINTAINER"):
                return f(*args, **kwargs)

            # Get product ID from route params
            product_id = kwargs.get(product_param)
            if not product_id:
                # Try query params or request body
                product_id = request.args.get("productId")

            if not product_id:
                # Non-product-scoped endpoint — allow through
                return f(*args, **kwargs)

            # Check ProductAccess
            db = get_db_client()
            access = db.productaccess.find_first(
                where={"userId": user["sub"], "productId": product_id}
            )

            if not access:
                return jsonify({"data": None, "errors": [{"message": "No access to this product"}]}), 403

            if LEVEL_HIERARCHY.get(access.level, 0) < LEVEL_HIERARCHY.get(min_level, 0):
                return jsonify({"data": None, "errors": [{"message": f"Requires '{min_level}' access level for this product"}]}), 403

            return f(*args, **kwargs)
        return wrapper
    return decorator
