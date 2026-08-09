"""KiCad symbol generator — creates .kicad_sym files from structured pin data.

Generates multi-unit symbols where each unit corresponds to a functional
pin group (Power, GPIO_A, UART, etc.). Uses vendored kiutils for output.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

from kiutils.symbol import SymbolLib

# KiCad pin electrical types
VALID_PIN_TYPES = {
    "input", "output", "bidirectional", "tri_state", "passive",
    "free", "unspecified", "power_in", "power_out", "open_collector",
    "open_emitter", "no_connect",
}


@dataclass
class PinDef:
    """Definition of a single pin."""
    number: str
    name: str
    electrical_type: str  # must be in VALID_PIN_TYPES
    group: str
    gpio: int | None = None  # logical GPIO number, MCUs only; see ecad_bridge


@dataclass
class ChipDef:
    """Definition of a chip to generate a symbol for."""
    name: str
    library: str
    description: str
    footprint: str
    datasheet_url: str
    pins: list[PinDef] = field(default_factory=list)


def generate_symbol(chip: ChipDef) -> SymbolLib:
    """Generate a KiCad symbol library from a ChipDef.

    Creates a multi-unit symbol with one unit per pin group.
    Each unit has a rectangular body with pins on the left side.

    Args:
        chip: The chip definition with pins grouped by function.

    Returns:
        A kiutils SymbolLib ready to write with to_file().
    """
    # Delegate to the unified geometry source in src/ecad (lazy import to
    # avoid a cycle through ecad_bridge, which imports ChipDef from here).
    from src.ecad import SymbolModel

    from .ecad_bridge import chipdef_to_component

    return SymbolModel.from_component(chipdef_to_component(chip)).to_kicad_sym()


def generate_symbol_file(chip: ChipDef, output_path: Path) -> Path:
    """Generate a .kicad_sym file from a ChipDef.

    Args:
        chip: The chip definition.
        output_path: Where to write the .kicad_sym file.

    Returns:
        The output path.
    """
    lib = generate_symbol(chip)
    lib.to_file(str(output_path))
    return output_path
