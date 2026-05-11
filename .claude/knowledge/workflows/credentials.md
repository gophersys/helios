# Credentials — knowledge

Every credential a developer needs to operate the platform locally, where it lives in dev, where it lives in staging/production, and how to obtain it. Bitwarden is the canonical store; this file is the index.

Refresh this file when: a new credential is added to any `.env.example`, a credential is rotated, the Bitwarden vault is renamed, or the K8s Secret sync flow changes.

## Prerequisites

- Bitwarden account on the `secrets.mateosegura.com` server. Ask the platform owner to be invited.
- The Bitwarden CLI (`bw`) — not strictly required, but the in-browser app works too.
- A populated `~/.ssh-devcontainer/` directory on the host (this is the dir bind-mounted readonly into the devcontainer at `/root/.ssh/`).

## The canonical store

| Layer | Where | Used by |
|---|---|---|
| Source of truth | Bitwarden vault `Concord/` | humans |
| Production / staging runtime | K8s `Secret` resources in `production` / `staging` namespaces | running pods |
| Sync mechanism | `infrastructure/clusters/office/secrets/create-all.sh` reads `shared.env` + per-env `.env` and applies as K8s Secrets | platform admins |
| Local dev runtime | per-service `.env` (gitignored) + `deploy/development/.env` (gitignored) | docker-compose |
| Templates | every `.env.example` in `tools/env/known-env-files.txt` (committed) | onboarding |

See [`../../rules/secrets-handling.md`](../../rules/secrets-handling.md) for what may and may not enter git.

## The credentials, by domain

Most of these are populated automatically as empty placeholders by `nx run env:setup`. Run `nx run env:status` to see which are missing.

### Bitbucket (firmware repo access)

| Variable | Lives in | Bitwarden item | Notes |
|---|---|---|---|
| `BITBUCKET_SSH_KEY` | `deploy/development/.env`, `apps/backend/http-api/.env`, `apps/backend/build-service/.env`, `apps/backend/git-poller/.env` | `Concord/bitbucket-ssh-key` | Base64-encoded private key. Generate: `cat ~/.ssh/keys/bitbucket \| base64 -w0`. Required for `build-service`, `git-poller`, and http-api to clone firmware repos. |
| `BITBUCKET_API_TOKEN` | same set | `Concord/bitbucket-api-token` | Workspace token for REST API (PRs, webhooks, branch listing). |
| `BITBUCKET_EMAIL` | same set | your email | `you@corekinect.com`. Used as git author when concord performs operations on behalf of you. |
| `BITBUCKET_WORKSPACE` | `apps/backend/http-api/.env` (and docker-compose) | hardcoded | `corekinect`. Don't change. |
| `BITBUCKET_WEBHOOK_SECRET` | `apps/backend/http-api/.env` | `Concord/bitbucket-webhook-secret` | HMAC secret. Only required if you're testing real Bitbucket webhook delivery; otherwise blank. |

The SSH key also has to be present **as a real key file** at `~/.ssh-devcontainer/` on the host so VS Code's container can SSH directly (e.g. when running `git pull` inside the container). The base64 env var is a parallel input used by service workers — they decode and inject the key at runtime.

### Kubernetes (staging/production access)

| File | Source | Purpose |
|---|---|---|
| `~/.kube/config` | office cluster admin (issued via `kubeadm` / k3s join) | Direct cluster access when on-site |
| `~/.kube/config-concord-remote` | provisioned by the `concord-remote` tunnel installer (a separate tool in the umbrella `work/` workspace — not in this repo) | Off-site staging/prod access via WSL tunnel |

Both are mounted into the devcontainer **readonly** at `/root/.kube/`. The `http-api` container in dev compose bind-mounts your host `~/.kube` at `/tmp/.kube` and reads `KUBECONFIG=/tmp/.kube/config` so it can discover MTIB nodes and schedule jobs against your cluster of choice.

To switch contexts inside the devcontainer:

```bash
export KUBECONFIG=$HOME/.kube/config-concord-remote
kubectl config use-context concord-remote-staging
```

### Google OAuth (production auth)

| Variable | Lives in | Bitwarden item | Notes |
|---|---|---|---|
| `JWT_SECRET_KEY` | `apps/backend/http-api/.env` | `Concord/jwt-secret-staging` and `Concord/jwt-secret-production` | 32+ char string. Used to sign HS256 JWTs. Enforced ≥32 chars in staging/production at startup. Default `concord-dev-jwt-secret-change-in-production` is fine for local dev. |
| `AUTH_SERVER_URL` | `apps/backend/http-api/.env` | hardcoded | `https://auth.office.corekinect.cloud:2013`. Only consulted in non-dev (`AUTH_ENABLED=true`). |
| `AUTH_SERVER_API_KEY` | `apps/backend/http-api/.env` | `Concord/auth-server-api-key` | Required when `AUTH_ENABLED=true`. Blank in dev. |

In dev, set `AUTH_ENABLED=false` and the API injects a synthetic admin (`admin@concord.local`) on every request. **Never** set `AUTH_ENABLED=false` in staging or production — the startup check refuses to come up.

### MinIO (object storage)

| Variable | Default in dev | Lives in |
|---|---|---|
| `STORAGE_ACCESS_KEY` | `concord` | `apps/backend/http-api/.env`, `apps/backend/build-service/.env`, dev compose |
| `STORAGE_SECRET_ACCESS_KEY` | `concordstorage!` | same |
| `STORAGE_BUCKET_NAME` | `concord` | same |
| `STORAGE_URL` | `http://localhost:8675` (host) / `http://minio:8675` (compose network) | same |

In staging/production these point at the cluster's MinIO deployment with secrets from K8s.

### CoreOps (device personalization)

| Variable | Lives in | Bitwarden item |
|---|---|---|
| `COREOPS_API_KEY` | `apps/backend/http-api/.env` | `Concord/coreops-api-key` |
| `COREOPS_AUTH_USER` | `apps/backend/http-api/.env` | `Concord/coreops-auth-user` |
| `COREOPS_AUTH_PASS` | `apps/backend/http-api/.env` | `Concord/coreops-auth-pass` |
| `COREOPS_SERVER_URL` | hardcoded | `https://coreops.office.corekinect.cloud:2013` |
| `COREOPS_VERIFY_SSL` | `false` (dev) | — |

Dev compose ships with valid CoreOps creds baked into `deploy/development/docker-compose.yaml` so device personalization works against the office CoreOps instance out of the box. Don't commit changes that replace those with placeholders.

### Firmware signing keys

| Variable | Bitwarden item | Used by |
|---|---|---|
| `BENCH_SIGNING_KEY` | `Concord/firmware-signing-bench` | build-service for `release_track=bench` |
| `ENGINEERING_SIGNING_KEY` | `Concord/firmware-signing-engineering` | build-service for `release_track=engineering` |
| `PRODUCTION_SIGNING_KEY` | `Concord/firmware-signing-production` | build-service for `release_track=production` |

All base64-encoded PEM. Leaving them empty in dev falls through to the bench keys seeded by `prisma/seed.py`.

### Internal API key

| Variable | Lives in | Notes |
|---|---|---|
| `CONCORD_API_KEY` | `deploy/development/.env` (and `apps/backend/{git-poller,build-service}/.env`) | Used by git-poller and build-service to authenticate to http-api. Not needed in dev because `AUTH_ENABLED=false`. Required in staging/production. |

### Misc dev-only convenience

| Variable | Default | Notes |
|---|---|---|
| `DELETE_ALL_KEY` | `dev-delete-key` (compose default) | Guards `/v2/system/delete-all`. Never set in production. |
| `JWT_SECRET_KEY` (dev) | `concord-dev-jwt-secret-change-in-production` | OK as-is in dev. |

## First-time bootstrap

```bash
# 1. From inside the devcontainer
nx run env:setup
nx run env:status    # see what's blank

# 2. Pull each missing value from Bitwarden and paste into the relevant .env
$EDITOR apps/backend/http-api/.env
$EDITOR apps/backend/build-service/.env
$EDITOR apps/backend/git-poller/.env
$EDITOR deploy/development/.env

# 3. Sanity check
nx run env:preflight                  # development
nx run env:preflight -c staging       # staging
nx run env:preflight -c production    # production (admin only)

# 4. Bring services up
nx start platform
```

## Rotating a credential

1. Generate the new value.
2. Update Bitwarden first. **Always**, before anything else.
3. For dev — update the relevant `.env`, restart the affected service (`docker compose restart http-api`).
4. For staging/production — update `infrastructure/clusters/office/secrets/{staging,production}/.env`, run `nx run platform:sync-secrets -c <env>`, then rolling-restart the deployment that consumed it (`kubectl -n <env> rollout restart deploy/concord-http-api`).
5. If the old value was ever committed to git: rotate first, scrub history second. The leaked value is dead the moment it enters git history. See [`../../rules/secrets-handling.md`](../../rules/secrets-handling.md#if-a-secret-leaks).

## Off-site K8s access (concord-remote)

When working remotely, the developer's WSL distro runs a tunnel daemon that bridges the office K3s API + container registry to localhost. The tunnel is provisioned by a separate tool (`concord-remote`) that lives in the umbrella `work/` workspace, not in this repo. Standalone clones of concord that need off-site cluster access should use direct VPN to `10.4.45.0/24` instead.

What you get once it's up:

- `KUBECONFIG=~/.kube/config-concord-remote` resolves to the office cluster.
- `containers.ad.corekinect.com` resolves through the tunnel — pulls/pushes work as if you were on the office LAN.
- Internal DNS (`auth.office.corekinect.cloud`, `coreops.office.corekinect.cloud`) resolves correctly.

No additional credentials beyond the kubeconfig and an SSH key pinned in the tunnel installer.

## Troubleshooting

**`nx run env:preflight` says a required var is missing but the `.env` has it** — the var has trailing whitespace or quotes. The preflight checker reads literal values; `FOO="bar"` becomes the string `"bar"` with quotes. Strip them.

**`build-service` logs `Permission denied (publickey)` cloning** — `BITBUCKET_SSH_KEY` is empty or malformed. Re-base64-encode the key (`base64 -w0`, no newlines) and restart the container.

**Frontend stuck on login screen even with `AUTH_ENABLED=false`** — `localStorage.concord-token` has a stale token from a previous staging session. Clear it (DevTools → Application → Storage → Clear site data).

**Staging deploy fails with `Secret "concord-http-api" not found`** — the K8s Secret was never synced. `kubectl -n staging get secrets` to confirm, then `nx run platform:sync-secrets -c staging`.

**`COREOPS_API_KEY` rejected by CoreOps server (401)** — verify the matching `COREOPS_AUTH_USER` / `COREOPS_AUTH_PASS` are also set. The three rotate together.

## Related knowledge

- [`local-dev.md`](local-dev.md) — the bootstrap flow that consumes these credentials
- [`debugging.md`](debugging.md) — using `kubectl exec` to inspect secrets at runtime
- [`../../rules/secrets-handling.md`](../../rules/secrets-handling.md) — what must never enter git
- [`../../rules/auth-defaults.md`](../../rules/auth-defaults.md) — how the JWT and auth bypass work
- `concord-remote` — the WSL tunnel to the office cluster (a separate tool in the umbrella `work/` workspace, not in this repo)
