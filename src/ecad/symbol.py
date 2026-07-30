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

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .component import Component
from .model import ElectricalType

if TYPE_CHECKING:
    from kiutils.symbol import Symbol, SymbolLib

PIN_LENGTH = 2.54
PIN_SPACING = 2.54
TEXT_SIZE = 1.27


def _esc(value: str) -> str:
    """Escape a value for a KiCad S-expression string literal.

    Backslash first, then quote — the other order would re-escape the
    backslash the quote rule just introduced. Every interpolated field must
    go through this: descriptions come from parsed datasheets and routinely
    contain quotes (``2.5" display``), which otherwise close the literal
    early and make the whole .kicad_sch unparseable.
    """
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _snap_up(v: float, grid: float) -> float:
    """Round v UP to the next multiple of grid."""
    import math
    return round(math.ceil(round(v / grid, 9)) * grid, 4)


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
class PinLocation:
    """Where a pad connects, in library space (+Y up, origin body center)."""

    unit_id: int
    x: float
    y: float
    side: Side
    angle: int
    length: float


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
    def from_component(cls, component: Component,
                       style: str = "legacy") -> SymbolModel:
        """Build the symbol geometry.

        style="legacy": byte-parity with the pre-ecad emitters (all pins on
        the left). style="readable": 4-side placement — power TOP, ground
        BOTTOM, inputs LEFT, outputs RIGHT, bidirectional toward the hub —
        the geometry the layout engine consumes.
        """
        place = (cls._place_unit_readable if style == "readable"
                 else cls._place_unit)
        units = []
        for unit_id, unit_def in enumerate(component.units(), start=1):
            specs = [component.pin_by_pad(pad).spec for pad in unit_def.pads]
            if style == "readable":
                units.append(place(unit_id, unit_def.name, specs, component))
            else:
                units.append(place(unit_id, unit_def.name, specs))
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

    @staticmethod
    def _side_for(spec, component: Component, single_pin_count: int,
                  position: int) -> Side:
        """Side-assignment rules for readable geometry."""
        from .model import PinRole

        if single_pin_count == 2:
            return Side.LEFT if position == 0 else Side.RIGHT
        if spec.role is PinRole.GROUND:
            return Side.BOTTOM
        if spec.etype is ElectricalType.POWER_IN:
            return Side.TOP
        if spec.etype is ElectricalType.INPUT:
            return Side.LEFT
        if spec.etype in (ElectricalType.OUTPUT, ElectricalType.POWER_OUT):
            return Side.RIGHT
        # bidirectional / passive / everything else: face the bus partner
        return Side.RIGHT if component.orientation_hint == "hub" else Side.LEFT

    @staticmethod
    def _natural_key(name: str):
        import re as _re
        return [int(t) if t.isdigit() else t
                for t in _re.split(r"(\d+)", name)]

    @classmethod
    def _place_unit_readable(cls, unit_id: int, name: str, specs,
                             component: Component) -> SymbolUnit:
        """4-side geometry: derived widths, pins on all four sides."""
        n = len(specs)
        by_side: dict[Side, list] = {s: [] for s in Side}
        for pos, s in enumerate(specs):
            by_side[cls._side_for(s, component, n, pos)].append(s)
        for side in (Side.LEFT, Side.RIGHT, Side.TOP, Side.BOTTOM):
            by_side[side].sort(key=lambda s: cls._natural_key(s.name))

        max_l = max((len(s.name) for s in by_side[Side.LEFT]), default=0)
        max_r = max((len(s.name) for s in by_side[Side.RIGHT]), default=0)
        width = max(
            15.24,
            _snap_up(1.27 * (max_l + max_r) + 5.08, PIN_SPACING),
            (max(len(by_side[Side.TOP]), len(by_side[Side.BOTTOM])) + 1)
            * PIN_SPACING,
        )
        height = max(
            5.08,
            (max(len(by_side[Side.LEFT]), len(by_side[Side.RIGHT])) + 1)
            * PIN_SPACING,
        )
        half_w, half_h = width / 2, height / 2

        pins: list[PlacedPin] = []
        for i, s in enumerate(by_side[Side.LEFT]):
            pins.append(PlacedPin(s.pad, s.name, s.etype,
                                  x=-half_w - PIN_LENGTH,
                                  y=half_h - PIN_SPACING * (i + 1),
                                  angle=0, length=PIN_LENGTH, side=Side.LEFT))
        for i, s in enumerate(by_side[Side.RIGHT]):
            pins.append(PlacedPin(s.pad, s.name, s.etype,
                                  x=half_w + PIN_LENGTH,
                                  y=half_h - PIN_SPACING * (i + 1),
                                  angle=180, length=PIN_LENGTH, side=Side.RIGHT))
        for row, side, y, angle in (
            (by_side[Side.TOP], Side.TOP, half_h + PIN_LENGTH, 270),
            (by_side[Side.BOTTOM], Side.BOTTOM, -half_h - PIN_LENGTH, 90),
        ):
            m = len(row)
            for i, s in enumerate(row):
                x = (i - (m - 1) / 2) * PIN_SPACING
                pins.append(PlacedPin(s.pad, s.name, s.etype,
                                      x=round(x, 4), y=y, angle=angle,
                                      length=PIN_LENGTH, side=side))
        return SymbolUnit(unit_id=unit_id, name=name, width=width,
                          height=height, pins=tuple(pins))

    # ── queries (layout-engine contract) ────────────────────────────────────

    @property
    def component(self) -> Component:
        return self._component

    def pin_position(self, pad: str) -> "PinLocation":
        """Full placement of a pad's connection point in library space.

        Geometry answered here matches ``to_kicad_sym()`` (multi-unit).
        The single-unit inline embedding has its own geometry — query
        ``flatten().pin_position(pad)`` when consuming ``to_inline_sexp()``.
        """
        unit_id, p = self._pin_index[pad]
        return PinLocation(unit_id=unit_id, x=p.x, y=p.y,
                           side=p.side, angle=p.angle, length=p.length)

    def unit(self, unit_id: int) -> SymbolUnit:
        return self.units[unit_id - 1]

    def node_size(self, unit_id: int) -> tuple[float, float]:
        """Full bbox (w, h) of a unit in schematic space, pin tips included."""
        u = self.unit(unit_id)
        return (u.width + 2 * PIN_LENGTH, u.height + 2 * PIN_LENGTH)

    def node_ports(self, unit_id: int) -> list[tuple]:
        """Ports for the layout engine, in schematic space (+Y down).

        Returns [(pad, name, etype_value, side, index, (dx, dy)), ...] where
        (dx, dy) is the pin CONNECTION point relative to the node's top-left
        origin, and index orders ports along their side (top→bottom for
        left/right, left→right for top/bottom).
        """
        u = self.unit(unit_id)
        half_w, half_h = u.width / 2, u.height / 2
        ox, oy = -half_w - PIN_LENGTH, half_h + PIN_LENGTH  # lib-space origin
        by_side: dict[Side, list[PlacedPin]] = {s: [] for s in Side}
        for p in u.pins:
            by_side[p.side].append(p)
        by_side[Side.LEFT].sort(key=lambda p: -p.y)
        by_side[Side.RIGHT].sort(key=lambda p: -p.y)
        by_side[Side.TOP].sort(key=lambda p: p.x)
        by_side[Side.BOTTOM].sort(key=lambda p: p.x)
        out = []
        for side in (Side.LEFT, Side.RIGHT, Side.TOP, Side.BOTTOM):
            for idx, p in enumerate(by_side[side]):
                dx = round(p.x - ox, 4)
                dy = round(oy - p.y, 4)
                out.append((p.pad, p.name, p.etype.value, side, idx, (dx, dy)))
        return out

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

    def to_kicad_sym(self) -> "SymbolLib":
        """Multi-unit kiutils SymbolLib (legacy generate_symbol format)."""
        # Lazy: only this emitter needs kiutils (and the tools/ path insert).
        from ._kicad import Effects, Font, Property, Symbol, SymbolLib

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
    def _unit_to_kiutils(parent_name: str, unit: SymbolUnit) -> "Symbol":
        from ._kicad import Fill, Position, Stroke, SyRect, Symbol, SymbolPin

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

        safe_name = _esc(lib_id)
        footprint = _esc(comp.footprint.lib_id if comp.footprint else "")
        datasheet = _esc(comp.datasheet)
        description = _esc(comp.description)
        # Must match to_kicad_sym() — both emitters describe the same part.
        # Bridged ChipDefs never set reference_prefix, so this stays "U" and
        # preserves byte-parity with _generate_lib_symbol_sexp_legacy.
        ref_prefix = _esc(comp.reference_prefix or "U")

        lines = [f'(symbol "{safe_name}"']
        lines.append('      (pin_names (offset 1.016))')
        lines.append('      (exclude_from_sim no)')
        lines.append('      (in_bom yes)')
        lines.append('      (on_board yes)')
        lines.append(f'      (property "Reference" "{ref_prefix}" (at 0 1.27 0) '
                     '(effects (font (size 1.27 1.27))))')
        lines.append(f'      (property "Value" "{safe_name}" (at 0 -1.27 0) '
                     '(effects (font (size 1.27 1.27))))')
        lines.append(f'      (property "Footprint" "{footprint}" (at 0 0 0) '
                     '(effects (font (size 1.27 1.27)) (hide yes)))')
        lines.append(f'      (property "Datasheet" "{datasheet}" (at 0 0 0) '
                     '(effects (font (size 1.27 1.27)) (hide yes)))')
        if comp.description:
            lines.append(f'      (property "Description" "{description}" '
                         '(at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))')

        half_h = unit.height / 2
        lines.append(f'      (symbol "{safe_name}_0_1"')
        lines.append(f'        (rectangle (start -{unit.width / 2} {half_h}) '
                     f'(end {unit.width / 2} -{half_h})')
        lines.append('          (stroke (width 0.254) (type default)) '
                     '(fill (type background))))')

        lines.append(f'      (symbol "{safe_name}_1_1"')
        for placed in unit.pins:
            pin_name = _esc(placed.name)
            lines.append(
                f'        (pin {placed.etype.value} line '
                f'(at {placed.x} {placed.y} 0) (length 2.54)'
                f'\n          (name "{pin_name}" (effects (font (size 1.27 1.27))))'
                f'\n          (number "{_esc(placed.pad)}" '
                f'(effects (font (size 1.27 1.27)))))'
            )
        lines.append('      )')
        lines.append('      (embedded_fonts no))')
        return "\n".join(lines)
