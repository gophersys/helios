# Infrastructure Debt Register

A living record of state that exists in the running cluster / on hosts / in
PVCs but is **not yet fully captured declaratively in this repo**, plus the
engineering agreement we hold new work to. The goal is zero invisible state:
anything load-bearing must be reproducible from git, or explicitly recorded
here as accepted-imperative with recreation steps.

Status legend: 🔴 open (reliability/security risk) · 🟠 open (reproducibility) ·
🟡 minor / accepted · ✅ resolved (captured declaratively).

Last updated: 2026-07-06.

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

### D2 🟡 Prowlarr indexer/download-client config not reproducible — DOCUMENTED (PR #31)
Prowlarr's config lives in its PVC SQLite DB (UI-managed, not GitOps-able).
**Resolved-as-runbook:** `apps/music/prowlarr/SETUP.md` — the reproducible
source of truth for indexers + the qBittorrent download client, with exact
values. Headless API automation was attempted and rejected as fragile: Prowlarr
2.4.0's download-client test NREs against qBittorrent 5.2.2, and indexer-add
hangs on a synchronous site-test (`?forceSave=true` skips neither). Both work in
the Web UI. **Remaining (honest):** full search→grab automation needs the
download client wired via the UI, or qBittorrent pinned to a Prowlarr-compatible
version (remediation in SETUP.md). Search itself works once indexers are added.

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

### D5 ✅ Default / unset credentials — RESOLVED (PR #32)
Both now have strong random passwords stored in Vaultwarden:
- **qBittorrent** — `shared/qbittorrent/webui`; set via API (verified: the WebUI
  password hash changed, `admin`/`admin`-era default gone). External login only;
  in-cluster is subnet-bypassed.
- **Filebrowser** — `shared/filebrowser/admin`; set by
  `apps/music/filebrowser/reset-admin/job.yaml` from the `filebrowser-admin`
  Secret. `admin`/`admin` verified rejected (403). A successful-login re-check is
  pending the app's login rate-limiter cooldown (tripped during setup) — noted
  for the final verification pass.
Recreation for both: `docs/runtime-secrets.md`.

### D6 🟡 Workspaces create/destroy unimplemented
`POST`/`DELETE /api/workspaces` return `501 gitops automation pending`. Feature,
not a bug — tracked as task 6 (full TDD: create/remove `apps/embedded/envs/<name>`
via a GitHub PR using a scoped bot PAT).

### D7 🟡 Documentation drift
`docs/` predates today's media/portal/workspaces build-out and the live
imperative installs (ingress-nginx, cloudflared). No authoritative
"what runs in each namespace and why" reference exists.
**Resolution:** task 7 — full namespace-by-namespace documentation round.

### D8 🟡 Missing referenced doc
`docs/migration-homelab-to-idp.md` is referenced from `identity.yaml` and
`README.md` but absent. Either restore it or update the references.
**Resolution:** folded into task 7.

---

## Resolved

Resolved items stay in the ledger above, marked ✅ with the PR that captured
them. So far: **D1** (#29), **D3** (#30), **D4** (#32), **D5** (#32); **D2** documented (#31).
