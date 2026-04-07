---
paths:
  - "apps/backend/http-api/src/**/*.py"
  - "apps/frontend/app/src/**/*.{ts,svelte}"
  - "apps/frontend/app/src/**/*.{ts,svelte}"
  - "deploy/production/helm/**/*.yaml"
  - "deploy/development/**/*.yaml"
  - "config/**/*.py"
---

# Testing Rules

After completing a new feature, bug fix, or significant refactor, run the test suites:

- **Backend**: `cd apps/backend/http-api && PYTHONPATH=src:$(pwd)/../../../libs/python:$(pwd)/../../../libs:. pytest tests/ -v`
- **Frontend**: `cd apps/frontend/app && npx nx test app`

## Requirements

These rules are **forward-looking only** — they apply when writing new code via the `add-endpoint`, `add-page`, or `add-crud-feature` skills. They do NOT apply retroactively to existing modules. Do not flag existing code as a violation for lacking tests.

- When adding a **new** backend route handler (via skill), add corresponding tests in `tests/api/<domain>/`
- When adding a **new** frontend page or component (via skill), add a colocated `.spec.tsx` file
- When adding a **new** request validation type (`types.py` via skill), add `from_json()` tests covering valid input, missing required fields, and invalid values
- When modifying an existing handler/page that already has tests, update the tests to cover the change
- Never skip tests with `@pytest.skip` or `it.skip` without a comment explaining why

Existing modules that already have tests: `products` (backend + frontend), `inventory` (backend types + API), `codebases` (backend types + API). All other existing modules are exempt from retroactive test requirements.

## Cross-Environment Testing (MANDATORY)

These rules apply to ALL changes, not just those made via skills. They prevent regressions like config fields existing in deployment manifests but never being read by application code.

### Auth behavior

When modifying **any** auth-related code (decorators, middleware, login, endpoints behind `@require_permissions`):

1. Test with `AUTH_ENABLED=true` (normal auth flow — JWT required, permissions checked)
2. Test with `AUTH_ENABLED=false` (bypass flow — no token needed, default admin identity returned)
3. Use `patch("config.env.env_config.AUTH_ENABLED", True/False)` to toggle behavior in tests
4. See `tests/auth/test_auth_bypass.py` for the reference pattern

### Environment config fields

When adding a **new field** to `config/env.py` (ProxyConfig):

1. Add the field to `tests/conftest.py:pytest_configure()` env_vars dict so all tests have it set
2. Add a test in `tests/unit/test_env_config.py:TestProxyConfigFieldCoverage` asserting the field exists and has the correct type
3. If the field is a `bool`, add parsing tests (string `"true"`/`"false"` → Python `True`/`False`)
4. Add the key to `_REQUIRED_CONFIG_KEYS` or `_REQUIRED_SECRET_KEYS` in the same test file if it must appear in Helm values

### Helm values consistency

When modifying `deploy/production/helm/values-staging.yaml` or `deploy/production/helm/values-production.yaml`:

1. Mirror config/secret changes to **both** environment files
2. The tests in `tests/unit/test_env_config.py:TestHelmValuesCompleteness` will catch missing keys
3. `AUTH_ENABLED` must be a **quoted string** (`"true"` or `"false"`), never a bare YAML boolean
4. Staging and production must have **different** `JWT_SECRET_KEY` and `DATABASE_URL` values

## Backend Test Patterns

### Directory structure
```
tests/
  conftest.py              # MockPrismaClient, auth fixtures, Flask test client
  unit/types/              # Pure from_json() validation tests
  unit/lib/                # ApiResponse, utility tests
  auth/                    # JWT, decorator tests
  api/<domain>/            # Route handler integration tests
```

### Mock import paths
When patching functions, use the module path **without** the `src.` prefix since modules are loaded via the `src/` PYTHONPATH entry:
- `patch("api.v2.auth.login.verify_google_token", ...)` — NOT `src.api.v2...`
- `patch("api.v2.products.products.log_audit")` — NOT `src.api.v2...`

### Storage mocking
Modules that import `presigned_url` from `shared.py` will trigger real MinIO connections. Use an `autouse` fixture to mock at the source:
```python
@pytest.fixture(autouse=True)
def _mock_presigned_url():
    with patch("api.v2.<domain>.shared.presigned_get_url", return_value=None):
        yield
```

For delete handlers that call `get_storage_client()` directly, patch at the handler module:
```python
with patch("api.v2.<domain>.<entity>.get_storage_client", return_value=mock_storage):
    with patch("api.v2.<domain>.<entity>.get_bucket_name", return_value="test-bucket"):
```

### Permission set mocks
The `authed_client` fixture mocks `permissionset.find_unique` for the auth decorator. If a test also needs to use `permissionset.find_unique` for business logic, **always include the `permissions` field** so the auth decorator doesn't break:
```python
mock_db.permissionset.find_unique.return_value = make_obj(
    id="perm-1", name="Admin", permissions=_all_perms,
)
```

### Key fixtures (from conftest.py)
- `mock_db` — MockPrismaClient patching the module-level global
- `auth_headers` — Real JWT headers using test secret key
- `client` — Flask test client (no auth)
- `authed_client` — Wraps client with auth headers + superadmin permissions
- `make_obj(**kwargs)` — Creates `SimpleNamespace` for mock DB returns

## Frontend Test Patterns

### Test helpers (from `src/testing/`)
- `renderApp(ui, { auth?, route? })` — Wraps with AuthContext + MemoryRouter
- `authenticatedAuth(permissions?)` — Mock auth context with given permissions
- `unauthenticatedAuth()` — Mock auth context without user
- `mockFetch(data)` / `mockFetchRoutes(routes)` — Mock `global.fetch`
- `createProduct()`, `createCodebase()`, etc. — Factory functions for test data

### Test file naming
- Colocated: `<component>.spec.tsx` next to `<component>.tsx`
- Pure utils: `<util>.spec.ts` next to `<util>.ts`
