"""Collection-time slot attribution for pytest items.

Manufacturing and multi-slot validation runs parametrize every
``def test_*`` by slot index — pytest produces nodeids like
``test_01_uvlo_off_state[slot-2]``. The backend's ``RunTarget`` rows
are keyed by ``(runId, slotIndex)`` and every report payload must
name its target.

This module offers a single, immutable record for that attribution:
:class:`SlotBinding`. The autoconf plugin stashes one on every
parametrized item at collection time via :data:`SLOT_BINDING_KEY`,
and the reporter reads it when firing any payload. No regex at hook
time, no thread-local propagation, no fixture-side-effect races.

Why frozen + hashable
---------------------

The binding is shared across threads (the ``slot_parallel`` plugin
runs slot parametrizations on worker threads). Immutability
eliminates any "which thread sees what version" question and lets
callers cache bindings in dicts/sets safely.

Usage
-----

Producer (autoconf, at collection):

    from corekinect.test.slot_binding import SlotBinding, SLOT_BINDING_KEY
    binding = SlotBinding(slot_index=2, serial_number="095H", ...)
    item.stash[SLOT_BINDING_KEY] = binding

Consumer (reporter, per-item payload):

    binding = item.stash.get(SLOT_BINDING_KEY)
    payload = {"testName": ...}
    if binding:
        payload["slotIndex"] = binding.slot_index
        if binding.serial_number:
            payload["deviceSerial"] = binding.serial_number

Use :func:`attach_binding` / :func:`get_binding` instead of touching
``item.stash`` directly if the call site benefits from the explicit
API.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pytest


@dataclass(frozen=True)
class SlotBinding:
    """Immutable record tying a pytest item to the slot it targets.

    Attributes
    ----------
    slot_index
        Global slot index — matches ``RunTarget.slotIndex`` on the
        backend and the ``[slot-N]`` suffix in the pytest nodeid.
    serial_number
        J-Link probe serial (aka "SNR"). Present when
        ``SLOT_SNRS`` was provided; ``None`` otherwise.
    device_id
        Device hex ID (CoreOps). Present when ``SLOT_DEVICE_IDS`` was
        provided; ``None`` otherwise.
    mtib_host
        Hostname or IP of the MTIB server that controls this slot.
    mtib_port
        gRPC port on the MTIB server (default 50053).
    """

    slot_index: int
    serial_number: Optional[str]
    device_id: Optional[str]
    mtib_host: str
    mtib_port: int


# Pytest stash key used to attach a :class:`SlotBinding` to an item.
# ``pytest.StashKey`` is the pytest-idiomatic way to add typed
# per-item metadata without polluting the item's public attributes.
SLOT_BINDING_KEY: pytest.StashKey[SlotBinding] = pytest.StashKey()


def attach_binding(item: pytest.Item, binding: SlotBinding) -> None:
    """Stash ``binding`` on ``item`` under :data:`SLOT_BINDING_KEY`.

    Idempotent: attaching the same binding twice is a no-op;
    attaching a different binding raises ``ValueError`` to surface a
    bug (two collection-time passes disagreeing on attribution).
    """
    existing = item.stash.get(SLOT_BINDING_KEY, None)
    if existing is not None and existing != binding:
        raise ValueError(
            f"item {item.nodeid!r} already has a different SlotBinding "
            f"({existing!r}); refusing to overwrite with {binding!r}"
        )
    item.stash[SLOT_BINDING_KEY] = binding


def get_binding(item: pytest.Item) -> Optional[SlotBinding]:
    """Return the :class:`SlotBinding` on ``item``, or ``None`` if absent.

    Absent bindings are the norm for single-slot validation runs
    whose items aren't parametrized by slot. Callers must handle the
    ``None`` path explicitly (typically: skip slotIndex, let the
    backend's single-target fallback resolve).
    """
    return item.stash.get(SLOT_BINDING_KEY, None)
