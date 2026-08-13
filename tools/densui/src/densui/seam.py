"""densui.seam — coalescing at the seam, never in the widget (DENSE-UI §5/§9).

Wraps an adapter: writes buffer last-write-wins per address and forward on
flush() (one frame). The queue is bounded by construction — one slot per
address — so 120 Hz of drag events into a 9600-baud link decimates here and
the widget never knows.
"""

from __future__ import annotations


class Seam:
    def __init__(self, adapter):
        self._adapter = adapter
        self._buf: dict[str, tuple[object, int]] = {}
        self.forwarded = 0

    def apply(self, addr: str, value, token: int) -> None:
        self._buf[addr] = (value, token)  # last write wins, bounded by addr count

    def flush(self) -> int:
        n = 0
        for addr, (value, token) in self._buf.items():
            self._adapter.apply(addr, value, token)
            n += 1
        self._buf.clear()
        self.forwarded += n
        return n

    def depth(self) -> int:
        return len(self._buf)
