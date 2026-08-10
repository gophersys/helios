# Infrastructure Debt Register

A living record of state that exists in the running cluster / on hosts / in
PVCs but is **not yet fully captured declaratively in this repo**, plus the
engineering agreement we hold new work to. The goal is zero invisible state:
anything load-bearing must be reproducible from git, or explicitly recorded
here as accepted-imperative with recreation steps.

Status legend: 🔴 open (reliability/security risk) · 🟠 open (reproducibility) ·
🟡 minor / accepted · ✅ resolved (captured declaratively).

Last updated: 2026-08-09 (cloud-cluster reconciliation — see docs/cloud-cluster.md).

---

## Working agreement (applies to all new changes)

1. **Declarative or it didn't happen.** No imperative cluster/PVC/host mutation
   without capturing it in git (manifest, initContainer, Ansible, or a
   documented runbook referenced here).
2. **Tests first.** Real code follows red → green → refactor. Config/scripts
   ship with a validation test.
3. **Reviewed.** Every change on a branch → PR → self-review of the diff (or a
   reviewer agent) → merge. Nothing straight to `main`.
4. **Clean as we go.** Each task ends with worktrees removed, scratchpad tidy,
   and this register updated.
5. **One thing at a time, done fully.**

---

## Ledger

### D1 ✅ qBittorrent runtime config lives only on the PVC — RESOLVED (PR #29)
The fix that made downloads work — binding qBittorrent to the VPN interface —
plus the in-cluster auth bypass and search-plugin state were all set via the
WebUI API and persist only in `qbittorrent-config` PVC
(`/config/qBittorrent/qBittorrent.conf`). If that PVC is recreated, downloads
silently break again (traffic leaks to `eth0`, Gluetun's kill-switch drops it).

Keys that must be enforced:
```
Session\Interface=tun0
Session\InterfaceName=tun0
WebUI\AuthSubnetWhitelist=10.42.0.0/16
WebUI\AuthSubnetWhitelistEnabled=true
WebUI\LocalHostAuth=false
```
**Resolved (PR #29):** `apps/music/qbittorrent/config-enforce/` — a tested
(9 unit tests), idempotent, surgical initContainer enforces these keys into
`qBittorrent.conf` before qBittorrent starts, drift-guarded against the deployed
ConfigMap. Verified a no-op against the live config; downloads re-verified.

### D2 ✅ Prowlarr download client — RESOLVED (PR #40 + categories fix)
Prowlarr's config lives in its PVC SQLite DB (UI-managed, not GitOps-able).
**Resolved-as-runbook:** `apps/music/prowlarr/SETUP.md` — the reproducible
source of truth for indexers + the qBittorrent download client, with exact
values. Headless API automation was attempted and rejected as fragile: Prowlarr
2.4.0's download-client test NREs against qBittorrent 5.2.2, and indexer-add
hangs on a synchronous site-test (`?forceSave=true` skips neither). Both work in
the Web UI. **Remaining (honest):** full search→grab automation needs the
download client wired via the UI, or qBittorrent pinned to a Prowlarr-compatible
version (remediation in SETUP.md). Search itself works once indexers are added.

The download-client NRE ("Object reference not set") was **not** a qBit-5.2
incompatibility — it was a missing top-level `categories: []` in the POST body,
which null-crashed Prowlarr's `ValidateCategories`. Adding it registers the
qBittorrent client cleanly (HTTP 201, test passes). Prowlarr is pinned to
`nightly-2.5.1.5460-ls4` (PR #40); the fix works on any version, but the DB was
migrated by 2.5.1 so we stay there rather than risk a downgrade. Exact working
payload in `apps/music/prowlarr/SETUP.md`. Indexers still added via the UI
(PVC-resident); search→grab now works end-to-end once indexers exist.

**FlareSolverr proxy** (for CF-protected indexers) is also PVC-resident config — the
`flaresolverr` indexer-proxy + per-indexer tags live only in the Prowlarr SQLite;
recreation is in `apps/music/prowlarr/SETUP.md` (§1b).

**Backup gap — RESOLVED 2026-07-09 (PRs #88 + follow-up):** Prowlarr's config PV
was migrated k3s-w-0 → k3s-w-1 (backup-first: pre-migration tar taken, ApiKey
verified identical after restore) and the deployment hostname-pinned there. All
three media configs now live on k3s-w-1 and `prowlarr-config` is a **required**
archive in the nightly config-backup — a future miss fails the Job loudly.

### D3 ✅ Host-level changes made over SSH, not in IaC — RESOLVED (PR #30)
None of these are in Ansible or any tracked config:
- **pve-01** (Proxmox / ThinkPad P1): lid-suspend disabled
  (`/etc/systemd/logind.conf.d/99-hypervisor-no-sleep.conf` + masked
  `sleep.target suspend.target hibernate.target hybrid-sleep.target`).
- **pve-01**: USB passthrough on VM 925 (`qm set 925 -usb0..5 host=3-1.x`) +
  `net.ipv4.ip_forward` for the Tailscale subnet router
  (`advertise-routes=10.168.0.0/24`).
- **k3s-w-4**: `linux-generic` meta + `linux-modules-extra-$(uname -r)`
  (the stock cloud kernel lacks `cp210x`/`cdc_acm`), `qemu-guest-agent`, and
  the `/etc/udev/rules.d/99-mcu-slots.rules` stable-slot symlinks.
**Resolved (PR #30):** idempotent, shellcheck-clean bootstrap scripts —
`clusters/instances/homelab/nodes/k3s-w-4/bootstrap/` (kernel modules, guest
agent, udev slot rules) and `clusters/instances/homelab/hypervisors/pve-01/`
(no-suspend, ip-forward). File-based config is auto-applied; live device/tailnet
ops (USB passthrough, subnet-router advertise) are documented in each README.

### D4 ✅ Secrets created imperatively — DOCUMENTED (PR #32)
**Resolved-as-doc:** `docs/runtime-secrets.md` is the **live inventory** of every
imperative k8s Secret — spanning `media`, `workspaces-prod`, `arc-runners`,
`minio`, `longhorn-system`, and `cloudflare-tunnel` — each with its Vaultwarden
source and exact recreation command, and explains why single-value logins stay
imperative (the ESO store returns an item's `notes` blob, not individual fields).
Consult that file for the current set rather than an inline list here (which drifts).

### D5 ✅ Default / unset credentials — RESOLVED (PR #32, #36-#38)
- **qBittorrent** — ✅ strong password (`shared/qbittorrent/webui`), set via API,
  verified (WebUI hash changed, `admin`/`admin` default gone). In-cluster is
  subnet-bypassed; the password is for external/UI login only.
- **Filebrowser** — ✅ strong password (`shared/filebrowser/admin`), set by a
  `bootstrap-admin` initContainer that runs before the server (no BoltDB-lock
  fight) and re-applies it every boot. **Login verified (HTTP 200).** Root cause
  of the earlier saga: the `:v2` tag became the "quantum" rewrite (v2.63) that
  broke `/api/login` auth — pinned to classic **v2.31.2** (PR #36-#38).

### D6 ✅ Workspaces create/destroy — RESOLVED (gophersys/workspaces#1 + PR #33)
Implemented with full TDD (34 tests: interface fakes + an httptest GitHub mock).
`POST`/`DELETE /api/workspaces` open a PR against this repo that adds/removes
`apps/embedded/envs/<name>/` (the `zephyr-envs` ApplicationSet deploys/prunes on
merge). Name validation is path-traversal-safe; the manager is token-gated (no
token → read-only, 503). Live wiring: the `workspaces-github` bot-PAT Secret
(optional, `docs/runtime-secrets.md`) — creating the PAT is a one-time GitHub-UI
step, the only part not automatable headlessly. VERIFIED: the new binary is live (logs `gitops env management disabled … 503` — correctly token-gated).

### D7 ✅ Documentation drift — RESOLVED (PR #34)
`docs/cluster-topology.md` is the authoritative namespace-by-namespace reference
(platform / edge / apps, the exposure model, node roles), reconciled against the
live 14-namespace cluster.

### D8 ✅ Missing referenced doc — RESOLVED (PR #34)
`docs/migration-homelab-to-idp.md` restored as a historical record (migration
complete) with the 9 ratified decisions, so the references from identity.yaml
and the READMEs no longer dangle.

---

### D9 🟠 Version drift on imperative platform components — OPEN (reproducibility)
All the 2026-07 audit versions were upgraded (undisrupted), but **four are still
installed by raw `kubectl apply` of upstream manifests, unmanaged by Argo** — so the
running versions live only in prose, not reproducibly in git. Versions are current;
the open gap is DR/reproducibility. **cloudflared is now reconciled into git** (PR
#81, manual-sync). Pin table (canonical upstream manifest for the pinned version):

| Component | Version | In git/Argo? | Reinstall |
|---|---|---|---|
| cloudflared | 2026.6.1 | ✅ git (manual-sync) | `platform/core/edge/tunnel/cloudflare-tunnel/` |
| cert-manager | v1.20.3 | ❌ raw manifest | `.../cert-manager/releases/download/v1.20.3/cert-manager.yaml` |
| ingress-nginx | v1.15.1 | ❌ raw manifest | `ingress-nginx` tag `controller-v1.15.1`, `deploy/static/provider/cloud` (MetalLB-backed LB) |
| MetalLB | v0.16.1 | ❌ raw manifest | `metallb` v0.16.1 `config/manifests/metallb-native.yaml` |
| Longhorn | v1.12.0 | ❌ raw manifest | staged — `docs/runbooks/longhorn-upgrade.md` (client-side CRDs) |

Upgrade notes: cert-manager ships the DNS-01 cleanup fix (D10); MetalLB VIP stayed
up; ingress-nginx all 7 routes stayed up; Longhorn cleared EOL via a staged 5-minor
upgrade, zero data loss (in-cluster MinIO backup target, `apps/minio/`). **Follow-up:**
vendor the four raw-manifest components into Argo Applications like cloudflared, or
formally accept-imperative via this pin table.
- ⬜ **Tempo** 2.9→3.0 + observability minors live in the **eden-observability Helm
  chart** (`obs` release, **failed** helm state) — the Eden agent's domain, not this.

### D10 ✅ cert-manager DNS-01 cleanup — RESOLVED
The 5 orphaned `_acme-challenge` TXT records were deleted from Cloudflare, and the
cleanup fix ships with the cert-manager 1.20.3 upgrade (D9). Watch the next renewal
to confirm no new orphans.

### D11 🟡 bw-serve cannot run non-root (image limitation)
The vault bridge is hardened to caps-drop + seccomp, but the
`charlesthomas/bitwarden-cli` image's entrypoint crashloops under
non-root/read-only-rootfs (verified). Full hardening needs a vendored non-root
bitwarden-cli image. Accepted ceiling for now.

### D12 🟡 MinIO backup target runs root (deferred non-root)
`apps/minio/` drops ALL caps + seccomp but keeps root + a writable rootfs — it writes
the hostPath NVMe as root. Full non-root/RO-rootfs needs a pre-chown of
`/mnt/media/minio` + a writable `/tmp`; deferred. Accepted for a homelab backup sink
that is network-isolated to `longhorn-system` (NetworkPolicy in `apps/minio/`).

### D13 🟡 arc-runners egress is unrestricted (ingress now default-denied)
The privileged dind CI runners can dial anything (cluster pod network + internet).
Ingress default-deny landed (`platform/services/ci/arc-runners/`), but a default-deny
EGRESS needs a curated allowlist (GitHub, ghcr, package registries, Go proxy, apt,
k3d pulls, DNS) to avoid breaking builds — deferred until someone wants to enumerate
it. Related non-repo guardrails (GitHub runner group scoping, dedicated build node
taint) also remain open.

### D14 ✅ Vaultwarden automated backup — RESOLVED (2026-08-09)
A nightly CronJob (`clusters/instances/prod/manifests/vault-backup/`) dumps the
`vaultwarden` database plus `/data` (rsa_key.pem, attachments, sends), encrypts
with a public key the cluster cannot decrypt, and uploads via a write-only OCI
pre-authenticated request to `eden-backups/vault/`. 30-day lifecycle retention.
**Verified end-to-end**: a produced backup was downloaded, decrypted with the
offline private key and restored into a scratch database matching live exactly
(`live_ciphers=96 users=1 folders=5 attachments=12`, zero errors).
Private key held in two failure domains: `shared/backup/vault-backup-private-key`
in the vault, and offline beside the encrypted recovery bundle.
**Residual (tracked as D16):** single-cloud, and no alerting on failure.

### D16 🟠 Backups are single-cloud and unmonitored — OPEN
D14's backups land in OCI Object Storage: a different service and durability
domain from the block volume, so they survive instance and disk loss, but **not
the loss of the Oracle account**. Wanted: an off-Oracle pull leg (homelab or
workstation fetching from `eden-backups/vault/` on a schedule). Separately, a
CronJob that silently stops failing looks identical to one that works — nothing
alerts today. The PAR also expires **2027-08-10**; renewal is currently a
calendar event, not an automated one.

### D15 🟠 `code-kit-server` node name is stale and cannot be renamed in place
The OCI instance, boot volume and OS hostname are all `server-00`; only the k3s
node registration still reads `code-kit-server`. k3s derives its **etcd** member
identity from the node name, so on this single-member cluster a rename can leave
etcd refusing to start against a member list it no longer recognises. `agent-00`
was renamed successfully on 2026-08-09 precisely because an agent carries no such
coupling. **Wanted:** add a second server node, let etcd form a real quorum, then
roll the original — worth doing for HA regardless. Do NOT rename in place.

### D17 ✅ Public exposure was undeclared and undetected — RESOLVED (2026-08-09)
`grafana.mateosegura.com` was reachable from the internet behind only Grafana's
own login — admin password generated-not-vaulted — while `cluster-topology.md`
claimed it was tailnet-private. `notes` and `obsv` were public behind CouchDB
basic auth and a Grafana login. Nothing detected any of it.
**Resolved:** `contracts/exposure.yaml` declares every hostname's class with a
reason; `scripts/verify-exposure.sh` (verb: `ctl.sh verify-exposure`, wired into
CI) asserts reality matches and fails the build on drift. grafana moved to
tailnet; notes and obsv put behind the existing oauth2-proxy. Every public
ingress now carries a real cert with `ssl-redirect: "false"` so the tunnel keeps
working. Verified 13/13.

### D18 🟠 The prod cluster is not GitOps-reconciled — OPEN
Argo drives the homelab only, so everything on the prod cluster (vault-backup
CronJob, oauth2-proxy gating, the `obs` Helm release) is applied by hand. The
manifests are in git under `clusters/instances/prod/manifests/` and documented,
but nothing reconciles or detects drift there. Related: the homelab `obs` Helm
release has been in `failed` state at revision 8 since 2026-06-18 and is not
managed by Argo either — the grafana ingress change was applied with `kubectl`
and will be reverted by the next `helm upgrade` unless it uses the updated
`values-homelab.yaml`.

### D19 🟡 `shared/cloudflare/api-token` stores the wrong zone id — OPEN
The `CLOUDFLARE_ZONE_ID` line in that vault item is the zone for **code-kit.dev**,
not `mateosegura.com`. Anything trusting it edits DNS in the wrong zone. Tooling
should resolve the zone by name until the item is corrected. The token itself is
valid (expires 2027-06-17) and can see three zones: `claude-kit.dev`,
`code-kit.dev`, `mateosegura.com`.


### D20 🟡 Cloudflare Access apps are not API-manageable — OPEN
The API token can read DNS and the tunnel config, so publishing a service is fully
programmatic (`scripts/cf-expose.py`). It cannot read Access apps — account scope
returns empty, zone scope fails — so it lacks *Access: Apps and Policies*. Adding
`public-access` to a NEW hostname still needs one dashboard visit. Fix: add
`Account · Access: Apps and Policies · Edit` to the token (expires 2027-06-17).
Existing public-access hosts are unaffected.


### D21 🟡 No admission policy engine — ACCEPTED (2026-08-09)
Kyverno was removed. It ran `audit-only` from installation with one
`pod-security-baseline` ClusterPolicy excluding eight namespaces, so it enforced
nothing, cost four controller pods, and sat permanently OutOfSync in Argo on four
CRDs. Accepted rather than fixed: with one operator and everything reconciled
from git, code review is the guardrail, and an unfinished policy engine is worse
than none because it implies enforcement that is not happening. Revisit when more
than one person deploys here — and only with two policies you would genuinely
enforce, not audit. Pod hardening is still applied per workload in manifests.


### D22 🟠 Machine inventory has four gaps — OPEN
Full inventory in `docs/machine-inventory.md` (2026-08-09). Undeclared:
(1) `mateos-macbook-air` — `machines/development/` is empty, so the workstation
holding every kubeconfig, the vault CLI and the OCI CLI has no identity file;
(2) hypervisors `pve-00` and `pve-03` — only `pve-01` is declared, yet all three
host the 8 k3s VMs. Unverified: (3) `arm-builder`, `macos-ci-runner`,
`windows-ci-runner` are declared but absent from the tailnet — arm-builder's
stated consumers were codectl and fintel, and codectl no longer exists. Stale:
(4) `sentinel-00`/`sentinel-01` (instances terminated) and two laptops offline
153 days still hold tailnet identities; every tailnet device is a potential
ingress.

### D23 🟠 Backups have no alerting — OPEN (noted, deferred by decision)
The nightly vault backup CronJob works and is restore-tested, but a job that
silently stops looks identical to one that works. Nothing would tell you. Also
still single-cloud: backups survive disk and instance loss, not loss of the
Oracle account. Deferred deliberately 2026-08-09; recorded so it is not
rediscovered as a surprise.

### D24 🟡 The CI pull secret is a god-mode token — OPEN
`arc-runners/ghcr-pull` materializes `shared/github/pat-godmode` into a
`dockerconfigjson` so the kubelet can pull the private `.devcontainer` runner
images. That token carries `admin:enterprise`, `admin:org`, `delete_repo` and
`write:packages`; a pull credential needs `read:packages` alone.

Chosen deliberately on 2026-08-10 because GitHub has no API to mint a PAT, so a
narrower token cannot be created without a human at the browser. Two things
lower the severity: `imagePullSecrets` are consumed by the kubelet and never
mounted into the container, and the runner ServiceAccount
(`*-gha-rs-no-permission`) has no RBAC, so a job cannot `get` the Secret.

Remedy: create a classic PAT with **only** `read:packages`, store it as
`shared/github/ghcr-pull`, and repoint the ExternalSecret's `remoteRef.key`.
One line, no other change.


### D25 ✅ Argo's repo credential was hand-applied and per-repo — RESOLVED (2026-08-10)
`repo-infrastructure` was a `kubectl apply`-ed Secret holding a classic PAT, with
no record in git and no source of truth outside the cluster. Every new private
repo would have needed another one by hand.

Replaced with an org-wide `repo-creds` ExternalSecret at
`platform/services/gitops/repo-credentials/`. Argo matches `repo-creds` by URL
prefix, so one entry now covers every repository under `github.com/gophersys` —
adding `gophersys/home`, or the next repo, needs no cluster change at all.

The token was not regenerated: the existing one was moved into the vault as
`shared/github/argocd-repo`, so the value finally has a home outside the cluster.
Retire `repo-infrastructure` once the org-wide entry has proven itself.


## Resolved

Resolved items stay in the ledger above, marked ✅ with the PR that captured
them. So far: **D1** (#29), **D3** (#30), **D4** (#32), **D5** (#32), **D6** (#33 + workspaces#1), **D7** (#34), **D8** (#34); **D2** (#40); **D5** (#32, #36-#38, login verified).
