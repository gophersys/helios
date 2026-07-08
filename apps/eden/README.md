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
| `07-vault.yaml` | StatefulSet + Service `vault:8200` + ConfigMap | `eden` (**apps**) | Single-node file storage, `IPC_LOCK`, boots SEALED. |
| `08-vault-seed-job.yaml` | Job `eden-vault-seed` | `eden` (**apps**) | Seeds `eden/data/production`, mints `eden-vault-token`. Idempotent. |
| `10-external-secret-bootstrap.yaml` | ExternalSecret → Secret `eden-bootstrap` | `eden` (**apps**) | Optional harness creds from Vaultwarden. |
| `20-rbac.yaml` | SAs + Roles + RoleBindings | `eden` (**apps**) | `eden-agent`, `eden-orchestrator` (lease), `eden-vault-seed`. |
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
  `platformgateway-database-dsn`, and optional `setup-token`, `gh-token`,
  `openrouter-api-key` (resolved as `vault://eden/production#<field>`).
- **ServiceAccounts:** `eden-agent` (agentgateway · agent-runtime · frontend),
  `platformgateway` (platformgateway), `eden-orchestrator` (orchestrator) — every
  chart Deployment's `serviceAccountName` is declared in `20-rbac.yaml`.
- **Postgres:** user/db `eden`, password in Secret `eden-orchestrator-postgres`
  (key `password`).

---

## Bring-up runbook

Run against the homelab cluster (`kubectl` context `home`). The Namespace and the
backing stack (Postgres/NATS/Vault) sync via Argo automatically once these
manifests reach `main`; the steps below are the OUT-OF-BAND actions Argo cannot
do (secret material + the Vault ceremony).

### 1. Imperative secrets (never in git)

Postgres password — created once, before Postgres schedules:

```sh
# BW_SESSION exported; KUBECONFIG at homelab.
kubectl -n eden create secret generic eden-orchestrator-postgres \
  --from-literal=password="<PLACEHOLDER — e.g. openssl rand -hex 24>" \
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

```sh
# Wait for the pod to be Running (it stays NOT Ready until unsealed — expected).
kubectl -n eden wait --for=jsonpath='{.status.phase}'=Running pod/vault-0 --timeout=120s

# Initialize (prints the unseal key + root token to YOUR terminal ONLY — capture
# them into a password manager / the Secret below; do not paste into any file).
kubectl -n eden exec vault-0 -- \
  vault operator init -key-shares=1 -key-threshold=1

# Store the unseal key + root token as the imperative eden-vault-init Secret
# (the seed Job reads root-token from it; keep unseal-key for reboots).
kubectl -n eden create secret generic eden-vault-init \
  --from-literal=unseal-key="<PLACEHOLDER — the Unseal Key 1 from init>" \
  --from-literal=root-token="<PLACEHOLDER — the Initial Root Token from init>" \
  --dry-run=client -o yaml | kubectl apply -f -

# Unseal.
kubectl -n eden exec vault-0 -- \
  vault operator unseal "<PLACEHOLDER — the unseal key>"
```

**After a node reboot** Vault comes back sealed (file storage is durable but the
master key is not persisted). Re-unseal — the data survives:

```sh
kubectl -n eden exec vault-0 -- \
  vault operator unseal "$(kubectl -n eden get secret eden-vault-init \
    -o jsonpath='{.data.unseal-key}' | base64 -d)"
```

### 4. Run the seed Job

Once Vault is unsealed and `eden-vault-init` exists, the seed Job (synced by Argo)
enables kv-v2 at `eden/`, generates the two JWT signing keys **only-if-absent**
(a re-run NEVER rotates them, so sessions survive), writes the platformgateway
DSN, copies any present `eden-bootstrap` harness creds, creates the `eden-read`
policy, and mints the `eden-vault-token` the pods consume. Re-run it any time:

```sh
kubectl -n eden delete job eden-vault-seed --ignore-not-found
kubectl apply -f apps/eden/08-vault-seed-job.yaml   # or let Argo re-sync
kubectl -n eden logs -f job/eden-vault-seed
```

### 5. Workloads

The workload Deployments arrive via the eden chart promotion (next section). Once
`eden-vault-token` exists and the workloads are pinned, they resolve their
`vault://eden/production#…` refs and come Ready; the ingress starts serving
`eden.mateosegura.com` (add a DNS-only A record → the nginx VIP `10.168.0.240`).

---

## What the release pipeline promotes

A parallel release workflow (in the **eden monorepo**) builds
`ghcr.io/gophersys/eden/{agentgateway,agent-runtime,platformgateway,frontend}`
multi-arch images on a `v<semver>` tag and opens a **digest-pin PR against THIS
repo** that adds the workload Deployments/Services into `apps/eden/` (flat,
numbered above `40-`, e.g. `50-agentgateway.yaml` …) pinned to the new image
**digest**. Those manifests set `serviceAccountName: eden-agent`, talk to
`nats:4222` / `postgres:5432` / `vault:8200`, and mount `eden-vault-token` at
`/vault/secrets/token`. The `app-eden` Application (recurse:false, flat dir) picks
them up automatically; Argo (`selfHeal + prune + ServerSideApply`) reconciles.
