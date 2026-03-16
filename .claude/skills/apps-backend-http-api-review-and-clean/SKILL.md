---
name: apps-backend-http-api-review-and-clean
description: Review and clean the HTTP API backend for pattern violations, test gaps, and code quality issues
user-invocable: true
argument-hint: [module-name|all]
---

# Review & Clean HTTP API Backend

Audit the backend HTTP API for pattern violations, missing tests, security issues, and code consistency. Optionally target a single module or scan everything.

Arguments: $ARGUMENTS

## Scope

If an argument is provided (e.g., `catalog`, `inventory`, `codebases`), review only that module. If the argument is `all` or omitted, review every module under `apps/backend/http-api/src/api/v2/`.

## Execution Strategy

Launch **parallel agents** (using the Task tool with `subagent_type: "general-purpose"`) for each review dimension. Each agent reads the relevant source files and reports findings. After all agents complete, compile a unified report and apply auto-fixable changes.

### Agent 1: Module Structure & Import Review

Read every file in the target module(s) and check:

1. **Module structure** — Every API domain at `src/api/v2/<domain>/` must have:
   - `__init__.py` (empty)
   - `types.py` with request dataclasses
   - One `.py` file per entity (not one file with all handlers)
   - `shared.py` if the module uses constants/helpers (optional)

2. **Import ordering** — Must follow: stdlib → third-party (flask) → `src.lib.*` → `src.services.*` → relative (`.types`, `.shared`)

3. **Unused imports** — Flag any import that isn't referenced in the file

4. **Logger declaration** — Every handler file should have `logger = logging.getLogger(__name__)`

**Reference files:**
- `apps/backend/http-api/src/api/v2/catalog/` (canonical module structure)
- `apps/backend/http-api/src/api/v2/inventory/` (module with shared.py)

### Agent 2: Request Type Pattern Review

Read every `types.py` and verify:

1. **Create requests** have:
   - `from_json(cls, data: dict) -> Tuple[Optional["ClassName"], Optional[str]]`
   - `if not data: return None, "Request body must contain JSON data"` as first check
   - `.strip()` on all string inputs
   - Required field validation with specific error messages
   - Type constraint checks (`isinstance(active, bool)`) with error messages

2. **Update requests** have:
   - `_has_<field>: bool = False` for every nullable field (description, notes, etc.)
   - `has_<field> = "<field>" in data` tracking in `from_json()`
   - `to_update_data()` that only includes fields with `_has_*` or non-None values
   - `"No fields to update"` error when all fields are None/omitted
   - `to_update_data()` must NOT include join-table relations (chipsets, BOM items, etc.)

3. **Enum validation** — Any field with fixed values (status, type) must validate against the allowed set

4. **List/array fields** — Must check `isinstance(field, list)` and sanitize items

**Reference file:** `apps/backend/http-api/src/api/v2/catalog/types.py`

### Agent 3: Route Handler Pattern Review

Read every handler `.py` file and verify:

1. **Decorators** — Every handler uses `@require_permissions(Permissions.ADMIN_<MODULE>_<VIEW|MANAGE>)`
   - GET/list → `VIEW`
   - POST/PUT/DELETE → `MANAGE`

2. **Request parsing** — Mutations use `data, error = Request.from_json(request.get_json()); if error: return bad_request(error)`

3. **DB access** — Uses `db = get_db_client()` (not a global or import-level client)

4. **Existence checks** — GET/PUT/DELETE check for entity existence and return `not_found()` if missing

5. **Uniqueness checks** — CREATE checks for duplicates before inserting; UPDATE checks only if name/unique field changed (`data.name and data.name != existing.name`)

6. **Audit logging** — Every mutation calls `log_audit()` AFTER the successful DB operation (never before)
   - Format: `log_audit("<entity>.<verb>", "<EntityType>", entity_id, {details})`
   - Verbs: create, update, delete, upload

7. **Response format** — All responses use `jsonify(ApiResponse.ok(data).to_dict()), status_code`
   - Create → 201
   - Get/Update/Delete → 200
   - Delete payload: `{"deleted": True}`

8. **Serialization** — Uses `_serialize_<entity>()` helper with:
   - `hasattr(obj, "field") and obj.field is not None` for optional relations
   - `.isoformat()` for datetime fields
   - `str(field)` for BigInt fields (sizeBytes)

9. **Pagination** — List endpoints must have:
   ```python
   page = max(1, request.args.get("page", 1, type=int))
   limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
   skip = (page - 1) * limit
   ```

10. **Error handling** — Uses `bad_request()`, `not_found()`, `conflict()`, `internal_error()` from `src.lib.errors`. Never returns raw `str(e)` to clients.

11. **Referential integrity** — DELETE handlers check for child references before deleting (e.g., chipset used by board revisions)

12. **Join table management** — Uses delete-then-recreate pattern: `delete_many()` + loop of `create()`. Never in `to_update_data()`.

**Reference files:**
- `apps/backend/http-api/src/api/v2/catalog/products.py` (complete CRUD)
- `apps/backend/http-api/src/api/v2/catalog/board_revisions.py` (nested resource + join tables)
- `apps/backend/http-api/src/api/v2/catalog/firmware_builds.py` (file upload)

### Agent 4: Test Coverage Review

Read every test file in `tests/api/` and `tests/unit/types/` and verify:

1. **Every entity has integration tests** covering:
   - `test_list_*` — 200 with pagination structure
   - `test_list_*_unauthorized` — 401 without auth (at least one per module)
   - `test_create_*` — 201 with valid data
   - `test_create_*_duplicate_*` — 409 on uniqueness violation
   - `test_create_*_missing_*` — 400 on required field missing
   - `test_get_*` — 200 with serialized data
   - `test_get_*_not_found` — 404
   - `test_update_*` — 200 with changed fields
   - `test_update_*_not_found` — 404
   - `test_update_*_no_fields` — 400 (empty body)
   - `test_update_*_duplicate_*` — 409 on name collision
   - `test_delete_*` — 200
   - `test_delete_*_not_found` — 404 (if applicable)
   - `test_delete_*_in_use` — 409 if referential integrity checked

2. **Upload endpoints** have tests for:
   - Successful upload (201)
   - No file (400)
   - Invalid extension (400)
   - Missing required form fields (400)
   - Duplicate version (409)

3. **Unit types tests** exist for every `types.py` covering:
   - Valid create/update
   - Missing required fields
   - Invalid field types
   - `to_update_data()` output

4. **Test patterns are correct:**
   - Uses `authed_client` and `mock_db` from conftest
   - Uses `make_obj()` for mock return values
   - Patches `log_audit` at `api.v2.<module>.<entity>.log_audit` (for catalog) or `src.api.v2.<module>.<entity>.log_audit`
   - Patches `presigned_get_url` with autouse fixture if module uses storage
   - Uses `json.dumps()` for request bodies
   - Assert structure: `response.status_code` then `json.loads(response.data)`

**Reference files:**
- `apps/backend/http-api/tests/conftest.py`
- `apps/backend/http-api/tests/api/catalog/test_products.py`
- `apps/backend/http-api/tests/api/catalog/test_firmware_builds.py`

### Agent 5: Security & Router Review

1. **Router completeness** — Every handler in source has a corresponding `add_url_rule()` in `router.py`

2. **Permission consistency** — Permissions used in decorators match those defined in `permissions.py` and seeded in `prisma/seed.py`

3. **No raw exception exposure** — Search for `str(e)` or `repr(e)` returned in responses

4. **No SQL injection** — Verify all DB queries use parameterized Prisma calls (no string concatenation)

5. **File upload safety** — Extension whitelist checked before processing; path traversal prevented

6. **Storage key safety** — No user input directly in storage keys without sanitization

7. **OpenAPI completeness** — Every route has documentation in `docs.py`

**Reference files:**
- `apps/backend/http-api/src/api/v2/router.py`
- `apps/backend/http-api/src/lib/permissions.py`
- `apps/backend/http-api/src/api/v2/docs.py`

## Output

After all agents complete, compile findings into a structured report:

```
## HTTP API Review Report

### Critical (must fix)
- [ ] Finding with file:line reference

### Warnings (should fix)
- [ ] Finding with file:line reference

### Missing Tests
- [ ] Test that should exist

### Style Issues
- [ ] Minor pattern deviation
```

Then apply auto-fixable changes (import ordering, missing `__init__.py`, etc.) and list what was fixed vs what needs manual review.

## Verification

After applying fixes, run:
```bash
cd apps/backend/http-api
PYTHONPATH=src:$(pwd)/../../../libs/python:$(pwd)/../../../libs:. pytest tests/ -v
python3 -c "import py_compile,glob;[py_compile.compile(f,doraise=True) for f in glob.glob('src/**/*.py',recursive=True)]"
```

All tests must pass and compilation must be clean.
