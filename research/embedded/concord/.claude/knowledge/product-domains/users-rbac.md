# Users & RBAC — knowledge

The users-and-RBAC domain models who can do what. Two layers stack: a global `Role` + named `PermissionSet` controls platform-wide access (read builds, manage users, trigger validation), while a per-`Product` `AccessLevel` controls fine-grained access to individual product lines. Authentication is Google OAuth → JWT in production, a synthetic admin bypass in development.

Refresh this file when: a new `Role` or `AccessLevel` value is added, a new `Permissions.*` constant is added or renamed, the JWT auth flow changes, the dev bypass changes, or the docs role-manifest hook changes.

## Entities

| Model | Role |
|---|---|
| `User` | A platform account. Authenticated via Google OAuth (externalId = Google sub ID) or the dev synthetic admin. |
| `Role` | Global RBAC tier: `ADMIN | MAINTAINER | DEVELOPER | OPERATOR`. Coarse default. |
| `PermissionSet` | A named cluster of `Permissions.*` strings assigned to a user. Multiple users share a PermissionSet (e.g. "Validation Engineer"). |
| `ProductAccess` | Per-product, per-user `AccessLevel`. Stacks on top of global Role. |
| `AccessLevel` | `view | operate | develop | admin` — granular per-product access. |
| `ApiKey` | Programmatic key (SHA-256 hashed). Tied to a User. |
| `AuthSession` / `RefreshToken` | Device-code flow (RFC 8628) for CLI auth. Approved in browser, polled by CLI. |
| `AuditLog` | Every mutation, written by `log_audit(...)`. Indexed by `(entity_type, entity_id, createdAt)`. |

Schema: `prisma/schema.prisma:984-1158` (User, ProductAccess, PermissionSet, ApiKey, AuthSession, RefreshToken, AuditLog), `:151-156` (Role enum), `:182-187` (AccessLevel enum).

## Lifecycle

### User

```
(first Google OAuth login) ──► User created, role=DEVELOPER, no PermissionSet
                                            │
                                            │ (admin assigns a PermissionSet and/or upgrades role)
                                            ▼
                                       fully provisioned
                                            │
                                            └─► active=false (deactivated, retains audit history)
```

Users are created on first login — the OAuth handler at `apps/backend/http-api/src/api/v2/auth/` looks up by `externalId` (Google sub ID), creates the row with `role=DEVELOPER` and no PermissionSet if not found. An admin then assigns the right PermissionSet and (optionally) per-product `AccessLevel` rows.

Deactivation flips `active=false` but never deletes — the audit log references the user id; deleting orphans history.

### PermissionSet

```
(admin creates) ──► PermissionSet with permissions: []
                              │
                              │ (admin edits, adds/removes Permissions.* strings)
                              ▼
                       assigned to users
                              │
                              └─► (deleted only when no User references it)
```

PermissionSet edits are immediate — the next request for any user holding that set picks up the new permissions. No JWT re-issue required because the JWT only carries the user id; permissions are loaded per-request.

### CLI device-code flow (`AuthSession`)

```
CLI: POST /v2/auth/device       → { userCode, deviceCode, expiresAt }
CLI shows userCode to operator
Operator: opens /settings/sessions/, enters userCode, clicks Approve
Server: status=APPROVED, issues RefreshToken
CLI: poll POST /v2/auth/token with deviceCode
   → first poll: 200 with { accessToken, refreshToken }
   → subsequent polls: 400 (pending) until approval
Auth complete; CLI rotates refreshToken on expiry
```

`AuthSession.expiresAt` is `createdAt + 10 minutes` for `PENDING`. A daily cron sweeps `EXPIRED|DENIED` rows older than 7 days.

## Where the code lives

| Concern | Path |
|---|---|
| Google OAuth handler | `apps/backend/http-api/src/api/v2/auth/oauth.py` (and adjacent) |
| JWT mint/verify | `apps/backend/http-api/src/lib/tokens.py` |
| `@require_permissions` decorator | `apps/backend/http-api/src/lib/decorators.py` |
| `require_product_access(...)` | `apps/backend/http-api/src/lib/decorators.py:276` |
| Permission constants + registry | `apps/backend/http-api/src/lib/permissions.py` |
| User CRUD | `apps/backend/http-api/src/api/v2/system/users.py` (or under `system/`) |
| PermissionSet CRUD | `apps/backend/http-api/src/api/v2/system/permission_sets.py` |
| ApiKey CRUD | `apps/backend/http-api/src/api/v2/system/api_keys.py` |
| CLI device-code endpoints | `apps/backend/http-api/src/api/v2/auth/sessions.py` |
| Audit log writer | `apps/backend/http-api/src/lib/audit.py` |
| Audit log reader | `apps/backend/http-api/src/api/v2/system/audit.py` |
| Frontend permission gates | `apps/frontend/app/src/lib/permissions.ts`, `apps/frontend/app/src/lib/stores/user.ts` |
| Docs role-manifest hook | `apps/frontend/docs/hooks/role_filter.py` (MkDocs hook), referenced by `mkdocs.yml` |
| Prisma models | `prisma/schema.prisma:984-1158` |

## The permission catalog

Defined in `apps/backend/http-api/src/lib/permissions.py`. Naming is `<DOMAIN>_<VERB>` — no `ADMIN_` prefix. Reads use `_VIEW`, mutations use `_MANAGE` (or a more intent-specific verb when the domain distinguishes — `_TRIGGER`, `_RUN`).

| Module | Permissions |
|---|---|
| Products & Builds | `PRODUCTS_VIEW`, `PRODUCTS_MANAGE`, `BUILDS_VIEW`, `BUILDS_TRIGGER`, `BUILDS_MANAGE` |
| Testing | `VALIDATION_VIEW`, `VALIDATION_RUN`, `VALIDATION_MANAGE` |
| Manufacturing | `MANUFACTURING_VIEW`, `MANUFACTURING_RUN`, `MANUFACTURING_MANAGE` |
| Infrastructure | `FIXTURES_VIEW`, `FIXTURES_MANAGE`, `DEVICES_VIEW`, `DEVICES_MANAGE`, `KUBERNETES_VIEW`, `KUBERNETES_MANAGE` |
| Platform | `USERS_VIEW`, `USERS_MANAGE`, `PERMISSIONS_MANAGE`, `API_KEYS_VIEW`, `API_KEYS_MANAGE`, `SYSTEM_VIEW`, `SYSTEM_MANAGE`, `RELEASES_VIEW`, `RELEASES_MANAGE`, `NOTIFICATIONS_VIEW`, `NOTIFICATIONS_MANAGE` |

`PERMISSION_REGISTRY` in the same file annotates each with a UI-facing label and description used in the permission-set editor.

## The decorator

The standard handler shape:

```python
from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions

@app.route("/v2/products/<id>", methods=["GET"])
@require_permissions(Permissions.PRODUCTS_VIEW)
def get_product(id):
    ...
```

- Validates the JWT (`Authorization: Bearer <token>` for REST, `auth` payload for SocketIO).
- Loads the user's `PermissionSet`. ADMIN role bypasses permission checks entirely; non-admin roles require the named permission to be in the set.
- Returns `401` for missing/expired tokens, `403` for insufficient permission.
- Sets `flask.g.current_user` for the handler.

For per-product gating, additionally call:

```python
from src.lib.decorators import require_product_access
require_product_access(g.current_user, product_id, level="operate")
```

Raises `Forbidden` (403) if the user lacks that level for that product. `ADMIN` and `MAINTAINER` roles bypass `ProductAccess` checks. Used in handlers where product-level granularity matters (e.g. an OPERATOR who manages Alpha shouldn't trigger Sigma5 manufacturing).

## The dev bypass

When `AUTH_ENABLED=false` (default in `deploy/development/docker-compose.yaml`), every request injects a synthetic admin:

```python
{
  "sub": "00000000-0000-0000-0000-000000000000",
  "email": "admin@concord.local",
  "role": "ADMIN",
  "permissionSetId": None,  # bypassed
}
```

The decorator short-circuits on this user — every permission check passes. Useful for local development; **never** set `AUTH_ENABLED=false` in staging/production. The startup check at `apps/backend/http-api/src/main.py` refuses to come up if `ENVIRONMENT != development` and `AUTH_ENABLED=false`.

## Endpoints that bypass `@require_permissions`

A short list, each with its own guard:

| Endpoint | Guard |
|---|---|
| `/health`, `/ready`, `/v2/healthcheck` | None — status-only |
| `/v2/builds/webhook` | Bitbucket HMAC signature verification |
| `/v2/runs/.../heartbeat` (runner pings) | API key (SHA-256 of shared secret) |

Adding to this list requires a documented alternative auth, a route-level comment, and a knowledge update to `.claude/knowledge/apps/backend/http-api.md`.

## Docs role-manifest hook

The MkDocs site under `apps/frontend/docs/` filters page visibility by role via a custom hook. Each page declares its required role(s) in the frontmatter; the hook (`apps/frontend/docs/hooks/role_filter.py`) strips pages the current viewer can't see. The viewer's role is loaded from the same JWT that the SvelteKit app uses — the docs subdomain reads the `concord-auth` cookie set on the parent domain.

## Key invariants

- **`User.externalId` (Google sub) is unique.** First login on a fresh sub creates a new user; subsequent logins update `lastSeenAt`.
- **`PermissionSet.name` is unique.** Easier to reason about than UUIDs in the admin UI.
- **ApiKey plaintext is never persisted.** The DB stores `keyHash = SHA-256(plaintext)` and `keyPrefix` (first 8 chars, for display). Plaintext is shown once at creation, then gone.
- **`AuthSession.userCode` and `deviceCode` are unique.** `userCode` is human-friendly (8 chars, no ambiguous I/O/0/1), `deviceCode` is a UUID.
- **`ProductAccess` is `(userId, productId)` unique.** A user has exactly one access level per product.
- **`ADMIN` and `MAINTAINER` roles bypass `ProductAccess` checks.** They can operate on any product. Document this in the role-onboarding UX so OPERATORs understand why admins always work.
- **Audit log is append-only.** No update or delete endpoint. Retention is enforced by a daily sweep, not by handlers.
- **Reads aren't audited.** The audit log captures mutations only. See [`../../rules/audit-logging.md`](../../rules/audit-logging.md).

## How to extend

### Adding a new permission

1. Add a constant in `apps/backend/http-api/src/lib/permissions.py`:
   ```python
   WIDGETS_VIEW = "widgets:view"
   WIDGETS_MANAGE = "widgets:manage"
   ```
2. Add an entry to `PERMISSION_REGISTRY` in the same file (label, description, module group).
3. Update the default `PermissionSet` seed under `apps/backend/http-api/src/services/permissions/` so the right roles inherit it.
4. Apply via `@require_permissions(Permissions.WIDGETS_VIEW)` in the new handler.
5. Update the frontend's `apps/frontend/app/src/lib/permissions.ts` (if it exists) and any UI gating.
6. Update this knowledge file's permission table.

### Adding a new Role

1. Add to the `Role` enum in `prisma/schema.prisma` + migration.
2. Decide ADMIN-bypass semantics — does this role also skip ProductAccess?
3. Update the seed PermissionSets for the new role.
4. Update `apps/frontend/app/src/lib/types/models.ts`.
5. Update this knowledge file and `.claude/knowledge/prisma/enums.md`.

### Adding a new AccessLevel

1. Add to the enum in `prisma/schema.prisma` + migration.
2. Update `require_product_access` logic to order the new level.
3. Update the frontend per-product access editor.

## Common failure modes

**`401` on every request despite a fresh login** — clock skew between client and server. JWTs are HS256 with `iat`/`exp`; >5 min skew tips them invalid. Sync NTP on both sides.

**`403` on an endpoint the user "should" be able to call** — they're missing the specific permission constant in their PermissionSet. Check via `/v2/users/<id>` → `permissionSet.permissions`. If they're an `ADMIN`, the permission check should be bypassed — if it isn't, the decorator is loading a stale user (rare; usually a caching bug).

**Synthetic admin bleeds into staging** — `AUTH_ENABLED=false` was set in the wrong env. Startup check should refuse, but if a developer overrode it in a quick-fix deploy, every request becomes "admin". Fix: set `AUTH_ENABLED=true` in values, rolling-restart.

**OAuth callback fails with `unknown user`** — Google sub ID changed (extremely rare — happens if the user's Google Workspace tenant moves). Manually update `User.externalId` to the new sub.

**ApiKey rejected with `401`** — plaintext lookup uses `SHA-256(plaintext) == keyHash`. If the user pasted whitespace or the key is truncated, hashes don't match. Re-issue.

**Audit log empty for an action that definitely happened** — handler returned before `log_audit(...)`. Trace: did the handler raise after the DB write but before the audit call? The order is "audit after mutation, before notifications" — if you see notifications but no audit, the handler is in the wrong order.

**Docs page visible to wrong role** — frontmatter `roles:` list is wrong, or the hook caching is stale. `nx update docs` rebuilds.

## Related knowledge

- [`products.md`](products.md) — `ProductAccess` stacks on top of Role
- [`manufacturing.md`](manufacturing.md) — `MANUFACTURING_RUN` vs `MANUFACTURING_MANAGE` distinction
- [`validation.md`](validation.md) — `VALIDATION_RUN` for triggering runs
- [`builds.md`](builds.md) — `BUILDS_TRIGGER` for kicking off builds
- [`../apps/backend/http-api.md`](../apps/backend/http-api.md) — auth handler internals
- [`../apps/frontend/app.md`](../apps/frontend/app.md) — frontend permission gating
- [`../../rules/auth-defaults.md`](../../rules/auth-defaults.md) — the unconditional decorator rule
- [`../../rules/audit-logging.md`](../../rules/audit-logging.md) — what to log and what not to
- [`../workflows/credentials.md`](../workflows/credentials.md) — JWT_SECRET_KEY rotation
