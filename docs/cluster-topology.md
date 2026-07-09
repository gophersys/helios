# Homelab cluster topology

What actually runs in the `homelab` k3s cluster, namespace by namespace, and
why. Everything is reconciled by Argo CD from this repo's
`platform/services/gitops/registry/` (the `root` app-of-apps). This is the
"what/why" companion to `.claude/rules/50-cluster-architecture.md` (the
vocabulary) and reflects the live cluster as of 2026-07-09.

Cluster: 8 k3s VMs on 3 Proxmox hosts (pve-00 MS-A2, pve-01 ThinkPad P1,
pve-03 Yoga). CNI flannel + kube-router (NetworkPolicy IS enforced). All nodes
on the Tailscale mesh.

## Exposure model at a glance
- **Public (internet), behind Cloudflare Access + Google SSO** — the CF tunnel
  (`cloudflared`) forwards to `ingress-nginx:80`: `home.` (portal) and
  `workspaces.`. Their Ingresses carry **no** `tls:` block (the tunnel enters
  nginx on :80; TLS there 308-loops).
- **Tailnet-private** — DNS-only A records → `10.168.0.240` (the MetalLB nginx
  VIP), reachable only on the tailnet/LAN, TLS via cert-manager: `torrent.`,
  `prowlarr.`, `files.`, `argocd.`, `s3.` (MinIO API).
- **Grafana is the exception**: `grafana.` → its **own** MetalLB LoadBalancer at
  `10.168.0.241`, plain **HTTP :80** — no Ingress, no cert-manager cert (managed
  by the `obs` Helm release). Tailnet-private like the rest, just a different
  path and no TLS.

---

## Platform — core (every cluster gets these)

### `argocd` — GitOps engine
Argo CD (server, repo-server, applicationset-controller, redis, and the
application-controller StatefulSet). Reconciles the whole cluster from
`registry/`. UI at `argocd.mateosegura.com` (tailnet). The `root` Application
recurses `registry/` so dropping a `*.yaml` there registers a new workload.

### `cert-manager` — TLS issuance
cert-manager + cainjector + webhook. ClusterIssuer `letsencrypt-homelab`
(DNS-01 via Cloudflare) issues real LE certs for the tailnet-private hostnames.

### `external-secrets` — secrets bridge
External Secrets Operator (controller, webhook, cert-controller) + **`bw-serve`**,
a bridge to the cloud Vaultwarden. ClusterSecretStore `vaultwarden` resolves
items by name and returns their `notes` field. Single-value credentials are
created imperatively instead (see `docs/runtime-secrets.md`).

### `kyverno` — policy
Admission/background/cleanup/reports controllers. Runs **audit-only**
(`policy_profile: audit-only`); the one ClusterPolicy `pod-security-baseline`
excludes the namespaces that legitimately need elevated pods (media, tailscale,
embedded-lab, longhorn-system, observability, metallb-system).

### `metallb-system` — bare-metal LoadBalancer
controller + speaker DaemonSet, L2 mode, pool `10.168.0.240-250`. Backs the
`ingress-nginx` Service VIP (`.240`) and Grafana (`.241`).

### `ingress-nginx` — ingress controller
The single IngressClass `nginx` (Traefik was removed). Everything HTTP enters
here — from the CF tunnel (public) or the MetalLB VIP (tailnet).

### `longhorn-system` — replicated storage
Longhorn (manager, CSI plugin/attacher/provisioner/resizer/snapshotter, UI,
engine-image DaemonSet). Available for RWO volumes that must survive a node, but
the media/embedded workloads deliberately use **local-path** (node-local,
re-downloadable data) instead.

### `minio` — S3 backup target
A single MinIO (hostPath NVMe on k3s-w-1, deliberately off-Longhorn so backups
don't depend on the thing they protect) with two buckets:
- `longhorn-backups` — Longhorn's `BackupTarget/default`.
- `music-backups` — restic repository for the music-studio workspace on
  Mateo's Mac (scoped user, tailnet-private `s3.mateosegura.com`).
Network-isolated — only `longhorn-system` and `ingress-nginx` may reach
`:9000`. See `apps/minio/README.md`.

### `observability` — metrics/logs/traces
kube-prometheus-stack (prometheus-server, kube-state-metrics, node-exporter
DaemonSet) + Grafana + Loki (StatefulSet) + Tempo (StatefulSet) + Alloy
(gateway + logs DaemonSet). Grafana at `grafana.mateosegura.com`.

## Platform — edge

### `cloudflare-tunnel` — public ingress
`cloudflared` (2 replicas), a **dashboard-managed** tunnel (`eden-home`,
token-only in-cluster) with a single catch-all rule → `ingress-nginx:80`. The
only path from the public internet into the cluster. Hostnames + Cloudflare
Access apps are configured in the Zero Trust dashboard, not git.

### `tailscale` — tailnet exposure
The Tailscale k8s operator + one `ts-*` proxy StatefulSet **per** env Service
that opts in (`loadBalancerClass: tailscale`). Gives each Zephyr devbox its own
MagicDNS name (`zephyr-<env>`). Needs the imperative `operator-oauth` Secret.

## Platform — CI

### `arc-systems` / `arc-runners` — self-hosted GitHub Actions
Actions Runner Controller (`arc-systems`: the controller) drives an org-wide
runner scale set (`arc-runners`: `arc-org`, dind, minRunners 0 / maxRunners 4)
that serves Eden, infrastructure, and workspaces (`runs-on: arc-org`).
Authenticates as the **gophersys-arc** GitHub App (`arc-github-app` Secret).

## Apps

### `media` — self-hosted media/portal stack (project `music`)
- **qbittorrent** — torrent client behind a **gluetun** ProtonVPN kill-switch
  (shared netns; all torrent egress via `tun0`). An initContainer enforces the
  download-critical config (`apps/music/qbittorrent/config-enforce/`).
  `torrent.mateosegura.com`.
- **prowlarr** — indexer manager / search (`prowlarr.`). Setup runbook:
  `apps/music/prowlarr/SETUP.md`.
- **flaresolverr** — headless-Chrome proxy that solves Cloudflare challenges for
  CF-protected indexers; Prowlarr drives it via an indexer-proxy tag (ClusterIP,
  no ingress).
- **filebrowser** — web file access to `/mnt/media` + downloads (`files.`).
- **homepage** — the single-pane portal (`home.`), live widgets over qBit /
  Prowlarr / disk. The one public app besides workspaces.

### `embedded-lab` — Zephyr dev environments (project `embedded`)
One `zephyr-devbox-<env>` Deployment per ephemeral env (currently
`nucleo-bringup`, `zephyr-libs`), pinned to `k3s-w-4` with USB microcontrollers
QEMU-passed in. Privileged + hostPath `/dev` for flashing (why the ns is
Kyverno-excluded). Envs are kustomize overlays under `apps/embedded/envs/*`,
generated by the `zephyr-envs` ApplicationSet (prune=true → dir deletion tears
an env down).

### `workspaces-prod` — the workspace manager (project `workspaces`)
`workspaces-api` — Go + Svelte app at `workspaces.mateosegura.com` (public,
Access-gated). Read-only view of the `embedded-lab` envs plus create/destroy
that opens GitOps PRs — authenticated as the **gophersys-arc** GitHub App via the
optional `workspaces-github-app` Secret (absent → read-only, 503).

### `eden` — the Eden platform (project `apps`)
The Eden agentic-engineering stack (`apps/eden/`: backing services + RBAC + seed
+ ingress) at `eden.mateosegura.com`, a separate workstream. Owned by the Eden
build; noted here for completeness — see `apps/eden/README.md`.

---

## Node roles (see each `clusters/instances/homelab/nodes/<n>/identity.yaml`)
- **cp-0/1/2 + w-0** — control-plane + platform (`devops`).
- **w-1** — media node (NVMe `/mnt/media`, GPU labels); runs the `media` stack.
- **w-4** — embedded/USB node (`usb-embedded: true`); runs `embedded-lab`.
- **w-2/3** — general `apps`.

Host-level bootstrap that isn't reconciled lives in
`clusters/instances/homelab/{nodes/k3s-w-4,hypervisors/pve-01}/bootstrap/`.
