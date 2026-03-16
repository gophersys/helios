# Development Workflow

Three environments, strict promotion gates, quality checks at each stage.

## Environments

| Environment | Purpose | Infrastructure | Deploy Method |
|------------|---------|---------------|---------------|
| **Development** | Local testing, fast iteration | Docker Compose | `./deploy/ctl.sh development up` |
| **Staging** | Integration testing, pre-prod validation | Kubernetes | `./deploy/ctl.sh staging deploy` |
| **Production** | Live system | Kubernetes | `./deploy/ctl.sh production deploy` |

## Development Stage

**Goal**: Fast iteration, verify features work before committing.

### Start Development

```bash
# 1. Start infrastructure (DB, MinIO, InfluxDB)
./deploy/ctl.sh development up

# 2. Run apps via Nx
npx nx serve http-api        # Backend on :9001
npx nx dev app        # Frontend on :4200
```

### Before Committing

Run all quality checks:

```bash
# Type checks
npx nx typecheck http-api
npx nx typecheck app

# Tests
npx nx test http-api
npx nx test app

# Lint (if configured)
npx nx lint http-api
npx nx lint app
```

**All checks must pass before committing.**

### Commit Conventions

```bash
# Feature
git commit -m "feat(http-api): add device firmware endpoint"

# Bug fix
git commit -m "fix(app): correct validation status display"

# Refactor
git commit -m "refactor(protocols): consolidate device message types"
```

## Staging Promotion

**Goal**: Verify changes work in K8s environment identical to production.

### Gate Requirements

Before deploying to staging:

1. All development checks pass
2. Code is committed and pushed
3. No breaking changes to API contracts (or version bump)

### Deploy to Staging

```bash
# Preview changes
./deploy/ctl.sh diff staging

# Deploy (builds + pushes + helm upgrade)
./deploy/ctl.sh staging deploy

# Verify
./deploy/ctl.sh staging status
./deploy/ctl.sh staging logs http-api
```

### Staging Validation

After deploy, verify:

```bash
# API health
curl -s https://staging.concord.local/v2/docs | head

# Run integration tests (if available)
npx nx test validation-alpha --configuration=staging
```

## Production Promotion

**Goal**: Deploy validated changes to live system.

### Gate Requirements

Before deploying to production:

1. Staging deploy successful
2. Staging validation passed
3. No open P0/P1 issues related to the change
4. Team sign-off (for major changes)

### Deploy to Production

```bash
# Preview changes
./deploy/ctl.sh diff production

# Deploy
./deploy/ctl.sh production deploy

# Verify
./deploy/ctl.sh production status
./deploy/ctl.sh production logs http-api
```

### Rollback (if needed)

```bash
# Rollback Helm release
helm rollback concord -n production

# Or redeploy previous version
./deploy/ctl.sh production deploy --set httpApi.image.tag=<previous-tag>
```

## Quick Reference

| Action | Command |
|--------|---------|
| Start dev infra | `./deploy/ctl.sh development up` |
| Stop dev infra | `./deploy/ctl.sh development down` |
| Run backend | `npx nx serve http-api` |
| Run frontend | `npx nx dev app` |
| Run tests | `npx nx test http-api` |
| Type check | `npx nx typecheck http-api` |
| Build staging | `npx nx run http-api:containerize -c staging` |
| Deploy staging | `./deploy/ctl.sh staging deploy` |
| Deploy production | `./deploy/ctl.sh production deploy` |
| Check status | `./deploy/ctl.sh status staging` |
| View diff | `./deploy/ctl.sh diff staging` |

## Environment Configuration

Every config field must exist in ALL environments:

| File | Purpose |
|------|---------|
| `deploy/local/.env` | Development secrets |
| `deploy/helm/values-staging.yaml` | Staging config |
| `deploy/helm/values-production.yaml` | Production config |

When adding a new config field, update all three files.
