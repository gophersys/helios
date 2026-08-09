"""Catalog passives used by the composer, as typed ``src.ecad`` components.

The composer never emits anonymous 2-pin stubs any more: a decoupling cap
is a real ``Device:C`` component with real pads, a real footprint and a
per-instance value, so the layout engine can apply its satellite rule and
the emitted symbol carries a footprint the PCB flow can consume.

ICs come from the generated-part registry (``src.ecad.library``) or the
seed ``chip_library``; only genuinely generic passives live here.
"""

from __future__ import annotations

from src.ecad import Component, FootprintRef, pin

# Short footprint token → installed KiCad footprint (mirrors
# decoupling_gen._DEFAULT_FOOTPRINT_MAP, which speaks the same rule data).
_CAP_FOOTPRINTS: dict[str, str] = {
    "C_0201": "Capacitor_SMD:C_0201_0603Metric",
    "C_0402": "Capacitor_SMD:C_0402_1005Metric",
    "C_0603": "Capacitor_SMD:C_0603_1608Metric",
    "C_0805": "Capacitor_SMD:C_0805_2012Metric",
    "C_1206": "Capacitor_SMD:C_1206_3216Metric",
}


def parse_footprint(raw: str) -> FootprintRef | None:
    """``"Capacitor_SMD:C_0402_1005Metric"`` → FootprintRef (None if empty)."""
    if not raw:
        return None
    if ":" in raw:
        lib, name = raw.split(":", 1)
        return FootprintRef(lib=lib, name=name)
    return FootprintRef(lib="", name=raw)


def cap_footprint(token: str) -> FootprintRef:
    """Resolve a decoupling-rule footprint token to a real footprint ref."""
    full = token if ":" in token else _CAP_FOOTPRINTS.get(token, "")
    return parse_footprint(full) or FootprintRef("Capacitor_SMD",
                                                 "C_0402_1005Metric")


class Capacitor(Component):
    """``Device:C`` — value and footprint are per-instance."""

    part_name = "C"
    lib_id = "Device:C"
    reference_prefix = "C"
    description = "Unpolarized capacitor"
    footprint = FootprintRef("Capacitor_SMD", "C_0402_1005Metric")
    _PIN_SPECS = (
        pin("1", "P1", "passive", "passive"),
        pin("2", "P2", "passive", "passive"),
    )

    def __init__(self, value: str = "100nF",
                 footprint: FootprintRef | None = None) -> None:
        super().__init__()
        self.value = value
        if footprint is not None:
            self.footprint = footprint


class Resistor(Component):
    """``Device:R`` — value and footprint are per-instance."""

    part_name = "R"
    lib_id = "Device:R"
    reference_prefix = "R"
    description = "Resistor"
    footprint = FootprintRef("Resistor_SMD", "R_0402_1005Metric")
    _PIN_SPECS = (
        pin("1", "P1", "passive", "passive"),
        pin("2", "P2", "passive", "passive"),
    )

    def __init__(self, value: str = "10k",
                 footprint: FootprintRef | None = None) -> None:
        super().__init__()
        self.value = value
        if footprint is not None:
            self.footprint = footprint
