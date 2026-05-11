# Deploy — network

Network plane of the platform: Traefik ingress, cert-manager TLS, K3s service DNS, NetworkPolicy boundaries, and the MTIB gRPC routing to edge nodes. K3s ships Traefik as the default Ingress controller and `local-path` as the default StorageClass; the chart targets both directly.

Refresh this file when: the ingress hostnames change, the TLS issuer/secret changes, a new NetworkPolicy is added or an existing one's egress/ingress set changes, the MTIB port moves, or the K3s control-plane VIP / API server endpoint changes.

## Hostnames

| Environment | Host | Subdomains |
|---|---|---|
| staging | `staging.concord.ad.corekinect.com` | `docs.staging.concord.ad.corekinect.com`, `pypi.staging.concord.ad.corekinect.com` |
| production | `concord.ad.corekinect.com` | `docs.concord.ad.corekinect.com`, `pypi.concord.ad.corekinect.com` |
| CI dashboard (devops) | `admin.concord.local` (legacy) / `admin.staging.concord.local` | — |
| dev (compose) | `localhost:9001` (api), `localhost:4200` (app via `nx serve`), `localhost:8675` (minio) | — |

DNS for `*.concord.ad.corekinect.com` is served by the office Active Directory DNS; cluster IPs route through the office VIP. From off-site, the `concord-remote` tool (in the umbrella workspace) tunnels these to `127.0.0.2:443` on WSL — see [`/home/mateo/work/docs/CONCORD-REMOTE.md`](../../../../docs/CONCORD-REMOTE.md).

The Helm `values.yaml` defaults still reference `staging.concord.local` (the bootstrap hostname); both staging and production override with `*.ad.corekinect.com` in their values files. The K3s-served `concord.local` host is what cert-manager bootstrap and the CI Helm chart use.

## Ingress

`deploy/production/helm/concord/templates/ingress.yaml` renders one `Ingress/concord-ingress` per env. Traefik fronts everything.

```
host: {{ .Values.ingress.host }}              # staging.concord.ad.corekinect.com or concord.ad.corekinect.com
ingressClassName: traefik
annotations:
  traefik.ingress.kubernetes.io/router.entrypoints: web,websecure
  traefik.ingress.kubernetes.io/router.tls: "true"
tls:
  - hosts: [<host>, docs.<host>, pypi.<host>]
    secretName: concord-tls
rules:
  - host: <host>
    paths:
      /v2         → concord-http-api:9001
      /auth       → concord-http-api:9001
      /socket.io  → concord-http-api:9001
      /           → concord-frontend:80
  - host: docs.<host>
    paths:
      /           → concord-docs:80
  - host: pypi.<host>          # only if infrastructure.pypi.enabled
    paths:
      /           → concord-pypi:8080
```

The order of `paths` matters: longer prefixes (`/v2`, `/auth`, `/socket.io`) come first, the catch-all `/` last. Traefik resolves longest-prefix first regardless, but the explicit ordering makes the intent obvious.

## TLS — cert-manager

`infrastructure/clusters/office/networking/cert-manager-ca.yaml` bootstraps a self-signed `ClusterIssuer/selfsigned-bootstrap`, then issues a 10-year CA Certificate (`concord-ca`) stored in `Secret/concord-ca-secret` in the `cert-manager` namespace, then exposes `ClusterIssuer/concord-ca-issuer` referencing that CA Secret.

`infrastructure/clusters/office/networking/certificates/staging-cert.yaml` issues the per-namespace Certificate:

```
kind: Certificate
metadata:
  name: staging-concord-tls
  namespace: staging
spec:
  secretName: staging-concord-tls
  issuerRef:
    name: concord-ca-issuer
    kind: ClusterIssuer
  commonName: staging.concord.local
  dnsNames: [staging.concord.local, "*.concord.local"]
  duration: 8760h        # 1 year
  renewBefore: 720h      # 30 days
```

The Ingress in the chart references `secretName: concord-tls`. **The naming is environment-dependent**: bootstrap uses `*.concord.local` for self-signed certs (suitable for the lab and `concord-remote` tunneling). When the cluster is wired to the real CoreKinect SubCA, the secret name in the chart values still references `concord-tls` — the Certificate resource gets pointed at the upstream issuer in `infrastructure/`.

cert-manager renews automatically 30 days before expiry. To force re-issue: `kubectl delete secret concord-tls -n <env>` and wait ~30 seconds for cert-manager to recreate it.

### CA distribution

`infrastructure/clusters/office/networking/concord-ca.crt` is the committed root CA. It's mounted into the CI nightly CronJob via Secret `corekinect-ca-certs` so that `pip install` and `git clone` against internal hosts succeed. Developers off-cluster trust the CoreKinect SubCA at the OS level (`deploy/ca-certs/CoreKinect*.crt` are also committed for that).

## Internal cluster DNS

K3s ships CoreDNS. Service DNS follows the standard pattern:

```
<service>.<namespace>.svc.cluster.local
```

Used in the chart values:

| URL | What |
|---|---|
| `http://concord-http-api.staging.svc.cluster.local:9001` | http-api inside staging (used by `CONCORD_API_URL` in values-staging) |
| `http://concord-http-api.production.svc.cluster.local:9001` | same, production |
| `http://concord-http-api:9001` | short form for same-namespace consumers (build-service, git-poller, docs) |
| `http://concord-minio:9000` | MinIO inside the namespace |
| `http://concord-build-service:9002` | build-service inside the namespace |
| `http://concord-pypi:8080` | internal PyPI |
| `concord-postgres:5432` | Postgres inside the namespace (no scheme — `psycopg2` connection string) |

Cross-namespace calls (e.g., validation runner pods in `validation` namespace calling http-api in `staging`) use the FQDN form. The helper `services/kubernetes/runner_env.py::expand_to_fqdn` does this expansion automatically when http-api builds env vars for spawned Jobs.

## NetworkPolicy boundaries

`network-policies.yaml` defines three policies. Each is gated on `networkPolicies.enabled` (true in both staging and production values).

### `concord-postgres-restrict`

Ingress allow-list (port 5432):

- pods with `app.kubernetes.io/name: concord-http-api`
- pods with `app.kubernetes.io/name: concord-backup-postgres` (the CronJob)
- pods with `app.kubernetes.io/name: concord-backup-pre-upgrade` (Helm hook)
- pods with `app.kubernetes.io/name: concord-backup-verify`

Egress: `[]` (Postgres never initiates outbound).

Note: validation/manufacturing runner pods are **not** allowed direct Postgres access. They go through http-api.

### `concord-minio-restrict`

Ingress allow-list (port 9000):

- pods with `app.kubernetes.io/name: concord-http-api`
- pods with `app.kubernetes.io/name: concord-build-service`
- all backup-related pods (postgres backup uploads dumps here; minio backup mirrors itself)
- `devops` namespace pods with `app.kubernetes.io/component: ci` (weekly CronJob uploads results)
- `validation` namespace, **any pod** (`podSelector: {}` — namespace-scoped). Runner pods upload telemetry; their names are session-specific and change over time. Both selectors must be on the same `from` entry; k3s's kube-router rejects namespaceSelector-only rules without an explicit `podSelector: {}`.

Egress: `[]`.

### `concord-http-api-restrict`

Ingress (port 9001):

- `kube-system` namespace (Traefik ingress controller)
- pods with name `concord-frontend`
- pods with name `concord-build-service`
- pods with name `concord-git-poller`
- `validation` namespace (any pod — runner reporter callbacks)
- `from: []` (kubelet probes)

Egress:

- `concord-postgres` :5432
- `concord-minio` :9000
- `concord-pypi` :8080
- `kube-system` namespace :53 UDP+TCP (DNS)
- IPs 10.4.45.11/12/13 :6443 (the three K3s control-plane nodes — for `kubernetes` Python client calls)
- `0.0.0.0/0` except RFC1918 ranges on :443 and :2013 (external HTTPS — Bitbucket, CoreOps, the office auth server on 2013)
- `concord-build-service` :9002
- `10.4.45.0/24` :50053 (every node in the office cluster CIDR on the MTIB gRPC port)

The last rule is what lets http-api reach the mtib-server on every edge Verdin node.

## MTIB gRPC routing (port 50053)

mtib-server runs on every fixture node — one Deployment per (node, slot) pair, named `mtib-<verdin-hostname>-s<slot>`. Each binds to host networking on the Verdin's IP at port 50053.

When http-api spawns a validation/manufacturing runner Job, it passes `MTIB_HOSTS=<ip1>:50053,<ip2>:50053,…` via the Job env. The runner connects directly to each MTIB by IP — there is **no K8s Service** in front of MTIBs. The egress NetworkPolicy on http-api whitelists `10.4.45.0/24:50053` so http-api itself can poll MTIBs for observability.

See [`verdin-edge.md`](verdin-edge.md) for how edge nodes onboard and how the IP gets resolved.

## Smoke endpoints from inside the cluster

`ctl.sh::_smoke_test` execs into an http-api pod and curls `http://concord-http-api:9001/v2/docs`. It deliberately does **not** smoke frontend (port 80) or docs — the http-api egress policy doesn't allow port 80 to those services, so a smoke from http-api would fail with `Connection refused`. Their readiness probes (kubelet from the node) already gate the rollout.

## concord-remote — off-site routing

When a developer is off the office network, the `concord-remote` CLI (in the umbrella `work/` workspace, see `/home/mateo/work/docs/CONCORD-REMOTE.md`) sets up:

- WireGuard tunnel to the office
- DNS overrides so `staging.concord.ad.corekinect.com` resolves to `127.0.0.2`
- Local TLS termination using the CoreKinect CA (`deploy/ca-certs/`)
- Forwarding to the actual cluster ingress

This is purely a *client-side* layer; the cluster itself is unaware. From inside the cluster everything still uses `.svc.cluster.local`.

## How to add a new ingress hostname

1. Add the host string to the `hosts` array in `tls:` of `ingress.yaml`.
2. Add a new `rules` entry with the host and its backend Service.
3. Add the host to `dnsNames` on the cert-manager `Certificate` (in `infrastructure/clusters/office/networking/certificates/`).
4. Wait for cert-manager to refresh `concord-tls` to include the new SAN.
5. Confirm DNS resolves (office AD DNS, plus `concord-remote` if relevant).
6. Update this file's hostname table.

## How to add a new egress destination from http-api

The default http-api NetworkPolicy egress is restrictive. Any new outbound endpoint needs an explicit rule:

1. Edit `concord-http-api-restrict` in `network-policies.yaml`.
2. Add a `- to:` entry with the IP block or namespace/pod selector and the destination port.
3. Re-deploy: `nx update platform -c staging`.
4. Validate: `kubectl exec -n <env> <http-api-pod> -- nc -zv <host> <port>`.

Forgetting this step manifests as the http-api silently failing connections with no error in logs (until the request handler times out).

## Common failure modes

- **TLS cert expired / invalid** — cert-manager renewal stuck. `kubectl describe certificate concord-tls -n <env>` shows the renewal error. Most often: the issuer Secret was rotated and the Certificate hasn't been re-issued. Delete the cert + secret and let cert-manager recreate.
- **Frontend pages 502** — the Ingress is up but `concord-frontend` is `CrashLoopBackOff` or unready. Check pod logs; common cause is the SvelteKit container missing env vars (CORS, API URL).
- **`Connection refused` from http-api → external host** — the egress NetworkPolicy doesn't allow that destination. Add an egress rule (see above).
- **MTIB pod runs but http-api can't reach it** — `MTIB_PORT` mismatch (always `50053`) or the Verdin host's IP changed (DHCP). Re-resolve via `services/kubernetes/client.py::resolve_node_ips` or check that the node still has its `concord.corekinect.com/workload-edge=true` label.
- **`docs.<host>` and `pypi.<host>` 404** — `docs.enabled` or `infrastructure.pypi.enabled` is `false` in the values. The Ingress conditionally adds rules; without enabling those, Traefik returns 404 for the subdomains.
- **concord-remote shows handshake errors** — usually WSL DNS reverted to a public resolver. Restart `concord-remote`; it overrides `/etc/resolv.conf` on each run.

## Related knowledge

- [`overview.md`](overview.md) — cluster topology that the ingress/network sits on top of.
- [`helm.md`](helm.md) — the templates that render ingress + network policies.
- [`secrets.md`](secrets.md) — `concord-tls`, `corekinect-ca-certs`.
- [`verdin-edge.md`](verdin-edge.md) — how edge nodes get IPs that http-api whitelists.
- [`../apps/backend/http-api.md`](../apps/backend/http-api.md) — the consumer of most egress rules.
