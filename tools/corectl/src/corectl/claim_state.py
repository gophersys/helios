"""DEV_HOLD claim state — the on-disk record of an active fixture claim.

A claim is a lease on real hardware (a fixture or a set of nodes) held by
the developer for the duration of a local TDD session. The CLI writes a
state file at ``.concord-claim.json`` next to the test project and forks
a heartbeat daemon to keep the lease alive against the backend.

The state file is the single source of truth for ``corectl test run`` —
when it exists, ``run`` injects ``MTIB_HOST`` / ``MTIB_HOSTS`` env vars
into the pytest subprocess so the tests target the held slots. When it's
missing, ``run`` falls back to whatever the operator's shell set.

State file shape::

    {
      "id": "clm_...",
      "fixtureId": "fix_abc",          // null in node-mode
      "slotBindings": [
        {"label": "slot1", "nodeId": "node_xyz", "mtibHost": "10.4.45.38:50053"}
      ],
      "hardCeilingAt": "2026-05-22T02:00:00Z",
      "heartbeatPid": 12345,
      "createdAt": "2026-05-21T17:00:00Z"
    }

Only immutable values live on disk. ``expiresAt`` is sliding
(``lastHeartbeatAt + 5 min``) and changes with every heartbeat — caching
it locally would create a "state file says alive, backend already
expired" drift class. ``corectl test status`` fetches that field live
from the backend instead. ``hardCeilingAt`` IS immutable (set once at
claim time, never moves) so it stays on disk.

Why a flat JSON file (not YAML, not a .corectl/ dir):

* JSON parses without an extra dep — the daemon must be importable on a
  bare Python install. corectl already bundles PyYAML for ``concord.yaml``
  but the daemon path stays free of that.
* One file = atomic ``Path.unlink`` for the "tell the daemon to stop"
  signal. No directory teardown races.
* ``.concord-claim.json`` next to ``concord.yaml`` keeps the lease
  scoped to the project the dev is working in — multiple checkouts can
  each hold their own claims.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


STATE_FILENAME = ".concord-claim.json"
LOG_FILENAME = ".concord-claim.log"


def state_path(project_dir: Path) -> Path:
    """Path to the claim state file inside ``project_dir``."""
    return project_dir / STATE_FILENAME


def log_path(project_dir: Path) -> Path:
    """Path to the heartbeat daemon log inside ``project_dir``."""
    return project_dir / LOG_FILENAME


def load(project_dir: Path) -> Optional[Dict[str, Any]]:
    """Return the parsed state, or None when no state file exists.

    Parse errors are raised — a corrupt file is a real problem the dev
    needs to see (probably hand-edited, or two writers raced). The
    daemon and the CLI both treat None as "no active claim" and a raise
    as "stop and surface this".
    """
    path = state_path(project_dir)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(project_dir: Path, state: Dict[str, Any]) -> None:
    """Write the state file atomically (write-temp-then-rename).

    The atomic swap matters because the daemon polls for file existence
    every loop — a partial write would let the daemon read a half-empty
    file. ``os.replace`` is atomic on POSIX and on NTFS, so this works
    on every host where corectl runs.
    """
    path = state_path(project_dir)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def remove(project_dir: Path) -> bool:
    """Delete the state file. Returns True if it existed, False otherwise.

    Idempotent — the unclaim flow may be called after a daemon exit
    already cleaned up, and the CLI must not raise in that case.
    """
    path = state_path(project_dir)
    try:
        path.unlink()
        return True
    except FileNotFoundError:
        return False


def slot_hosts(state: Dict[str, Any]) -> List[str]:
    """Extract MTIB host strings from a state dict, in slot order.

    Used by ``corectl test run`` to build ``MTIB_HOST`` (single-slot) or
    ``MTIB_HOSTS`` (multi-slot, comma-joined).
    """
    bindings = state.get("slotBindings") or []
    return [b["mtibHost"] for b in bindings if b.get("mtibHost")]


def claim_id(state: Dict[str, Any]) -> str:
    """The claim's server-side id."""
    return state["id"]
