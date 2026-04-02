# Nx Workflow Rules

**ALWAYS use Nx for ALL build, test, and deploy operations.** Never run raw commands directly.

## Core Principle

Nx provides caching, dependency tracking, and parallel execution. Running raw commands bypasses these benefits and can cause inconsistent builds.

## Commands Reference

### Development

```bash
# Start development infrastructure (DB, MinIO, InfluxDB)
nx start platform

# Run backend locally (after infra is up)
npx nx serve http-api

# Run frontend locally
npx nx serve app

# Run both in parallel
npx nx run-many -t serve dev -p http-api app
```

### Testing

```bash
# Backend tests
npx nx test http-api

# Frontend tests
npx nx test app

# Type checking
npx nx typecheck http-api
npx nx typecheck app

# All tests in parallel
npx nx run-many -t test typecheck
```

### Building

```bash
# Build for staging
npx nx run http-api:containerize -c staging
npx nx run app:containerize -c staging

# Build for production
npx nx run http-api:containerize -c production
npx nx run app:containerize -c production
```

### Deployment

```bash
# Deploy to staging (includes build)
./deploy/ctl.sh staging deploy

# Deploy to production (includes build)
./deploy/ctl.sh production deploy

# Preview changes before deploy
./deploy/ctl.sh diff staging
./deploy/ctl.sh diff production
```

## NEVER Do These

```bash
# WRONG - bypasses Nx caching
cd apps/backend/http-api && python3 -m src.main

# WRONG - bypasses Nx
docker build -t concord/http-api .

# WRONG - no dependency tracking
pytest tests/

# RIGHT - use Nx
npx nx serve http-api
npx nx run http-api:containerize
npx nx test http-api
```

## Nx Project Dependencies

When modifying code, Nx automatically tracks dependencies:

- `http-api` depends on `protocols` (protobuf)
- `http-api` depends on `database` (Prisma client)
- `app` depends on `http-api` types
- `validation-alpha` depends on `protocols`
- `mtib-server` depends on `protocols`

After changing a library, Nx will rebuild all dependents. Don't manually rebuild each project.

## Caching

Nx caches build/test outputs in `.nx/cache`. The cache is valid based on:
- Source file hashes
- Dependency output hashes
- Environment variables in `nx.json`

If you need to bypass cache (rare): `npx nx reset && npx nx <command>`

## Adding New Projects

When adding a new app or library:

1. Create `project.json` in the project root
2. Define targets: `build`, `test`, `serve`, `containerize`
3. Add `implicitDependencies` if needed
4. Add to appropriate `nx.json` target defaults
