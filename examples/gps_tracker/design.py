"""GPS tracker — ESP32-S3-WROOM-1 + u-blox NEO-6M over UART, LDO from battery.

This is the example that `tests/test_e2e_gps_tracker.py` validates end to end:
a `DesignSpec` goes into `compose_design`, and out comes a hierarchical KiCad
project (root + power + mcu + gps) whose ERC has zero errors and whose exported
netlist equals `Design.intended_netlist()`.

Example module contract — see `examples/README.md`:
    TITLE / SUMMARY   optional module-level strings
    build()           REQUIRED, returns a composer GeneratedProject
    blocks()          optional, src.ecad.circuits blocks to cite provenance for
"""

from __future__ import annotations

from src.pipeline.composer import (
    DesignSpec,
    GeneratedProject,
    PeripheralSpec,
    PowerSpec,
    compose_design,
)

TITLE = "GPS Tracker"
SUMMARY = (
    "ESP32-S3-WROOM-1 talking to a u-blox NEO-6M over UART, running off a "
    "battery through an LDO. The smallest design that exercises the whole "
    "spec -> typed model -> layout -> hierarchical schematic path."
)


def spec() -> DesignSpec:
    """The design intent, as a spec — the composer derives everything else."""
    return DesignSpec(
        name="GPS_Tracker",
        mcu_family="ESP32-S3",
        mcu_chip="ESP32-S3-WROOM-1",
        peripherals=[
            PeripheralSpec(name="GPS", chip="NEO-6M", interface="UART"),
        ],
        power=PowerSpec(input_source="battery", voltage="3.3V", regulator="LDO"),
    )


def build() -> GeneratedProject:
    """Compose the project. Deterministic: same spec in, same bytes out."""
    return compose_design(spec())
