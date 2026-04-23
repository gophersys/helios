---
name: concord-add-crud-feature
description: Create a full-stack CRUD feature (Prisma + HTTP API + SvelteKit frontend) following Concord patterns
user-invocable: true
argument-hint: <feature-name> <description>
---

# Add Full-Stack CRUD Feature

Create a complete feature with backend API endpoints and a frontend page.

Arguments: $ARGUMENTS

## Overview

This skill combines the backend and frontend patterns to create a complete feature. Read the reference files listed below before writing any code.

## Phase 1 — Prisma Schema

1. Read `prisma/schema.prisma` to understand existing models
2. Add new model(s) with proper relations, `@@unique` constraints, and `@@map("table_name")`
3. Update `prisma/migrations/0001_init/migration.sql` with the new table DDL
4. Run `cd prisma && npx prisma generate` to regenerate the client

## Phase 2 — Backend API

Follow the pattern in `apps/backend/http-api/src/api/v2/products/`:

### Module files

1. **`__init__.py`** — Empty or with a module docstring
2. **`types.py`** — Create/Update request dataclasses with `from_json()` validation
3. **`shared.py`** — Constants and helpers (if needed)
4. **`<entity>.py`** — CRUD handlers: list (paginated), create, get, update, delete
5. **`routes.py`** — `register_<domain>_routes(api)` function that registers all routes

### Route registration

Each domain has its own `routes.py` with a registration function. Follow the pattern in `src/api/v2/runs/routes.py`:

```python
"""Route registration for /v2/<domain> endpoints."""

from flask import Blueprint

from .<entity> import list_items, create_item, get_item, update_item, delete_item


def register_<domain>_routes(api: Blueprint):
    api.add_url_rule("/<domain>", endpoint="list_items", view_func=list_items, methods=["GET"])
    api.add_url_rule("/<domain>", endpoint="create_item", view_func=create_item, methods=["POST"])
    api.add_url_rule("/<domain>/<item_id>", endpoint="get_item", view_func=get_item, methods=["GET"])
    api.add_url_rule("/<domain>/<item_id>", endpoint="update_item", view_func=update_item, methods=["PUT"])
    api.add_url_rule("/<domain>/<item_id>", endpoint="delete_item", view_func=delete_item, methods=["DELETE"])
```

Then wire it into `src/api/v2/router.py`:
```python
from .<domain>.routes import register_<domain>_routes
# Inside register_v2_routes():
register_<domain>_routes(v2)
```

### Other backend files

6. **`src/lib/permissions.py`** — Add `ADMIN_<MODULE>_VIEW` / `ADMIN_<MODULE>_MANAGE` permissions
7. **`prisma/seed.py`** — Add permissions to seed arrays
8. **`src/api/v2/docs.py`** — Add OpenAPI schemas and path operations

### Key requirements

- `@require_permissions()` on every endpoint
- `log_audit()` after every mutation
- `ApiResponse.ok()` envelope on all responses
- `_serialize_<entity>()` helpers for consistent output
- Pagination on list endpoints (page/limit/total/pages)
- Config imports: `from config.env import env_config`

Verify: `python3 -c "import py_compile,glob;[py_compile.compile(f,doraise=True) for f in glob.glob('src/**/*.py',recursive=True)]"`

## Phase 3 — Service Layer (if needed)

If the feature requires business logic beyond simple CRUD (e.g., external API calls, background jobs, complex state machines), add service files under `src/services/`.

**Service directory structure:**
```
src/services/
  auth/           — Authentication (JWT, CoreCloud)
  builds/         — CI build lifecycle (run_service, trigger, promotion, etc.)
  ck_boards/      — Board definition repository
  database/       — Prisma ORM singleton
  devices/        — MTIB device observability
  executors/      — Job execution (Docker/K8s)
  integrations/   — External API clients (Bitbucket, webhooks)
  kubernetes/     — K8s API abstractions
  log/            — Structured logging
  scheduling/     — Background job scheduling
  storage/        — MinIO/S3 client
```

Place new services in the appropriate subdirectory or create a new one if no existing group fits.

## Phase 4 — Frontend (SvelteKit)

Follow the pattern in `apps/frontend/app/src/routes/products/`:

1. **`src/lib/types/models.ts`** — Add interfaces for new entities
2. **`src/routes/<domain>/+page.svelte`** — List page with search, filter, pagination, cards
3. **`src/lib/components/<domain>/<entity>-card.svelte`** — Card component
4. **`src/lib/components/<domain>/<entity>-detail.svelte`** — Detail view with tabs (if needed)
5. **`src/routes/<domain>/[id]/+page.svelte`** — Detail route (if needed)
6. **`src/lib/components/sidebar.svelte`** — Add navigation link with permission gate

Key requirements:
- Permission check on mount: `if (!auth.hasPermission('<domain>:view')) goto('/')`
- Use `$lib/components/ui/` components: `error-alert`, `confirm-delete-dialog`, `select`, `status-badge`, `pagination`
- `submitting` state on all forms with `disabled={submitting}` on buttons
- Use `$lib/api` for ALL API calls (never direct `fetch` or `localStorage`)
- Use Svelte 5 runes: `$state`, `$derived`, `$effect`
- `aria-label` on icon buttons, icons from `lucide-svelte`
- Design tokens for all colors (never hardcoded hex values)

Verify: `npx nx typecheck app && npx nx build app`

## Phase 5 — Verification

1. Python compiles clean
2. TypeScript compiles clean
3. Vite builds clean
4. API responds (if server is running): `curl -s localhost:9001/v2/<domain> | head`

## Phase 6 — Tests

1. **Backend types tests** — Add `tests/unit/types/test_<domain>_types.py`:
   - Test `from_json()` for valid input, missing required fields, invalid values
   - Test `to_update_data()` returns only changed fields
   - Use `make_obj()` from `tests/conftest` for mock data

2. **Backend API tests** — Add `tests/api/<domain>/test_<entity>.py`:
   - Create `__init__.py` in the test directory
   - Add `autouse` fixture to mock `presigned_get_url` if the module uses `presigned_url`:
     ```python
     @pytest.fixture(autouse=True)
     def _mock_presigned_url():
         with patch("api.v2.<domain>.shared.presigned_get_url", return_value=None):
             yield
     ```
   - Test list (pagination), create (with duplicate check), get, get-not-found, update, delete
   - Use `authed_client` for authenticated requests, `mock_db` for DB mocks
   - Patch `log_audit` at `api.v2.<domain>.<entity>.log_audit` (not `src.api...`)
   - For delete tests with storage cleanup, patch `get_storage_client` and `get_bucket_name`

3. **Frontend tests** — Add `src/lib/components/<domain>/<component>.test.ts`:
   - Use `createMockFetch()` from `src/tests/helpers.ts`
   - Use `createMockUser()`, `createMockProduct()` etc. from `src/tests/helpers.ts`
   - Test permission guard, loading state, data rendering, form submission
   - Run: `cd apps/frontend/app && npx vitest run`

4. **Run both suites**:
   - `cd apps/backend/http-api && PYTHONPATH=src:$(pwd)/../../../libs/python:$(pwd)/../../../libs:. pytest tests/ -v`
   - `cd apps/frontend/app && npx nx test app`
