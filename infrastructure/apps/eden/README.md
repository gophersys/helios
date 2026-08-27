# apps/eden — the Eden platform on homelab

Eden is the agentic-engineering platform. This directory deploys a stable release
of it on the `homelab` cluster, and Argo CD drives that deployment from this repo.
**There is one namespace: `eden`.** This directory owns the **backing stack**
(Postgres, NATS and Vault), the **RBAC**, the **bring-up of the secrets** and the
**ingress**. The workload Deployments (agentgateway, agent-runtime,
platformgateway and frontend) are added LATER by the promotion of the eden Helm
chart. See "What the release pipeline promotes".

## What lands where

| File | Kind | Argo Application (project) | Notes |
|---|---|---|---|
| `00-namespace.yaml` | Namespace `eden` | `eden-namespace` (**platform**) | Cluster-scoped, so the platform project owns it; `app-eden` excludes it. |
| `05-postgres.yaml` | StatefulSet + Service `postgres:5432` | `eden` (**apps**) | pg16, `local-path` PVC, password from Secret `eden-orchestrator-postgres`. |
| `06-nats.yaml` | StatefulSet + Service `nats:4222` | `eden` (**apps**) | nats 2.14.2 + JetStream, PVC `eden-nats-data`. |
| `07-vault.yaml` | StatefulSet + Service `vault:8200` + ConfigMap | `eden` (**apps**) | Single-node file storage, `disable_mlock=true` (so no IPC_LOCK capability), boots SEALED. |
| `08-vault-seed-job.yaml` | Job `eden-vault-seed` | `eden` (**apps**) | Seeds `eden/data/production`: the JWT keys and the connectors KEK only if absent, plus `platformgateway-database-dsn` and the generic `database-dsn`, both derived from the pg password. It mints `eden-vault-token`. It is idempotent. |
| `10-external-secret-bootstrap.yaml` | ExternalSecret → Secret `eden-bootstrap` | `eden` (**apps**) | Optional harness credentials from Vaultwarden. |
| `20-rbac.yaml` | SAs + Roles + RoleBindings | `eden` (**apps**) | `eden-agent`, `platformgateway`, `eden-frontend`, `eden-orchestrator` (lease), `eden-vault-seed` (its Secrets Role includes **`delete`** for the unpublish step of the seed Job). Every workload SA carries the `ghcr-pull` imagePullSecret. |
| `40-ingress.yaml` | Ingress `eden.mateosegura.com` | `eden` (**apps**) | nginx + `letsencrypt-homelab` TLS, all paths → `frontend:8080`. |
| `rbac-cluster/rbac.yaml` | ClusterRole + ClusterRoleBinding | `eden-rbac` (**platform**) | The authority of the orchestrator to create a project namespace. |

The Argo Applications live in
`platform/services/gitops/registry/app-eden*.yaml`. `eden` is registered in
`clusters/instances/homelab/identity.yaml`, and it is permitted in the
destinations of the `apps` and `platform` AppProjects.

## Contract surface (what the eden Helm chart and the app code depend on)

- **Service DNS:** `nats:4222`, `vault:8200`, and Postgres through BOTH
  `postgres:5432` (a plain ClusterIP) and
  `eden-postgres-0.eden-postgres.eden.svc` (the stable pod FQDN through the
  headless governing Service). The chart emits the pod form, and the DSN of the
  seed Job uses the plain form. Both resolve to the same database.
- **Vault token file:** the eden chart mounts the k8s Secret `eden-vault-token`
  (key `token`) at `/vault/secrets/token`. The pods run
  `EDEN_VAULT_MODE=token-file` and `VAULT_ADDR=http://vault:8200`. The seed Job
  in this directory mints that token.
- **The Vault kv-v2 mount `eden/`, path `production`.** The fields are:
  `agentgateway-jwt-signing-key`, `platformgateway-jwt-signing-key`,
  `connectors-kek` (the AES-256 KEK; the envelope library of the platformgateway
  wraps the data key of every user connector under it — ADR-0029, doc 19;
  resolved as `vault://eden/production#connectors-kek`),
  `platformgateway-database-dsn`, the generic `database-dsn` (the record and
  dashboard store of the agentgateway, in the SAME eden Postgres, derived from
  the mounted password), and the optional `setup-token`, `gh-token` and
  `openrouter-api-key` (resolved as `vault://eden/production#<field>`). The seed
  Job writes the 2 DSN fields deterministically, so a second run rewrites the
  identical derived value. It generates the JWT keys AND the connectors KEK only
  if they are absent, and it NEVER rotates them on a reseed. A rotated KEK would
  orphan every stored connector.
- **ServiceAccounts:** `eden-agent` (agentgateway and agent-runtime),
  `platformgateway` (platformgateway), `eden-frontend` (frontend) and
  `eden-orchestrator` (orchestrator). `20-rbac.yaml` declares the
  `serviceAccountName` of every chart Deployment, and each SA carries the
  `ghcr-pull` imagePullSecret for the private registry.
- **Postgres:** the user and the database are both `eden`. The password is in the
  Secret `eden-orchestrator-postgres`, key `password`.

---

## Bring-up runbook

Run these steps against the homelab cluster (`kubectl` context `home`). Argo
syncs the Namespace and the backing stack (Postgres, NATS and Vault)
automatically once these manifests reach `main`. The steps below are the actions
that Argo cannot do: the secret material and the Vault ceremony.

### The `bw` ceremony (how secret material moves)

Every imperative secret below comes from the cloud Vaultwarden
(`secrets.mateosegura.com`) through the `bw` CLI. This is the pattern as
executed:

1. **Unlock in a REAL terminal, not in this session.** The unlock prompt inside a
   session crashes readline. Unlock separately and hand over the session token:

   ```sh
   bw unlock --raw > ~/.bw-session      # run in a real terminal
   export BW_SESSION="$(cat ~/.bw-session)"
   ```

2. **A value flows bw → tmpfs → kubectl, and is NEVER printed.** Write each value
   into a tmpfs scratch file under `umask 077`, feed it to `kubectl`, then shred
   it. No secret value lands in the transcript, in a git-tracked file, or in a
   `--from-literal` argument on the command line:

   ```sh
   umask 077
   d="$(mktemp -d /dev/shm/eden-bring-up.XXXXXX)"
   trap 'rm -rf "$d"' EXIT
   bw get password shared/eden/postgres-password --session "$BW_SESSION" > "$d/pg"
   # ... consume "$d/pg" via kubectl, then the trap shreds it.
   ```

The placeholders in this runbook stand for values that arrive this way. Never
write a real secret into any file.

### 0. The ghcr image-pull secret (never in git)

The Eden workload images live in the PRIVATE registry
`ghcr.io/gophersys/eden/*`. The cluster therefore needs a docker-registry pull
credential BEFORE any workload pod schedules. Without it the pod enters
`ImagePullBackOff`. Every workload SA in `20-rbac.yaml` references the credential
by the name `ghcr-pull`. Build it from the Vaultwarden item
`shared/github/pat-godmode` (see the `bw` ceremony above). The PAT flows bw →
tmpfs → kubectl, and it is never printed:

```sh
# BW_SESSION exported; "$d" is the umask-077 tmpfs scratch dir.
bw get item shared/github/pat-godmode --session "$BW_SESSION" \
  | jq -r '.login.password' > "$d/ghcr-pat"
kubectl -n eden create secret docker-registry ghcr-pull \
  --docker-server=ghcr.io \
  --docker-username=mateosegura \
  --docker-password="$(cat "$d/ghcr-pat")"
```

> **Follow-up (rotate):** `pat-godmode` is a broad token, and it is used here only
> because it was quick. Move `ghcr-pull` onto a NARROW PAT with `read:packages`
> only, and create the secret again from that PAT.

### 1. Imperative secrets (never in git)

The Postgres password is GENERATED once, before Postgres schedules. Vaultwarden
is the SOURCE OF TRUTH: generate the value, store it in the Vaultwarden item
`shared/eden/postgres-password` FIRST, and THEN create the k8s Secret from that
same value. The value flows bw → tmpfs → kubectl, and it is never printed:

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
`vaultwarden` ClusterSecretStore returns the **NOTES** field of each item, so put
the single token value in the notes of the item, not in the password field. All 3
items are OPTIONAL: chat and login work without them, and only a live agent turn
or the create-saga needs them.

- `shared/eden/claude-setup-token` — the Claude Code OAuth token (for agent
  runs).
- `shared/eden/forge-github-pat` — the GitHub PAT for project-forge (the
  create-saga).
- `shared/eden/openrouter-api-key` — the OpenRouter key (the omp path).

ESO then materializes the Secret `eden-bootstrap` in namespace `eden`, with the
keys `setup-token`, `gh-token` and `openrouter-api-key`. The seed Job copies the
keys that are present into Vault.

### 3. Vault init and unseal (a ONE-TIME operator ceremony)

Vault boots **sealed**, because it does not run in dev mode. Initialize it once,
capture the unseal key and the root token into the imperative Secret
`eden-vault-init`, then unseal. **This is a homelab-grade configuration: 1 key
share and a threshold of 1. That is deliberate.** NEVER commit these values
anywhere.

Store the init output in BOTH places: the k8s Secret `eden-vault-init` (the seed
Job reads `root-token`, and the reseal procedure reads `unseal-key`) AND the
Vaultwarden item `shared/eden/vault-init`, which is the durable backup off the
cluster and survives a cluster wipe. Capture the init output straight into a
tmpfs file. Never let it reach the terminal:

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

**After a node reboot** Vault comes back sealed, because the file storage is
durable but the master key is not persisted. See the reseal section below.

### 3b. The reseal problem (it happens repeatedly)

**ANY restart of the `vault-0` pod seals Vault again.** That includes a node
reboot, an OOM, a manual `kubectl delete pod`, AND — the case that is easy to
miss — **Argo rolling the StatefulSet** when it reconciles a change to
`07-vault.yaml`. The file storage is durable, so the DATA survives. The master
key is not persisted, so the pod boots SEALED, and every `vault://…` reference
stops resolving until you unseal it again. Expect this every time the Vault
StatefulSet rolls.

**The procedure to unseal again.** The unseal key stays in `eden-vault-init`.
Feed it through tmpfs and stdin, so that it never reaches the process table or
the transcript:

```sh
umask 077; f="$(mktemp /dev/shm/eden-unseal.XXXXXX)"; trap 'rm -f "$f"' EXIT
chmod 0600 "$f"
kubectl -n eden get secret eden-vault-init \
  -o jsonpath='{.data.unseal-key}' | base64 -d > "$f"
kubectl -n eden exec -i vault-0 -- sh -c 'read K; vault operator unseal "$K"' < "$f"
```

**If the seed Job used all its retries** while Vault was sealed, an unseal alone
does not run it again. The Job fails closed against a sealed Vault, and it can
exhaust `backoffLimit`. Delete the exhausted Job and let the `selfHeal` of Argo
create a new one:

```sh
kubectl -n eden delete job eden-vault-seed
# Argo selfHeal recreates the Job; it now runs green against the unsealed Vault.
```

### 4. Run the seed Job

Once Vault is unsealed and `eden-vault-init` exists, the seed Job (which Argo
syncs) does all of the following: it enables kv-v2 at `eden/`, generates the 2
JWT signing keys **only if they are absent** (a second run NEVER rotates them, so
the sessions survive), writes the platformgateway DSN, copies any
`eden-bootstrap` harness credentials that are present, creates the `eden-read`
policy, and mints the `eden-vault-token` that the pods consume. You can run it
again at any time.

The Role of the seed Job in `20-rbac.yaml` carries the **`delete`** verb on
Secrets. Its unpublish step does a `delete` and then a `create`, without a shell,
as the idempotent update. This was proven live: without `delete` the step fails
with `Forbidden` and the Job aborts. Do not narrow the Role back to `get`,
`create` and `update`.

```sh
kubectl -n eden delete job eden-vault-seed --ignore-not-found
kubectl apply -f apps/eden/08-vault-seed-job.yaml   # or let Argo re-sync
kubectl -n eden logs -f job/eden-vault-seed
```

### 5. Workloads

The workload Deployments arrive through the promotion of the eden chart. See the
next section. Once `eden-vault-token` exists and the workloads are pinned, they
resolve their `vault://eden/production#…` references and become Ready. The
ingress then starts to serve `eden.mateosegura.com`. See the DNS step below.

### 6. The DNS record (Cloudflare — DNS only, not proxied)

`eden.mateosegura.com` needs an **explicit A record, DNS only, that points at the
homelab nginx VIP `10.168.0.240`**. This is the same pattern as
`argocd.mateosegura.com`. Add it in Cloudflare as an A record with the proxy OFF
(grey cloud). Do NOT depend on a wildcard record.

**Why the explicit record matters, and the exact symptom we saw:** a wildcard
`*.mateosegura.com` record resolves `eden.mateosegura.com` to the **cloud
cluster**. The nginx there answers an unknown host with its **default TLS
certificate**, and the browser rejects it with `ERR_CERT_AUTHORITY_INVALID`. An
explicit record points the name straight at the homelab VIP, so the request
reaches the homelab nginx, which serves the correct `letsencrypt-homelab`
certificate for the ingress.

---

## What the release pipeline promotes

A parallel release workflow in the **eden monorepo** builds the multi-arch images
`ghcr.io/gophersys/eden/{agentgateway,agent-runtime,platformgateway,frontend}` on
a `v<semver>` tag. It then opens a **digest-pin PR against THIS repo** that adds
the workload Deployments and Services into `apps/eden/`. The files are flat and
numbered above `40-`, for example `50-agentgateway.yaml`, and they are pinned to
the new image **digest**. Those manifests set the `serviceAccountName` of each
service (`eden-agent` for agentgateway and agent-runtime; `platformgateway`;
`eden-frontend` for the frontend). They talk to `nats:4222`, `postgres:5432` and
`vault:8200`, and they mount `eden-vault-token` at `/vault/secrets/token`. The
`app-eden` Application (`recurse:false`, a flat directory) picks them up
automatically, and Argo reconciles them with `selfHeal`, `prune` and
`ServerSideApply`.
