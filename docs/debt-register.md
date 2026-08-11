# Infrastructure Debt Register

A current record of state that exists in the running cluster, on the hosts or in
the PVCs, but that this repo does **not yet capture fully in a declarative form**.
It also holds the engineering agreement that all new work must follow. The goal
is that no state is hidden: anything load-bearing must be reproducible from git,
or recorded here as accepted-imperative with the steps to recreate it.

Status legend: 🔴 open (reliability or security risk) · 🟠 open (reproducibility) ·
🟡 minor or accepted · ✅ resolved (captured declaratively).

Last updated: 2026-08-10 (`.ci/` deleted — see D38; testing standard written —
see docs/testing-standard.md).

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
every imperative k8s Secret. It covers `media`, `workspaces-prod`, `arc-runners`,
`minio`, `longhorn-system` and `cloudflare-tunnel`. Each entry names its
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
Every version from the 2026-07 audit was upgraded without an outage, but **4
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
| Longhorn | v1.12.0 | ❌ raw manifest | staged — `docs/runbooks/longhorn-upgrade.md` (client-side CRDs) |

Upgrade notes: cert-manager ships the DNS-01 cleanup fix (D10); the MetalLB VIP
stayed up; all 7 ingress-nginx routes stayed up; Longhorn left EOL through a
staged upgrade of 5 minor versions, with no data loss (the backup target was the
in-cluster MinIO, `apps/minio/`). **Follow-up:** move the 4 raw-manifest
components into Argo Applications, as done for cloudflared, or accept them as
imperative through this pin table.
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
that is network-isolated to `longhorn-system` (the NetworkPolicy is in
`apps/minio/`).

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

### D16 🟠 Backups are single-cloud and unmonitored — OPEN
The backups from D14 land in OCI Object Storage. That is a different service and
a different durability domain from the block volume, so the backups survive the
loss of an instance and the loss of a disk. They do **not** survive the loss of
the Oracle account. Wanted: a pull leg outside Oracle (the homelab or the
workstation fetches from `eden-backups/vault/` on a schedule). Separately, a
CronJob that stops working does not look different from one that works, and
nothing raises an alert today. The PAR also expires **2027-08-10**, and the
renewal is currently a calendar event, not an automated action.

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


### D21 🟡 No admission policy engine — ACCEPTED (2026-08-09)
Kyverno was removed. It ran `audit-only` from installation with a single
`pod-security-baseline` ClusterPolicy that excluded 8 namespaces. It therefore
enforced nothing, cost 4 controller pods, and stayed permanently OutOfSync in
Argo on 4 CRDs. This is accepted, not fixed: with 1 operator and everything
reconciled from git, code review is the control. An unfinished policy engine is
worse than no policy engine, because it suggests an enforcement that does not
happen. Review this decision when more than 1 person deploys here, and only with
2 policies that you would genuinely enforce, not audit. Pod hardening is still
applied per workload in the manifests.


### D22 🟠 The machine inventory has 4 gaps — OPEN
The full inventory is in `docs/machine-inventory.md` (2026-08-09). Undeclared:
(1) `mateos-macbook-air` — `machines/development/` is empty, so the workstation
that holds every kubeconfig, the vault CLI and the OCI CLI has no identity file;
(2) the hypervisors `pve-00` and `pve-03` — only `pve-01` is declared, and all 3
hosts run the 8 k3s VMs. Unverified: (3) `arm-builder`, `macos-ci-runner` and
`windows-ci-runner` are declared but do not appear on the tailnet. The stated
consumers of arm-builder were codectl and fintel, and codectl no longer exists.
Stale: (4) `sentinel-00` and `sentinel-01` (the instances are terminated) and 2
laptops offline for 153 days still hold tailnet identities. Every tailnet device
is a possible entry point.

### D23 🟠 Backups have no alerting — OPEN (noted, deferred by decision)
The nightly vault backup CronJob works and the restore is tested, but a job that
stops does not look different from one that works. Nothing would tell you. The
backups are also still on a single cloud: they survive the loss of a disk and the
loss of an instance, but not the loss of the Oracle account. Deferred
deliberately on 2026-08-09, and recorded here so nobody finds it again as a
surprise.

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


### D25 ✅ Argo's repo credential was hand-applied and per-repo — RESOLVED (2026-08-10)
`repo-infrastructure` was a Secret applied with `kubectl apply`. It held a
classic PAT, it had no record in git, and it had no source of truth outside the
cluster. Every new private repo would have needed another one by hand.

It is replaced with an org-wide `repo-creds` ExternalSecret at
`platform/services/gitops/repo-credentials/`. Argo matches `repo-creds` by URL
prefix, so one entry now covers every repository under `github.com/gophersys`.
Adding `gophersys/home`, or the next repo, needs no cluster change at all.

The token was not regenerated. The existing token was moved into the vault as
`shared/github/argocd-repo`, so the value now has a home outside the cluster.
Retire `repo-infrastructure` after the org-wide entry has proven itself.

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

### D27 🟠 `validate.yml` still downloads shellcheck — OPEN
The `manifests` job stopped installing tools when the pool moved to the dev
image. The `shellcheck` job still runs
`curl ... shellcheck-v0.10.0 ... | tar xJ` and calls the extracted binary. The
runner image already carries shellcheck. `docs/ci-substrate.md` claimed the whole
file had no tool-install step, which was not true.

**Fix:** call `shellcheck` from PATH and delete the download.

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

### D35 🟡 The old Argo repository secret is still in the cluster — OPEN
`repo-infrastructure` is a hand-applied Secret that holds a classic PAT. The
org-wide `gophersys-repo-creds` ExternalSecret replaced it and is `SecretSynced`.
The old Secret was left in place until the new one proved itself.

**Fix:** delete `repo-infrastructure` after the org-wide credential has served a
week without an error, and record the date here.

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


### D39

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

### D40

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

### D41

**The shared reviewer was unpinned in every repository.**

`pr-review.yml` cloned the default branch of `gophersys/cictl`. Every repository
ran whatever `cictl` main was at that minute, and `cictl` moved 23 commits in 1
evening, so no review from that period can be reproduced. A broken main would
also have broken the review job of every repository at the same time.

**Resolved** in #148 and gophersys/.devcontainer#24: the workflow clones the tag
in `CICTL_VERSION` and then asserts the checkout is that tag, because a clone that
fell back to a default branch would defeat the pin silently. `cictl v0.2.0` is the
first pinned version.


### D42

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
| `zephyr-devbox` | amd64+arm64 | FAIL — **publishes no arm64 variant at all** |
| `base-runner` | amd64 | PASS |

`zephyr-devbox` is a second and separate breach of the same policy: it does not
mislabel an arm64 image, it ships none. `00-identity.md` lists it among the
devcontainer images that MUST be multi-arch.

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


### D43

**`cictl` is pinned twice, at 2 versions, and nothing keeps the 2 in step.**

| consumer | pin | what it uses |
| --- | --- | --- |
| `.devcontainer/runner/Dockerfile` | `CICTL_VERSION=v0.1.0` | the `cictl` binary on PATH |
| `pr-review.yml`, both repositories | `CICTL_VERSION=v0.2.0` | `review/review.sh` and its instructions |

The 2 consumers are real and separate: the image needs the compiled contract
tool, and the review job needs the reviewer scripts. Pinning both is correct.
Pinning them at different versions with nothing to notice is not.

**This is not urgent today, and the measurement says so.** The only Go change
between `v0.1.0` and `v0.2.0` is a 9-line comment in `cmd/cictl/run.go`, so the
binary is functionally identical. Everything else in that range is `review/`.

**It becomes a defect on the next change to the Go sources.** Nothing then makes
anyone raise `CICTL_VERSION` in the Dockerfile, the image keeps an older contract
tool, and the gap is invisible because both numbers look deliberate.

Either give the 2 consumers 1 pin, or add a check that fails when the version in
`runner/Dockerfile` is behind the newest tag whose diff touches a `.go` file.


## Resolved

Resolved items stay in the ledger above, marked ✅ with the PR that captured them.
So far: **D41** (#148); **D1** (#29), **D3** (#30), **D4** (#32), **D5** (#32), **D6** (#33 +
workspaces#1), **D7** (#34), **D8** (#34); **D2** (#40); **D5** (#32, #36-#38,
login verified).
