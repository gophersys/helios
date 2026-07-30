"""Nets: named electrical connections between pins."""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from .component import Pin


class Net:
    """A named net. Connect pins with `net.connect(a, b, ...)`.

    Connecting a pin that is already on a *different* net is an error —
    nets are not silently merged; that is almost always a design mistake.
    """

    def __init__(self, name: str, *, group: str | None = None) -> None:
        if not name:
            raise ValueError("Net name must be non-empty")
        self.name = name
        self.group = group          # bus grouping hint, e.g. "SPI0"
        self.pins: list[Pin] = []

    def connect(self, *items: "Pin | Iterable[Pin]") -> "Net":
        """Attach pins (or iterables of pins) to this net. Idempotent."""
        for item in items:
            pins = [item] if hasattr(item, "spec") else list(item)
            for p in pins:
                if p.net is self:
                    continue
                if p.net is not None:
                    raise ValueError(
                        f"Pin {p.owner_ref}.{p.name} (pad {p.pad}) is already on "
                        f"net {p.net.name!r}; cannot also join {self.name!r}"
                    )
                p.net = self
                self.pins.append(p)
        return self

    def __repr__(self) -> str:
        return f"Net({self.name!r}, pins={len(self.pins)})"
