"""circuits — parameterized, provenance-carrying circuit topology blocks.

A *block* is a pure function that takes a :class:`~src.ecad.design.Design`
plus pins/nets, adds components and nets to it, and returns a
:class:`Block` handle naming what it built and citing where the values came
from.

    from src.ecad import Design
    from src.ecad.circuits import decoupling, en_reset_rc
    from src.ecad.library import get

    d = Design("mcu")
    mcu = get("ESP32-S3-WROOM-1")()
    decoupling(d, mcu, "+3V3", "GND")
    en_reset_rc(d, mcu.EN, "+3V3", "GND")
    assert d.check_ok()

Blocks never invent a part: every component comes from the generated-part
registry (``src.ecad.library``) or, transitionally, from the typed passives
the composer already ships. A block whose part does not exist yet raises
:class:`MissingPartError` naming the ``lib_id`` a future stage must add.
"""

from .blocks import (
    Block,
    LedResistor,
    MissingPartError,
    Provenance,
    decoupling,
    e24_nearest,
    en_reset_rc,
    format_ohms,
    indicator_led,
    ldo_regulator,
    led_series_resistor,
    pull_resistor,
    push_button,
)

__all__ = [
    "Block",
    "LedResistor",
    "MissingPartError",
    "Provenance",
    "decoupling",
    "e24_nearest",
    "en_reset_rc",
    "format_ohms",
    "indicator_led",
    "ldo_regulator",
    "led_series_resistor",
    "pull_resistor",
    "push_button",
]
