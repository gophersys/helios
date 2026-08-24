# Homelab cluster topology

What runs in the `homelab` k3s cluster, namespace by namespace, and why. Argo CD
reconciles everything from this repo's `platform/services/gitops/registry/` (the
`root` app-of-apps). This document gives the "what and why".
`.claude/rules/50-cluster-architecture.md` gives the vocabulary. This document
reflects the live cluster as of 2026-08-19.

Cluster: 8 k3s VMs on 3 Proxmox hosts (pve-00 MS-A2, pve-01 ThinkPad P1, pve-03
Yoga). CNI is flannel plus kube-router, so NetworkPolicy IS enforced. All nodes
are on the Tailscale mesh.

## The exposure model

- **Public (internet), behind Cloudflare Access + Google SSO** — the Cloudflare
  tunnel (`cloudflared`) forwards to `ingress-nginx:80`. `home.` (the portal) is
  the only one left: `workspaces.` was removed on 2026-08-19. Its Ingress carries
  **no** `tls:` block, because the tunnel enters nginx on :80 and TLS there
  causes a 308 loop.
- **Tailnet-private** — DNS A records only, pointing at `10.168.0.240` (the
  MetalLB nginx VIP). They are reachable only on the tailnet or the LAN, and
  cert-manager supplies the TLS: `torrent.`, `prowlarr.`, `files.`, `argocd.` and
  `s3.` (the MinIO API).
- **Hosted on the workstation (NOT in the cluster)** — the **studio dashboard**
  runs on Mateo's MacBook Air at `http://100.89.71.64:8737` (the launchd agent
  `com.mateosegura.studio-dashboard`, source in `MateoSegura/music-studio` →
  `tools/studio`). `home.` links to it under **Studio**, but the tunnel never
  routes it. It runs there because it needs Ableton Live 12, AbletonOSC
  (localhost UDP) and the 2.5 GB `~/Music` tree. None of these exist in k3s. Its
  Homepage cards read
  offline when the laptop sleeps. That is correct, not a fault. See
  `music-studio/docs/architecture.md` → "The studio dashboard".
- **Grafana** — **no hostname at all** since the stack came back on 2026-08-19.
  Reach it at the MetalLB LoadBalancer `10.168.0.241`, plain HTTP, tailnet only
  — an address the chart **pins** with `metallb.io/loadBalancerIPs`, so it is a
  fact rather than an allocation accident.
  Before 2026-08-09 it was *publicly reachable through the Cloudflare tunnel*
  behind nothing but Grafana's own login, with an admin password that was
  generated and never stored in the vault, while this document stated the
  opposite. That is the incident `contracts/exposure.yaml` exists for.
  An earlier revision of this document said `grafana.mateosegura.com` "no longer
  resolves to anything". **That was wrong.** Its dedicated A record was deleted,
  but `*.mateosegura.com` is a wildcard to `144.24.23.2` — the OCI cloud
  cluster's public IP — so the name still resolves publicly, to a different
  cluster, and nothing serves it (`dig` → `144.24.23.2`, `curl` → `000`,
  measured 2026-08-19). An Ingress on the homelab for that name could therefore
  never receive a request, so the reinstall ships without one. The restore order
  is written in the header of
  `platform/services/observability/chart/values-homelab.yaml`: explicit A record
  first, then the Ingress, then the `contracts/exposure.yaml` declaration in the
  same PR.
  **The wildcard is a standing property of the zone, not a Grafana quirk:** every
  undeclared `*.mateosegura.com` name resolves publicly to the cloud cluster.

---

## Platform — core (every cluster gets these)

### `argocd` — the GitOps engine
Argo CD (server, repo-server, applicationset-controller, redis, and the
application-controller StatefulSet). It reconciles the whole cluster from
`registry/`. The UI is at `argocd.mateosegura.com` (tailnet). The `root`
Application recurses through `registry/`, so a new `*.yaml` file there registers
a new workload.

### `cert-manager` — TLS issuance
cert-manager plus cainjector and the webhook. The ClusterIssuer
`letsencrypt-homelab` (DNS-01 through Cloudflare) issues real Let's Encrypt
certificates for the tailnet-private hostnames.

### `external-secrets` — the secrets bridge
The External Secrets Operator (controller, webhook, cert-controller) plus
**`bw-serve`**, a bridge to the cloud Vaultwarden. The ClusterSecretStore
`vaultwarden` resolves items by name and returns their `notes` field.
Single-value credentials are created imperatively instead (see
`docs/runtime-secrets.md`). The CronJob **`bw-serve-sync`** POSTs `/sync` to
the bridge every 10 minutes, because the bridge caches the vault at login and
never syncs on its own (build ledger #89).

### `metallb-system` — LoadBalancer on bare metal
The controller plus the speaker DaemonSet, in L2 mode, with the pool
`10.168.0.240-250`. It backs the Service VIP of `ingress-nginx` (`.240`,
**unpinned** — it holds that address by creation order, recorded as a follow-up
in `platform/core/edge/loadbalancer/metallb/README.md`) and Grafana (`.241`,
pinned). The allocation table lives in that README.

### `ingress-nginx` — the ingress controller
The single IngressClass is `nginx` (Traefik was removed). All HTTP enters here,
either from the Cloudflare tunnel (public) or from the MetalLB VIP (tailnet).

### `longhorn-system` — REMOVED 2026-08-19
Longhorn is gone. It held **0 volumes**: its one real consumer was the
`observability` stack, which was itself removed on 2026-08-09, and every
workload that remains — the media stack, eden, MinIO — is on `local-path` or a
hostPath by deliberate choice. It cost a manager, a CSI plugin, attacher,
provisioner, resizer and snapshotter, the UI and an engine-image DaemonSet, on
every node, to replicate nothing. It was also **untracked drift**: installed by a
raw `kubectl apply` of the upstream manifests, so Argo never managed it and its
running version existed only in prose (debt-register D9).

**`local-path` is the storage story for this cluster.** A volume that must
survive the loss of a node does not exist here today; if one appears, that is a
deliberate decision to make again, not a component to keep running on the chance.
See `platform/core/storage/README.md`.

### `minio` — the S3 backup target
One MinIO instance on a hostPath NVMe on k3s-w-1, kept off any replicated volume
so that the backups do not depend on the thing they protect. It has 1 live
bucket:
- `music-backups` — the restic repository for the music-studio workspace on
  Mateo's Mac (a scoped user, tailnet-private at `s3.mateosegura.com`).
- `longhorn-backups` — **orphaned by the Longhorn removal (2026-08-19)**. The
  bucket and its objects still sit on the NVMe. Deleting them is a deliberate
  step, not a side effect of this document.

It is network-isolated: `ingress-nginx` may reach `:9000`, and the
`allow-longhorn-backups` rule in `apps/minio/25-networkpolicy.yaml` now selects a
namespace that no longer exists. See `apps/minio/README.md`.

### `observability` — REMOVED 2026-08-09, REINSTALLED under Argo
Prometheus, Alertmanager (since 2026-08-24, Discord delivery), Loki, Tempo,
Grafana and 2 Grafana Alloy collectors (an OTLP gateway Deployment and a
log-tailing DaemonSet), from the in-repo `eden-observability`
chart at `platform/services/observability/chart`, release `obs`.

**Why it was removed.** The `obs` release had been in `failed` helm state at
revision 8 since 2026-06-18, and Argo never managed it. Nothing reconciled it,
and every hand-applied fix reverted with no message. It was uninstalled on
2026-08-09 instead of left in a broken half state, and the namespace with its
`storage-tempo-0` PVC was reclaimed.

**What is different now.** It is an Argo Application
(`registry/app-observability.yaml`, project `platform`, automated + `selfHeal`),
so nothing reconciles it by hand and drift cannot survive. Its 5 PVCs — Loki
10Gi, Tempo 10Gi, Prometheus 20Gi, Grafana 5Gi, Alertmanager 2Gi (added
2026-08-24 with the Discord alerting) — are on **`local-path`**, decided
2026-08-19: node-local, no replication, on the stated ground that telemetry is
re-derivable and none of it is a system of record.

**Grafana has no hostname.** The reinstall ships the MetalLB LoadBalancer
(`10.168.0.241`, pinned with `metallb.io/loadBalancerIPs`, plain HTTP, tailnet)
and **no Ingress**: the dedicated
`grafana` A record was deleted on 2026-08-09, and `*.mateosegura.com` sends the
name to the cloud cluster's public IP instead, so a homelab Ingress for it could
never be reached. See the exposure model above and the restore order in
`platform/services/observability/chart/values-homelab.yaml`.
`contracts/exposure.yaml` declares no `grafana` host, and that is correct: there
is no hostname to declare.

**One imperative secret.** `grafana-admin` is created by hand
(`docs/runtime-secrets.md`); Grafana does not start until it exists. The
Alertmanager Discord webhook is NOT imperative: it is an ExternalSecret in the
chart (vault item `shared/discord/alerts-webhook`), and Alertmanager sits in
ContainerCreating until ESO syncs it. The
observability of the cloud cluster (`obsv.mateosegura.com`) is a separate,
unaffected install.

## Platform — edge

### `cloudflare-tunnel` — public ingress
`cloudflared` (2 replicas) runs a **dashboard-managed** tunnel (`eden-home`,
token-only in the cluster) with a single catch-all rule to `ingress-nginx:80`. It
is the only path from the public internet into the cluster. The hostnames and the
Cloudflare Access apps are configured in the Zero Trust dashboard, not in git.

### `tailscale` — tailnet exposure
The Tailscale k8s operator plus one `ts-*` proxy StatefulSet for **each**
Service that opts in (`loadBalancerClass: tailscale`). It needs the imperative
`operator-oauth` Secret. (The Zephyr devboxes were its first consumers; they
were removed 2026-08-18 and no Service opts in today.)

## Platform — CI

### `arc-systems` / `arc-runners` — self-hosted GitHub Actions
The Actions Runner Controller (`arc-systems` holds the controller) drives an
org-wide runner scale set (`arc-runners`: `arc-org`, dind, `minRunners` 0 and
`maxRunners` 4) that serves the `eden`, `infrastructure` and `workspaces`
REPOSITORIES (`runs-on: arc-org`) — `workspaces` here is the source repo, which
is untouched by the removal of its deployment. It authenticates as the
**gophersys-arc** GitHub App (the `arc-github-app` Secret).

## Apps

### `media` — the self-hosted media and portal stack (project `music`)
- **qbittorrent** — a torrent client behind a **gluetun** ProtonVPN kill-switch
  (a shared network namespace; all torrent egress uses `tun0`). An initContainer
  enforces the configuration that the downloads depend on
  (`apps/music/qbittorrent/config-enforce/`). `torrent.mateosegura.com`.
- **prowlarr** — the indexer manager and search (`prowlarr.`). The setup runbook
  is `apps/music/prowlarr/SETUP.md`.
- **flaresolverr** — a headless-Chrome proxy that solves Cloudflare challenges
  for the indexers behind Cloudflare. Prowlarr drives it through an indexer-proxy
  tag (ClusterIP, no ingress).
- **filebrowser** — web file access to `/mnt/media` and the downloads (`files.`).
- **homepage** — the single portal (`home.`), with live widgets over qBittorrent,
  Prowlarr and the disk. It is now the **only** public app on this cluster.

### `workspaces-prod` — REMOVED 2026-08-19
`workspaces-api` was a Go and Svelte app at `workspaces.mateosegura.com` whose
only function was to manage the `embedded-lab` Zephyr devbox envs — a read-only
view plus create/destroy operations that opened GitOps PRs against this repo.
Those envs and the whole `embedded-lab` stack were removed on 2026-08-18, so the
app managed nothing. By then it was also **403-looping and 0/1 Ready**: its
GitHub App credential no longer authorized it. Mateo's decision on 2026-08-19 was
to remove rather than repurpose.

Gone with it: the `workspaces-prod` Namespace and its NetworkPolicy, the
`workspaces-api` Deployment, Service, ServiceAccount and Ingress, the
`workspaces` AppProject, both registry Applications, and the public exposure
declaration. The `gophersys/workspaces` source repository is untouched — this
repo only ever held the deployment. The `workspaces-github-app` Secret was
namespaced into `workspaces-prod` and dies with it; the **gophersys-arc** App key
it came from is still live for ARC (`docs/runtime-secrets.md`).

### `eden` — the Eden platform (project `apps`)
The Eden agentic-engineering stack (`apps/eden/`: backing services, RBAC, seed
and ingress) at `eden.mateosegura.com`. It is a separate workstream, owned by the
Eden build, and it is noted here only for completeness. See
`apps/eden/README.md`.

---

## Node roles (see each `clusters/instances/homelab/nodes/<n>/identity.yaml`)
- **cp-0/1/2 + w-0** — control-plane and platform (`devops`).
- **w-1** — the media node (NVMe `/mnt/media`, GPU labels); runs the `media`
  stack.
- **w-2/3/4** — general `apps`. **w-4 returned to general capacity on
  2026-08-19** (decision closed): it held the `usb-embedded: true` label and QEMU
  USB passthrough for the removed `embedded-lab` stack, nothing scheduled on that
  label, and `arc-org`, `arc-review` and the image warmer all reserved it. Those
  exclusions are gone and the label is off the declaration. It stays out of
  `arc-build` on the RAM rule alone — 9Gi, the same reason k3s-w-3 is out.

Host-level bootstrap that nothing reconciles lives in
`clusters/instances/homelab/hypervisors/pve-01/bootstrap/`. The k3s-w-4 half was
removed with the embedded role; the USB passthrough it depended on is still
declared on pve-01, and unwinding that is a hypervisor-side call.
