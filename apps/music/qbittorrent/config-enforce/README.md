# qbittorrent config-enforce

Keeps the download-critical qBittorrent settings reproducible instead of living
only on the config PVC (see `docs/debt-register.md`, D1).

## Why
qBittorrent must bind to the VPN interface (`tun0`); without it, torrent traffic
leaves via `eth0` and Gluetun's kill-switch silently drops everything. That
setting — plus the in-cluster API auth whitelist — was originally set through
the Web UI and persisted only in `qbittorrent-config`. If that PVC is ever
recreated, downloads break with no obvious cause. This makes the settings
declarative: an initContainer enforces them into `qBittorrent.conf` before
qBittorrent starts.

## Files
- `enforce_qbt.py` — **source of truth.** Idempotent, surgical INI reconciler.
  Exposes `enforce_config(text)` and `REQUIRED`.
- `test_enforce_qbt.py` — the spec. `python3 test_enforce_qbt.py` (9 tests).
- `gen_configmap.py` — renders `../15-config-enforce.configmap.yaml` from
  `enforce_qbt.py`, so the deployed ConfigMap can't drift from the tested code.

## Change workflow
1. Edit `enforce_qbt.py` (adjust `REQUIRED`).
2. `python3 test_enforce_qbt.py` — must be green.
3. Regenerate the ConfigMap:
   `python3 gen_configmap.py > ../15-config-enforce.configmap.yaml`
4. The drift-guard test (`test_committed_configmap_matches_generated`) fails if
   you skip step 3.

The `qbittorrent` Argo app syncs with `directory.recurse: false`, so only the
top-level `*.yaml` deploy — this `config-enforce/` directory (Python + tests)
is never applied to the cluster.
