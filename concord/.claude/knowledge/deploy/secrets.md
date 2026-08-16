# Deploy — secrets

Every credential the platform needs at runtime, where it lives in code, where it lands in K8s, and how to rotate it. Secrets are not in the Helm chart — they're created by `infrastructure/clusters/office/secrets/create-all.sh`, which reads local `.env` files and applies `kubectl create secret` for each namespace.

Refresh this file when: a new K8s Secret is added or removed; a key inside a Secret is renamed; a new consuming service starts (or stops) using a Secret; the rotation flow for any credential changes.

## Location

```
infrastructure/clusters/office/secrets/
├── create-all.sh           # bash sync script — reads env, applies K8s Secrets
├── create-theta-keys.sh    # standalone Theta MCUboot key creator
├── shared.env              # GITIGNORED — secrets shared across envs (paths, API tokens)
├── staging.env             # GITIGNORED — staging-only secrets (Postgres pw, JWT key, etc.)
├── production.env          # GITIGNORED — production-only secrets
├── .env.example            # committed — placeholder values + docs
└── README.md
```

The committed source of truth for *what* each Secret needs is `.env.example`. The committed source of truth for *how* it gets applied is `create-all.sh`. The values themselves live in your team's secret store (1Password, Vault, encrypted file — admin's call); developers copy them into local `.env` files when bootstrapping. See [`../../rules/secrets-handling.md`](../../rules/secrets-handling.md).

## How a secret reaches a pod

```
team secret store ──manual──▶ shared.env / <env>.env (gitignored, on dev or CI host)
                              │
                              │ bash create-all.sh <env>
                              ▼
                     kubectl create secret … --dry-run=client -o yaml | kubectl apply -f -
                              │
                              ▼
                     K8s Secret in <env> namespace
                              │
                              │ secretKeyRef in Deployment template (Helm)
                              ▼
                     Container env var or mounted file
```

`nx run platform:sync-secrets -c <env>` is the developer-facing entry. The same script runs as part of `nx start platform -c <env>` and is also called by `nx update platform -c staging -- --sync-secrets` when secrets need to be re-pushed.

## Master inventory

| K8s Secret | Namespaces | Keys | Consumed by | Source env var | Rotation |
|---|---|---|---|---|---|
| `bitbucket-ssh-key` | staging, production, devops | `ssh-private-key` (file) | http-api (`/home/appuser/.ssh/id_rsa`), build-service, git-poller, ci-nightly CronJob | `BITBUCKET_SSH_KEY_PATH` → path on local disk | Generate new Bitbucket app key, replace file, rerun `sync-secrets`, rolling-restart consumers. |
| `concord-build-service-secrets` | staging, production | `api-key`, `bitbucket-email`, `bitbucket-api-token` | build-service, git-poller (`CONCORD_API_KEY`, `BITBUCKET_EMAIL`, `BITBUCKET_API_TOKEN`); **http-api** (`BITBUCKET_EMAIL` only — explicit `env` override) | `BUILD_SERVICE_API_KEY`, `BITBUCKET_EMAIL`, `BITBUCKET_API_TOKEN` | Rotate `BUILD_SERVICE_API_KEY`, re-seed it on the http-api side (the matching `User.api_key`), sync-secrets, restart build-service + git-poller. **`bitbucket-email` must be the Atlassian account that owns `bitbucket-api-token`** — REST basic auth is `email:token`, so a mismatched pair 401s. Both come from `shared.env` so they rotate together. |
| `concord-secrets` | staging, production | `DATABASE_URL`, `DIRECT_DATABASE_URL`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_ACCESS_KEY`, `JWT_SECRET_KEY`, `BITBUCKET_API_TOKEN`, `AUTH_SERVER_API_KEY`, `DELETE_ALL_KEY`, `BITBUCKET_WEBHOOK_SECRET`, `COREOPS_API_KEY`, `COREOPS_AUTH_USER`, `COREOPS_AUTH_PASS` | http-api (entire Secret via `envFrom.secretRef`) | All keys named above | Rotate via your team's secret store + `<env>.env`, sync-secrets, rolling-restart http-api. JWT rotation forces all users to log in again. |
| `concord-infra-credentials` | staging, production | `POSTGRES_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Postgres StatefulSet, MinIO Deployment | `POSTGRES_PASSWORD`, `MINIO_ROOT_USER`, `MINIO_ROOT_PASSWORD` | Sensitive — rotating the Postgres password requires a coordinated change inside Postgres + restart of http-api with new `DATABASE_URL`. See "Postgres rotation" below. |
| `concord-pypi-htpasswd` | staging, production | `.htpasswd` (file) | concord-pypi (htpasswd init container copies it into `/data/.htpasswd`) | `PYPI_HTPASSWD` (full htpasswd content) | Generate with `htpasswd -nb <user> <password>`; paste into `shared.env`; sync-secrets; restart pypi pod. |
| `coreops-credentials` | staging, production | `api-key`, `auth-user`, `auth-pass` | (currently mirrored into `concord-secrets`; this Secret exists as a separate handle for clarity) | `COREOPS_API_KEY`, `COREOPS_AUTH_USER`, `COREOPS_AUTH_PASS` | Coordinate with the CoreOps service owner; rotate in both Concord and CoreOps simultaneously. |
| `corecloud-validation` | staging, production (optional) | `api-key` | validation runners that talk to CoreCloud telemetry | `CORECLOUD_VALIDATION_API_KEY` | Rotate from the CoreCloud side, paste into `shared.env`, sync-secrets. |
| `theta-mcuboot-keys` | staging, production (optional) | `encryption_key.pem`, `comms_encryption_key.pem` (files) | Theta firmware signing path (FUOTA) | `MCUBOOT_APP_KEY_PATH`, `MCUBOOT_COMMS_KEY_PATH` (paths on local disk) | These are device-fleet keys — rotation requires a fleet-wide FUOTA campaign. Don't rotate casually. |
| `ci-minio-upload` | devops | `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | concord-ci-weekly CronJob (uploads results to ci-minio) | `CI_MINIO_USER`, `CI_MINIO_PASSWORD` | Rotate, sync-secrets devops, the next CronJob picks it up. |
| `claude-code-oauth` | devops | `credentials.json` (file) | concord-ci-nightly + weekly CronJobs (AI review stages) | `CLAUDE_CREDENTIALS_PATH` → path on local disk | Refresh the credentials file via `claude` CLI; sync-secrets devops. |
| `concord-tls` | staging, production | `tls.crt`, `tls.key` | Traefik (via Ingress `tls.secretName`) | Managed by cert-manager — see [`network.md`](network.md). | Automatic renewal 30 days before expiry by cert-manager. If stuck, inspect `Certificate/staging-concord-tls`. |
| `corekinect-ca-certs` | devops | `*.crt` files | concord-ci-nightly (mounted into `/usr/local/share/ca-certificates/`) | (cluster-managed) | Update only when the CoreKinect internal CA root changes. |
| `concord-ci-secrets` | devops | `MINIO_ROOT_PASSWORD`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY` | concord-ci-minio Deployment, concord-ci-admin | **Managed by the concord-ci Helm chart** (not by `create-all.sh`) | Edit `deploy/ci/helm/concord-ci/values.yaml` `minio.rootPassword`, redeploy. |

Optional Secrets are skipped silently by `create-all.sh` when the source env var is empty.

## What's a config var, not a secret

Even though they look credential-shaped, these go in the Helm `values.yaml` (or compose `environment:`), not in a Secret:

| Key | Why |
|---|---|
| `AUTH_SERVER_URL`, `COREOPS_SERVER_URL`, `COREOPS_AUTH_SERVER_URL` | URLs are not secret — the authentication tokens that flow to them are. |
| `BITBUCKET_WORKSPACE` | Identifier, not a credential. (`BITBUCKET_EMAIL` used to live here too, but it pairs with the API token for REST basic auth and now travels with the token in `concord-build-service-secrets` — see the inventory row above. Do **not** put it back in the configmap.) |
| `MINIO_ROOT_USER` (in development) | Set to `concord` in compose; the production value lives in `concord-infra-credentials`. |
| `JWT_SECRET_KEY` (in development) | Compose default is `concord-dev-jwt-secret-change-in-production`. Production lives in `concord-secrets`. |

## Where each consumer reads from

| Service | Reads via |
|---|---|
| http-api | `envFrom: [configMapRef: concord-config, secretRef: concord-secrets]`, plus an explicit `env` entry for `BITBUCKET_EMAIL` from `concord-build-service-secrets.bitbucket-email` (so the REST basic-auth username pairs with `BITBUCKET_API_TOKEN`). `bitbucket-ssh-key` mounted at `/home/appuser/.ssh/id_rsa`. |
| build-service | Individual `valueFrom.secretKeyRef` entries for `CONCORD_API_KEY`, `BITBUCKET_SSH_KEY`. Also mounts `bitbucket-ssh-key` as a file. |
| git-poller | `valueFrom.secretKeyRef` for `CONCORD_API_KEY`, `BITBUCKET_EMAIL`, `BITBUCKET_API_TOKEN`. `bitbucket-ssh-key` mounted as a file. |
| Postgres StatefulSet | `valueFrom.secretKeyRef: name=concord-infra-credentials key=POSTGRES_PASSWORD`. |
| MinIO Deployment | `valueFrom.secretKeyRef: concord-infra-credentials key=MINIO_ROOT_USER / MINIO_ROOT_PASSWORD`. |
| pypi Deployment | htpasswd init container copies from mounted `concord-pypi-htpasswd`. |
| ci-nightly / ci-weekly CronJobs | `bitbucket-ssh-key`, `corekinect-ca-certs`, `claude-code-oauth`, `ci-minio-upload` — all mounted as files with `optional: true`. |

## Postgres rotation — the one that's tricky

The Postgres password lives in two places that must agree: inside the Postgres data directory and inside `DATABASE_URL` (which http-api uses to connect).

```
1. Edit <env>.env:  POSTGRES_PASSWORD=<new>
                    DATABASE_URL=postgresql://concord:<new>@concord-postgres:5432/concord
                    DIRECT_DATABASE_URL=postgresql://concord:<new>@concord-postgres:5432/concord

2. Apply the password change inside Postgres (the StatefulSet won't pick up
   a new password automatically — Postgres reads it once at initdb):
     kubectl exec -n <env> concord-postgres-0 -- \
       psql -U concord -d concord -c "ALTER USER concord WITH PASSWORD '<new>';"

3. nx run platform:sync-secrets -c <env>          # updates K8s Secrets
4. kubectl rollout restart deployment/concord-http-api -n <env>
   kubectl rollout restart deployment/concord-build-service -n <env>
   kubectl rollout restart deployment/concord-git-poller -n <env>
```

Skipping step 2 makes everyone fail-to-authenticate-against-Postgres. Skipping step 4 leaves stale connections that work until the pod restarts.

## JWT rotation — security impact

Rotating `JWT_SECRET_KEY` invalidates every issued token immediately. After rotation, every active user must log in again. Coordinate the change (announce in #platform), do it during low-traffic, accept that the next 10 minutes will be noisy with 401s.

## How to add a new secret

1. **Define the env var** in `.env.example` (under `shared.env` or `{namespace}.env` as appropriate) with a placeholder + a comment explaining what it is and which K8s Secret it lands in.
2. **Add the `apply_secret` call** to `create-all.sh` under the right namespace block.
3. **Reference it in the Helm template** that consumes it (`valueFrom.secretKeyRef`).
4. **Mirror it in compose** if the service also runs locally — usually a non-secret default + a docs note.
5. **Put the real value in your team's secret store** so other admins can find it during rotation.
6. **Update this file's master inventory table**.
7. **Run `nx run platform:sync-secrets -c <env>`** to push it.
8. **Restart consuming pods**.

## Common failure modes

- **`Error: Secret "concord-secrets" not found`** when http-api boots — secrets weren't synced after a namespace recreate. Run `nx run platform:sync-secrets -c <env>`.
- **`P3009 migration failed`** during init container — usually unrelated to secrets, but if `DATABASE_URL` has wrong credentials the init container fails before reaching migrations. Check `concord-secrets`'s `DATABASE_URL` matches `concord-infra-credentials`'s `POSTGRES_PASSWORD`.
- **`bitbucket-ssh-key not mounted`** when build-service tries to clone — the volume mount is `optional: true` so a missing Secret doesn't crash the pod; it just makes clones fail with `Permission denied (publickey)`. Sync secrets and restart the deployment.
- **pypi pod CrashLoopBackOff after enabling auth** — the htpasswd init container couldn't find `concord-pypi-htpasswd`. `PYPI_HTPASSWD` wasn't set in `shared.env`, or sync-secrets wasn't run. Disable auth temporarily in values (`infrastructure.pypi.auth.enabled: false`), set the secret, re-enable.
- **CI nightly CronJob can't talk to CoreKinect internal hosts** — `corekinect-ca-certs` missing in `devops`. That Secret is cluster-managed by infra (not by `create-all.sh`); contact whoever bootstrapped the office cluster.

## Secret material registry

Each rotation works the same: edit the value in your team's secret store, mirror to `shared.env` / `<env>.env`, run `sync-secrets`, rolling-restart consumers. The table below lists *what* each secret is and where it lands; *where the canonical value lives* is a team decision (1Password, Vault, encrypted file, etc.).

| Secret material | Mirrors to (gitignored env file → K8s) | Used by |
|---|---|---|
| Bitbucket API token | `BITBUCKET_API_TOKEN` in `shared.env` → `concord-secrets`, `concord-build-service-secrets` | http-api, build-service, git-poller — REST API + PR webhooks |
| Bitbucket account email | `BITBUCKET_EMAIL` in `shared.env` | git commit author for platform-driven commits |
| Bitbucket SSH key (file) | `BITBUCKET_SSH_KEY_PATH` (host file path) → `bitbucket-ssh-key` | http-api, build-service — git clone over SSH |
| Internal pypi htpasswd plaintext | `PYPI_USERNAME=concord`, `PYPI_PASSWORD=<plaintext>` (env vars only at release time) | `nx run corectl:push -c <env>` + `nx run corekinect:push -c <env>` |
| Internal pypi htpasswd hash | `PYPI_HTPASSWD` in `shared.env` → `concord-pypi-htpasswd` K8s Secret | the `concord-pypi` deployment in staging + production |
| Firmware signing keys (3) | `BENCH_SIGNING_KEY`, `ENGINEERING_SIGNING_KEY`, `PRODUCTION_SIGNING_KEY` in `deploy/development/.env` / production `.env` | build-service — signs firmware images per release track |
| Build-service API key | `BUILD_SERVICE_API_KEY` in `shared.env` → `concord-build-service-secrets` | build-service identifies itself to http-api; must match a `User.api_key` row seeded in the DB |
| JWT signing key | `JWT_SECRET_KEY` in `<env>.env` → `concord-secrets` | http-api signs HS256 session tokens — ≥32 chars in staging/production |
| CoreOps creds | `COREOPS_API_KEY`, `COREOPS_AUTH_USER`, `COREOPS_AUTH_PASS` in `<env>.env` → `concord-secrets` | http-api + device personalizer — calls the CoreOps device registry |

Each entry above is one rotation unit — when you rotate a Bitbucket API token, you touch one secret-store entry, one env-file line, then sync. If a value appears in multiple K8s Secrets (e.g. `BITBUCKET_API_TOKEN` lands in two), `sync-secrets` writes both from the single source.

## Related knowledge

- [`overview.md`](overview.md) — env model.
- [`helm.md`](helm.md) — what `envFrom`/`valueFrom` references look like in templates.
- [`ctl-sh.md`](ctl-sh.md) — the deploy script that calls `create-all.sh`.
- [`network.md`](network.md) — TLS Secret (`concord-tls`) + cert-manager.
- [`../../rules/secrets-handling.md`](../../rules/secrets-handling.md) — the rule of "no secrets in git".
- [`../../rules/all-three-envs.md`](../../rules/all-three-envs.md) — every new env var touches dev + staging + production.


## Internal PyPI upload credentials

`nx push corectl -c <env>` and `nx push corekinect -c <env>` need to authenticate against the cluster's internal pypi (`concord-pypi` service in each namespace, htpasswd-protected). Set:

```
export PYPI_USERNAME=concord
export PYPI_PASSWORD=<plaintext from your team's secret store>
```

| Field | Where |
|---|---|
| Plaintext password | your team's secret store (alongside the hashed `PYPI_HTPASSWD` so they stay paired) |
| Hashed entry | `infrastructure/clusters/office/secrets/shared.env` as `PYPI_HTPASSWD` |
| K8s Secret | `concord-pypi-htpasswd` in both `staging` + `production` namespaces (synced by `create-all.sh`) |
| Username | always `concord` |

### Rotation procedure

1. Generate new plaintext + htpasswd line:
   ```bash
   NEW_PW=$(openssl rand -base64 24 | tr -d '/+=' | head -c 32)
   HTPASSWD=$(echo -n "$NEW_PW" | openssl dgst -sha1 -binary | base64 | awk -v u=concord '{print u":{SHA}"$1}')
   ```
2. Update your team's secret store with the new plaintext (paired with the hash from the next step).
3. Update `infrastructure/clusters/office/secrets/shared.env`: `PYPI_HTPASSWD=$HTPASSWD`.
4. Re-apply both K8s Secrets:
   ```bash
   for ns in production staging; do
     echo "$HTPASSWD" | kubectl -n $ns create secret generic concord-pypi-htpasswd \
       --from-file=.htpasswd=/dev/stdin --dry-run=client -o yaml | kubectl apply -f -
   done
   ```
5. Restart pypi pods so the init container reloads the htpasswd:
   ```bash
   kubectl -n production rollout restart deploy/concord-pypi
   kubectl -n staging    rollout restart deploy/concord-pypi
   ```
6. Test: `PYPI_PASSWORD=$NEW_PW nx push corectl -c staging` should succeed.

The credential was rotated 2026-05-15 — previous hash `concord:{SHA}cLWNyHnLEc9PjKNjtW9nvOjjLp8=` (plaintext never captured) replaced with a fresh one stored in the team secret store.
