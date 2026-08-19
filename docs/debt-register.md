# Infrastructure Debt Register

A current record of state that exists in the running cluster, on the hosts or in
the PVCs, but that this repo does **not yet capture fully in a declarative form**.
It also holds the engineering agreement that all new work must follow. The goal
is that no state is hidden: anything load-bearing must be reproducible from git,
or recorded here as accepted-imperative with the steps to recreate it.

Status legend: 🔴 open (reliability or security risk) · 🟠 open (reproducibility) ·
🟡 minor or accepted · ✅ resolved (captured declaratively) · ➡️ merged into
another entry, and kept so that its number never dangles.

**Every `### D<n>` heading carries exactly one of those markers.** A heading
without one is invisible to the scan that finds the high items. D40 through D44
carried none until 2026-08-12, and D40 says "the bump must not merge until this
is understood" — so the entry that most needed the scan was the one it could not
see. D40 is marked 🔴 from that sentence; change it if you read it differently.

For the date of the last change to this file, ask git rather than a line here:

```
git log -1 --format='%ad %s' --date=short -- docs/debt-register.md
```

A hand-written date goes stale on the next commit that forgets it. The one that
stood here still described D39 while the newest entry was D44.

---

## Working agreement (applies to all new changes)

1. **Capture every change in git.** Do not mutate a cluster, a PVC or a host
   imperatively without a record in git (a manifest, an initContainer, Ansible,
   or a runbook referenced here).
2. **Tests first.** Real code follows red → green → refactor. Configuration and
   scripts ship with a validation test.
3. **Reviewed.** Every change goes on a branch, then a PR, then a self-review of
   the diff (or a review by an agent), then a merge. Nothing goes straight to
   `main`.
4. **Clean as you go.** Each task ends with the worktrees removed, the scratchpad
   tidy, and this register updated.
5. **One thing at a time, done fully.**

---

## Ledger

### D1 ✅ qBittorrent runtime config lives only on the PVC — RESOLVED (PR #29)
The change that made downloads work — a bind of qBittorrent to the VPN interface
— plus the in-cluster auth bypass and the search-plugin state were all set
through the WebUI API. They persist only in the `qbittorrent-config` PVC
(`/config/qBittorrent/qBittorrent.conf`). If that PVC is recreated, downloads
stop again with no message: the traffic goes to `eth0`, and the kill-switch of
Gluetun drops it.

The keys that must be enforced:
```
Session\Interface=tun0
Session\InterfaceName=tun0
WebUI\AuthSubnetWhitelist=10.42.0.0/16
WebUI\AuthSubnetWhitelistEnabled=true
WebUI\LocalHostAuth=false
```
**Resolved (PR #29):** `apps/music/qbittorrent/config-enforce/` holds a tested
initContainer (9 unit tests). It is idempotent and precise. It writes these keys
into `qBittorrent.conf` before qBittorrent starts, and it is drift-guarded
against the deployed ConfigMap. It was verified as a no-op against the live
config, and the downloads were verified again.

### D2 ✅ Prowlarr download client — RESOLVED (PR #40 + categories fix)
Prowlarr's configuration lives in the SQLite database on its PVC. The UI manages
that database, so GitOps cannot. **Resolved as a runbook:**
`apps/music/prowlarr/SETUP.md` is the reproducible source of truth for the
indexers and for the qBittorrent download client, with the exact values. Headless
API automation was tried and rejected as unreliable: the download-client test of
Prowlarr 2.4.0 throws an NRE against qBittorrent 5.2.2, and an indexer-add call
stops on a synchronous site test (`?forceSave=true` skips neither). Both actions
work in the Web UI. **What remains:** full search-to-grab automation needs the
download client wired through the UI, or qBittorrent pinned to a version that
Prowlarr supports (the remediation is in SETUP.md). Search itself works once you
add the indexers.

The download-client NRE ("Object reference not set") was **not** an
incompatibility with qBittorrent 5.2. The POST body was missing the top-level
`categories: []`, and that null crashed Prowlarr's `ValidateCategories`. Add it
and the qBittorrent client registers correctly (HTTP 201, the test passes).
Prowlarr is pinned to `nightly-2.5.1.5460-ls4` (PR #40). The fix works on any
version, but 2.5.1 migrated the database, so we stay on 2.5.1 rather than risk a
downgrade. The exact working payload is in `apps/music/prowlarr/SETUP.md`. The
indexers are still added through the UI and live on the PVC. Search-to-grab now
works end to end once the indexers exist.

**FlareSolverr proxy** (for indexers behind Cloudflare) is also configuration on
the PVC. The `flaresolverr` indexer-proxy and the per-indexer tags live only in
the Prowlarr SQLite database. The steps to recreate them are in
`apps/music/prowlarr/SETUP.md` (§1b).

**Backup gap — RESOLVED 2026-07-09 (PRs #88 + follow-up):** the config PV of
Prowlarr was migrated from k3s-w-0 to k3s-w-1. The backup came first: a tar was
taken before the migration, and the ApiKey was verified as identical after the
restore. The deployment is now pinned to that hostname. All 3 media configs now
live on k3s-w-1, and `prowlarr-config` is a **required** archive in the nightly
config-backup, so a future omission fails the Job with a clear error.

### D3 ✅ Host-level changes made over SSH, not in IaC — RESOLVED (PR #30)
None of these were in Ansible or in any tracked configuration:
- **pve-01** (Proxmox / ThinkPad P1): lid-suspend disabled
  (`/etc/systemd/logind.conf.d/99-hypervisor-no-sleep.conf` + masked
  `sleep.target suspend.target hibernate.target hybrid-sleep.target`).
- **pve-01**: USB passthrough on VM 925 (`qm set 925 -usb0..5 host=3-1.x`) +
  `net.ipv4.ip_forward` for the Tailscale subnet router
  (`advertise-routes=10.168.0.0/24`).
- **k3s-w-4**: the `linux-generic` meta package and
  `linux-modules-extra-$(uname -r)` (the standard cloud kernel has no `cp210x` or
  `cdc_acm`), `qemu-guest-agent`, and the stable-slot symlinks in
  `/etc/udev/rules.d/99-mcu-slots.rules`.

**Resolved (PR #30):** idempotent bootstrap scripts that pass shellcheck —
`clusters/instances/homelab/nodes/k3s-w-4/bootstrap/` (kernel modules, guest
agent, udev slot rules) and `clusters/instances/homelab/hypervisors/pve-01/`
(no-suspend, ip-forward). File-based configuration is applied automatically. The
live device and tailnet operations (USB passthrough, subnet-router advertise) are
documented in each README.

### D4 ✅ Secrets created imperatively — DOCUMENTED (PR #32)
**Resolved as a document:** `docs/runtime-secrets.md` is the **live inventory** of
every imperative k8s Secret. It covers `media`, `arc-runners`, `minio` and
`cloudflare-tunnel`. (`workspaces-prod` and `longhorn-system` were in that list
until 2026-08-19; both namespaces were removed and their Secrets went with
them.) Each entry names its
Vaultwarden source and the exact command to recreate it, and the document
explains why single-value logins stay imperative: the ESO store returns the
`notes` blob of an item, not the individual fields. Read that file for the
current set. An inline list here would drift.

### D5 ✅ Default or unset credentials — RESOLVED (PR #32, #36-#38)
- **qBittorrent** — ✅ strong password (`shared/qbittorrent/webui`), set through
  the API and verified (the WebUI hash changed, and the `admin`/`admin` default
  is gone). In-cluster access uses the subnet bypass. The password is for
  external and UI login only.
- **Filebrowser** — ✅ strong password (`shared/filebrowser/admin`), set by a
  `bootstrap-admin` initContainer that runs before the server, so it does not
  compete for the BoltDB lock. It applies the password again at every boot.
  **Login verified (HTTP 200).** The cause of the earlier problem: the `:v2` tag
  became the "quantum" rewrite (v2.63), which broke `/api/login` authentication.
  The image is pinned to the classic **v2.31.2** (PR #36-#38).

### D6 ✅ Workspaces create/destroy — RESOLVED (gophersys/workspaces#1 + PR #33)
Implemented with full TDD (34 tests: interface fakes and an httptest GitHub
mock). `POST` and `DELETE /api/workspaces` open a PR against this repo that adds
or removes `apps/embedded/envs/<name>/`. The `zephyr-envs` ApplicationSet deploys
or prunes on merge. Name validation is safe against path traversal. The manager
is gated by a token: with no token it is read-only and returns 503. Live wiring:
the `workspaces-github` bot-PAT Secret (optional, `docs/runtime-secrets.md`).
Creating the PAT is a one-time step in the GitHub UI, and it is the only part
that no headless process can do. VERIFIED: the new binary is live (it logs
`gitops env management disabled … 503`, so the token gate works).

**Closed by removal, 2026-08-19.** The text above is HISTORY, kept because the
mechanism was real and the number must not dangle. What happened since:
- **2026-08-18** — Mateo retired the devboxes and the whole `embedded-lab` stack,
  so the surface this mechanism managed stopped existing.
- **2026-08-19** — Mateo's decision: remove the app rather than repurpose it. By
  then it was 403-looping and 0/1 Ready. `apps/workspaces/`, both registry
  Applications, the `workspaces` AppProject, the `workspaces-prod` destination on
  the platform AppProject, the `workspaces` entry in the homelab
  `projects_hosted:`, the portal tile and the `contracts/exposure.yaml`
  declaration are all deleted.

Nothing in this repo deploys `workspaces-api` anymore. The `gophersys/workspaces`
SOURCE repository is untouched and still builds on `arc-org`; so is the
`ghcr.io/gophersys/workspaces-api` package and the weekly
`.github/workflows/ghcr-retention.yml` that prunes it. Retiring those is a
separate, deliberate decision.

### D7 ✅ Documentation drift — RESOLVED (PR #34)
`docs/cluster-topology.md` is the authoritative reference, namespace by namespace
(platform, edge, apps, the exposure model, the node roles). It is reconciled
against the live 14-namespace cluster.

### D8 ✅ Missing referenced doc — RESOLVED (PR #34)
`docs/migration-homelab-to-idp.md` is restored as a historical record (the
migration is complete) with the 9 ratified decisions. The references from
identity.yaml and from the READMEs now resolve.

---

### D9 🟠 Version drift on imperative platform components — OPEN (reproducibility)
Every version from the 2026-07 audit was upgraded without an outage, but **3
components are still installed by a raw `kubectl apply` of the upstream
manifests, and Argo does not manage them**. The running versions therefore exist
only in prose, not reproducibly in git. The versions are current. The open gap is
disaster recovery and reproducibility. **cloudflared is now reconciled into git**
(PR #81, manual-sync). The pin table below names the canonical upstream manifest
for each pinned version:

| Component | Version | In git/Argo? | Reinstall |
|---|---|---|---|
| cloudflared | 2026.6.1 | ✅ git (manual-sync) | `platform/core/edge/tunnel/cloudflare-tunnel/` |
| cert-manager | v1.20.3 | ❌ raw manifest | `.../cert-manager/releases/download/v1.20.3/cert-manager.yaml` |
| ingress-nginx | v1.15.1 | ❌ raw manifest | `ingress-nginx` tag `controller-v1.15.1`, `deploy/static/provider/cloud` (MetalLB-backed LB) |
| MetalLB | v0.16.1 | ❌ raw manifest | `metallb` v0.16.1 `config/manifests/metallb-native.yaml` |
| ~~Longhorn~~ | ~~v1.12.0~~ | **REMOVED 2026-08-19** | not reinstalled — see below |

**Longhorn left this table by removal, not by resolution (2026-08-19).** It was
the 4th raw-manifest component and the most privileged one. It held 0 volumes:
its only consumer, the `observability` stack, was itself removed on 2026-08-09.
Mateo's decision was to delete it rather than carry 8 untracked controllers
against a future need. `local-path` is now the only StorageClass on the cluster.
`docs/runbooks/longhorn-upgrade.md` was deleted with it — a runbook for a
component that does not exist is a trap, and git history keeps the text. See
`platform/core/storage/README.md` for the removal rationale and what replaces it.

Upgrade notes: cert-manager ships the DNS-01 cleanup fix (D10); the MetalLB VIP
stayed up; all 7 ingress-nginx routes stayed up. **Follow-up:** move the 3
remaining raw-manifest components into Argo Applications, as done for
cloudflared, or accept them as imperative through this pin table.
- ⬜ **Tempo** 2.9→3.0 and the observability minor upgrades live in the
  **eden-observability Helm chart** (the `obs` release, in **failed** helm
  state). That is the Eden agent's domain, not this one.

### D10 ✅ cert-manager DNS-01 cleanup — RESOLVED
The 5 orphaned `_acme-challenge` TXT records were deleted from Cloudflare, and
the cleanup fix ships with the cert-manager 1.20.3 upgrade (D9). Watch the next
renewal to confirm that no new orphan records appear.

### D11 🟡 bw-serve cannot run non-root (image limitation)
The vault bridge is hardened with dropped capabilities and seccomp, but the
entrypoint of the `charlesthomas/bitwarden-cli` image crashloops under a non-root
user and a read-only root filesystem (verified). Full hardening needs a vendored
non-root bitwarden-cli image. Accepted as the current limit.

### D12 🟡 MinIO backup target runs as root (non-root deferred)
`apps/minio/` drops ALL capabilities and applies seccomp, but it keeps root and a
writable root filesystem. It writes the hostPath NVMe as root. Full non-root and
read-only-rootfs operation needs a chown of `/mnt/media/minio` first and a
writable `/tmp`. That work is deferred. It is accepted for a homelab backup sink
whose ingress is default-denied (the NetworkPolicy is in `apps/minio/`). Note
that the isolation narrowed on 2026-08-19: with Longhorn removed, the only live
allow-rule is `ingress-nginx` for the tailnet-private `s3.` host, and
`allow-longhorn-backups` now selects a namespace that does not exist.

### D13 🟡 arc-runners egress is unrestricted (ingress is now default-denied)
The privileged dind CI runners can reach anything: the cluster pod network and
the internet. Ingress default-deny is in place
(`platform/services/ci/arc-runners/`). A default-deny EGRESS needs a curated
allowlist (GitHub, ghcr, package registries, the Go proxy, apt, k3d pulls, DNS)
to avoid broken builds, and it is deferred until someone lists the entries.
Related controls outside this repo are also open: GitHub runner group scoping and
a dedicated taint on the build node.

### D14 ✅ Vaultwarden automated backup — RESOLVED (2026-08-09)
A nightly CronJob (`clusters/instances/prod/manifests/vault-backup/`) dumps the
`vaultwarden` database and `/data` (rsa_key.pem, attachments, sends). It encrypts
the result with a public key that the cluster cannot decrypt, and it uploads the
result through a write-only OCI pre-authenticated request to
`eden-backups/vault/`. Lifecycle retention is 30 days.
**Verified end to end**: a produced backup was downloaded, decrypted with the
offline private key, and restored into a scratch database that matched the live
database exactly (`live_ciphers=96 users=1 folders=5 attachments=12`, no errors).
The private key is held in 2 failure domains:
`shared/backup/vault-backup-private-key` in the vault, and offline beside the
encrypted recovery bundle.
**Residual risk (tracked as D16):** a single cloud, and no alert on failure.

### D16 🟠 Backups are single-cloud and unmonitored — OPEN (deferred by decision)
The backups from D14 land in OCI Object Storage. That is a different service and
a different durability domain from the block volume, so the backups survive the
loss of an instance and the loss of a disk. They do **not** survive the loss of
the Oracle account. Wanted: a pull leg outside Oracle (the homelab or the
workstation fetches from `eden-backups/vault/` on a schedule). Separately, a
CronJob that stops working does not look different from one that works, and
nothing raises an alert today. The PAR also expires **2027-08-10**, and the
renewal is currently a calendar event, not an automated action. The
`bw-serve-sync` CronJob (external-secrets, added for build ledger #89) sits in
the same gap: a failed sync is a Failed Job object and nothing more, so the
vault cache can go stale again with only `kubectl get jobs -n external-secrets`
to show it. Its wiring — though not its runtime health — is CI-guarded by
`scripts/verify-bw-sync-wiring.sh`.

**Deferred deliberately on 2026-08-09**, and recorded so that nobody finds it
again as a surprise. The restore itself is tested; see D14.

**D23 was merged in here on 2026-08-12.** It stated the same 2 facts — a single
cloud, and no alert on a CronJob that stops — and it held 1 fact this entry did
not: the deferral date above.

### D15 🟠 The node name `code-kit-server` is stale and cannot be renamed in place
The OCI instance, the boot volume and the OS hostname are all `server-00`. Only
the k3s node registration still reads `code-kit-server`. k3s derives its **etcd**
member identity from the node name, so on this single-member cluster a rename can
leave etcd unable to start against a member list it no longer recognises.
`agent-00` was renamed successfully on 2026-08-09 because an agent has no such
coupling. **Wanted:** add a second server node, let etcd form a real quorum, then
replace the original. That work is worth doing for HA in any case. Do NOT rename
in place.

### D17 ✅ Public exposure was undeclared and undetected — RESOLVED (2026-08-09)
`grafana.mateosegura.com` was reachable from the internet behind only Grafana's
own login, and its admin password was generated but never stored in the vault,
while `cluster-topology.md` stated that the host was tailnet-private. `notes` and
`obsv` were public behind CouchDB basic auth and a Grafana login. Nothing
detected any of this.
**Resolved:** `contracts/exposure.yaml` declares the class of every hostname with
a reason. `scripts/verify-exposure.sh` (verb: `ctl.sh verify-exposure`, wired
into CI) asserts that reality matches the declaration and fails the build on
drift. grafana moved to the tailnet; notes and obsv are now behind the existing
oauth2-proxy. Every public ingress now carries a real certificate with
`ssl-redirect: "false"`, so the tunnel keeps working. Verified 13 of 13.

### D18 🟠 The prod cluster is not GitOps-reconciled — OPEN
Argo drives the homelab only. Everything on the prod cluster is applied by hand:
the vault-backup CronJob, the oauth2-proxy gating, and the `obs` Helm release.
The manifests are in git under `clusters/instances/prod/manifests/` and are
documented, but nothing reconciles them and nothing detects drift there. Related:
the homelab `obs` Helm release has been in `failed` state at revision 8 since
2026-06-18, and Argo does not manage it either. The grafana ingress change was
applied with `kubectl`, and the next `helm upgrade` will revert it unless that
upgrade uses the updated `values-homelab.yaml`.

### D19 🟡 `shared/cloudflare/api-token` stores the wrong zone id — OPEN
The `CLOUDFLARE_ZONE_ID` line in that vault item holds the zone for
**code-kit.dev**, not `mateosegura.com`. Anything that trusts it edits DNS in the
wrong zone. Tooling should resolve the zone by name until the item is corrected.
The token itself is valid (it expires 2027-06-17) and can see 3 zones:
`claude-kit.dev`, `code-kit.dev` and `mateosegura.com`.


### D20 🟡 Cloudflare Access apps are not manageable through the API — OPEN
The API token can read DNS and the tunnel configuration, so publication of a
service is fully programmatic (`scripts/cf-expose.py`). The token cannot read
Access apps: account scope returns empty and zone scope fails, so the token lacks
*Access: Apps and Policies*. To add `public-access` to a NEW hostname you must
still open the dashboard once. Fix: add
`Account · Access: Apps and Policies · Edit` to the token (it expires
2027-06-17). Existing public-access hosts are not affected.


### D21 ✅ No admission policy engine — SUPERSEDED by D46 (2026-08-19)
Kyverno was removed. It ran `audit-only` from installation with a single
`pod-security-baseline` ClusterPolicy that excluded 8 namespaces. It therefore
enforced nothing, cost 4 controller pods, and stayed permanently OutOfSync in
Argo on 4 CRDs. This was accepted, not fixed: with 1 operator and everything
reconciled from git, code review was the control. An unfinished policy engine is
worse than no policy engine, because it suggests an enforcement that does not
happen.

**Closed 2026-08-19.** The review condition this entry set — "only with 2 policies
that you would genuinely enforce, not audit" — was met, and met without any
engine. `platform/core/policy/` holds 2 in-tree `ValidatingAdmissionPolicy`
objects that the apiserver evaluates itself: 0 pods, 0 CRDs, 0 OutOfSync lines.
The premise that needed correcting was the word "engine": this entry banned a
*controller*, and an admission *policy* is an API object with none of the cost
that justified the ban. Pod hardening is still applied per workload in the
manifests, still unenforced — that half moved to D46. Read D46.


### D22 🟠 The machine inventory has 4 gaps — OPEN
The full inventory is in `docs/machine-inventory.md` (2026-08-09). Undeclared:
(1) `mateos-macbook-air` — `machines/development/` is empty, so the workstation
that holds every kubeconfig, the vault CLI and the OCI CLI has no identity file;
(2) the hypervisors `pve-00` and `pve-03` — only `pve-01` is declared, and all 3
hosts run the 8 k3s VMs. Unverified: (3) `windows-ci-runner` is declared but it
does not appear on the tailnet. `arm-builder` was terminated on 2026-08-10.
`macos-ci-runner` was measured on the machine on 2026-08-13, and it is reachable
by key on the LAN, but it is not on the tailnet yet.
Stale: (4) `sentinel-00` and `sentinel-01` (the instances are terminated) and 2
laptops offline for 153 days still hold tailnet identities. Every tailnet device
is a possible entry point.

**Added (2026-08-18) — gap (2) bit, and the fix it needed lives only on the
host.** While `apps/proxmox` was built, pve-00 was found unreachable from its own
LAN for every protocol: ping, ssh and `:8006` all timed out from the ingress-nginx
pod while ARP still answered, so the node looked present. Cause: pve-00 accepted
tailnet routes (`RouteAll: true`) and pve-01 advertises the same `10.168.0.0/24`,
so pve-00 installed `10.168.0.0/24 dev tailscale0` in table 52 and sent every
reply to a `10.168.0.x` host out over the tailnet with a tailnet source address.
The fix was imperative — `tailscale set --accept-routes=false` on pve-00 — and
verified: table 52 no longer carries the subnet, and a GET to
`https://10.168.0.201:8006/` from the ingress pod returns 200.

That fix is exactly the kind of state this register exists for. It is Tailscale
prefs on a host that has **no identity file**, so nothing in git describes it: a
re-provision of pve-00, or one `tailscale up --accept-routes`, silently restores
the black-hole, and the only symptom is that `proxmox.mateosegura.com` starts
timing out. Declaring pve-00 (gap 2) is what makes the pref reproducible.

**DECIDED and EXECUTED 2026-08-19 — the subnet is single-homed on pve-01.** The
open question was whether pve-00 should keep advertising `10.168.0.0/24` beside
pve-01 (failover) or stop (one path, no ambiguity). Mateo chose single-home.
Executed live on pve-00:

```
tailscale set --advertise-routes=          # empty list — advertise nothing
```

pve-00 is now a host-only tailnet node. **pve-01 is the sole subnet router for
`10.168.0.0/24`** (`clusters/instances/homelab/hypervisors/pve-01/`, which is the
one declared hypervisor and the one with the bootstrap script). Verified after
the change: `bash ctl.sh verify-access` is **15/15**.

**The silent-return caveat moved with the advertisement — it now applies to
pve-01.** pve-00's `accept-routes=false` is still the fix that keeps its own LAN
reachable, and is still unreproducible for the reason above. But the new single
point is pve-01: if its advertisement stops (a re-provision, a `tailscale up`
without `--advertise-routes`, or the route left unapproved in the admin console),
nothing else advertises the subnet and every tailnet client loses the LAN with no
alert. pve-01's README records the command; nothing asserts it is in effect.
Consumers to check when it changes: `apps/proxmox` reaches `10.168.0.201:8006`
from the ingress pod, and every `10.168.0.x` address used from off-LAN.

### D23 ➡️ Backups have no alerting — MERGED into D16 (2026-08-12)
This was D16 written a second time. Both entries said the same 2 things: the
backups sit on a single cloud, and a CronJob that stops looks exactly like one
that works. The 1 fact that only D23 held — the deliberate deferral on
2026-08-09 — is now in D16, which also carries the PAR expiry date.

Read D16. The number stays here so that no link to D23 dangles, and the entry is
not deleted, because a merged duplicate is still part of the record.

### D24 🟡 The CI pull secret uses a token with far too many permissions — OPEN
`arc-runners/ghcr-pull` materializes `shared/github/pat-godmode` into a
`dockerconfigjson`, so the kubelet can pull the private `.devcontainer` runner
images. That token carries `admin:enterprise`, `admin:org`, `delete_repo` and
`write:packages`. A pull credential needs `read:packages` alone.

This was chosen deliberately on 2026-08-10, because GitHub has no API that mints
a PAT, so nobody can create a narrower token without a human at the browser. Two
facts lower the severity: the kubelet consumes `imagePullSecrets` and never
mounts them into the container, and the runner ServiceAccount
(`*-gha-rs-no-permission`) has no RBAC, so a job cannot `get` the Secret.

Remedy: create a classic PAT with **only** `read:packages`, store it as
`shared/github/ghcr-pull`, and point the ExternalSecret's `remoteRef.key` at it.
That is 1 line, and no other change.


### D25 ✅ Argo's repo credential was hand-applied and per-repo — RESOLVED (2026-08-10), 1 cleanup outstanding
`repo-infrastructure` was a Secret applied with `kubectl apply`. It held a
classic PAT, it had no record in git, and it had no source of truth outside the
cluster. Every new private repo would have needed another one by hand.

It is replaced with an org-wide `repo-creds` ExternalSecret at
`platform/services/gitops/repo-credentials/`. Argo matches `repo-creds` by URL
prefix, so one entry now covers every repository under `github.com/gophersys`.
Adding `gophersys/home`, or the next repo, needs no cluster change at all.

The token was not regenerated. The existing token was moved into the vault as
`shared/github/argocd-repo`, so the value now has a home outside the cluster.

**The cleanup that is outstanding, merged in from D35 on 2026-08-12.**
`repo-infrastructure` is still in the cluster. It is the hand-applied Secret that
holds the classic PAT, and it was left in place on purpose until the org-wide
credential proved itself. `gophersys-repo-creds` is `SecretSynced`. **Delete
`repo-infrastructure` after the org-wide credential has served a week with no
error, and write the date here.** The heading of this entry names the cleanup, so
that a reader who scans for ✅ does not read it as finished work.

### D26 🔴 eden CI is red: 5 workflows use `container:` on a self-hosted pool — OPEN
`eden/.github/workflows/{on-pr,on-push,harness-conformance}.yml` set
`runs-on: arc-org` and also a `container:` block for
`ghcr.io/gophersys/base:latest`. This is the pattern that `docs/ci-substrate.md`
and ADR-0031 exist to remove. The pool's runner image already carries the
toolchain, so the container block adds a second image pull inside the pod. That
pull is measured at more than 5 minutes, it happens on every job, and it
authenticates to a private package with `GITHUB_TOKEN`, which returns 403.

**Fix:** give eden a `.ci/ci.contract.yaml` with `runner.container: false` and
generate its workflows, as `libs` now does. Do this after `libs` is green.

### D27 ✅ `validate.yml` downloaded shellcheck — RESOLVED (2026-08-10)
The `manifests` job stopped installing tools when the pool moved to the dev
image. The `shellcheck` job still ran
`curl ... shellcheck-v0.10.0 ... | tar xJ` and called the extracted binary. The
runner image already carries shellcheck. `docs/ci-substrate.md` claimed the whole
file had no tool-install step, which was not true.

**Resolved** in `08ad452`, "fix(ci): no advisory steps — shellcheck fails,
yamllint is deleted". The job calls `shellcheck` from PATH at full strictness.
The same commit removed the 4 ways the job stayed green without linting:
`continue-on-error` on the step, `|| exit 0` on the download, `|| true` on the
run, and a `-S warning` filter that dropped the findings `ctl.sh` says must fail
the build.

Measured on this branch. `grep` exits 1 because the workflow holds no `curl` at
all, not only no shellcheck download:

```
$ grep -c 'curl' .github/workflows/validate.yml; echo "rc=$?"
0
rc=1
```

### D28 🟠 17 of 20 repositories have no `.ci/ctl.sh` — OPEN
The CI contract generates workflows whose only step form is
`bash .ci/ctl.sh <verb>`. 17 repositories have no such file, and 11 have no CI at
all, including the 4 `zephyr-*` repositories. The contract's language enum also
has no C, no Shell and no JavaScript, so it cannot describe 7 repositories.

The count moved from 16 to 17 on 2026-08-10: `infrastructure` deleted its own
`.ci/`, which was unreferenced and partly broken. See D38.

**Consequence:** "roll the contract out to every repository" is not possible
today. The real number of candidates is 2.

**Fix:** decide per repository whether it needs CI at all. Do not add a contract
to a repository that has no verbs to run.

### D29 🟠 No check can be required: branch protection is not on this plan — OPEN
```
GET /repos/gophersys/infrastructure/branches/main/protection  -> 403
GET /repos/gophersys/infrastructure/rulesets                  -> 403
"Upgrade to GitHub Pro or make this repository public to enable this feature."
```
Every gate in this organization is advisory. A red check does not stop a merge,
and nothing enforces review. The git hooks are the other half of the story: eden's
`core.hooksPath` pointed at `/Users/mateo/helios/.git/hooks`, a path deleted in
the rename to `~/code/eden`, so the hooks had not run for weeks. It now points at
the tracked `.githooks`, but `core.hooksPath` is local configuration. It is not
tracked, so a fresh clone starts with no hooks again.

**Fix options:** GitHub Pro for the private repositories; or accept that the
gates are advisory and write that down; or add a `ctl.sh setup` verb that sets
`core.hooksPath` so a fresh clone is one command from being gated.

### D30 🟡 `node` is not on PATH in the runner image — OPEN
`bash ctl.sh verify-runner-image` found it. The base image installs Node through
nvm, and nvm only initializes in a login shell. A job that calls `node` directly
fails. GitHub's own JavaScript actions are unaffected: the runner supplies its
own Node from `/home/runner/externals`.

**Fix:** put the nvm Node on PATH in the image, or state in `docs/ci-runners.md`
that a job must use `setup-node` for a direct `node` call.

### D31 🟡 A cached layer reverted `/etc/group` — OPEN, worked around
The docker group step ran, its assertion passed, and the published image still
held `docker:x:123:root` with no `dev` member. The likely cause is a restored
BuildKit layer whose snapshot diff carried an older copy of `/etc/group`. The
work-around is to make the group the last mutation in the image, so no layer can
follow it.

The root cause is not proven. If another file shows the same behaviour, this is
the entry to read first.

### D32 🟡 The provider twins are maintained by hand — OPEN
`.github/workflows/*.yml` and `.ci/providers/github/*.yml` hold the same YAML
twice. 9 files across eden, libs and `.devcontainer`. The documents said these
were symlinks, and git records every one as mode `100644`. They have already
drifted once: the `.devcontainer` copy held a stale 3-image version while it
claimed to be the source of truth.

`cictl generate` writes both copies and `cictl drift` fails a build on a hand
edit, but only `libs` runs that gate.

**Fix:** wire `ci-drift` into each repository as it adopts a contract.

### D33 🟡 arm64 has no verified consumer — OPEN, decision deferred
No arm64 consumer could be found for any image. Every Kubernetes node is amd64.
This Mac has created 1 container in its history, `node:22-bookworm`, and has
never run a gophersys devcontainer. `base-runner` and `zephyr-devbox` now build
amd64 only. `base`, `flutter` and `zephyr` keep arm64 because the
devcontainer-first rule intends them to be opened on this Mac.

**Decision point:** if this Mac still has not run a devcontainer by 2026-09-10,
drop the remaining arm64 halves. `runs-on: ubuntu-24.04-arm` gives native arm64
in 1 line if it is ever needed.

### D34 🟡 Almost half of image-build time is spent freeing disk — OPEN
About 47% of recent CI time in `.devcontainer` goes to
`jlumbroso/free-disk-space`, not to the build. The hosted runner has about 14 GB
free and these images are near 10 GB.

**Fix:** measure which reclaim flags actually matter, and remove the rest. A
faster fix is to stop building what nothing consumes: see D33.

### D35 ➡️ The old Argo repository secret is still in the cluster — MERGED into D25 (2026-08-12)
This was the last line of D25 written out as its own entry. D25 already said
"retire `repo-infrastructure` after the org-wide entry has proven itself", and
this entry said the same thing with a week-long waiting period attached.

The action survives in D25, and the heading of D25 now names it, so the cleanup
does not hide inside a ✅ entry. Read D25. The number stays here so that no link
to D35 dangles.

### D36 🟠 The container user model is decided for macOS, not for Kubernetes — OPEN
The runner image runs as root, and the dev images keep the unprivileged `dev`
user. That split was decided on 1 piece of evidence: on macOS, a file written by
root inside a container appears on the host as the host user, because the
virtualization layer remaps the owner.

```
in container:  root uid=0
on the Mac:    mateo:staff
```

**Kubernetes does no such remapping.** When these images run as a dev box in a
pod, and an agent writes to a PersistentVolumeClaim, the owner on the volume is
the uid of the process that wrote it. 2 failures follow from that:

1. A pod that runs as root writes root-owned files. A later pod that runs as
   `dev` cannot change or delete them.
2. A pod that runs as `dev` writes files with uid 1000. A later root process can
   read them, but any other uid cannot.

`zephyr-devbox` already meets this: it starts as root, runs sshd, and a login
lands as `dev`. That works because 1 user writes the files. It stops working as
soon as 2 pods with different users share a volume.

**Before agent pods write to a shared volume, decide 1 uid for every pod that
touches it, and set `securityContext.fsGroup` on the pod so the volume is group
owned by that id.** `fsGroup` is the field Kubernetes provides for exactly this,
and it works whatever user the image declares.

Revisit also if development ever moves to a Linux host: there, root in a
container really does write root-owned files to the bind mount, and the macOS
evidence above does not apply.

### D37 🟡 The Claude CLI pin has 2 homes — OPEN
ADR-0021 says a harness pin lives once, in eden `harnesses/versions.env`. The
runner image now repeats it:

```
eden/harnesses/versions.env          CLAUDE_CODE_VERSION=2.1.212
.devcontainer/runner/Dockerfile      ARG CLAUDE_CODE_VERSION=2.1.212
```

The cause is structural, not carelessness. The runner image is built from the
`.devcontainer` repository, which stands alone. It cannot read a file that lives
in eden, so the pull request review agent could not get a pinned CLI any other
way.

**The 2 values must move together.** `harness-upgrade-check` bumps the eden file
on a weekly schedule and opens a pull request; that pull request does not touch
the Dockerfile, so the 2 will drift on the next bump.

**Remedies, in order of preference:**
1. Move the pin to `.devcontainer`, and have eden read it from the submodule. 1
   home again, and the submodule is already vendored.
2. Extend `harness-upgrade-check` to edit both files in the same pull request.
3. Assert equality in CI, so a drift fails rather than passes.

Option 1 removes the duplication. Options 2 and 3 only make the duplication
visible.

### D38 ✅ The `.ci/` layer was unreferenced and broken — RESOLVED (2026-08-10)
`infrastructure/.ci/` held 298 lines across 5 files: `ctl.sh` with 9 verbs, a
`project.json` that named the Nx project `ci-infrastructure`, and 2 READMEs. It
predates `.github/workflows/validate.yml` and it was superseded by it.

3 facts decided the deletion:

1. **Nothing invoked it.** No workflow, no script and no `ctl.sh` verb in this
   repository called any `.ci/` verb. The only mentions were prose.
2. **Its `validate-platform` verb failed.** It required a README in every
   directory under `platform/core` and `platform/services`, and reported 9
   errors. All 9 were the rule being wrong, not the tree. 2 of the 9 directories
   hold a real script and the Argo AppProject YAML.
3. **Its `validate-contracts` verb could not detect a renamed heading.** It used
   `grep -F "## Guarantees"`, which `## GuaranteesXX (TBD)` satisfies. Proven:
   the heading was renamed and the verb still printed `validate-contracts: OK`.

Its 2 useful checks moved to `scripts/verify-structure.sh`, which runs from
`validate.yml` and from `ctl.sh verify-structure`, and which uses a whole-heading
match. The other 7 verbs were dropped: `validate-machines` and
`validate-clusters` only wrapped `machines/ctl.sh validate` and
`clusters/ctl.sh validate`; `validate-providers` was a README-presence rule over
a stub tree; `status` wrapped `ctl.sh status`; `release-check` was a preflight
for a `release.sh` in the "brain" ecosystem, and those paths do not exist.

**Consequence for D28:** the count of repositories with no `.ci/ctl.sh` goes from
16 of 20 to 17 of 20. This repository is now one of them, deliberately. Its CI
entry point is `.github/workflows/validate.yml` calling `scripts/verify-*.sh`.

**Still not covered by CI after this change:** `bash ctl.sh validate` (the
`project.json` JSON parse and the `bash -n` syntax pass) is not a step in
`validate.yml`. The `shellcheck` job covers the lint half of it. Nothing invoked
`.ci`, so nothing was lost, but nothing was gained there either.


### D39 ✅ hnslint was required by the libs gate and was in no image — RESOLVED (2026-08-11)

**hnslint is required by the libs gate and is in no image.**

`gophersys/libs` `go/_ctl/lib.sh` runs `cmd_maintainability` inside
`phase_implementation`, and that verb needs `hnslint`. The tool is in neither
`.devcontainer/base/Dockerfile` nor `runner/Dockerfile`. The `post-create` verb
builds it from the bind-mounted `tools/hnslint`, so a developer in the container
has it and CI never does. `libs` is a separate repository and does not carry the
source, so its pull request tier fails with `missing required tool(s): hnslint`.

Eden `CLAUDE.md` said the image contained it. 10 of the 11 tools in that sentence
were real. The claim is corrected in gophersys/eden#6.

**The gate is behaving correctly.** It names the tool and fails, which is the
standing rule. `libs` cannot go green until the tool is reachable.

Options, cheapest first:
1. Move `tools/hnslint` into `gophersys/libs`. It exists to lint `libs/go/<lib>`
   structure, so that is arguably its home. No new repository, no credential.
2. Publish it as its own public repository, as `cictl` was, and bake a pinned
   version into `base-runner`. This also serves eden.
3. Build it in CI from a checked-out eden with a token. This puts a private
   dependency inside a public repository's gate.

Option 1 is the recommendation. The choice is Mateo's, because it moves code
between repositories.

**Resolved (2026-08-11) — Mateo chose option 2.** The tool is now the public
repository `gophersys/hnslint`, tagged `v0.1.0`. `.devcontainer/base/Dockerfile`
installs it in the Go-tools layer, pinned by `ARG HNSLINT_VERSION`, so every
image that descends from `base` carries it, `base-runner` included. The
repository is public for the same reason `gophersys/cictl` is: an image build
cannot authenticate to a private repository.
`scripts/verify-runner-image.sh` asserts `hnslint on PATH`, and the assertion
passed on `e0c6bc5`.

The duplicate source at `eden/tools/hnslint` is deleted, and the `post-create`
verb no longer builds it. The 2 changes go together: while both existed, the
`post-create` build put a working tree in `GOPATH/bin`, which takes precedence on
`PATH`, so a developer ran their own copy and CI ran `v0.1.0`. To change the
version now, cut a release in `gophersys/hnslint` and raise the pin.

### D40 🔴 omp 17.2.12 does not reach a terminal event — OPEN, blocks the bump

**omp 17.2.12 does not reach a terminal event.**

eden#4 bumps the pinned harnesses. `TestIntegration_LiveOmp_Gated` failed twice
independently, at 64.65s and 62.27s, with no terminal event inside the 60-second
drain deadline. `claudeadapter` passed both times, at 11.6s and 10.8s, and both
`affected-gate` jobs pass. The failure is specific to omp.

The message named the last event rather than the deadline, which sent the first
reader to look at event kinds instead of the clock. That is fixed in
gophersys/libs#2, and the deadline branch there is proven in both directions.

**The bump must not merge until this is understood.** A harness that stops
terminating is not a version to pin. The decision is Mateo's: raise the deadline,
take it upstream, or reject the bump.

### D41 ✅ The shared reviewer was unpinned in every repository — RESOLVED (#148)

**The shared reviewer was unpinned in every repository.**

`pr-review.yml` cloned the default branch of `gophersys/cictl`. Every repository
ran whatever `cictl` main was at that minute, and `cictl` moved 23 commits in 1
evening, so no review from that period can be reproduced. A broken main would
also have broken the review job of every repository at the same time.

**Resolved** in #148 and gophersys/.devcontainer#24: the workflow clones the tag
in `CICTL_VERSION` and then asserts the checkout is that tag, because a clone that
fell back to a default branch would defeat the pin silently. `cictl v0.2.0` is the
first pinned version.


### D42 🟠 The published `linux/arm64` base image is not arm64 — OPEN

**The published `linux/arm64` base image is not arm64.**

Measured on `ghcr.io/gophersys/base:e0c6bc5` by running each manifest variant and
reading the ELF machine byte of a Go binary. It was not read off the Dockerfile.

| variant | `uname -m` | `dpkg --print-architecture` | gofumpt ELF |
| --- | --- | --- | --- |
| amd64 | x86_64 | amd64 | x86-64 |
| arm64 | x86_64 | amd64 | **aarch64** |

The arm64 entry is an **amd64 Ubuntu userland that carries aarch64 Go binaries**.
`:latest` is the same. The amd64 entry is correct.

**Cause.** `base/Dockerfile` line 27 is
`FROM --platform=${BUILDPLATFORM:-linux/amd64} ubuntu:24.04`. A `FROM` pinned to
`BUILDPLATFORM` makes the operating system layer and every apt package the
architecture of the BUILDER for both targets, while the Go tool layer still
builds for `TARGETARCH`.

**What is affected.** Only `base/Dockerfile` carries the `BUILDPLATFORM` pin.
`flutter`, `zephyr` and `zephyr-devbox` all build `FROM ghcr.io/gophersys/base`,
so their arm64 variants inherit the same amd64 userland. `base-runner` is amd64
only, by the measured decision in D-runner-arch, so **the CI pool is not
affected**: `verify-image-arch` passes on `base-runner:e0c6bc5`.

**All 5 are measured now**, each by running the variant:

| image | required | result |
| --- | --- | --- |
| `base` | amd64+arm64 | FAIL — arm64 entry is an amd64 userland |
| `flutter` | amd64+arm64 | FAIL — same, inherited |
| `zephyr` | amd64+arm64 | FAIL — same, inherited |
| `zephyr-devbox` | amd64 | PASS — amd64 only **by decision**, see below |
| `base-runner` | amd64 | PASS |

**Correction.** An earlier version of this entry called `zephyr-devbox` a second
breach of the policy. That was wrong. Commit `c7e8e94` narrowed it to amd64
deliberately, and verified the reason against the live cluster: it runs only as a
Kubernetes pod, its 3 pods sat on `k3s-w-1`, `k3s-w-3` and `k3s-w-4`, and every
node is amd64. It is the same rule as `base-runner` — build the arch you deploy
to. It fails only when it is judged against the devcontainer default list, and so
does `base-runner`.

**But `00-identity.md` was never updated**, so it still calls multi-arch
non-negotiable for all 4 devcontainer images while 1 of them is amd64 only by a
merged decision. Corrected in gophersys/.devcontainer.

**Measured: the arm64 variant works, and that is the argument against keeping it.**
Running `ghcr.io/gophersys/base:e0c6bc5` as `linux/arm64` on an Apple Silicon
host, the Go tools execute:

```
gofumpt        v0.10.0 (go1.26.4)
golangci-lint  2.12.2
```

They run because the host executes the aarch64 binaries natively while Docker
Desktop emulates the amd64 userland around them. That is why nobody saw this: on
the only machine that would consume an arm64 image, it appears to work.

**The point of a native arm64 image is to avoid emulation. This one emulates its
userland regardless.** So it delivers none of the benefit that justifies the
build, and it costs the larger half of a 41.7-minute build. On a bare arm64 Linux
host with no Rosetta, the amd64 `bash` itself would need `qemu-user-static`
registered, and the image would be slower still or would not start.

**A third option for this entry, from that same commit.** It records that no arm64
consumer can be verified for ANY image: this Mac has created 1 container in its
history, `node:22-bookworm`, and never a gophersys devcontainer. So the choice is
not only "drop the pin" or "cross-compile". It may be "drop arm64", which costs
nothing to build and nothing to verify, and which the evidence currently
supports. Decide that before spending on either fix.

So the reach is every arm64 **devcontainer** user, and no CI job.

**Why nobody saw it.** The manifest declares the platform and nothing verifies the
content. `.claude/rules/00-identity.md` calls the multi-arch policy
non-negotiable, because an arm64 Mac has real users. Those users pull an emulated
amd64 userland whose gate tools are a different architecture.

**The fix** is to drop the `BUILDPLATFORM` pin so each target builds its own
operating system layer, or to add a `--platform=$BUILDPLATFORM` builder stage that
cross-compiles the Go tools with `GOARCH=$TARGETARCH` and copies them into a
normal per-target final stage. The second also removes most of the 41.7-minute
base build.

**The assertion exists now**: `scripts/verify-image-arch.sh`, and
`bash ctl.sh verify-image-arch <ref>`. It runs each published variant and fails
when `uname -m`, `dpkg --print-architecture` and the ELF machine of a Go binary
disagree with the manifest platform. Two of those agreeing is what hid this
defect, because `uname` and `dpkg` agreed with each other and the binaries did
not.

Proven against real images, not against a fixture:

| image | result |
| --- | --- |
| `base:e0c6bc5` | exit 1 — `declares linux/arm64 but holds: uname=x86_64(want aarch64) dpkg=amd64(want arm64)` |
| `base-runner:e0c6bc5` | exit 0 |

**It is NOT a step in any workflow yet, and that is deliberate.** It would be red
on `base` from the moment it landed, for the defect recorded here, and it would
block unrelated work before the fix is chosen. It also needs binfmt registered on
the runner to execute a foreign-architecture variant. Wire it into
`build-and-push.yml` in the same change that fixes this entry. Until then it is a
tool that a human runs, and this paragraph is the record that CI does not enforce
it.


### D43 🟡 `cictl` is pinned twice, at 2 versions — OPEN

**`cictl` is pinned twice, at 2 versions, and nothing keeps the 2 in step.**

| consumer | pin | what it uses |
| --- | --- | --- |
| `.devcontainer/runner/Dockerfile` | `CICTL_VERSION=v0.1.0` | the `cictl` binary on PATH |
| `pr-review.yml`, both repositories | `CICTL_VERSION=v0.3.0` | `review/review.sh` and its instructions |

The 2 consumers are real and separate: the image needs the compiled contract
tool, and the review job needs the reviewer scripts. Pinning both is correct.
Pinning them at different versions with nothing to notice is not.

**This is not urgent today, and the measurement says so.** The only Go change
between `v0.1.0` and `v0.3.0` is a 9-line comment in `cmd/cictl/run.go`, so the
binary is functionally identical. Everything else in that range is `review/`.

The review pin moved `v0.2.0` -> `v0.3.0` on 2026-08-13, to take the fix that
stops a paid review being discarded over its verdict line. The skew therefore
widened by 1 minor version, and the conclusion above is UNCHANGED, because it was
re-measured rather than assumed: `git diff --stat v0.2.0..v0.3.0 -- '*.go'` is
EMPTY. Everything in that range is `review/`.

**It becomes a defect on the next change to the Go sources.** Nothing then makes
anyone raise `CICTL_VERSION` in the Dockerfile, the image keeps an older contract
tool, and the gap is invisible because both numbers look deliberate.

Either give the 2 consumers 1 pin, or add a check that fails when the version in
`runner/Dockerfile` is behind the newest tag whose diff touches a `.go` file.


### D44 ✅ 4 Argo applications were permanently OutOfSync — RESOLVED (#166)

**Resolved on 2026-08-11** by #166: `ServerSideApply` is now set only where a
resource measurably needs it, and never on an Application that manages an
`ExternalSecret`. The cause was proven by a control experiment, not inferred.
The history below is kept because 3 hypotheses were refuted on the way, and each
one is a path nobody should walk again.

#### D44 — the history

**4 Argo applications are permanently OutOfSync, and the difference is not in the
spec.**

`root`, `arc-netpol`, `repo-credentials` and `eden` all report OutOfSync while
Healthy. They carry `syncPolicy.automated` with `prune` and `selfHeal`, and
`arc-netpol` is at the current `main` revision. So Argo is trying to converge and
cannot.

The difference is not the manifest. The `spec` of
`ExternalSecret/claude-review-token` was dumped from the cluster and compared
against `platform/services/ci/arc-runners/30-claude-review-token-externalsecret.yaml`:
**identical**, and the object is `Ready=True`. The same shape appears on the other
`ExternalSecret` objects and on `StatefulSet/eden-postgres` and
`StatefulSet/vault`. A StatefulSet that reports OutOfSync on a server-defaulted
field is a known Argo behaviour.

**Why this matters more than it looks.** These are not broken workloads: every one
is Healthy. The cost is the signal. OutOfSync is the alarm that says the cluster
stopped matching git, and 4 applications hold it permanently for a reason nobody
has diagnosed. A real drift would arrive into a display that already reads
OutOfSync, and nobody would see it. It is the same defect as a check that is
always red.

**Not caused by the CI work.** The applications changed on 2026-08-10 —
`arc-org` and `arc-review` — are Synced. The 4 above were not touched.

**Diagnosed.** The `argocd` binary is not absent, it is inside the
application-controller pod, which is where it lives on this cluster:
`kubectl exec -n argocd argocd-application-controller-0 -- argocd app diff <app> --core`.
It needs the controller and not the server, whose service account cannot list
services. The result splits the 4 apps in 2:

| app | diff | meaning |
| --- | --- | --- |
| `root` | exit 1, 81 bytes | a real difference — **resolved**, see below |
| `arc-netpol` | exit 0, empty | the status says OutOfSync and the diff says identical |
| `repo-credentials` | exit 0, empty | the same |
| `eden` | exit 0, empty | the same |

**`root` is resolved.** The whole difference was `recurse: false` on
`Application/eden`: git declared it and the live object had no such field.
`recurse: false` is the Argo default, and `root` syncs with
`ServerSideApply=true`, so the API server normalised the field away every time
Argo wrote it and Argo then saw it missing again. `selfHeal` made it retry for 5
weeks. Removing the line changed no behaviour, because `false` is what `recurse`
already is, and `root` reports Synced with an empty diff now.

**What remains is proven false, 4 ways.** `arc-netpol` is the worked example, and
its 2 `ExternalSecret` resources are the ones it reports:

| test | result |
| --- | --- |
| `argocd app diff arc-netpol --core` | exit 0, empty |
| `kubectl diff -f 30-claude-review-token-externalsecret.yaml` | exit 0, empty |
| live `.spec` against the file in git | identical |
| `argocd.argoproj.io/refresh=hard` | status unchanged |

Argo also compares against the right commit: `OutOfSync from main (348f5ba)`, and
`348f5ba` is the current `main`. The `NetworkPolicy` in the same Application is
`Synced`. Only the 2 CRD resources disagree, and both carry the message
`serverside-applied`.

So the cluster matches git and the alarm is wrong. It is not a stale cache, and it
is not the revision. It is Argo's comparison of these CRD objects under
server-side apply.

**The cost is unchanged and it is the reason this stays open.** OutOfSync is the
alarm that says the cluster stopped matching git. 3 Applications hold it
permanently while matching git exactly, so a real drift arrives into a display
that already reads OutOfSync.

**2 hypotheses tested and REFUTED.** Both are recorded so nobody spends the time
again.

1. *The stored API version differs.* It does not. Git and the live objects are
   both `external-secrets.io/v1`, and the CRD serves only `v1`.
2. *Argo counts the controller's finalizer as a difference.* `managedFields` shows
   `argocd-controller` holding `f:spec` by Apply and `external-secrets` holding
   `f:metadata.finalizers` by Update, and the finalizer
   `externalsecrets.external-secrets.io/externalsecret-cleanup` is on the live
   object and not in git. That looked decisive. It is not the cause: an
   `ignoreDifferences` on `/metadata/finalizers` for `ExternalSecret` was merged,
   confirmed present on the live Application, with `root` Synced at the same
   commit — and `arc-netpol` stayed OutOfSync with an empty diff. The entry was
   reverted rather than left in place, because configuration that changes nothing
   and carries a false explanation is worse than none.

An earlier version of this entry said there was nothing legitimate to ignore. That
was stated before the ownership data existed, and hypothesis 2 above shows why it
was not a safe thing to assert.

3. *The known upstream defect in server-side diff for CRDs.* Argo CD is `v3.4.4`,
   and issue [argoproj/argo-cd#27625](https://github.com/argoproj/argo-cd/issues/27625)
   describes exactly this shape: server-side diff mishandles a CRD whose schema
   declares `x-kubernetes-preserve-unknown-fields`, because the code cannot tell
   "not in the manager's recorded ownership" from "added by a webhook". The
   precondition does not hold here. The `externalsecrets.external-secrets.io` CRD
   has **0** occurrences of `x-kubernetes-preserve-unknown-fields` in its schema.

**The correlation, measured.** Every Application that carries an `ExternalSecret`
sets `ServerSideApply=true`, and all 3 are OutOfSync. The `NetworkPolicy` inside
`arc-netpol`, under the same Application and the same sync option, is Synced. So
it is not server-side apply alone; it is server-side apply together with this CRD.
No Application without `ServerSideApply=true` carries an `ExternalSecret`, so the
cluster holds no control case to compare against.

**What is left is a decision, not a diagnosis.** The documented workaround is
`controller.diff.server.side=false` in `argocd-cmd-params-cm`, which turns off
server-side diff for the WHOLE cluster. That trades a false OutOfSync on 3
Applications for a change in how every Application is compared, and it is Mateo's
call, not a fix to apply quietly. A control case would settle it first: 1
`ExternalSecret` in an Application without `ServerSideApply=true`.

**Do not reach for a broad `ignoreDifferences`**: the measurements show the objects
match git, so a blanket ignore would hide a real drift without fixing anything.


### D45 🟠 Node labels and taints exist in git and on no node — OPEN

**Every homelab node declares labels that nothing applies, and half of them
declare taints that nothing applies either.** All 8
`clusters/instances/homelab/nodes/<node>/identity.yaml` files carry
`kubernetes.labels.role` (`devops` on k3s-cp-0/1/2 and k3s-w-0, `apps` on
k3s-w-1..4). Only those same 4 declare a taint —
`devops=true:PreferNoSchedule` — and the other 4 declare `taints: []`, so the
gap is the labels on all 8 and the taints on 4. Every one of them lists
`cluster-node-labels` in its `roles:`, and `clusters/CONVENTIONS.md` names that
Ansible role as the applier. It does not exist: `machines/roles/` holds 10 roles
and none of them is it.

Measured live on 2026-08-18, all 8 nodes:

```
kubectl get nodes -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints,ROLE:.metadata.labels.role'
```

Every node answers `<none>` in both columns. Zero taints, zero `role=` labels.

**The cost is that a manifest can believe them.** `42-image-warmer-daemonset.yaml`
did: it carried no tolerations and a comment saying control planes tainted away
from runners are tainted away from the warmer too. The premise was false, so the
DaemonSet ran on the 3 control planes and held ~3.86GB of images there that
image GC cannot reclaim while its initContainers hold them. `k3s-cp-0` reached
93% used / 2.7GB free at 22:31Z on 2026-08-18 while serving etcd on a 38GB disk.

Until this entry is resolved, **scheduling is governed by manifest affinity
only**. The warmer, the refresh CronJob and both NotIn runner pools now exclude
the control planes by hostname, and `scripts/verify-warmer-pins.sh` derives that
set from the identity files, so a 4th control plane fails validate the day it is
declared. That is a guard, not the fix.

The fix is a choice, and it is Mateo's: write `cluster-node-labels` and apply
what the identity files declare, or delete the declarations. Do not leave the
third state — a declaration that reads like enforcement and enforces nothing.


### D45 🔴 Argo's first sync after a values-only change can apply the OLD render — OPEN, guarded

**Argo CD reported a sync Succeeded at the correct revision pair while applying
the previous rendered config. Twice on 2026-08-18, on the `argocd` app itself.**

The app is multi-source: source 1 is the pinned chart `argo-cd 10.1.2`, source 2
is this repo supplying the values file through `$values` / `ref: values`. After a
commit that changed ONLY `platform/services/gitops/bootstrap/values.yaml`, the
first deliberate sync applied the pre-commit render.

**It was proven, not inferred.** The `last-applied-configuration` annotation on
the applied objects carried a fresh timestamp and the OLD content. So the write
really happened, at that moment, with stale input. A sync that reports the right
revision and writes the wrong bytes is worse than a failed sync: the alarm that
would say "this did not land" says Succeeded instead.

**Both occurrences were the FIRST sync after the change.** A hard refresh
followed by a sync was always correct.

**Mechanism — what is verified upstream, and what is ours.**

Verified against the Argo CD sources and docs at `v3.4.4`:

| fact | source |
| --- | --- |
| The repo-server resolves a `ref:` source's revision itself, in `runRepoOperation` → `repoRefs`, separately from the controller | root-cause text of [argo-cd#29185](https://github.com/argoproj/argo-cd/pull/29185) |
| `argocd-repo-server --revision-cache-expiration` defaults to `3m0s` | `docs/operator-manual/server-commands/argocd-repo-server.md` @ v3.4.4 |
| That flag has NO `argocd-cmd-params-cm` key — `extraArgs` is the only route | `docs/operator-manual/argocd-cmd-params-cm.yaml` @ v3.4.4 |
| A hard refresh sets `noRevisionCache`, bypassing that cache | Argo CD refresh semantics |

Ours, and labelled as a hypothesis because it was not reproduced in a control
experiment: a sync raised inside the 3-minute window renders against the
repo-server's cached resolution of `main`, which still points at the previous
commit. That fits every observation — first sync only, hard refresh always
correct, correct revision pair reported (the controller resolved it; the
repo-server did not). **It is not proven.** Proving it needs a deliberate
reproduction: commit, sync within 3 minutes, diff the applied annotation.

**Upstream has no fix. This was checked, not assumed.**

| issue | state | relevance |
| --- | --- | --- |
| [#28956](https://github.com/argoproj/argo-cd/issues/28956) | OPEN, `bug/severity:major`, `feature:multi-source`, `component:repo-server` | The closest match: a `$values`/ref-source cache not invalidated, and a hard refresh not clearing it |
| [#29185](https://github.com/argoproj/argo-cd/pull/29185) | OPEN, unmerged | The fix for #28956 |
| [#25942](https://github.com/argoproj/argo-cd/issues/25942) | OPEN since 2026-01 | Multi-source renders new values against old chart templates |
| [#28677](https://github.com/argoproj/argo-cd/issues/28677) | OPEN | Repo-server renders stale content across revisions, a v3.4.0 regression |
| [#28074](https://github.com/argoproj/argo-cd/pull/28074) / [#29049](https://github.com/argoproj/argo-cd/pull/29049) | MERGED, shipped in **v3.5.1** | The one cache-key fix that shipped. Scoped to `manifest-generate-paths`, which this repo uses NOWHERE (`grep -rn manifest-generate-paths` is empty). **Not our bug.** |

So there is no version to upgrade to. `v3.4.7` and `v3.5.1` both still carry
this. The chart pin stays at `10.1.2` deliberately: a bump buys nothing here, and
`v3.5.x` carries the Helm 3 → Helm 4 migration (argo-cd#29068), which is real
rendering risk taken for no gain.

**The guard, and what it is worth.**

1. `--revision-cache-expiration=10s` via `repoServer.extraArgs` in
   `bootstrap/values.yaml`. This narrows the window from 3 minutes to 10 seconds.
   It does **not** close it.
2. The hard-refresh requirement, written into the header of
   `registry/argocd-self.yaml` — the file anyone reads before syncing this app.

**Residual risk, stated plainly.** A sync raised within 10 seconds of a push can
still apply a stale render, and it will still report Succeeded. The hard refresh
remains mandatory and remains a human step: nothing in this repo enforces it.
Every other multi-source app with a `$values` ref source carries the same defect;
`argocd` is simply the one where it was caught, because it is synced by hand.

**What closes this entry:** #29185 merging and reaching a release, then the chart
bump that carries it. Until then D45 stays 🔴 — the failure mode is silent, and a
guard that depends on a person remembering is not a fix.


### D46 🟡 Admission policy: 2 in-tree VAPs enforce; everything else is PR-gate or unenforced — OPEN (bounded)
**Successor to D21.** The decision, its evidence and its counter-argument:
`.claude/rules/50-cluster-architecture.md` §4 and `platform/core/policy/README.md`.

**What is now enforced at admission**, by
`platform/core/policy/manifests/`, applied by the `policy` Argo Application, both
bindings `validationActions: [Deny]`, both policies `failurePolicy: Fail`:

| Policy | Refuses | Gated on |
|---|---|---|
| `storage-delete-guard` | `DELETE persistentvolumeclaims` | namespace `platform.gophersys/protected-storage=true`, or PVC `platform.gophersys/retain=true` |
| `namespace-delete-guard` | `DELETE namespaces` | namespace `platform.gophersys/protected=true` |

**Why it earned admission and CI could not.** `local-path` is the only
StorageClass, it is the default, every PV reclaims with `Delete`, and the
provisioner's teardown script is `rm -rf`. The `eden` namespace holds Vault (the
root of trust), Postgres and the NATS JetStream store, and it has **no backup** —
`apps/music/config-backup` covers media only, and Longhorn was removed
2026-08-19. `apps/eden/06-nats.yaml` declared a bare PVC inside an Argo
Application with `prune: true` and `selfHeal: true`, so deleting or renaming that
file in a **merged** PR would have destroyed the store with no human in the loop.
**A deletion is not a manifest**: kubeconform validates what you add, and Argo's
prune runs after merge. The PR gate is structurally blind to this class.

**What this entry stays OPEN for.** Three named gaps, each with its bucket:

1. **Pod security is unenforced.** `applied-per-workload-unenforced`. The fix is
   in-tree PodSecurity namespace labels, not a policy engine, and `restricted`
   cannot hold today: metallb needs `hostNetwork` + `NET_RAW`. Only
   `metallb-system` carries PSA labels on the live cluster. Honest per-namespace
   levels are unbuilt.
2. **No registry allowlist anywhere.** The list documented in
   `50-cluster-architecture.md` §7 was fiction — the estate also pulls `lscr.io`,
   `docker.io`, `qmcgaw`, `hashicorp`, `openresty`, `filebrowser` — so the claim
   was deleted rather than softened. It belongs at the PR gate with an explicit
   list derived from what runs. Unbuilt.
3. **`prod` is not covered.** `platform/core/policy/` is `platform/core`, so every
   cluster is supposed to get it, but the OCI `prod` cluster runs no Argo root
   from this repo. Its `protection:` block still enforces nothing. That is a
   GitOps gap, not a capability gap (k3s v1.34.5 serves the same GA API).

**Known limits, so they are not rediscovered.** A VAP cannot read another object,
and cannot reach one through `paramRef` either, so it cannot condition on the PV's
`reclaimPolicy` — the label carries that intent, and that is the only in-tree
shape (KEP-3488 names external lookups a permanent non-goal). A VAP cannot expire
an annotation, so `platform.gophersys/allow-delete` has **no TTL** and this entry
does not claim one. `MutatingAdmissionPolicy` is not served on k3s 1.35, so the
labels cannot be injected at admission; it goes GA in 1.36, which is when
auto-labelling should be revisited. A VAP does not protect itself — `kubectl
delete vap` on the guard succeeds, and the only thing that undoes it is the
`policy` Application's `selfHeal: true` on the next reconcile.

**Never re-adopt a generator for these.** Kyverno can emit VAPs from a
`ClusterPolicy`, and the emitted object carries an `ownerReference` back to the
Kyverno policy — uninstalling Kyverno garbage-collects the enforcement on the way
out. There is no converter back (`kyverno migrate` migrates resource versions).
The manifests are hand-written and depend on nothing that can be uninstalled.

**Verification.** `bash ctl.sh verify-vap-policies` (in `validate.yml`; manifest
shape, with a fixture suite of 17 cases that prove it fails) and
`bash ctl.sh test-vap-guard` (LOCAL-ONLY; exercises the live admission chain with
`--dry-run=server` in both directions, and exits 2 rather than 0 when the
policies are absent).

**What closes this entry:** the 3 gaps above, each with a named artifact.


## Resolved

Resolved items stay in the ledger above, marked ✅ with the PR or the date that
captured them. **Do not write a second list of them here.** The ledger is the
source. To print the current set:

```
grep -n '^### D.*✅' docs/debt-register.md
```

Change the marker for any other status: 🔴, 🟠, 🟡 or ➡️.

The list that stood here was maintained by hand and it had drifted. It named D5
twice, it gave no date, and it omitted 7 entries that the ledger above had
already marked ✅: D10, D14, D17, D25, D38, D39 and D44. That is the whole
argument for the command.
