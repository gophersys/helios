# Local development — knowledge

Clone → green dev loop. What a fresh contributor runs to get the platform serving on `localhost`, the daily commands once it's running, and how to reset when state gets weird.

Refresh this file when: the devcontainer image changes, a new app is added to the dev compose stack, `ctl.sh` lifecycle hooks change, port assignments shift, or the bootstrap UX (`nx start platform`, env file generation) changes.

## Prerequisites

- VS Code with the **Dev Containers** extension installed.
- Docker Desktop (Windows/macOS) or Docker Engine (Linux/WSL2). The host must have `/var/run/docker.sock` writeable.
- Access to your team's secret store for first-run secrets — see [`credentials.md`](credentials.md). Ask the platform owner.
- Bitbucket SSH access — your `~/.ssh-devcontainer/` populated with the `corekinect` SSH key so the devcontainer can clone firmware repos. Keys are mounted **readonly** into the container at `/root/.ssh/`.
- Kubeconfig for the office cluster at `~/.kube/config-concord-remote` if you intend to touch staging or run anything that hits real K8s. Not required for `nx start platform`.

## The flow

### 1. Clone

```bash
git clone --recursive git@bitbucket.org:corekinect/concord.git
cd concord
```

The `--recursive` matters — submodules under `apps/validation/`, `apps/manufacturing/`, and `libs/zephyr/` won't materialize otherwise. Recover later with `git submodule update --init --recursive`.

### 2. Repo-level env file

```bash
cp .env.example .env
$EDITOR .env
```

Set `CONCORD_MONOREPO_ROOT` to the absolute host path of the clone. Docker-in-Docker needs the **host** path (not the container path) to bind-mount volumes. On WSL2 use the Linux path (`/home/<you>/work/concord/concord`), not `/mnt/c/...`.

### 3. Reopen in container

Open the repo in VS Code. When the prompt appears, choose **"Reopen in Container"** → pick the **`base`** devcontainer. The image is `containers.ad.corekinect.com/concord-devcontainer-base:latest`.

| Container | Use case |
|---|---|
| `base` | Backend services, frontend, platform tooling, K8s operations. **Default.** |
| `mtib` | MTIB edge server (runs on arm64 only). |
| `ncs-v2.7.0` | Nordic nRF Connect SDK v2.7.0 firmware builds. |
| `ncs-v3.2.1` | Nordic nRF Connect SDK v3.2.1 firmware builds. |
| `zephyr-v4.0` | Vanilla Zephyr v4.0 (no Nordic HAL). |

First open triggers `./.devcontainer/ctl.sh create` — installs Python/Node deps, sets up the Docker buildx builder, injects the internal CA certs into the system trust store, and copies `.env.example` → `.env` for every service. Subsequent re-opens run `./.devcontainer/ctl.sh start` (deps + preflight).

### 4. Bootstrap service env files

Inside the devcontainer:

```bash
nx run env:setup
nx run env:status
```

`env:setup` copies every `.env.example` listed in `tools/env/known-env-files.txt` to its matching `.env` (idempotent). `env:status` reports which secrets are unpopulated. Fill in the missing values per [`credentials.md`](credentials.md).

### 5. Start the platform

```bash
nx start platform
```

This wraps `docker compose -f deploy/development/docker-compose.yaml up -d`. Brings up:

| Service | Port | What it is |
|---|---:|---|
| `db` (Postgres 16) | `5433` | The concord DB. User/pass `concord/concord`. |
| `minio` | `8675` | S3-compatible storage. Console on `8676`. Root user `concord`, password `concordstorage!`. |
| `pypi` | `8091` | Internal pypiserver — hosts the `corekinect` wheel. |
| `http-api` | `9001` | Flask + SocketIO. The hub. |
| `build-service` | `9002` | Build worker. |
| `git-poller` | (no port) | Bitbucket branch watcher. |

Prisma migrations apply automatically on `http-api` startup. `prisma/seed.py` seeds a default admin user, baseline products, and a dev fixture.

### 6. Serve the frontends

```bash
nx serve app        # http://localhost:4200 — SvelteKit, HMR
nx serve docs       # http://localhost:4000 — MkDocs Material
nx serve ci-admin   # http://localhost:4201 — independent CI dashboard
```

`AUTH_ENABLED=false` is baked into the dev compose stack, so the app auto-logs you in as `admin@concord.local` with full permissions. No Google OAuth round-trip needed.

## Daily commands

| Intent | Command |
|---|---|
| Rebuild + hot-swap a backend container after a code change | `nx update platform` |
| Restart a single service | `docker compose -f deploy/development/docker-compose.yaml restart http-api` |
| Tail logs | `docker compose -f deploy/development/docker-compose.yaml logs -f http-api` |
| Stop everything | `nx stop platform` |
| Run backend tests | `nx test http-api` |
| Run frontend unit tests | `nx test app` |
| Run frontend E2E | `nx run app:test:e2e` |
| Type check | `nx typecheck http-api` / `nx typecheck app` |
| Lint | `nx run app:lint` |
| Apply a new Prisma migration | `cd prisma && npx prisma migrate dev --name <name>` |
| Regenerate the Python Prisma client | `npx prisma generate` |
| Connect to the DB | `psql postgresql://concord:concord@localhost:5433/concord` |

All build, test, deploy, run actions go through Nx. Bare `docker compose`, `pytest`, `vitest`, `helm`, `prisma migrate` are forbidden — see [`../../../rules/nx-only.md`](../../rules/nx-only.md).

## URLs at a glance

| What | URL |
|---|---|
| Frontend app | http://localhost:4200 |
| HTTP API | http://localhost:9001 |
| Build service | http://localhost:9002 |
| MinIO console | http://localhost:8676 |
| MinIO S3 API | http://localhost:8675 |
| Docs (MkDocs) | http://localhost:4000 |
| CI admin | http://localhost:4201 |
| Postgres | localhost:5433 |
| PyPI mirror | http://localhost:8091 |

## Resetting the local DB

When migrations diverge, seed data drifts, or you want a known-clean state:

```bash
nx stop platform
docker volume rm development-postgres_data
nx start platform
```

Postgres comes up empty; the http-api init flow re-applies every migration and reruns `prisma/seed.py`. MinIO state lives in `development-minio_data` — wipe it the same way if uploads have gone weird.

## Resetting everything

```bash
nx stop platform
docker volume rm development-postgres_data development-minio_data \
                  development-build_workspace development-ccache_data \
                  development-pypi_packages
nx start platform
```

Then re-upload any test packages or asset sets you were working with.

## Working off-site (concord-remote)

When you need staging K8s access from outside the office network, start the WSL tunnel:

```bash
~/work/docs/CONCORD-REMOTE.md   # full procedure
```

Sets `KUBECONFIG=~/.kube/config-concord-remote`. Verify with `kubectl get nodes`. See [`debugging.md`](debugging.md) for what to do with it.

## Troubleshooting

**`port is already allocated` on `nx start platform`** — another compose stack or local Postgres is on the port. `docker ps -a | grep <port>`; stop the conflicting container or change `POSTGRES_PORT` in `deploy/development/.env`.

**HTTP API stuck in `Init:CrashLoopBackOff` (locally that's just the container exiting on startup)** — migration failure. `docker compose logs http-api` → look for `P3009`. Either reset the DB (above) or hand-write a corrective forward migration. Never edit a committed migration.

**`Cannot connect to Docker daemon`** — Docker Desktop isn't running, or the WSL2 integration is off. Restart Docker Desktop. Inside the devcontainer the socket is bind-mounted from the host at `/var/run/docker.sock`.

**Frontend gets `401` on every request** — the dev bypass relies on `AUTH_ENABLED=false`. If you've toggled it, also clear `localStorage.concord-token`. Confirm with `docker compose exec http-api env | grep AUTH_ENABLED`.

**`prisma generate` complains about missing `database` package** — you ran it outside the devcontainer or before `nx run env:setup`. The generated client lands in `libs/python/database/` and is picked up via `pythonpath` in `apps/backend/http-api/pytest.ini`.

**Build worker never picks up a job** — `docker compose logs build-service`. The worker polls `GET /v2/builds?status=QUEUED&limit=20` every `SCHEDULER_INTERVAL_S` seconds (default 15). If it sees jobs but never claims, check `BITBUCKET_SSH_KEY` is populated — the clone step fails silently otherwise.

**SSH clone fails inside the devcontainer** — your `~/.ssh-devcontainer/` is empty or the wrong key. The host directory is mounted **readonly** at `/root/.ssh/`. Drop a `config` + key pair there matching what Bitbucket expects for the `corekinect` workspace.

## Related knowledge

- [`credentials.md`](credentials.md) — every secret you'll be asked to fill in
- [`testing.md`](testing.md) — pytest, vitest, Playwright markers and forbidden patterns
- [`debugging.md`](debugging.md) — reading prod logs once you have a real bug
- [`../architecture.md`](../architecture.md) — what the services you just started actually do
- [`../../rules/nx-only.md`](../../rules/nx-only.md) — why bare `docker compose` is forbidden
- [`../../rules/prisma-flow.md`](../../rules/prisma-flow.md) — schema changes end-to-end
