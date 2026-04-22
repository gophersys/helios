# Concord

Internal hardware testing platform — firmware builds, validation, manufacturing, and fleet management for CoreKinect devices.

## Prerequisites

- VS Code with the Dev Containers extension
- Docker Desktop (or Docker Engine on Linux)
- WSL2 (Windows) or native Linux
- Clone with submodules: `git clone --recursive <repo-url>`

## Getting Started

Open the repo in VS Code and select a devcontainer when prompted. All development happens inside containers — never install dependencies on the host.

| Container | Use case |
|-----------|----------|
| `base` | Backend services, frontend, platform tooling, K8s operations |
| `mtib` | MTIB edge server (runs on arm64 hardware) |
| `ncs-v2.7.0` | Nordic nRF Connect SDK v2.7.0 firmware |
| `ncs-v3.2.1` | Nordic nRF Connect SDK v3.2.1 firmware |
| `zephyr-v4.0` | Zephyr RTOS v4.0 firmware (vanilla, no Nordic HAL) |

On first launch the container runs `ctl.sh create` which installs dependencies, sets up env files, and bootstraps the Docker buildx builder. Subsequent starts run `ctl.sh start` (installs deps only).

See [.devcontainer/README.md](.devcontainer/README.md) for container details, mounts, and cert management.

## Repo Structure

```
apps/
  backend/        HTTP API, build service, git poller, PyPI server
  frontend/       SvelteKit app, MkDocs site, CI dashboard
  edge/           MTIB server (gRPC, runs on Verdin iMX8MM)
  firmware/       Product firmware (submodules)
  manufacturing/  Manufacturing test suites
  validation/     Validation test suites
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
tools/            corectl CLI, env setup, scripts
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

# Run tests
npx nx test http-api
npx nx test app

# Type check
npx nx typecheck http-api
npx nx typecheck app
```

All build, test, and deploy operations go through [Nx](https://nx.dev/). See `.claude/rules/nx-workflow.md` for the full command reference.

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
