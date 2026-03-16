---
name: concord-add-crud-feature
description: Create a full-stack CRUD feature (Prisma + HTTP API + React frontend) following Concord patterns
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

1. **types.py** — Create/Update request dataclasses with `from_json()` validation
2. **shared.py** — Constants and helpers (if needed)
3. **<entity>.py** — CRUD handlers: list (paginated), create, get, update, delete
4. **router.py** — Register all routes
5. **permissions.py** — Add VIEW/MANAGE permissions
6. **seed.py** — Add permissions to seed arrays
7. **docs.py** — Add OpenAPI schemas and path operations

Key requirements:
- `@require_permissions()` on every endpoint
- `log_audit()` after every mutation
- `ApiResponse.ok()` envelope on all responses
- `_serialize_<entity>()` helpers for consistent output
- Pagination on list endpoints (page/limit/total/pages)

Verify: `python3 -c "import py_compile,glob;[py_compile.compile(f,doraise=True) for f in glob.glob('src/**/*.py',recursive=True)]"`

## Phase 3 — Frontend

Follow the pattern in `apps/frontend/concord-app/src/app/pages/products/`:

1. **types/models.ts** — Add interfaces for new entities
2. **<domain>-page.tsx** — List page with cards, inline form, detail routing
3. **<domain>-card.tsx** — Card component with hover-reveal actions
4. **<domain>-detail.tsx** — Detail view with tabs
5. **app.tsx** — Lazy import + route registration
6. **sidebar.tsx** — Navigation link with permission gate

Key requirements:
- Permission check with `<Navigate>` redirect
- `<ErrorAlert>`, `<ConfirmDeleteDialog>`, `<Select>`, `<StatusBadge>` from `components/ui/`
- `submitting` state on all forms
- `api()` for requests, never direct `localStorage`
- `aria-label` on icon buttons
- Design tokens for all colors (never hardcoded)
- `animate-fade-in` on page root

Verify: `npx tsc --noEmit && npx vite build`

## Phase 4 — Verification

1. Python compiles clean
2. TypeScript compiles clean
3. Vite builds clean
4. API responds (if server is running): `curl -s localhost:9001/v2/<domain> | head`

## Phase 5 — Tests

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

3. **Frontend tests** — Add `<domain>-page.spec.tsx`:
   - Use `renderApp()` from `src/testing/render-app`
   - Use `mockFetch()` / `mockFetchRoutes()` from `src/testing/mock-api`
   - Test permission guard, loading state, data rendering, form submission

4. **Run both suites**:
   - `cd apps/backend/http-api && PYTHONPATH=src:$(pwd)/../../../libs/python:$(pwd)/../../../libs:. pytest tests/ -v`
   - `cd apps/frontend/concord-app && npx nx test concord-app`
