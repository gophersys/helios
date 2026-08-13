"""densui.fakes — the fake backend Gate 3 demands ("the whole panel runs
headless against a fake backend"). FakeSerial coerces like real firmware,
echoes with the write's token, and can be disconnected mid-flight.
"""

from __future__ import annotations

from collections.abc import Callable


class FakeSerial:
    """Adapter + device in one: quantizes configured addresses (a firmware
    register that rounds), echoes every accepted write with its token, drops
    everything while disconnected."""

    def __init__(self, tree_report: Callable, quantize: dict[str, float] | None = None):
        self._report = tree_report
        self._q = quantize or {}
        self.connected = True
        self.applied: list[tuple[str, object, int]] = []

    def apply(self, addr: str, value, token: int) -> None:
        if not self.connected:
            return  # a dead link acks nothing
        if addr in self._q:
            step = self._q[addr]
            value = round(round(value / step) * step, 10)
        self.applied.append((addr, value, token))
        self._report(addr, value, token)

    def readAll(self) -> dict:
        """The device's full truth: last accepted value per address."""
        state: dict = {}
        for addr, value, _tok in self.applied:
            state[addr] = value
        return state

    def push_unsolicited(self, addr: str, value) -> None:
        """The device disagreeing on its own (knob on the bench, reset...)."""
        self._report(addr, value, None)
