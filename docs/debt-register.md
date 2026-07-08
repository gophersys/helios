# Infrastructure Debt Register

A living record of state that exists in the running cluster / on hosts / in
PVCs but is **not yet fully captured declaratively in this repo**, plus the
engineering agreement we hold new work to. The goal is zero invisible state:
anything load-bearing must be reproducible from git, or explicitly recorded
here as accepted-imperative with recreation steps.

Status legend: 🔴 open (reliability/security risk) · 🟠 open (reproducibility) ·
🟡 minor / accepted · ✅ resolved (captured declaratively).

Last updated: 2026-07-07 (full cluster audit — see docs/audit-2026-07.md).

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
**Resolved-as-doc:** `docs/runtime-secrets.md` inventories every imperative
k8s Secret (`gluetun-wireguard`, `homepage-secrets`, `filebrowser-admin`,
`operator-oauth`) with its Vaultwarden source and exact recreation command, and
explains why single-value logins stay imperative (the ESO store returns an
item's `notes` blob, not individual fields).

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

### D9 🟢 Version drift on imperative platform components — LARGELY RESOLVED
Full audit 2026-07-07 (`docs/audit-2026-07.md`). Progress:
- ✅ **cloudflared** 2025.5.0 → 2026.6.1 + hardened (non-root, RO-rootfs, drop-ALL, seccomp).
- ✅ **cert-manager** 1.16.3 → 1.20.3 (certs undisrupted; ships the DNS-01 cleanup fix — D10).
- ✅ **MetalLB** 0.14.9 → 0.16.1 (VIP stayed up).
- ✅ **ingress-nginx** 1.12.1 → 1.15.1 (all 7 routes stayed up).
- ⬜ **Tempo** 2.9→3.0 + observability minors — these live in the **eden-observability
  Helm chart** (`obs` release, currently in **failed** helm state), so they're the Eden
  agent's domain, not an imperative upgrade. Flag for that chart's owner.
- ✅ **Longhorn** 1.7.2 → **1.12.0** (EOL cleared). Backup target set up (in-cluster MinIO,
  `apps/minio/`), all 4 volumes backed up, staged 5-minor upgrade done autonomously with zero
  data loss / downtime. See `docs/runbooks/longhorn-upgrade.md` (incl. the client-side-CRD lesson).

### D10 ✅ cert-manager DNS-01 cleanup — RESOLVED
The 5 orphaned `_acme-challenge` TXT records were deleted from Cloudflare, and the
cleanup fix ships with the cert-manager 1.20.3 upgrade (D9). Watch the next renewal
to confirm no new orphans.

### D11 🟡 bw-serve cannot run non-root (image limitation)
The vault bridge is hardened to caps-drop + seccomp, but the
`charlesthomas/bitwarden-cli` image's entrypoint crashloops under
non-root/read-only-rootfs (verified). Full hardening needs a vendored non-root
bitwarden-cli image. Accepted ceiling for now.

## Resolved

Resolved items stay in the ledger above, marked ✅ with the PR that captured
them. So far: **D1** (#29), **D3** (#30), **D4** (#32), **D5** (#32), **D6** (#33 + workspaces#1), **D7** (#34), **D8** (#34); **D2** (#40); **D5** (#32, #36-#38, login verified).
