---
paths:
  - "deploy/**/*"
  - "config/**/*.py"
  - "apps/backend/http-api/src/lib/decorators.py"
  - "apps/backend/http-api/src/api/v2/auth/**/*.py"
---

# Environment & Deployment Rules

Concord runs in **three environments**: `development`, `staging`, `production`. Every feature must work correctly across all of them.

## Environments Overview

| Env | How it runs | Auth | Config source |
|-----|------------|------|---------------|
| `development` | Nx serve + Docker Compose infra | Varies | `.env` / shell exports |
| `staging` | K8s via Helm (`ctl.sh staging deploy`) | `AUTH_ENABLED=true` | `deploy/helm/values-staging.yaml` |
| `production` | K8s via Helm (`ctl.sh production deploy`) | `AUTH_ENABLED=true` | `deploy/helm/values-production.yaml` |

## Development Workflow

```bash
# 1. Start infrastructure (DB, MinIO, InfluxDB)
./deploy/ctl.sh development up

# 2. Run apps via Nx
npx nx serve http-api         # Backend on :9001
npx nx dev app         # Frontend on :4200
```

## Wiring Config Fields End-to-End

When adding a new environment-dependent feature (e.g., a config toggle):

1. **Python code**: Add the field to `config/env.py` (ProxyConfig) with a sensible default
2. **Backend logic**: Read via `env_config.FIELD_NAME` — never hardcode the value
3. **Helm values**: Add to `config:` or `secrets:` in BOTH `values-staging.yaml` AND `values-production.yaml`
4. **Docker Compose**: Add to `deploy/local/docker-compose.yaml` environment block
5. **Tests**: Add to `tests/conftest.py:pytest_configure()` AND `tests/unit/test_env_config.py`

Failure to complete ALL steps leads to "works in dev, breaks in production" bugs.

## AUTH_ENABLED Behavior

`AUTH_ENABLED` is a critical toggle:

- When `true`: All endpoints require a valid JWT or API key. Permission sets are checked.
- When `false`: All endpoints are accessible without auth. A default admin identity is injected:
  ```python
  g.current_user = {
      "sub": "00000000-0000-0000-0000-000000000000",
      "email": "admin@concord.local",
      "name": "Admin (auth disabled)",
      "permissionSetId": None,
  }
  ```
- The `/v2/auth/me` endpoint returns a mock admin profile when auth is disabled
- This bypass is implemented in `src/lib/decorators.py` (`require_auth` and `require_permissions`)

## Deployment Commands

```bash
# Build + deploy to staging
./deploy/ctl.sh staging deploy

# Build + deploy to production
./deploy/ctl.sh production deploy

# Check status
./deploy/ctl.sh staging status
./deploy/ctl.sh production status

# Preview Helm changes before deploying (requires helm-diff plugin)
./deploy/ctl.sh diff staging
./deploy/ctl.sh diff production
```

## DB Migrations

Prisma migrations run automatically on every deploy via an init container. The http-api Dockerfile
includes `/prisma/schema.prisma` and `/prisma/migrations/`. The init container executes
`prisma migrate deploy` before the API container starts. If there are no pending migrations,
it exits in ~1s.

To create a new migration:
```bash
cd prisma && npx prisma migrate dev --name <description>
```

## Security Constraints

- `JWT_SECRET_KEY` MUST be different between staging and production
- `JWT_SECRET_KEY` MUST NOT use the default value in production (enforced at startup)
- `DATABASE_URL` MUST be different between staging and production
- Never commit secrets to values files — use `values-*-secrets.yaml` (gitignored) for sensitive overrides
