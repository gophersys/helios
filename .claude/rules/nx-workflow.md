# Nx Workflow Rules

**ALWAYS use Nx for ALL build, test, and deploy operations.** Never run raw commands directly.

## Core Principle

Nx provides caching, dependency tracking, and parallel execution. Running raw commands bypasses these benefits and can cause inconsistent builds.

## Platform Lifecycle (7 core verbs)

All platform operations go through `nx <verb> platform` with an optional `-c <env>` configuration flag. Development is the default when no `-c` is specified.

```bash
# Development (default — Docker Compose)
nx start platform              # Start all services in Docker containers
nx stop platform               # Compose down
nx status platform             # Show container status
nx update platform             # Rebuild + hot-swap changed containers

# Staging / Production (Kubernetes)
nx start platform -c staging   # Full 0→running (infra + secrets + build + deploy)
nx stop platform -c staging    # Helm uninstall
nx status platform -c staging  # Show pods + services
nx update platform -c staging  # Rebuild + deploy (zero downtime)
nx diff platform -c staging    # Preview Helm changes before deploy
nx restart platform -c staging # Rolling restart of pods
nx rollback platform -c staging # Helm rollback to previous revision
```

### Arg forwarding

`update` and `restart` forward extra args to `ctl.sh`:

```bash
nx update platform -c staging -- --sync-secrets    # Force secret sync during deploy
nx restart platform -c staging -- frontend         # Restart specific service
```

### Environment support matrix

| Verb | dev | staging | production |
|------|-----|---------|------------|
| start | yes | yes | yes |
| stop | yes | yes | yes |
| status | yes | yes | yes |
| update | yes | yes | yes |
| diff | — | yes | yes |
| restart | — | yes | yes |
| rollback | — | yes | yes |

## Frontend Dev Servers

Only frontend apps have `serve` targets for HMR:

```bash
nx serve app                   # SvelteKit on :4200
nx serve docs                  # MkDocs on :4000
nx serve ci-admin              # CI dashboard on :4300
```

Backends NEVER use `nx serve` — they always run in containers via `nx start platform`.

## Testing

```bash
nx test http-api
nx test app
nx typecheck http-api
nx typecheck app
nx run-many -t test typecheck  # All in parallel

# Platform-level test targets
nx run platform:check          # Tests + typecheck (pre-deploy gate)
nx run platform:test           # All unit tests
nx run platform:test:smoke -c staging  # Smoke test live environment
```

## Secrets

```bash
nx run platform:sync-secrets -c staging     # Push env files → K8s secrets
nx run platform:sync-secrets -c production
nx update platform -c staging -- --sync-secrets  # Sync + deploy in one step
```

## Release (check + deploy + smoke in one step)

```bash
nx run platform:release -c staging
nx run platform:release -c production
```

## CI Platform

```bash
nx run deploy-ci:start           # Install CI Helm chart
nx run deploy-ci:stop            # Uninstall (preserves PVCs)
nx run deploy-ci:update          # Rebuild dashboard + redeploy
nx run deploy-ci:status          # Show CI resources
nx run deploy-ci:trigger-nightly # Manual nightly run
nx run deploy-ci:trigger-weekly  # Manual weekly run
nx serve ci-admin                # Dashboard dev server on :4300
```

## Infrastructure

```bash
nx test infrastructure                     # Run all infra tests
nx run infrastructure:bootstrap -c office  # Set up cluster
nx run infrastructure:status -c office     # Check readiness
```

## NEVER Do These

```bash
# WRONG — backends always run in containers
nx serve http-api           # target doesn't exist

# WRONG — bypasses Nx
cd apps/backend/http-api && python3 -m src.main

# WRONG — use nx update platform instead
docker build -t concord/http-api .

# WRONG — use nx commands, not ctl.sh directly
bash deploy/ctl.sh staging update
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

If you need to bypass cache (rare): `nx reset && nx <command>`

## Adding New Projects

1. Create `project.json` in the project root
2. Define targets: `build`, `test`, `containerize`
3. Add `implicitDependencies` if needed
4. Add Helm template + values entries
5. Add to `deploy/ctl.sh` build/push targets
