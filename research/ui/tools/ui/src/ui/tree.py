"""ui.tree — the CONTRACT stage's reference implementation (LAYOUT-MATH
companion: DENSE-UI stage 3). One parameter tree, both sides talk to it.

- set(addr, value, source) — clamps, notifies, forwards to the adapter with a
  generation token. source in {user, device, preset, automation, test}; undo
  and echo handling key off it (a device echo must never enter undo).
- Three-value sync per address: local (optimistic), confirmed (last device
  ack), pending token. Echo suppression is BY TOKEN, never value comparison —
  a device that quantizes must not cause loops, and an UNSOLICITED readback
  is adopted and repainted (hiding a disagreement hides a range bug).
- Streams live in their own namespace: set() on one throws; each carries a
  staleness deadline and reports stale rather than a plausible zero.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

SOURCES = {"user", "device", "preset", "automation", "test"}


class TreeError(RuntimeError):
    pass


@dataclass
class Desc:
    addr: str
    kind: str = "float"  # float|int|bool|enum|stream
    min: float | None = None
    max: float | None = None
    default: Any = None
    enum: list | None = None
    staleness_s: float | None = None  # streams only


@dataclass
class _State:
    local: Any = None
    confirmed: Any = None
    pending_token: int | None = None
    last_stream_t: float | None = None


class Tree:
    def __init__(self, descs: list[Desc], adapter=None, now: Callable[[], float] | None = None):
        self._d = {d.addr: d for d in descs}
        self._s = {d.addr: _State(local=d.default, confirmed=d.default) for d in descs}
        self._adapter = adapter
        self._subs: dict[str, list] = {}
        self._undo: list[tuple[str, Any]] = []
        self._token = 0
        self._now = now or (lambda: 0.0)
        self._engaged: set[str] = set()
        self._deferred: dict[str, tuple] = {}

    def desc(self, addr: str) -> Desc:
        try:
            return self._d[addr]
        except KeyError:
            raise TreeError(f"unknown parameter address {addr!r}") from None

    def get(self, addr: str) -> Any:
        return self._s[self.desc(addr).addr].local

    def confirmed(self, addr: str) -> Any:
        return self._s[self.desc(addr).addr].confirmed

    def pending(self, addr: str) -> bool:
        return self._s[self.desc(addr).addr].pending_token is not None

    def subscribe(self, addr: str, fn) -> Callable[[], None]:
        self.desc(addr)
        self._subs.setdefault(addr, []).append(fn)
        return lambda: self._subs[addr].remove(fn)

    def _notify(self, addr: str) -> None:
        for fn in list(self._subs.get(addr, [])):
            fn(self._s[addr].local, addr)

    # -- settable path ------------------------------------------------------
    def set(self, addr: str, value: Any, source: str) -> Any:
        d = self.desc(addr)
        if source not in SOURCES:
            raise TreeError(f"unknown source {source!r}")
        if d.kind == "stream":
            raise TreeError(f"{addr} is a stream — set() must throw (RoT 3)")
        if d.kind in ("float", "int") and d.min is not None:
            value = min(max(value, d.min), d.max)
        if d.kind == "int":
            value = round(value)
        st = self._s[addr]
        if source == "user":
            self._undo.append((addr, st.local))
        st.local = value
        self._notify(addr)
        if self._adapter is not None and source != "device":
            self._token += 1
            st.pending_token = self._token
            self._adapter.apply(addr, value, self._token)
        return value

    def engage(self, addr: str) -> None:
        """While a control is engaged (drag in progress), device pushes to its
        address QUEUE instead of moving the value under the cursor (§8)."""
        self.desc(addr)
        self._engaged.add(addr)

    def release(self, addr: str) -> None:
        self._engaged.discard(addr)
        if addr in self._deferred:
            value, token = self._deferred.pop(addr)
            self.device_report(addr, value, token)

    def resync(self) -> None:
        """Adopt the adapter's full truth (reconnect path, §12): every pending
        clears, every value becomes device truth."""
        if self._adapter is None or not hasattr(self._adapter, "readAll"):
            raise TreeError("resync needs an adapter with readAll()")
        state = self._adapter.readAll()
        for addr, value in state.items():
            self.device_report(addr, value, None)
        # A still-pending address the device did not report never received the
        # write: it was LOST in the disconnect. Reverting to confirmed truth is
        # the honest outcome — keeping the optimistic value would show a
        # setpoint the hardware does not hold.
        for addr, st in self._s.items():
            if st.pending_token is not None and addr not in state:
                st.local = st.confirmed
                st.pending_token = None
                self._notify(addr)

    def device_report(self, addr: str, value: Any, token: int | None) -> None:
        """Inbound from the adapter. Token matching pending -> silent confirm
        (echo suppression BY TOKEN). No/unknown token -> the device disagrees:
        adopt and repaint."""
        if addr in self._engaged:
            self._deferred[addr] = (value, token)  # never move under the cursor
            return
        st = self._s[self.desc(addr).addr]
        if token is not None and token == st.pending_token:
            st.confirmed = value
            st.pending_token = None
            return
        st.local = st.confirmed = value
        st.pending_token = None
        self._notify(addr)

    def undo_stack(self) -> list:
        return list(self._undo)

    # -- streams ------------------------------------------------------------
    def stream_report(self, addr: str, value: Any) -> None:
        d = self.desc(addr)
        if d.kind != "stream":
            raise TreeError(f"{addr} is not a stream")
        st = self._s[addr]
        st.local = st.confirmed = value
        st.last_stream_t = self._now()
        self._notify(addr)

    def stale(self, addr: str) -> bool:
        d = self.desc(addr)
        if d.kind != "stream" or d.staleness_s is None:
            raise TreeError(f"{addr} has no staleness contract")
        st = self._s[addr]
        if st.last_stream_t is None:
            return True  # never seen: unknown, not zero
        return (self._now() - st.last_stream_t) > d.staleness_s
