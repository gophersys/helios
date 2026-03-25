# Concord — IoT Manufacturing Platform

Monorepo for the Concord platform: firmware management, device validation, inventory tracking, and manufacturing operations.

## Monorepo Structure

```
apps/
  backend/http-api/              # Flask REST API (Python, Prisma ORM, PostgreSQL, MinIO)
  frontend/app/   # SvelteKit SPA (TypeScript, Tailwind CSS)
  edge/mtib-server/              # gRPC embedded test bench server (Python)
libs/
  python/corekinect/             # Shared Python library (MTIB client, utils, protocols)
  protocols/                     # Protobuf definitions
prisma/                          # Prisma schema + migrations
deploy/                          # Helm charts, Docker Compose, deployment CLI
```

## Quick Commands (Always Use Nx)

```bash
# Start development infrastructure
./deploy/ctl.sh development up

# Run apps via Nx (after infra is up)
npx nx serve http-api              # Backend on :9001
npx nx dev app              # Frontend on :4200

# Tests and type checking
npx nx test http-api
npx nx typecheck http-api
npx nx test app

# Build for staging/production
npx nx run http-api:containerize -c staging
npx nx run app:containerize -c staging

# Deploy
./deploy/ctl.sh diff staging       # Preview changes
./deploy/ctl.sh staging deploy     # Build + deploy to staging K8s
./deploy/ctl.sh production deploy  # Build + deploy to production K8s
./deploy/ctl.sh status staging     # Quick status check

# Prisma
npx nx run database:generate-client
npx nx run database:migrate
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| API | Flask + Blueprints, Prisma Client Python, MinIO (S3-compatible) |
| Frontend | SvelteKit, TypeScript, Tailwind CSS |
| Database | PostgreSQL via Prisma ORM |
| Storage | MinIO for firmware builds, artifacts, images |
| Auth | Google OAuth → JWT, permission-set RBAC (toggleable via `AUTH_ENABLED`) |
| Infra | K3s Kubernetes, Helm charts, Docker Compose (local), Traefik ingress |
| Build | Nx monorepo, `@nx-tools/nx-container` for Docker builds |

## Environments

| Env | Purpose | Config Source | Command |
|-----|---------|---------------|---------|
| `development` | Local iteration | `.env` / Docker Compose | `./deploy/ctl.sh development up` + `npx nx serve` |
| `staging` | Pre-prod validation | `deploy/helm/values-staging.yaml` | `./deploy/ctl.sh staging deploy` |
| `production` | Live system | `deploy/helm/values-production.yaml` | `./deploy/ctl.sh production deploy` |

**Promotion flow**: development → staging → production. See `.claude/rules/development-workflow.md`.

**Every new config field must be added to ALL environments.**

## Conventions

- All API responses use `{ "data": <payload>, "errors": [] }` envelope
- Permission format: `Concord.Admin.<Module>.<View|Manage>`
- Frontend uses design token colors (never hardcoded): `surface-0/1/2`, `text-primary/secondary/tertiary`, `accent`, `error`, `success`, `warning`
- Every backend mutation is audit-logged via `log_audit()`
- Backend request validation is done in `types.py` dataclasses with `from_json()` → `(instance, error)` tuple pattern
- New features must include cross-environment tests — see `.claude/rules/testing.md`
