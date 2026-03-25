---
name: apps-backend-http-api-add-endpoint
description: Create a new backend HTTP API endpoint or module following Concord patterns
user-invocable: true
argument-hint: <module-name> <description>
---

# Add Backend API Endpoint

Create a new API endpoint or module for the Concord HTTP API.

Arguments: $ARGUMENTS

## Steps

1. **Read the reference pattern** — Read these files to understand the established conventions:
   - `apps/backend/http-api/src/api/v2/products/products.py` (CRUD handler pattern)
   - `apps/backend/http-api/src/api/v2/products/types.py` (request validation pattern)
   - `apps/backend/http-api/src/api/v2/router.py` (route registration)
   - `apps/backend/http-api/src/lib/permissions.py` (permission constants)

2. **Create the module** at `apps/backend/http-api/src/api/v2/<module>/`:
   - `__init__.py` (empty)
   - `types.py` — dataclass request types with `from_json()` returning `(instance, error)` tuple, `to_update_data()` on update types
   - `shared.py` — constants, allowed extensions, config (if needed)
   - `<entity>.py` — CRUD handler with `_serialize_<entity>()`, `list_`, `create_`, `get_`, `update_`, `delete_` functions

3. **Every handler must**:
   - Use `@require_permissions(Permissions.ADMIN_<MODULE>_<VIEW|MANAGE>)`
   - Parse request via `EntityRequest.from_json(request.get_json())`
   - Use `get_db_client()` for Prisma
   - Call `log_audit()` after mutations
   - Return `jsonify(ApiResponse.ok(data).to_dict()), status_code`
   - List endpoints must support `page`/`limit` pagination

4. **Register routes** in `router.py` — import handlers, add `v2.add_url_rule()` entries

5. **Add permissions** to `src/lib/permissions.py` and `prisma/seed.py`

6. **Document in OpenAPI** — add schemas and path operations to `src/api/v2/docs.py`

7. **Verify** — run `python3 -c "import py_compile,glob;[py_compile.compile(f,doraise=True) for f in glob.glob('src/**/*.py',recursive=True)]"` from the http-api directory

8. **Test** — Add tests following the patterns in `tests/api/products/`:
   - `tests/unit/types/test_<module>_types.py` — all `from_json()` paths (valid, missing fields, invalid values) and `to_update_data()`
   - `tests/api/<module>/test_<entity>.py` — CRUD route tests using `authed_client` and `mock_db`
   - Add `__init__.py` in new test directories
   - Mock `presigned_get_url` with an `autouse` fixture if the module uses `presigned_url`
   - Patch at `api.v2.<module>.<entity>.log_audit` (not `src.api...`)
   - Run: `cd apps/backend/http-api && PYTHONPATH=src:$(pwd)/../../../libs/python:$(pwd)/../../../libs:. pytest tests/ -v`
