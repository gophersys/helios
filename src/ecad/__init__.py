"""ecad — the typed electronic design model.

Canonical way to express a design in Python:

    from src.ecad import Design, Net

    mcu, gps = ESP32_S3_WROOM_1(), NEO_M9N()
    d = Design("tracker")
    d.add(mcu, gps)
    Net("3V3").connect(mcu.V3V3, gps.VCC)
    Net("GPS_TX").connect(mcu.gpio(17), gps.pin("RX"))
    assert d.check_ok()

`src/pipeline/` (the corpus/legacy layer) imports this package; never the
reverse.
"""

from .component import Component, Pin, sanitize_pin_name
from .design import Design
from .model import (
    ElectricalType,
    FootprintRef,
    Issue,
    PinRole,
    PinSpec,
    SourcingInfo,
    UnitDef,
    UnitStrategy,
    pin,
)
from .net import Net
from .symbol import PlacedPin, Side, SymbolModel, SymbolUnit

__all__ = [
    "Component", "Design", "ElectricalType", "FootprintRef", "Issue", "Net",
    "Pin", "PinRole", "PinSpec", "PlacedPin", "Side", "SourcingInfo",
    "SymbolModel", "SymbolUnit", "UnitDef", "UnitStrategy", "pin",
    "sanitize_pin_name",
]
