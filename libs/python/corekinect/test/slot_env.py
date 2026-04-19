"""Single source of truth for parsing slot-attribution env vars.

Before this module, four separate functions parsed ``MTIB_HOSTS`` /
``SLOT_FILTER`` / ``SLOT_SNRS`` / ``SLOT_DEVICE_IDS``:
``autoconf._seed_reporter_slot_serials``,
``autoconf._maybe_register_slot_parallel``,
``slot.FixtureContext._from_hosts_env``, and ``slot.get_slot_ids_from_env``.
Each drifted from the others (off-by-one on SLOT_FILTER, different
whitespace handling, different empty-var behaviour). One source of
truth eliminates that drift.

:func:`resolve_slot_bindings` reads the environment and produces an
ordered ``list[SlotBinding]`` — one per *filtered* slot. The caller
(autoconf at collection, slot.py at fixture setup) applies this list
however it needs: as item stash, as SlotContext seeds, or as a keyed
dict via :func:`slot_bindings_by_index`.

Design choices
--------------

* **Pure function.** No logging, no env mutation, no MTIB I/O.
  Easy to unit test; repeatable across calls.
* **Empty env is not an error.** Single-slot validation runs don't
  set ``MTIB_HOSTS``; returning ``[]`` lets the caller decide
  whether that's a misconfiguration or the expected path.
* **Global ``slot_index`` is preserved across filtering.** Panel
  runs that use ``SLOT_FILTER=4`` must produce a binding with
  ``slot_index=4``, not ``slot_index=0`` — otherwise attribution on
  the backend (RunTarget keyed by ``(runId, slotIndex)``) breaks.
* **SNR/device_id count mismatch is tolerated.** Matches the legacy
  ``_split_env`` behaviour: if counts don't line up, drop the
  metadata silently. Operators see the fields come back as ``None``
  and can retry; the alternative (hard failure) would brick panels
  with blank slots.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional

from corekinect.test.slot_binding import SlotBinding


_DEFAULT_MTIB_PORT = 50053


# ────────────────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────────────────


def resolve_slot_bindings() -> List[SlotBinding]:
    """Read env vars and return one :class:`SlotBinding` per active slot.

    Returns
    -------
    list[SlotBinding]
        Ordered by ``slot_index``. Empty when ``MTIB_HOSTS`` is unset.

    Environment variables
    ---------------------
    ``MTIB_HOSTS``
        Comma-separated MTIB addresses (``"host"`` or ``"host:port"``).
        Position in this list determines ``slot_index``.
    ``SLOT_FILTER``
        Optional comma-separated slot indices to include
        (e.g. ``"0,1,2,3"`` for panel, ``"4"`` for standalone).
        Absent = include every host.
    ``SLOT_SNRS``
        Optional comma-separated serial numbers, aligned with the
        *filtered* slot sequence (one entry per included slot).
    ``SLOT_DEVICE_IDS``
        Optional comma-separated device IDs, aligned with the
        *filtered* slot sequence.
    ``MTIB_PORT``
        Default port to use when an address in ``MTIB_HOSTS`` has no
        explicit ``:port``. Defaults to 50053.
    """
    raw_hosts = os.environ.get("MTIB_HOSTS", "").strip()
    if not raw_hosts:
        return []

    default_port = _read_port("MTIB_PORT", _DEFAULT_MTIB_PORT)

    # Preserve the original positional index even after dropping empties.
    addresses: List[tuple[int, str]] = []
    for raw_idx, addr in enumerate(raw_hosts.split(",")):
        stripped = addr.strip()
        if stripped:
            addresses.append((raw_idx, stripped))

    allowed_indices = _parse_slot_filter()
    if allowed_indices is not None:
        addresses = [(i, a) for (i, a) in addresses if i in allowed_indices]

    snrs = _split_csv(os.environ.get("SLOT_SNRS"), expected=len(addresses))
    device_ids = _split_csv(os.environ.get("SLOT_DEVICE_IDS"), expected=len(addresses))

    bindings: List[SlotBinding] = []
    for filtered_idx, (slot_idx, address) in enumerate(addresses):
        host, port = _parse_address(address, default_port)
        bindings.append(SlotBinding(
            slot_index=slot_idx,
            serial_number=snrs[filtered_idx] if snrs else None,
            device_id=device_ids[filtered_idx] if device_ids else None,
            mtib_host=host,
            mtib_port=port,
        ))
    return bindings


def slot_bindings_by_index(bindings: List[SlotBinding]) -> Dict[int, SlotBinding]:
    """Index a binding list by ``slot_index`` for O(1) lookup.

    Raises ``ValueError`` on duplicate slot_index — two bindings for
    the same slot is always a bug (double-parsed env, corrupted
    fixture config).
    """
    out: Dict[int, SlotBinding] = {}
    for b in bindings:
        if b.slot_index in out:
            raise ValueError(
                f"duplicate slot_index={b.slot_index}: {out[b.slot_index]!r} "
                f"and {b!r}"
            )
        out[b.slot_index] = b
    return out


# ────────────────────────────────────────────────────────────────────────
# Internals
# ────────────────────────────────────────────────────────────────────────


def _parse_slot_filter() -> Optional[set[int]]:
    """Return the allowed slot indices from ``SLOT_FILTER``, or ``None`` for all."""
    raw = os.environ.get("SLOT_FILTER", "").strip()
    if not raw:
        return None
    return {int(x.strip()) for x in raw.split(",") if x.strip()}


def _parse_address(addr: str, default_port: int) -> tuple[str, int]:
    """Parse ``"host"`` or ``"host:port"`` → ``(host, port)``."""
    if ":" in addr:
        host, port_str = addr.rsplit(":", 1)
        return host, int(port_str)
    return addr, default_port


def _read_port(var: str, default: int) -> int:
    raw = os.environ.get(var, "").strip()
    return int(raw) if raw else default


def _split_csv(raw: Optional[str], *, expected: int) -> List[str]:
    """Split a comma-separated env var into ``expected``-long list or [].

    Mirrors the legacy ``_split_env`` contract: count mismatch →
    empty list (so callers fall back to ``None`` fields). Whitespace
    around each value is stripped; empty items after stripping are
    dropped before the count check.
    """
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    parts = [p for p in parts if p]
    if len(parts) != expected:
        return []
    return parts
