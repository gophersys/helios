# apps/eden — the Eden platform on homelab

Eden (the agentic-engineering platform) deployed as a stable release on the
`homelab` cluster, GitOps-driven by Argo CD from this repo. **One namespace:
`eden`.** This directory owns the **backing stack** (Postgres · NATS · Vault),
**RBAC**, **secrets bring-up**, and the **ingress**. The workload Deployments
(agentgateway · agent-runtime · platformgateway · frontend) are added LATER by the
eden Helm chart promotion (see "What the release pipeline promotes").

## What lands where

| File | Kind | Argo Application (project) | Notes |
|---|---|---|---|
| `00-namespace.yaml` | Namespace `eden` | `eden-namespace` (**platform**) | Cluster-scoped → platform project owns it; `app-eden` excludes it. |
| `05-postgres.yaml` | StatefulSet + Service `postgres:5432` | `eden` (**apps**) | pg16, `local-path` PVC, password from Secret `eden-orchestrator-postgres`. |
| `06-nats.yaml` | StatefulSet + Service `nats:4222` | `eden` (**apps**) | nats 2.14.2 + JetStream, PVC `eden-nats-data`. |
| `07-vault.yaml` | StatefulSet + Service `vault:8200` + ConfigMap | `eden` (**apps**) | Single-node file storage, `disable_mlock=true` (no IPC_LOCK cap), boots SEALED. |
| `08-vault-seed-job.yaml` | Job `eden-vault-seed` | `eden` (**apps**) | Seeds `eden/data/production` (JWT keys + the connectors KEK only-if-absent; `platformgateway-database-dsn` + the generic `database-dsn` derived from the pg password), mints `eden-vault-token`. Idempotent. |
| `10-external-secret-bootstrap.yaml` | ExternalSecret → Secret `eden-bootstrap` | `eden` (**apps**) | Optional harness creds from Vaultwarden. |
| `20-rbac.yaml` | SAs + Roles + RoleBindings | `eden` (**apps**) | `eden-agent`, `platformgateway`, `eden-frontend`, `eden-orchestrator` (lease), `eden-vault-seed` (Secrets Role includes **`delete`** — the seed Job's unpublish step); workload SAs carry the `ghcr-pull` imagePullSecret. |
| `40-ingress.yaml` | Ingress `eden.mateosegura.com` | `eden` (**apps**) | nginx + `letsencrypt-homelab` TLS, all paths → `frontend:8080`. |
| `rbac-cluster/rbac.yaml` | ClusterRole + ClusterRoleBinding | `eden-rbac` (**platform**) | Orchestrator's create-project-namespace authority. |

The Argo Applications live in `platform/services/gitops/registry/app-eden*.yaml`;
`eden` is registered in `clusters/instances/homelab/identity.yaml` and permitted
in the `apps` + `platform` AppProject destinations.

## Contract surface (what the eden Helm chart / app code depends on)

- **Service DNS:** `nats:4222`, `vault:8200`, and Postgres via BOTH
  `postgres:5432` (plain ClusterIP) and `eden-postgres-0.eden-postgres.eden.svc`
  (stable pod FQDN via the headless governing Service) — the chart emits the pod
  form, the seed Job's DSN uses the plain form; both resolve to the same DB.
- **Vault token file:** the eden chart mounts k8s Secret `eden-vault-token` (key
  `token`) at `/vault/secrets/token`; pods run `EDEN_VAULT_MODE=token-file`,
  `VAULT_ADDR=http://vault:8200`. This directory's seed Job mints that token.
- **Vault kv-v2 mount `eden/`, path `production`** — fields:
  `agentgateway-jwt-signing-key`, `platformgateway-jwt-signing-key`,
  `connectors-kek` (the AES-256 KEK the platformgateway's envelope library wraps
  every user connector's data key under — ADR-0029, doc 19; resolved as
  `vault://eden/production#connectors-kek`),
  `platformgateway-database-dsn`, the generic `database-dsn` (the agentgateway's
  record + dashboard store — SAME eden Postgres, derived from the mounted
  password), and optional `setup-token`, `gh-token`, `openrouter-api-key`
  (resolved as `vault://eden/production#<field>`). The seed Job writes the two
  DSN fields deterministically (a re-run rewrites the identical derived value);
  the JWT keys AND the connectors KEK are generated only-if-absent and NEVER
  rotate on a reseed (a rotated KEK would orphan every stored connector).
- **ServiceAccounts:** `eden-agent` (agentgateway · agent-runtime),
  `platformgateway` (platformgateway), `eden-frontend` (frontend),
  `eden-orchestrator` (orchestrator) — every chart Deployment's
  `serviceAccountName` is declared in `20-rbac.yaml`, and each carries the
  `ghcr-pull` imagePullSecret for the private registry.
- **Postgres:** user/db `eden`, password in Secret `eden-orchestrator-postgres`
  (key `password`).

---

## Bring-up runbook

Run against the homelab cluster (`kubectl` context `home`). The Namespace and the
backing stack (Postgres/NATS/Vault) sync via Argo automatically once these
manifests reach `main`; the steps below are the OUT-OF-BAND actions Argo cannot
do (secret material + the Vault ceremony).

### The `bw` ceremony (how secret material actually moves)

Every imperative secret below is driven from the cloud Vaultwarden
(`secrets.mateosegura.com`) via the `bw` CLI. The AS-EXECUTED pattern:

1. **Unlock in a REAL terminal, not this session.** The in-session unlock
   prompt crashes readline — unlock separately and hand off the session token:

   ```sh
   bw unlock --raw > ~/.bw-session      # run in a real terminal
   export BW_SESSION="$(cat ~/.bw-session)"
   ```

2. **Values flow bw → tmpfs → kubectl, and are NEVER printed.** Materialize
   each value under a `umask 077` tmpfs scratch file, feed it to `kubectl`, and
   shred it. No secret value ever lands in the transcript, a git-tracked file,
   or `--from-literal` on the command line:

   ```sh
   umask 077
   d="$(mktemp -d /dev/shm/eden-bring-up.XXXXXX)"
   trap 'rm -rf "$d"' EXIT
   bw get password shared/eden/postgres-password --session "$BW_SESSION" > "$d/pg"
   # ... consume "$d/pg" via kubectl, then the trap shreds it.
   ```

The placeholders shown throughout this runbook stand in for values that arrive
this way — never write a real secret into any file.

### 0. ghcr image-pull secret (never in git)

The Eden workload images live in the PRIVATE `ghcr.io/gophersys/eden/*`
registry, so the cluster needs a docker-registry pull credential BEFORE any
workload pod schedules (otherwise `ImagePullBackOff`). Every workload SA in
`20-rbac.yaml` references it by name (`ghcr-pull`). Built from the Vaultwarden
item `shared/github/pat-godmode` (see the `bw` ceremony above) — the PAT flows
bw → tmpfs → kubectl, never printed:

```sh
# BW_SESSION exported; "$d" is the umask-077 tmpfs scratch dir.
bw get item shared/github/pat-godmode --session "$BW_SESSION" \
  | jq -r '.login.password' > "$d/ghcr-pat"
kubectl -n eden create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username=mateosegura \
  --docker-password="$(cat "$d/ghcr-pat")"
```

> **Follow-up (rotate):** `pat-godmode` is a broad token used here only for
> expedience. Rotate `ghcr-pull` onto a NARROW `read:packages`-only PAT and
> re-create the secret from that.

### 1. Imperative secrets (never in git)

Postgres password — GENERATED once, before Postgres schedules. Vaultwarden is
the SOURCE OF TRUTH: generate the value, store it to the Vaultwarden item
`shared/eden/postgres-password` FIRST, THEN create the k8s Secret from that same
value. The value flows bw → tmpfs → kubectl, never printed:

```sh
# BW_SESSION exported; KUBECONFIG at homelab; "$d" is the umask-077 tmpfs dir.
# 1. Generate and store to Vaultwarden FIRST (source of truth).
openssl rand -hex 24 > "$d/pg"                       # generated, not printed
#    ...create/update item shared/eden/postgres-password from "$d/pg" via bw...

# 2. Create the k8s Secret from the SAME value.
kubectl -n eden create secret generic eden-orchestrator-postgres \
  --from-literal=password="$(cat "$d/pg")" \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 2. Vaultwarden items (for the bootstrap ExternalSecret)

Create these items in the cloud Vaultwarden (`secrets.mateosegura.com`). The
`vaultwarden` ClusterSecretStore returns each item's **NOTES** field, so put the
single token value in the item's notes (not the password field). All OPTIONAL —
chat + login work without them; only live agent turns / the create-saga need them.

- `shared/eden/claude-setup-token` — Claude Code OAuth token (agent runs).
- `shared/eden/forge-github-pat` — GitHub PAT for project-forge (create-saga).
- `shared/eden/openrouter-api-key` — OpenRouter key (omp path).

ESO then materializes Secret `eden-bootstrap` in ns `eden` (keys `setup-token`,
`gh-token`, `openrouter-api-key`); the seed Job copies present keys into Vault.

### 3. Vault init & unseal (ONE-TIME operator ceremony)

Vault boots **sealed** (no dev mode). Init it once, capture the unseal key + root
token into the imperative Secret `eden-vault-init`, then unseal. **Homelab-grade:
1 key share, threshold 1 — deliberate.** NEVER commit these values anywhere.

The init output is stored in BOTH places: the k8s Secret `eden-vault-init` (the
seed Job reads `root-token`; the reseal recipe reads `unseal-key`) AND the
Vaultwarden item `shared/eden/vault-init` (durable off-cluster backup — survives
a cluster wipe). Capture init straight to a tmpfs file; never let it hit the
terminal:

```sh
# Wait for the pod to be Running (it stays NOT Ready until unsealed — expected).
kubectl -n eden wait --for=jsonpath='{.status.phase}'=Running pod/vault-0 --timeout=120s

# Initialize (JSON output captured to the umask-077 tmpfs "$d" — NOT printed).
kubectl -n eden exec vault-0 -- \
  vault operator init -key-shares=1 -key-threshold=1 -format=json > "$d/vault-init.json"

# Store the unseal key + root token as the imperative eden-vault-init Secret.
kubectl -n eden create secret generic eden-vault-init \
  --from-literal=unseal-key="$(jq -r '.unseal_keys_b64[0]' "$d/vault-init.json")" \
  --from-literal=root-token="$(jq -r '.root_token' "$d/vault-init.json")" \
  --dry-run=client -o yaml | kubectl apply -f -

#    ...and store the SAME init output to Vaultwarden item shared/eden/vault-init
#    (off-cluster backup) from "$d/vault-init.json" via bw.

# Unseal.
kubectl -n eden exec -i vault-0 -- sh -c 'read K; vault operator unseal "$K"' \
  < <(jq -r '.unseal_keys_b64[0]' "$d/vault-init.json")
```

**After a node reboot** Vault comes back sealed (file storage is durable but the
master key is not persisted) — see the reseal trap below.

### 3b. RESEAL TRAP (the recurring gotcha)

**ANY `vault-0` pod restart re-seals Vault** — a node reboot, an OOM, a manual
`kubectl delete pod`, AND (the sneaky one) **Argo rolling the StatefulSet** when
it reconciles a `07-vault.yaml` change. File storage is durable, so the DATA
survives; the master key is not persisted, so the pod boots SEALED and every
`vault://…` ref stops resolving until you re-unseal. Expect this every time the
Vault StatefulSet rolls.

**Re-unseal recipe** (the unseal key stays in `eden-vault-init`; feed it via
tmpfs and stdin so it never hits the process table or the transcript):

```sh
umask 077; f="$(mktemp /dev/shm/eden-unseal.XXXXXX)"; trap 'rm -f "$f"' EXIT
chmod 0600 "$f"
kubectl -n eden get secret eden-vault-init \
  -o jsonpath='{.data.unseal-key}' | base64 -d > "$f"
kubectl -n eden exec -i vault-0 -- sh -c 'read K; vault operator unseal "$K"' < "$f"
```

**If the seed Job burned its retries** while Vault was sealed (it fails closed
against a sealed Vault and can exhaust `backoffLimit`), re-unsealing alone won't
re-run it. Delete the exhausted Job and let Argo's `selfHeal` recreate it fresh:

```sh
kubectl -n eden delete job eden-vault-seed
# Argo selfHeal recreates the Job; it now runs green against the unsealed Vault.
```

### 4. Run the seed Job

Once Vault is unsealed and `eden-vault-init` exists, the seed Job (synced by Argo)
enables kv-v2 at `eden/`, generates the two JWT signing keys **only-if-absent**
(a re-run NEVER rotates them, so sessions survive), writes the platformgateway
DSN, copies any present `eden-bootstrap` harness creds, creates the `eden-read`
policy, and mints the `eden-vault-token` the pods consume. Re-run it any time:

The seed Job's Role in `20-rbac.yaml` carries the **`delete`** verb on Secrets —
its unpublish step does a shell-free `delete → create` as the idempotent update.
This was proven live: without `delete` the step fails `Forbidden` and the Job
aborts. Do not narrow the Role back to `get/create/update`.

```sh
kubectl -n eden delete job eden-vault-seed --ignore-not-found
kubectl apply -f apps/eden/08-vault-seed-job.yaml   # or let Argo re-sync
kubectl -n eden logs -f job/eden-vault-seed
```

### 5. Workloads

The workload Deployments arrive via the eden chart promotion (next section). Once
`eden-vault-token` exists and the workloads are pinned, they resolve their
`vault://eden/production#…` refs and come Ready; the ingress then starts serving
`eden.mateosegura.com` (see DNS below).

### 6. DNS record (Cloudflare — DNS-only, not proxied)

`eden.mateosegura.com` needs an **explicit, DNS-only A record → the homelab
nginx VIP `10.168.0.240`** — the same pattern as `argocd.mateosegura.com`. Add
it in Cloudflare as a proxied-OFF (grey-cloud) A record; do NOT rely on a
wildcard.

**Why the explicit record matters (the exact symptom we hit):** a wildcard
`*.mateosegura.com` record otherwise resolves `eden.mateosegura.com` to the
**cloud cluster**, whose nginx answers the unknown host with its **default TLS
cert** — the browser rejects it with `ERR_CERT_AUTHORITY_INVALID`. Pointing the
name straight at the homelab VIP routes it to the homelab nginx, which serves
the correct `letsencrypt-homelab` cert for the ingress.

---

## What the release pipeline promotes

A parallel release workflow (in the **eden monorepo**) builds
`ghcr.io/gophersys/eden/{agentgateway,agent-runtime,platformgateway,frontend}`
multi-arch images on a `v<semver>` tag and opens a **digest-pin PR against THIS
repo** that adds the workload Deployments/Services into `apps/eden/` (flat,
numbered above `40-`, e.g. `50-agentgateway.yaml` …) pinned to the new image
**digest**. Those manifests set their per-service `serviceAccountName`
(`eden-agent` for agentgateway · agent-runtime; `platformgateway`; `eden-frontend`
for the frontend), talk to `nats:4222` / `postgres:5432` / `vault:8200`, and mount
`eden-vault-token` at `/vault/secrets/token`. The `app-eden` Application
(recurse:false, flat dir) picks them up automatically; Argo (`selfHeal + prune +
ServerSideApply`) reconciles.
