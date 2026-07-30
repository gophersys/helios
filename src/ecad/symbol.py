"""SymbolModel: the single geometry source for schematic symbols.

Computes per-unit pin placement from a Component and emits every symbol
representation the pipeline needs:

- ``to_kicad_sym()``   — kiutils SymbolLib (multi-unit .kicad_sym files)
- ``to_inline_sexp()`` — the lib_symbols string embedded in .kicad_sch
- ``flatten()``        — single-unit projection (legacy inline format)

Phase A geometry is byte-compatible with the legacy `symbol_gen` /
`chip_library` algorithms (all pins on the left side); the 4-side layout
rules land with the layout engine.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

from kiutils.items.common import Effects, Fill, Font, Position, Property, Stroke
from kiutils.items.syitems import SyRect
from kiutils.symbol import Symbol, SymbolLib, SymbolPin

from .component import Component
from .model import ElectricalType

PIN_LENGTH = 2.54
PIN_SPACING = 2.54
TEXT_SIZE = 1.27


class Side(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


@dataclass(frozen=True)
class PlacedPin:
    """A pin placed in symbol (library) space: +Y is up, origin at body center."""

    pad: str
    name: str
    etype: ElectricalType
    x: float
    y: float
    angle: int
    length: float
    side: Side


@dataclass(frozen=True)
class SymbolUnit:
    unit_id: int              # 1-based KiCad unit
    name: str                 # unit/group name (metadata; not emitted)
    width: float
    height: float
    pins: tuple[PlacedPin, ...]


class SymbolModel:
    """Computed symbol geometry plus emitters. Construct via from_component()."""

    def __init__(self, component: Component, units: tuple[SymbolUnit, ...]) -> None:
        self._component = component
        self.units = units
        self._pin_index: dict[str, tuple[int, PlacedPin]] = {}
        for unit in units:
            for p in unit.pins:
                self._pin_index[p.pad] = (unit.unit_id, p)

    # ── construction ────────────────────────────────────────────────────────

    @classmethod
    def from_component(cls, component: Component) -> SymbolModel:
        units = []
        for unit_id, unit_def in enumerate(component.units(), start=1):
            specs = [component._pin(pad).spec for pad in unit_def.pads]
            units.append(cls._place_unit(unit_id, unit_def.name, specs))
        return cls(component, tuple(units))

    @staticmethod
    def _place_unit(unit_id: int, name: str, specs) -> SymbolUnit:
        # Legacy-parity geometry: all pins on the left, fixed width.
        height = max((len(specs) + 1) * PIN_SPACING, 5.08)
        width = 15.24
        half_h = height / 2
        start_y = half_h - PIN_SPACING
        pins = tuple(
            PlacedPin(
                pad=s.pad, name=s.name, etype=s.etype,
                x=-(width / 2) - PIN_LENGTH,
                y=start_y - i * PIN_SPACING,
                angle=0, length=PIN_LENGTH, side=Side.LEFT,
            )
            for i, s in enumerate(specs)
        )
        return SymbolUnit(unit_id=unit_id, name=name, width=width,
                          height=height, pins=pins)

    # ── queries (layout-engine contract) ────────────────────────────────────

    @property
    def component(self) -> Component:
        return self._component

    def pin_position(self, pad: str) -> tuple[int, float, float]:
        """(unit_id, x, y) of a pad's connection point in library space."""
        unit_id, p = self._pin_index[pad]
        return unit_id, p.x, p.y

    def unit(self, unit_id: int) -> SymbolUnit:
        return self.units[unit_id - 1]

    @property
    def pin_count(self) -> int:
        return len(self._pin_index)

    # ── projections ─────────────────────────────────────────────────────────

    def flatten(self) -> SymbolModel:
        """Single-unit projection with all pins in original pin order."""
        comp = self._component
        specs = [p.spec for p in comp.pins]
        unit = self._place_unit(1, comp.part_name, specs)
        return SymbolModel(comp, (unit,))

    # ── emitters ────────────────────────────────────────────────────────────

    def to_kicad_sym(self) -> SymbolLib:
        """Multi-unit kiutils SymbolLib (legacy generate_symbol format)."""
        comp = self._component
        name = comp.part_name

        lib = SymbolLib()
        lib.version = 20231120
        lib.generator = "symbol_gen"

        sym = Symbol()
        sym.entryName = name
        sym.libId = name
        sym.inBom = True
        sym.onBoard = True

        footprint = comp.footprint.lib_id if comp.footprint else ""
        sym.properties = [
            Property(key="Reference", value=comp.reference_prefix or "U", id=0,
                     effects=Effects(font=Font(width=TEXT_SIZE, height=TEXT_SIZE))),
            Property(key="Value", value=name, id=1,
                     effects=Effects(font=Font(width=TEXT_SIZE, height=TEXT_SIZE))),
            Property(key="Footprint", value=footprint, id=2,
                     effects=Effects(font=Font(width=TEXT_SIZE, height=TEXT_SIZE),
                                     hide=True)),
            Property(key="Datasheet", value=comp.datasheet or "", id=3,
                     effects=Effects(font=Font(width=TEXT_SIZE, height=TEXT_SIZE),
                                     hide=True)),
        ]
        if comp.description:
            sym.properties.append(Property(
                key="Description", value=comp.description, id=4,
                effects=Effects(font=Font(width=TEXT_SIZE, height=TEXT_SIZE),
                                hide=True)))

        sym.units = [self._unit_to_kiutils(name, u) for u in self.units]
        lib.symbols = [sym]
        return lib

    @staticmethod
    def _unit_to_kiutils(parent_name: str, unit: SymbolUnit) -> Symbol:
        ku = Symbol()
        ku.entryName = parent_name
        ku.libId = parent_name
        ku.unitId = unit.unit_id
        ku.styleId = 1

        rect = SyRect()
        rect.start = Position(X=-unit.width / 2, Y=unit.height / 2)
        rect.end = Position(X=unit.width / 2, Y=-unit.height / 2)
        rect.stroke = Stroke(width=0.254, type="default")
        rect.fill = Fill(type="background")
        ku.graphicItems = [rect]

        pins = []
        for placed in unit.pins:
            p = SymbolPin()
            p.electricalType = placed.etype.value
            p.graphicalStyle = "line"
            p.name = placed.name
            p.number = str(placed.pad)
            p.length = placed.length
            p.position = Position(X=placed.x, Y=placed.y, angle=placed.angle)
            pins.append(p)
        ku.pins = pins
        return ku

    def to_inline_sexp(self, lib_id: str) -> str:
        """Single-unit lib_symbols string for .kicad_sch embedding.

        Byte-compatible with the legacy chip_library.generate_lib_symbol_sexp
        output (KiCad 9 format, version 20250114 context).
        """
        comp = self._component
        unit = self.flatten().units[0]

        safe_name = lib_id.replace('"', '\\"')
        footprint = comp.footprint.lib_id if comp.footprint else ""

        lines = [f'(symbol "{safe_name}"']
        lines.append('      (pin_names (offset 1.016))')
        lines.append('      (exclude_from_sim no)')
        lines.append('      (in_bom yes)')
        lines.append('      (on_board yes)')
        lines.append('      (property "Reference" "U" (at 0 1.27 0) '
                     '(effects (font (size 1.27 1.27))))')
        lines.append(f'      (property "Value" "{safe_name}" (at 0 -1.27 0) '
                     '(effects (font (size 1.27 1.27))))')
        lines.append(f'      (property "Footprint" "{footprint}" (at 0 0 0) '
                     '(effects (font (size 1.27 1.27)) (hide yes)))')
        lines.append(f'      (property "Datasheet" "{comp.datasheet}" (at 0 0 0) '
                     '(effects (font (size 1.27 1.27)) (hide yes)))')
        if comp.description:
            lines.append(f'      (property "Description" "{comp.description}" '
                         '(at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))')

        half_h = unit.height / 2
        lines.append(f'      (symbol "{safe_name}_0_1"')
        lines.append(f'        (rectangle (start -{unit.width / 2} {half_h}) '
                     f'(end {unit.width / 2} -{half_h})')
        lines.append('          (stroke (width 0.254) (type default)) '
                     '(fill (type background))))')

        lines.append(f'      (symbol "{safe_name}_1_1"')
        for placed in unit.pins:
            pin_name = placed.name.replace('"', '\\"')
            lines.append(
                f'        (pin {placed.etype.value} line '
                f'(at {placed.x} {placed.y} 0) (length 2.54)'
                f'\n          (name "{pin_name}" (effects (font (size 1.27 1.27))))'
                f'\n          (number "{placed.pad}" '
                f'(effects (font (size 1.27 1.27)))))'
            )
        lines.append('      )')
        lines.append('      (embedded_fonts no))')
        return "\n".join(lines)
