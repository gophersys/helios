# Development Workflow

Three environments, strict promotion gates, quality checks at each stage.

## Environments

| Environment | Purpose | Infrastructure | Deploy Method |
|------------|---------|---------------|---------------|
| **Development** | Local testing, fast iteration | Docker Compose | `nx start platform` |
| **Staging** | Integration testing, pre-prod validation | Kubernetes | `nx update platform -c staging` |
| **Production** | Live system | Kubernetes | `nx update platform -c production` |

## Development Stage

**Goal**: Fast iteration, verify features work before committing.

### Start Development

```bash
# Start all backend services in Docker containers
nx start platform

# Start the frontend (only UI uses nx serve for HMR)
nx serve app              # Frontend on :4200
```

Backend services always run in containers — never use `nx serve` for backends. After making code changes, run `nx update platform` to rebuild and hot-swap containers.

### Before Committing

```bash
nx typecheck http-api
nx typecheck app
nx test http-api
nx test app
```

### Commit Conventions

```bash
git commit -m "feat(http-api): add device firmware endpoint"
git commit -m "fix(app): correct validation status display"
git commit -m "refactor(protocols): consolidate device message types"
```

## Staging Promotion

**Goal**: Verify changes work in K8s environment identical to production.

### Deploy to Staging

```bash
# Preview changes
nx diff platform -c staging

# Full deploy (builds + pushes + helm upgrade, zero downtime)
nx update platform -c staging

# Verify
nx status platform -c staging
```

## Production Promotion

**Goal**: Deploy validated changes to live system.

### Gate Requirements

1. Staging deploy successful and validated
2. No open P0/P1 issues related to the change
3. Team sign-off (for major changes)

### Deploy to Production

```bash
nx diff platform -c production
nx update platform -c production
nx status platform -c production
```

### Rollback (if needed)

```bash
nx rollback platform -c production
```

## Quick Reference

| Action | Command |
|--------|---------|
| Start dev platform | `nx start platform` |
| Update after code change | `nx update platform` |
| Stop dev platform | `nx stop platform` |
| Dev status | `nx status platform` |
| Start frontend (HMR) | `nx serve app` |
| Run tests | `nx test http-api` |
| Type check | `nx typecheck http-api` |
| Pre-deploy gate | `nx run platform:check` |
| Deploy staging | `nx update platform -c staging` |
| Deploy production | `nx update platform -c production` |
| Full release (staging) | `nx run platform:release -c staging` |
| Full release (production) | `nx run platform:release -c production` |
| Check status | `nx status platform -c staging` |
| Preview diff | `nx diff platform -c staging` |
| Rollback | `nx rollback platform -c staging` |
| Restart pods | `nx restart platform -c staging` |
| Sync secrets | `nx run platform:sync-secrets -c staging` |
| Start CI platform | `nx run deploy-ci:start` |
| CI status | `nx run deploy-ci:status` |
| CI dashboard (local) | `nx serve ci-admin` |
| Trigger nightly CI | `nx run deploy-ci:trigger-nightly` |

## Environment Configuration

Every config field must exist in ALL environments:

| File | Purpose |
|------|---------|
| `deploy/development/docker-compose.yaml` | Development config |
| `deploy/production/helm/values-staging.yaml` | Staging config |
| `deploy/production/helm/values-production.yaml` | Production config |

When adding a new config field, update all three files.
