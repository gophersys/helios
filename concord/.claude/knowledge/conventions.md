# Concord — Code-shape conventions

Patterns to follow when adding or modifying code. These aren't unique opinions — they're what the existing code does. Following them keeps the codebase legible.

Refresh this file when: a new pattern is introduced that crosses multiple services, or an existing one is deliberately changed.

## HTTP API handler shape

Standard order of operations for any `v2/` route handler:

1. **Authorization** via decorator: `@require_permissions(Permissions.<MODULE>_<VIEW|MANAGE>)`. Always present. No exceptions.
2. **Request parsing** via a typed `from_json()` classmethod. Errors raise `BadRequest` with a clear message.
3. **Business logic** — DB reads, computations, external service calls.
4. **Mutation** via Prisma client (`db.<model>.<action>(...)`).
5. **Audit log** via `log_audit(action, entity_type, entity_id, details)`. Required for any state mutation.
6. **Side effects** — `notify_user(...)`, SocketIO emits, K8s job creation.
7. **Response** via `ApiResponse.ok(data)` or `ApiResponse.error(message, code)`.

A handler that doesn't follow this order is almost certainly wrong.

## Response envelope

Every v2 endpoint returns this shape:

```json
{
  "data": <T> | null,
  "errors": [{ "message": "string" }] | undefined,
  "pagination": { "page": int, "limit": int, "total": int, "pages": int } | undefined
}
```

- **Success**: `data` populated, `errors` omitted.
- **Failure**: `data` is `null`, `errors` has at least one entry.
- **Paginated lists**: include `pagination`; cap `limit` at 100.

Status codes: `200` (GET/PUT/DELETE success), `201` (POST create), `400` (validation), `401` (unauth), `403` (forbidden), `404` (not found), `409` (conflict — e.g., last admin delete), `500` (internal).

## Permission constants

Defined in `apps/backend/http-api/src/lib/permissions.py`. Naming: `Permissions.<DOMAIN>_<VERB>`. Verb is usually `VIEW` (reads) or `MANAGE` (mutations); some domains add intent-specific verbs (`BUILDS_TRIGGER`, `VALIDATION_RUN`, `MANUFACTURING_RUN`) when the granularity matters.

Examples (real names from `permissions.py`): `Permissions.PRODUCTS_VIEW`, `Permissions.PRODUCTS_MANAGE`, `Permissions.BUILDS_TRIGGER`, `Permissions.MANUFACTURING_RUN`, `Permissions.USERS_MANAGE`, `Permissions.SYSTEM_VIEW`.

No `ADMIN_` prefix. The domain stands on its own.

When you add a new endpoint, either reuse an existing constant or add a new one in `permissions.py` and the corresponding `PermissionSet` defaults.

## Audit log strings

`log_audit(action, entity_type, entity_id, details)`.

- **`action`** uses dotted lowercase verbs: `product.create`, `build.trigger`, `test.stage.complete`, `user.permission_set.assign`.
- **`entity_type`** matches the Prisma model name in PascalCase: `Product`, `BuildRun`, `User`.
- **`entity_id`** is the UUID string.
- **`details`** is a JSON-serializable dict. Include before/after when relevant. Don't include secrets or PII beyond what's already in the entity.

## Frontend ↔ backend contract

There is **no code generation** between backend and frontend. The contract is:

- Backend defines response shapes in Python `<Module>Response.from_json` / `to_json` classes.
- Frontend mirrors them by hand in `apps/frontend/app/src/lib/types/models.ts`.

When you change a response shape:

1. Update the backend handler + its tests.
2. Update `models.ts` in the same commit.
3. Update any consuming Svelte components.

The pre-commit knowledge-freshness hook does **not** catch this — it's a discipline.

## Frontend API client

Always use `apiFetch<ApiResponse<T>>(path, options)` from `apps/frontend/app/src/lib/api.ts`. Never `fetch()` directly. The wrapper handles:

- `Authorization: Bearer <jwt>` header injection
- 401 → auto-redirect to login
- Error envelope parsing
- Optional loading/error state

For uploads: `apiUpload(path, formData)` or `apiUploadRaw(path, formData)`.

## Prisma usage (Python)

- Import the client from `database` (the generated Python package): `from database import db, enums`.
- Use enum constants, never raw strings: `enums.TestRunStatus.ACTIVE`, not `"ACTIVE"`.
- Use `db.<model>.find_unique(where={...})` / `find_many` / `update` / `create` / `delete`.
- Wrap multi-step writes in `async with db.tx():` when atomicity matters.

## File organization

### Backend (`apps/backend/http-api/`)

```
src/
├── api/v2/<domain>/
│   ├── routes.py        # register_<domain>_routes(api_blueprint)
│   ├── <entity>.py      # handlers (one file per resource)
│   └── types.py         # request/response dataclasses + from_json/to_json
├── services/<svc>/      # cross-cutting (notifications, k8s, storage)
├── lib/
│   ├── decorators.py    # @require_auth, @require_permissions
│   ├── permissions.py   # Permissions enum
│   └── responses.py     # ApiResponse helpers
└── main.py
```

### Frontend (`apps/frontend/app/`)

```
src/
├── routes/<domain>/...   # SvelteKit pages, mirrors URL structure
└── lib/
    ├── api.ts            # API client
    ├── stores/           # Svelte stores
    ├── components/       # Reusable UI
    └── types/models.ts   # Backend type mirrors
```

## Tests

- **Python**: pytest. Tests live in `tests/` next to each app. Mark integration tests with `@pytest.mark.integration`; they require the dev compose stack.
- **TypeScript**: vitest for unit, Playwright for E2E. Files: `*.test.ts` (unit), `*.e2e.ts` (Playwright).
- **No mocking the database.** The dev compose stack provides a real Postgres. Use it.
- **Marker discipline**: `@pytest.mark.unit`, `integration`, `contract`, `slow`. Pick one.

See [`workflows/testing.md`](workflows/testing.md).

## Logging

- Python: stdlib `logging`. Logger per module: `logger = logging.getLogger(__name__)`.
- Levels: `info` for state transitions, `warning` for recoverable degradations, `error` for failures with context, `exception` inside `except:` blocks.
- Never log secrets, JWTs, raw passwords, or full request bodies.

## Comments

Default to no comments. Only add when the *why* is non-obvious — a workaround for a specific bug, a constraint that isn't visible in the surrounding code, a deliberately-counterintuitive choice.

Never reference the current PR, ticket, or feature in a comment (those rot in place). That belongs in the commit message or PR description.

## Commit messages

Conventional Commits. Subject ≤72 chars, imperative mood, no trailing period. Body wrapped at 80, separated by blank line. **Never** mention Claude, AI, LLM, copilot, or any automated tool.

For commits that touch code but don't change architecture (typo fixes, log message tweaks, formatting), add `[no-arch-change]` to the message to bypass the knowledge-freshness hook.

See [`rules/git-commits.md`](../rules/git-commits.md).
