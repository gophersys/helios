# qbittorrent config-enforce

This keeps the qBittorrent settings that the downloads depend on reproducible.
Without it they live only on the config PVC. See `docs/debt-register.md`, D1.

## Why
qBittorrent must bind to the VPN interface `tun0`. Without that bind, the torrent
traffic leaves through `eth0`, and the kill-switch of Gluetun drops all of it
with no message. That setting, and the in-cluster allowlist for the API
authentication, were originally set through the Web UI, and they persisted only
in `qbittorrent-config`. If somebody recreates that PVC, the downloads stop and
the cause is not visible. This directory makes the settings declarative: an
initContainer enforces them in `qBittorrent.conf` before qBittorrent starts.

## Files
- `enforce_qbt.py` — **the source of truth.** It is an idempotent INI reconciler
  that changes only the keys it must change. It exposes `enforce_config(text)`
  and `REQUIRED`.
- `test_enforce_qbt.py` — the specification. Run `python3 test_enforce_qbt.py`.
  It has 9 tests.
- `gen_configmap.py` — renders `../15-config-enforce.configmap.yaml` from
  `enforce_qbt.py`, so that the deployed ConfigMap cannot differ from the tested
  code.

## How to change it
1. Edit `enforce_qbt.py` and adjust `REQUIRED`.
2. Run `python3 test_enforce_qbt.py`. Every test must pass.
3. Generate the ConfigMap again:
   `python3 gen_configmap.py > ../15-config-enforce.configmap.yaml`
4. The drift-guard test `test_committed_configmap_matches_generated` fails if you
   skip step 3.

The `qbittorrent` Argo app syncs with `directory.recurse: false`, so only the
top-level `*.yaml` files deploy. This `config-enforce/` directory, with the
Python code and the tests, never reaches the cluster.
