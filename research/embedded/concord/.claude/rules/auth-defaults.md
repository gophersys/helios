# Auth defaults

Every HTTP API endpoint uses `@require_permissions(...)`. No exceptions for new endpoints. The default is to require auth; opting out requires justification.

## The decorator

```python
from lib.decorators import require_permissions
from lib.permissions import Permissions

@app.route("/v2/products/<id>", methods=["GET"])
@require_permissions(Permissions.PRODUCTS_VIEW)
def get_product(id):
    ...
```

- Reads use `Permissions.<DOMAIN>_VIEW`.
- Mutations use `Permissions.<DOMAIN>_MANAGE` — or a more intent-specific verb when the domain distinguishes (e.g., `BUILDS_TRIGGER`, `VALIDATION_RUN`, `MANUFACTURING_RUN`).
- No `ADMIN_` prefix on permission names.
- The decorator validates the JWT, loads the user's `PermissionSet`, and returns `401` for missing/expired tokens or `403` for insufficient permission.
- The user object lands in `flask.g.current_user` for use inside the handler.

## Permission constants

All defined in `apps/backend/http-api/src/lib/permissions.py`. Real examples: `PRODUCTS_VIEW`, `PRODUCTS_MANAGE`, `BUILDS_VIEW`, `BUILDS_TRIGGER`, `BUILDS_MANAGE`, `VALIDATION_VIEW`, `VALIDATION_RUN`, `MANUFACTURING_MANAGE`, `FIXTURES_MANAGE`, `USERS_MANAGE`, `SYSTEM_VIEW`.

When you add an endpoint that doesn't fit any existing constant:

1. Add a new `Permissions.<DOMAIN>_<VERB>` flag.
2. Update the default `PermissionSet` definitions in `apps/backend/http-api/src/services/permissions/` (or wherever the seed-time defaults live) so the appropriate roles get it.
3. Update `apps/frontend/app/src/lib/permissions.ts` (if one exists) or wherever the frontend gates UI.

## The exceptions (which you must justify)

A small, fixed set of endpoints intentionally bypass `@require_permissions`:

| Endpoint | Why bypassed | What guards it instead |
|---|---|---|
| `/health`, `/ready`, `/v2/healthcheck` | K8s liveness/readiness probes | None — these return only status |
| `/v2/builds/webhook` (and similar webhook receivers) | Called by Bitbucket | HMAC signature verification |
| `/v2/runs/.../heartbeat` (K8s job pings) | Called by runner pods inside the cluster | API key hashing — SHA-256 of a shared secret env var |

Adding a new endpoint to this list requires:
- A documented alternative auth (HMAC, API key, mTLS, etc.).
- An explicit code comment at the route definition explaining the bypass.
- An update to `.claude/knowledge/apps/backend/http-api.md`.

## Dev bypass

In development, `AUTH_ENABLED=false` injects a synthetic admin identity:

```
{
  sub: "00000000-0000-0000-0000-000000000000",
  email: "admin@concord.local",
  permissionSetId: None,
}
```

This is the default for the compose stack. Tests can also use it. Staging and production always run with `AUTH_ENABLED=true`. Confirm before deploying.

## Where authorization data comes from

- **JWT**: signed with `JWT_SECRET_KEY` (HS256). Issued by `/v2/auth/login` after Google OAuth verification.
- **Frontend storage**: `localStorage.concord-token` for app calls; also set as cookie `concord-auth` on the parent domain so the docs subdomain can read it.
- **Server-side validation**: every request must include `Authorization: Bearer <token>`. WebSocket connections include the token in the auth payload.

## Authorization vs authentication

- `@require_auth` validates the token only. Use when an endpoint should accept any logged-in user.
- `@require_permissions(...)` validates the token **and** checks the permission. Prefer this — `@require_auth` alone is rarely what you want.

## Per-product access

On top of global Role and PermissionSet, users have a per-`Product` `AccessLevel` (`view | operate | develop | admin`). Handlers that operate on a specific product should additionally call:

```python
from lib.access import require_product_access

require_product_access(g.current_user, product_id, level="operate")
```

This raises `Forbidden` if the user lacks that level for that product. Not all handlers need this — only when product-level granularity is meaningful.
