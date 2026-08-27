# ck_analyzer — packet analyzer for the iface + cipher libraries

Wireshark-style observability for the CoreKinect protocol stack. Compiled out
entirely unless `CONFIG_CK_PKT_ANALYZER=y` (hooks become empty inlines).

## What it captures
- **iface layer**: transport events (connect/accept/close/errors) and TX/RX
  byte counts per interface.
- **cipher layer**: every encoded/decoded packet header — source/destination
  device, service id, operation id, packet type, payload length, flags, hops.

## Backends (both optional, both Kconfig-gated)
- `CK_PKT_ANALYZER_BACKEND_LOG` — decoded one-liners (+ optional hexdump) on
  the Zephyr log:
  `cipher RX 0x0001->0x0002 svc=12 op=3 RPC len=64 flags=0x01 hops=0`
- `CK_PKT_ANALYZER_BACKEND_NET` — compact JSON events over UDP to a collector
  (`CK_PKT_ANALYZER_NET_HOST:PORT`). Collector can be anything that reads
  JSONL from UDP — see `tools/collector.py` for a reference implementation.

## Wiring
The iface and cipher libraries call the `CK_ANA_*` hook macros at their
capture points. With the analyzer absent or disabled those macros are no-ops,
so neither library grows a hard dependency.
