# Development Workflow

Three environments, strict promotion gates, quality checks at each stage.

## Environments

| Environment | Purpose | Infrastructure | Deploy Method |
|------------|---------|---------------|---------------|
| **Development** | Local testing, fast iteration | Docker Compose | `nx start platform` |
| **Staging** | Integration testing, pre-prod validation | Kubernetes | `nx start platform -c staging` |
| **Production** | Live system | Kubernetes | `nx update platform -c production` |

## Development Stage

**Goal**: Fast iteration, verify features work before committing.

### Start Development

```bash
# Start all backend services in Docker containers
nx start platform

# Start the frontend (only UI uses nx serve for HMR)
npx nx serve app              # Frontend on :4200
```

Backend services always run in containers — never use `nx serve` for backends. After making code changes, run `nx update platform` to rebuild and hot-swap containers.

### Before Committing

```bash
npx nx typecheck http-api
npx nx typecheck app
npx nx test http-api
npx nx test app
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
./deploy/ctl.sh staging diff

# Full deploy (builds + pushes + helm upgrade, zero downtime)
nx update platform -c staging

# Verify
nx run platform:status -c staging
./deploy/ctl.sh staging logs http-api
```

## Production Promotion

**Goal**: Deploy validated changes to live system.

### Gate Requirements

1. Staging deploy successful and validated
2. No open P0/P1 issues related to the change
3. Team sign-off (for major changes)

### Deploy to Production

```bash
./deploy/ctl.sh production diff
nx update platform -c production
nx run platform:status -c production
```

### Rollback (if needed)

```bash
helm rollback concord -n production
helm history concord -n production  # List revisions
```

## Quick Reference

| Action | Command |
|--------|---------|
| Start dev platform | `nx start platform` |
| Update after code change | `nx update platform` |
| Stop dev platform | `nx stop platform` |
| Start frontend (HMR) | `npx nx serve app` |
| Run tests | `npx nx test http-api` |
| Type check | `npx nx typecheck http-api` |
| Deploy staging | `nx update platform -c staging` |
| Deploy production | `nx update platform -c production` |
| Check status | `nx run platform:status -c staging` |
| View diff | `./deploy/ctl.sh staging diff` |
| Start CI platform | `bash deploy/ci/ctl.sh start` |
| CI status | `bash deploy/ci/ctl.sh status` |
| CI dashboard (local) | `cd apps/ci/admin && npm run dev` (port 4300) |
| Trigger nightly CI | `kubectl create job --from=cronjob/concord-ci-nightly ci-manual -n devops` |
| Run PR pipeline locally | `.ci/run pr` |

## Environment Configuration

Every config field must exist in ALL environments:

| File | Purpose |
|------|---------|
| `deploy/development/docker-compose.yaml` | Development config |
| `deploy/production/helm/values-staging.yaml` | Staging config |
| `deploy/production/helm/values-production.yaml` | Production config |

When adding a new config field, update all three files.
