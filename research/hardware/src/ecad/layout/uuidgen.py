"""Deterministic UUIDs for schematic emission.

Same design name + same stable path → same UUID, every run. This is what
makes emitted files byte-identical across runs (a hard requirement for
golden-file tests and reviewable diffs).
"""

from __future__ import annotations

import uuid


class UuidGen:
    def __init__(self, design_name: str) -> None:
        self._ns = uuid.uuid5(uuid.NAMESPACE_DNS, f"ecad.design.{design_name}")

    def for_path(self, *parts: str) -> str:
        """UUID for a stable slash-joined path, e.g. ("mcu.kicad_sch", "U1#2",
        "pin", "14")."""
        return str(uuid.uuid5(self._ns, "/".join(parts)))
