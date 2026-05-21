"""Project-level pytest configuration.

The framework's autoconf plugin wires slot binding, MTIB clients,
asset-set fixtures, report helpers, and stage markers. The only
addition here is a local-dev convenience: if a developer ran
``corectl test claim`` and we're running ``pytest`` directly (i.e.
not via ``corectl test run``), pull the slot bindings out of the
on-disk ``.concord-claim.json`` so the autoconf ``slot`` fixture
sees ``MTIB_HOST`` / ``MTIB_HOSTS`` without an extra shell step.

``corectl test run`` performs the same injection upstream of pytest;
this hook is a belt-and-suspenders for the bare ``pytest`` invocation.
Ambient env vars always win — if you set ``MTIB_HOST`` by hand we
respect it.

Keep this file thin. Don't paper over framework issues by adding
project-level hooks here.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

pytest_plugins = ["corekinect.test.autoconf"]


def pytest_configure(config):
    """Inject MTIB_HOST(S) from .concord-claim.json when present.

    No-op when:
      * the claim state file doesn't exist (no ``corectl test claim``
        was run, or it was already released);
      * ``MTIB_HOST`` / ``MTIB_HOSTS`` is already set in the environment
        (ambient env, e.g. ``corectl test run``, wins);
      * the claim file is malformed — we don't want a stale or partially
        written claim to crash the pytest startup; the autoconf plugin
        will skip with a clean message if the bindings still aren't
        resolvable.
    """
    claim_file = Path(__file__).parent / ".concord-claim.json"
    if not claim_file.exists():
        return
    if os.environ.get("MTIB_HOST") or os.environ.get("MTIB_HOSTS"):
        return
    try:
        claim = json.loads(claim_file.read_text())
        hosts = [b["mtibHost"] for b in claim["slotBindings"]]
    except (json.JSONDecodeError, KeyError, OSError, TypeError):
        return
    if not hosts:
        return
    if len(hosts) == 1:
        os.environ["MTIB_HOST"] = hosts[0]
    else:
        os.environ["MTIB_HOSTS"] = ",".join(hosts)
    if "id" in claim:
        os.environ.setdefault("CONCORD_CLAIM_ID", str(claim["id"]))
