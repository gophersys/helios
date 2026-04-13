# Nx Workflow Rules

**ALWAYS use Nx for ALL build, test, and deploy operations.** Never run raw commands directly.

## Core Principle

Nx provides caching, dependency tracking, and parallel execution. Running raw commands bypasses these benefits and can cause inconsistent builds.

## Commands Reference

### Platform Lifecycle

```bash
# Development
nx start platform              # Start all services in Docker containers
nx update platform             # Rebuild + hot-swap changed containers
nx stop platform               # Compose down

# Staging / Production
nx start platform -c staging   # Full 0→running (infra + secrets + build + deploy)
nx update platform -c staging  # Rebuild + deploy (zero downtime)
nx stop platform -c staging    # Helm uninstall
nx run platform:status -c staging

# Frontend only (HMR dev server — only UI uses nx serve)
npx nx serve app               # SvelteKit on :4200
```

### Testing

```bash
npx nx test http-api
npx nx test app
npx nx typecheck http-api
npx nx typecheck app
npx nx run-many -t test typecheck  # All in parallel
```

### Building (handled automatically by update/start)

```bash
npx nx run http-api:containerize -c staging
npx nx run app:containerize -c staging
```

### Infrastructure

```bash
npx nx test infrastructure                    # Run all infra tests
npx nx run infrastructure:bootstrap -c office # Set up cluster
npx nx run infrastructure:secrets -c office   # Create K8s secrets
npx nx run infrastructure:status -c office    # Check readiness
```

### CI Platform

```bash
npx nx run deploy-ci:start          # Install CI Helm chart (MinIO + CronJobs + dashboard)
npx nx run deploy-ci:stop           # Uninstall (preserves PVCs)
npx nx run deploy-ci:update         # Rebuild dashboard image + redeploy
npx nx run deploy-ci:status         # Show CI resources in K8s
npx nx run deploy-ci:trigger-nightly  # Manual nightly run
npx nx run deploy-ci:trigger-weekly   # Manual weekly run
npx nx run ci:validate              # Run PR pipeline locally (.ci/run pr)
npx nx serve ci-admin               # Dashboard dev server on :4300
```

## NEVER Do These

```bash
# WRONG — backends always run in containers, never via nx serve
npx nx serve http-api

# WRONG — bypasses Nx
cd apps/backend/http-api && python3 -m src.main

# WRONG — use nx update platform instead
docker build -t concord/http-api .

# RIGHT
nx start platform           # Start everything
nx update platform          # After code changes
npx nx test http-api        # Run tests
```

## Nx Project Dependencies

When modifying code, Nx automatically tracks dependencies:

- `http-api` depends on `protocols` (protobuf)
- `http-api` depends on `database` (Prisma client)
- `app` depends on `http-api` types
- `validation-alpha` depends on `protocols`
- `mtib-server` depends on `protocols`
- `ci-admin` is independent (standalone dashboard app)
- `deploy-ci` manages the CI Helm chart (independent from platform)

After changing a library, Nx will rebuild all dependents.

## Caching

Nx caches build/test outputs in `.nx/cache`. Docker layer caching handles container builds — unchanged services rebuild in sub-second.

If you need to bypass cache (rare): `npx nx reset && npx nx <command>`

## Adding New Projects

1. Create `project.json` in the project root
2. Define targets: `build`, `test`, `containerize`
3. Add `implicitDependencies` if needed
4. Add Helm template + values entries
5. Add to `deploy/ctl.sh` build/push targets
