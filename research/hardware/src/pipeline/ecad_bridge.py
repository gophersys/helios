"""Adapters between the legacy ChipDef/PinDef world and src/ecad.

Lives on the pipeline side so the dependency direction stays
pipeline → ecad, never the reverse.
"""

from __future__ import annotations

import re

from src.ecad import (
    Component,
    ElectricalType,
    FootprintRef,
    PinRole,
    PinSpec,
    UnitDef,
    UnitStrategy,
)

from .symbol_gen import ChipDef, PinDef


def _infer_role(pin: PinDef) -> PinRole:
    name = pin.name.upper()
    group = pin.group.lower()
    # "EP"/"EPAD" is the exposed-pad convention — match it only at a token
    # boundary, or names like EPWM1A (TI C2000), EP0/EP1_IN (USB endpoints)
    # and EPROM_* would be swept in as grounds.
    if (name in ("EP", "EPAD")
            or name.startswith(("GND", "VSS", "PAD_GND", "EP_", "EPAD_"))
            or group == "ground"):
        return PinRole.GROUND
    etype = ElectricalType.parse(pin.electrical_type)
    if etype in (ElectricalType.POWER_IN, ElectricalType.POWER_OUT):
        return PinRole.POWER
    if group == "strapping":
        return PinRole.STRAPPING
    if group in ("uart", "spi", "i2c", "usb", "sdio", "can", "jtag"):
        return PinRole.COMM
    if group == "gpio":
        return PinRole.GPIO
    if group in ("adc", "analog", "touch"):
        return PinRole.ANALOG
    if group == "rf":
        return PinRole.RF
    if group == "control":
        return PinRole.CONTROL
    if etype is ElectricalType.NO_CONNECT:
        return PinRole.NC
    return PinRole.SIGNAL


_GPIO_RE = re.compile(r"GPIO(\d+)(?![0-9A-Za-z])")


def _infer_gpio(pin: PinDef) -> int | None:
    """Logical GPIO number for Component.gpio(n).

    Explicit PinDef.gpio wins; otherwise fall back to the leading GPIOnn in
    the pin name ("GPIO17/ADC2_CH6/DAC1" → 17), which is how the ESP32
    factories name their pins. Parts that don't use that convention (STM32
    PA/PB, ...) simply have no GPIO numbers.
    """
    if pin.gpio is not None:
        return pin.gpio
    m = _GPIO_RE.match(pin.name.upper())
    return int(m.group(1)) if m else None


def _parse_footprint(raw: str) -> FootprintRef | None:
    if not raw:
        return None
    if ":" in raw:
        lib, name = raw.split(":", 1)
        return FootprintRef(lib=lib, name=name)
    return FootprintRef(lib="", name=raw)


def chipdef_to_component(chip: ChipDef) -> Component:
    """Build an anonymous Component subclass from a legacy ChipDef.

    Groups become the explicit unit plan in first-seen order, preserving
    the legacy group→unit derivation exactly.
    """
    specs = tuple(
        PinSpec(
            pad=str(p.number),
            name=p.name,
            etype=ElectricalType.parse(p.electrical_type),
            role=_infer_role(p),
            gpio=_infer_gpio(p),
        )
        for p in chip.pins
    )
    plan: dict[str, list[str]] = {}
    for p in chip.pins:
        plan.setdefault(p.group, []).append(str(p.number))
    unit_plan = tuple(UnitDef(name=g, pads=tuple(pads)) for g, pads in plan.items())

    cls_name = "Bridged_" + (re.sub(r"[^0-9A-Za-z_]", "_", chip.name) or "Anon")
    cls = type(
        cls_name,
        (Component,),
        {
            "part_name": chip.name,
            "lib_id": f"{chip.library}:{chip.name}" if chip.library else chip.name,
            "description": chip.description,
            "footprint": _parse_footprint(chip.footprint),
            "datasheet": chip.datasheet_url or "",
            "unit_strategy": UnitStrategy.EXPLICIT if unit_plan else UnitStrategy.SINGLE,
            "unit_plan": unit_plan,
            "_PIN_SPECS": specs,
        },
    )
    return cls()


def component_to_chipdef(component: Component) -> ChipDef:
    """Project a typed Component back to a legacy ChipDef."""
    unit_names = {}
    for unit in component.units():
        for pad in unit.pads:
            unit_names[pad] = unit.name
    lib = component.lib_id.split(":")[0] if ":" in component.lib_id else ""
    return ChipDef(
        name=component.part_name,
        library=lib,
        description=component.description,
        footprint=component.footprint.lib_id if component.footprint else "",
        datasheet_url=component.datasheet,
        pins=[
            PinDef(
                number=p.pad,
                name=p.name,
                electrical_type=p.etype.value,
                group=unit_names.get(p.pad, ""),
                gpio=p.spec.gpio,
            )
            for p in component.pins
        ],
    )
