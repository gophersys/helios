# Concord

Internal hardware testing platform — firmware builds, validation, manufacturing, and fleet management for CoreKinect devices.

## Prerequisites

- VS Code with the Dev Containers extension
- Docker Desktop (or Docker Engine on Linux)
- WSL2 (Windows) or native Linux
- Clone with submodules: `git clone --recursive <repo-url>`

## Getting Started

```bash
cp .env.example .env
# Edit .env — set CONCORD_MONOREPO_ROOT to your clone path
```

Open the repo in VS Code and select a devcontainer when prompted. All development happens inside containers — never install dependencies on the host.

| Container | Use case |
|-----------|----------|
| `base` | Backend services, frontend, platform tooling, K8s operations |
| `mtib` | MTIB edge server (runs on arm64 hardware) |
| `ncs-v2.7.0` | Nordic nRF Connect SDK v2.7.0 firmware |
| `ncs-v3.2.1` | Nordic nRF Connect SDK v3.2.1 firmware |
| `zephyr-v4.0` | Zephyr RTOS v4.0 firmware (vanilla, no Nordic HAL) |

On first launch the container runs `ctl.sh create` which installs dependencies, sets up env files, creates the Docker buildx builder, and injects internal CA certificates. Subsequent starts run `ctl.sh start` (installs deps, runs preflight checks).

See [.devcontainer/README.md](.devcontainer/README.md) for container details, mounts, and cert management.

## Repo Structure

```
apps/
  backend/        HTTP API, build service, git poller
  frontend/       SvelteKit app, MkDocs docs site
  ci/             CI dashboard (standalone SvelteKit app)
  edge/           MTIB server (gRPC, runs on Verdin iMX8MM)
  firmware/       Embedded firmware (ICLE power monitor)
  manufacturing/  Manufacturing test suites (submodules)
  validation/     Validation test suites (submodules)
libs/
  python/         Shared Python libraries
  protocols/      Protobuf definitions
  zephyr/         Zephyr drivers and board definitions (submodules)
  schemas/        JSON schemas
deploy/
  development/    Docker Compose stack
  production/     Helm charts, values files
  ci/             CI platform (Helm chart, CronJobs, dashboard)
infrastructure/   Cluster provisioning (namespaces, RBAC, storage, networking)
prisma/           Database schema and migrations
tools/
  corectl/        corectl CLI
  env/            Environment file manager (.env setup, validation, secrets status)
docs/             Product documentation (MkDocs)
tests/            Platform-level E2E, integration, and smoke tests
```

## Development

```bash
# Start the full platform (backend services in containers)
nx start platform

# Frontend dev server with HMR
npx nx serve app

# After code changes, rebuild and hot-swap containers
nx update platform

# Stop the platform
nx stop platform

# Run tests
npx nx test http-api
npx nx test app

# Type check
npx nx typecheck http-api
npx nx typecheck app
```

All build, test, and deploy operations go through [Nx](https://nx.dev/). See `.claude/rules/nx-workflow.md` for the full command reference.

## DevContainer Images

Build and push devcontainer images from inside a running devcontainer:

```bash
nx run devcontainer:create-platform-builder   # One-time: create multi-arch builder + inject CA certs
nx run devcontainer:build-all                 # Build base → all variants (local)
nx run devcontainer:push-all                  # Build + push all to registry
```

## Deployment

```bash
# Staging
nx update platform -c staging

# Production
nx update platform -c production
```

## Documentation

```bash
npx nx serve docs    # http://localhost:4000
```

Docs use MkDocs Material with role-based page filtering. See `docs/` for content and `mkdocs.yml` for nav config.
