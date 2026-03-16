---
paths:
  - "apps/backend/http-api/**/*.py"
---

# Backend API Rules

## Module Structure

Every new API domain creates a module at `src/api/v2/<domain>/` with:
- `__init__.py` (empty)
- `types.py` — request dataclasses with `from_json()` validation
- `shared.py` — constants and helpers (if needed)
- One `.py` file per entity (e.g., `products.py`, `board_revisions.py`)

Reference: `src/api/v2/products/` is the canonical example.

## Request Types

All request types follow this pattern (see `src/api/v2/products/types.py`):

```python
@dataclass
class EntityCreateRequest:
    name: str
    optional_field: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["EntityCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        if not name:
            return None, "Name is required"
        return cls(name=name), None
```

Update requests must include `to_update_data()` returning a dict of changed fields only. Use `_has_field` booleans to track explicitly-set-to-null vs omitted. Note: `to_update_data()` returns only **scalar column fields** for the primary table update. Many-to-many relations managed via join tables (e.g., BOM items) are handled separately in the handler and are intentionally excluded from `to_update_data()`.

## Route Handlers

Every handler must (see `src/api/v2/products/products.py`):

1. Use `@require_permissions(Permissions.ADMIN_<MODULE>_<VIEW|MANAGE>)` decorator
2. Parse request with `EntityRequest.from_json(request.get_json())`; return `bad_request(error)` on failure
3. Check uniqueness/existence before mutations
4. Use `get_db_client()` for Prisma access
5. Call `log_audit(action, entity_type, entity_id, details)` after every mutation
6. Return `jsonify(ApiResponse.ok(data).to_dict()), <status_code>`
7. Use `_serialize_<entity>()` helper functions for consistent output
8. Use `hasattr(obj, "field") and obj.field is not None` for optional relation checks

Status codes: 200 (get/update/delete), 201 (create), 400/404/409 for errors.

## List Endpoints

All list endpoints support pagination:
```python
page = max(1, request.args.get("page", 1, type=int))
limit = min(max(1, request.args.get("limit", 50, type=int)), 100)
skip = (page - 1) * limit
```

Return format: `{"data": [...], "pagination": {"page", "limit", "total", "pages"}}`

## Router Registration

Routes go in `src/api/v2/router.py` using `v2.add_url_rule()`. URL pattern: `/domain/resources[/<id>][/sub-resources[/<sub_id>]]`.

## Error Responses

Use helpers from `src/lib/errors`: `bad_request()`, `not_found()`, `conflict()`, `internal_error()`. Never return raw `str(e)` to clients.

## Permissions

Add new permissions to `src/lib/permissions.py` as `ADMIN_<MODULE>_VIEW` / `ADMIN_<MODULE>_MANAGE` following the `Concord.Admin.<Module>.<Action>` format. Add to `prisma/seed.py` arrays.

## OpenAPI Docs

Every new endpoint must be documented in `src/api/v2/docs.py`. Use the existing `_ok()`, `_paginated()`, `_err_resp()`, `_deleted_resp` helpers. Add schemas for new entities as `spec.components.schema()`.

## Storage

File uploads use MinIO via `src/services/storage/client.py`. Pattern: `storage_key(StoragePrefixes.X, f"{entity}/{id}/{filename}")`. Always set `Content-Disposition: attachment` on download presigned URLs.

## Testing

Tests live in `apps/backend/http-api/tests/`. Run with:
```bash
cd apps/backend/http-api && PYTHONPATH=src:$(pwd)/../../../libs/python:$(pwd)/../../../libs:. pytest tests/ -v
```

When creating a **new** module (via the `add-endpoint` or `add-crud-feature` skill), add:
- `tests/unit/types/test_<domain>_types.py` — `from_json()` tests for every request type
- `tests/api/<domain>/test_<entity>.py` — CRUD route integration tests using `authed_client` and `mock_db`

This is forward-looking only — existing modules without tests are not violations. See `tests/conftest.py` for fixtures and `tests/api/products/` for the reference test pattern.
