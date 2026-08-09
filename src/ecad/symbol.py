"""SymbolModel: the single geometry source for schematic symbols.

Computes per-unit pin placement from a Component and emits every symbol
representation the pipeline needs:

- ``to_kicad_sym()``   — kiutils SymbolLib (multi-unit .kicad_sym files)
- ``to_inline_sexp()`` — the lib_symbols string embedded in .kicad_sch
- ``flatten()``        — single-unit projection (legacy inline format)

Phase A geometry is byte-compatible with the legacy `symbol_gen` /
`chip_library` algorithms (all pins on the left side); the 4-side layout
rules land with the layout engine.

Preserved artwork
-----------------
A component ingested from an official KiCad symbol carries that symbol's
drawing on ``Component.symbol_art`` (:class:`~.model.SymbolArt`). For those
parts the readable style does not synthesize anything: the pins sit where
the SOURCE puts them, the body is the SOURCE's draw commands, and the node
bbox the layout engine consumes is measured off that same geometry. A
``Device:R`` therefore looks like a resistor because it *is* KiCad's
resistor — and, critically, the layout engine wires to the pin coordinates
the artwork was drawn around rather than to a guess. Parts with no source
artwork (datasheet-only ingests, hand-written test parts) keep the
synthesized body rectangle.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .component import Component
from .model import ElectricalType, SymbolArt

if TYPE_CHECKING:
    from kiutils.symbol import Symbol, SymbolLib

PIN_LENGTH = 2.54
PIN_SPACING = 2.54
TEXT_SIZE = 1.27
#: Horizontal room reserved beside a narrow symbol for its Reference/Value.
#: A preserved ``Device:R`` body is 2 mm wide; without an allowance the node
#: bbox would be 2 mm too and "10k" would be drawn over the neighbour.
TEXT_ALLOWANCE = 7.62
#: A symbol at most this wide carries its fields beside the body (KiCad's own
#: convention for two-terminal parts); wider ones get them above/below.
NARROW_BODY = 3 * PIN_SPACING

#: KiCad pin rotation → the body side the pin sticks out of.
_ANGLE_SIDE = {0: "left", 180: "right", 270: "top", 90: "bottom"}

#: Coordinate pairs inside a symbol draw command. Rotating a symbol means
#: rotating exactly these; radii and stroke widths are rotation-invariant.
_COORD_RE = re.compile(
    r"\((xy|start|end|mid|center)\s+(-?[\d.]+)\s+(-?[\d.]+)\)")
_TEXT_AT_RE = re.compile(r"\(at\s+(-?[\d.]+)\s+(-?[\d.]+)\s+(-?[\d.]+)\)")


def _num(v: float) -> str:
    """Render a coordinate the way KiCad does: no trailing ``.0`` noise."""
    r = round(v, 4)
    return str(int(r)) if r == int(r) else str(r)


def _rotate_art(art: SymbolArt) -> SymbolArt:
    """The same drawing turned a quarter turn counter-clockwise.

    ``(x, y) -> (-y, x)`` in library space, applied to the artwork AND to the
    pins so the two cannot drift apart. Used to lay a two-terminal part on
    its side: KiCad draws ``Device:R`` and ``Device:C`` vertically, but a
    series element in a left-to-right signal flow reads horizontally, and a
    vertical one also forces the router to escape over the body and to set
    its net labels on their side.
    """
    def rot(x: float, y: float) -> tuple[float, float]:
        return (round(-y, 4), round(x, 4))

    def fix(text: str) -> str:
        def one(m):
            nx, ny = rot(float(m.group(2)), float(m.group(3)))
            return f"({m.group(1)} {_num(nx)} {_num(ny)})"

        def at(m):
            nx, ny = rot(float(m.group(1)), float(m.group(2)))
            angle = (float(m.group(3)) + 90) % 360
            return f"(at {_num(nx)} {_num(ny)} {_num(angle)})"

        return _TEXT_AT_RE.sub(at, _COORD_RE.sub(one, text))

    x0, y0, x1, y1 = art.bbox
    return SymbolArt(
        children=tuple((suffix, tuple(fix(i) for i in items))
                       for suffix, items in art.children),
        pins=tuple(
            type(p)(pad=p.pad, x=rot(p.x, p.y)[0], y=rot(p.x, p.y)[1],
                    angle=int((p.angle + 90) % 360), length=p.length,
                    style=p.style, unnamed=p.unnamed)
            for p in art.pins),
        bbox=(round(-y1, 4), round(x0, 4), round(-y0, 4), round(x1, 4)),
        hide_pin_numbers=art.hide_pin_numbers,
        hide_pin_names=art.hide_pin_names,
        pin_names_offset=art.pin_names_offset)


def _fields_beside(box: tuple[float, float, float, float]) -> bool:
    """True when Reference/Value belong beside the body rather than above it.

    Only for a body that is both narrow and taller than it is wide — a
    standing two-terminal part. Anything wider (an IC, a connector, a
    resistor lying on its side) reads better with the reference above and
    the value below, which is also where a draughtsman puts them.
    """
    x0, y0, x1, y1 = box
    return (x1 - x0) <= NARROW_BODY and (y1 - y0) > (x1 - x0)


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
    style: str = "line"      # KiCad pin graphical style (line, inverted, …)
    #: True when the source symbol draws this pin unnamed; `name` is then a
    #: label this pipeline invented for addressing, and must not be drawn.
    unnamed: bool = False

    @property
    def draw_name(self) -> str:
        """The name to EMIT — ``~`` where the source drew none."""
        return "~" if self.unnamed else self.name


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
    #: Source draw commands, ``(("0_1", ("(rectangle …)", …)), …)``. Empty
    #: means "synthesize a body rectangle from width/height".
    art: tuple[tuple[str, tuple[str, ...]], ...] = ()
    #: Full node extent in library space (x0, y0, x1, y1), art + pin tips +
    #: text allowance. None means "derive it from width/height + PIN_LENGTH",
    #: which is what every synthesized unit does.
    bbox: tuple[float, float, float, float] | None = None
    #: Body extent in library space, art + pin tips, WITHOUT text allowance —
    #: where Reference/Value must not land.
    body: tuple[float, float, float, float] | None = None
    hide_pin_numbers: bool = False
    hide_pin_names: bool = False
    pin_names_offset: float = 1.016

    def extent(self) -> tuple[float, float, float, float]:
        """Node bbox in library space (+Y up), explicit or derived."""
        if self.bbox is not None:
            return self.bbox
        hw, hh = self.width / 2 + PIN_LENGTH, self.height / 2 + PIN_LENGTH
        return (-hw, -hh, hw, hh)

    def body_extent(self) -> tuple[float, float, float, float]:
        """Body bbox in library space (+Y up) — no text allowance."""
        if self.body is not None:
            return self.body
        hw, hh = self.width / 2, self.height / 2
        return (-hw, -hh, hw, hh)


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
    def from_component(cls, component: Component, style: str = "legacy",
                       lay_flat: bool = True) -> SymbolModel:
        """Build the symbol geometry.

        style="legacy": byte-parity with the pre-ecad emitters (all pins on
        the left). style="readable": 4-side placement — power TOP, ground
        BOTTOM, inputs LEFT, outputs RIGHT, bidirectional toward the hub —
        the geometry the layout engine consumes.

        ``lay_flat`` turns a standing two-terminal part (KiCad draws R, C, L
        and beads vertically) onto its side so it reads along the signal
        flow. Pass False where the caller needs the source's own upright
        geometry — a decoupling cap in a satellite row hangs vertically
        between its rail and its ground by construction.
        """
        place = (cls._place_unit_readable if style == "readable"
                 else cls._place_unit)
        art = cls._usable_art(component) if style == "readable" else None
        if art is not None and lay_flat and cls._stands_upright(art):
            art = _rotate_art(art)
        units = []
        for unit_id, unit_def in enumerate(component.units(), start=1):
            specs = [component.pin_by_pad(pad).spec for pad in unit_def.pads]
            if art is not None:
                units.append(cls._place_unit_from_art(
                    unit_id, unit_def.name, specs, art))
            elif style == "readable":
                units.append(place(unit_id, unit_def.name, specs, component))
            else:
                units.append(place(unit_id, unit_def.name, specs))
        return cls(component, tuple(units))

    @staticmethod
    def _usable_art(component: Component) -> SymbolArt | None:
        """The component's source artwork, when it really describes this part.

        Three things must hold or the art is a lie: it must exist, it must
        place EVERY pad the component declares (a partial drawing would leave
        pins with no coordinates), and the component must be single-unit —
        a datasheet-derived multi-unit plan slices pads across units the
        source symbol never split, so its one drawing cannot serve them.
        """
        art = getattr(component, "symbol_art", None)
        if art is None or not art.children or not art.pins:
            return None
        if len(component.units()) != 1:
            return None
        pads = {p.pad for p in component.pins}
        if pads != {p.pad for p in art.pins}:
            return None
        return art

    @staticmethod
    def _stands_upright(art: SymbolArt) -> bool:
        """A two-terminal symbol whose pins both point up/down."""
        return (len(art.pins) == 2
                and all(p.angle in (90, 270) for p in art.pins))

    @classmethod
    def _place_unit_from_art(cls, unit_id: int, name: str, specs,
                             art: SymbolArt) -> SymbolUnit:
        """Geometry straight off the source symbol — nothing is invented."""
        pins = []
        for s in specs:
            a = art.pin(s.pad)
            side = Side(_ANGLE_SIDE.get(a.angle, "left"))
            pins.append(PlacedPin(pad=s.pad, name=s.name, etype=s.etype,
                                  x=a.x, y=a.y, angle=a.angle,
                                  length=a.length, side=side, style=a.style,
                                  unnamed=a.unnamed))
        x0, y0, x1, y1 = art.bbox
        beside = _fields_beside(art.bbox)
        pad_x = TEXT_ALLOWANCE if beside else 0.0
        pad_y = 0.0 if beside else PIN_SPACING
        return SymbolUnit(
            unit_id=unit_id, name=name,
            width=round(x1 - x0, 4), height=round(y1 - y0, 4),
            pins=tuple(pins), art=art.children,
            bbox=(x0, round(y0 - pad_y, 4), round(x1 + pad_x, 4),
                  round(y1 + pad_y, 4)),
            body=(x0, y0, x1, y1),
            hide_pin_numbers=art.hide_pin_numbers,
            hide_pin_names=art.hide_pin_names,
            pin_names_offset=art.pin_names_offset)

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
        # Top and bottom pins are pitched at TWICE the pin spacing and the two
        # rows are staggered by one, so a top pin and a bottom pin never share
        # an x. They would otherwise draw their names up and down the same
        # line inside the body: the AP2112K's VIN and GND rendered as one
        # unreadable "GNDVIN", and so did every ESP32 module's power unit.
        top_pitch = 2 * PIN_SPACING
        width = max(
            15.24,
            _snap_up(1.27 * (max_l + max_r) + 5.08, PIN_SPACING),
            (max(len(by_side[Side.TOP]), len(by_side[Side.BOTTOM])) * 2 + 1)
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
                                  x=round(-half_w - PIN_LENGTH, 4),
                                  y=round(half_h - PIN_SPACING * (i + 1), 4),
                                  angle=0, length=PIN_LENGTH, side=Side.LEFT))
        for i, s in enumerate(by_side[Side.RIGHT]):
            pins.append(PlacedPin(s.pad, s.name, s.etype,
                                  x=round(half_w + PIN_LENGTH, 4),
                                  y=round(half_h - PIN_SPACING * (i + 1), 4),
                                  angle=180, length=PIN_LENGTH, side=Side.RIGHT))
        for row, side, y, angle, stagger in (
            (by_side[Side.TOP], Side.TOP, half_h + PIN_LENGTH, 270,
             -PIN_SPACING / 2),
            (by_side[Side.BOTTOM], Side.BOTTOM, -half_h - PIN_LENGTH, 90,
             PIN_SPACING / 2),
        ):
            m = len(row)
            for i, s in enumerate(row):
                x = (i - (m - 1) / 2) * top_pitch + stagger
                pins.append(PlacedPin(s.pad, s.name, s.etype,
                                      x=round(x, 4), y=round(y, 4), angle=angle,
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
        x0, y0, x1, y1 = self.unit(unit_id).extent()
        return (round(x1 - x0, 4), round(y1 - y0, 4))

    def node_anchor(self, unit_id: int) -> tuple[float, float]:
        """Offset from the node's top-left origin to the symbol's own origin.

        KiCad places a symbol by its library origin, which is only the centre
        of the node bbox when the bbox was derived from a centred rectangle.
        Preserved artwork is routinely off-centre (``Device:LED`` reaches
        4.6 mm left of origin and 3.8 mm right), so callers must ask rather
        than halve the size.
        """
        x0, _y0, _x1, y1 = self.unit(unit_id).extent()
        return (round(-x0, 4), round(y1, 4))

    def body_box(self, unit_id: int) -> tuple[float, float, float, float]:
        """Body extent in SCHEMATIC space relative to the symbol origin:
        ``(left, top, right, bottom)`` with top < bottom (+Y down)."""
        x0, y0, x1, y1 = self.unit(unit_id).body_extent()
        return (x0, round(-y1, 4), x1, round(-y0, 4))

    def field_offsets(self, unit_id: int = 1) -> tuple[
            tuple[float, float, str], tuple[float, float, str]]:
        """Where Reference and Value go, in LIBRARY space (+Y up).

        Returns ``((rx, ry, justify), (vx, vy, justify))``. Both sit outside
        the body and clear of the pins, which is the whole point: the
        previous fixed ``+2.54/±1.27`` offsets put both fields *inside*
        anything taller than 2.5 mm, so every IC rendered its reference on
        top of its own pin names.

        Which side is free is decided by the pins, not by taste. A field
        placed under a symbol whose pins leave the bottom is drawn across
        those pins' stubs and across the power symbols they end in — which
        is what "AP2112K-3.3" did to the LDO's ground tap.
        """
        unit = self.unit(unit_id)
        box = unit.body_extent()
        x0, y0, x1, y1 = box
        right = round(x1 + 1.27, 4)
        if _fields_beside(box):
            return ((right, 1.27, "left"), (right, -1.27, "left"))
        sides = {p.side for p in unit.pins}
        top_free = Side.TOP not in sides
        bottom_free = Side.BOTTOM not in sides
        mid = round((x0 + x1) / 2, 4)
        above, below = round(y1 + 1.27, 4), round(y0 - 1.27, 4)
        if top_free and bottom_free:
            return ((mid, above, ""), (mid, below, ""))
        if bottom_free:
            return ((mid, below, ""), (mid, round(y0 - 3.81, 4), ""))
        if top_free:
            return ((mid, above, ""), (mid, round(y1 + 3.81, 4), ""))
        return ((right, 1.27, "left"), (right, -1.27, "left"))

    def node_ports(self, unit_id: int) -> list[tuple]:
        """Ports for the layout engine, in schematic space (+Y down).

        Returns [(pad, name, etype_value, side, index, (dx, dy)), ...] where
        (dx, dy) is the pin CONNECTION point relative to the node's top-left
        origin, and index orders ports along their side (top→bottom for
        left/right, left→right for top/bottom).
        """
        u = self.unit(unit_id)
        x0, _y0, _x1, y1 = u.extent()
        ox, oy = x0, y1                                  # lib-space bbox corner
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

    def to_inline_sexp_multi(self, lib_id: str) -> str:
        """Genuinely multi-unit lib_symbols entry for .kicad_sch embedding.

        Emits one ``<name>_<unit>_1`` sub-symbol per unit, each with its own
        body rectangle and pins — placed instances then reference units via
        their ``(unit N)`` token. This is the layout-engine emission path
        (the legacy ``to_inline_sexp`` flattens for old callers).
        """
        comp = self._component
        safe_name = lib_id.replace('"', '\\"')
        footprint = comp.footprint.lib_id if comp.footprint else ""
        head = self.units[0]
        (rx, ry, rjust), (vx, vy, vjust) = self.field_offsets(head.unit_id)

        def just(j: str) -> str:
            return f" (justify {j})" if j else ""

        lines = [f'(symbol "{safe_name}"']
        if head.hide_pin_numbers:
            lines.append('      (pin_numbers (hide yes))')
        names = f'      (pin_names (offset {head.pin_names_offset})'
        lines.append(names + (' (hide yes))' if head.hide_pin_names else ')'))
        lines.append('      (exclude_from_sim no)')
        lines.append('      (in_bom yes)')
        lines.append('      (on_board yes)')
        lines.append(f'      (property "Reference" "{comp.reference_prefix or "U"}" '
                     f'(at {rx} {ry} 0) (effects (font (size 1.27 1.27))'
                     f'{just(rjust)}))')
        lines.append(f'      (property "Value" "{comp.part_name}" '
                     f'(at {vx} {vy} 0) (effects (font (size 1.27 1.27))'
                     f'{just(vjust)}))')
        lines.append(f'      (property "Footprint" "{footprint}" (at 0 0 0) '
                     '(effects (font (size 1.27 1.27)) (hide yes)))')
        lines.append(f'      (property "Datasheet" "{comp.datasheet}" (at 0 0 0) '
                     '(effects (font (size 1.27 1.27)) (hide yes)))')
        child_base = safe_name.split(":")[-1]
        for suffix, items in self._child_blocks():
            lines.append(f'      (symbol "{child_base}_{suffix}"')
            lines.extend(f"        {item}" for item in items)
            lines.append('      )')
        lines.append('      (embedded_fonts no))')
        return "\n".join(lines)

    def _child_blocks(self) -> list[tuple[str, list[str]]]:
        """``(suffix, draw/pin commands)`` per KiCad sub-symbol, sorted.

        Preserved artwork keeps the source's own ``<unit>_<style>`` split
        (``0_0`` = every unit and every body style); a synthesized unit
        contributes one body rectangle. Pins always land in
        ``<unit>_1`` — merged into the art block when the source used the
        same suffix, so a symbol never gets two blocks with one name.
        """
        blocks: dict[str, list[str]] = {}
        for unit in self.units:
            if unit.art:
                for suffix, items in unit.art:
                    blocks.setdefault(suffix, []).extend(items)
            else:
                half_w, half_h = unit.width / 2, unit.height / 2
                blocks.setdefault(f"{unit.unit_id}_1", []).append(
                    f"(rectangle (start -{half_w} {half_h}) "
                    f"(end {half_w} -{half_h}) "
                    "(stroke (width 0.254) (type default)) "
                    "(fill (type background)))")
            pin_lines = blocks.setdefault(f"{unit.unit_id}_1", [])
            for p in unit.pins:
                pin_name = _esc(p.draw_name)
                pin_lines.append(
                    f"(pin {p.etype.value} {p.style} "
                    f"(at {p.x} {p.y} {p.angle}) (length {p.length}) "
                    f'(name "{pin_name}" (effects (font (size 1.27 1.27)))) '
                    f'(number "{_esc(p.pad)}" '
                    "(effects (font (size 1.27 1.27)))))")
        return sorted(blocks.items())

    def kicad_sym_text(self) -> str:
        """Serialized ``.kicad_sym`` library for this part.

        Parts with no preserved artwork keep the kiutils emitter byte for
        byte — every already-generated symbol in the tree came from it, and
        a formatting change there would rewrite files this work has no
        business touching.
        """
        if not any(u.art for u in self.units):
            return self.to_kicad_sym().to_sexpr()
        return self._art_kicad_sym_text()

    def _art_kicad_sym_text(self) -> str:
        """``.kicad_sym`` text for a part that carries source artwork.

        Text rather than a kiutils object graph because preserved artwork
        arrives as source S-expressions: round-tripping arbitrary draw
        commands through typed classes would mean re-implementing every
        graphic KiCad can draw, and losing whichever ones this vendored
        kiutils does not model.
        """
        comp = self._component
        name = _esc(comp.part_name)
        footprint = _esc(comp.footprint.lib_id if comp.footprint else "")
        head = self.units[0]
        (rx, ry, rjust), (vx, vy, vjust) = self.field_offsets(head.unit_id)

        def just(j: str) -> str:
            return f" (justify {j})" if j else ""

        lines = ["(kicad_symbol_lib (version 20231120) (generator symbol_gen)",
                 f'  (symbol "{name}" (in_bom yes) (on_board yes)']
        if head.hide_pin_numbers:
            lines.append("    (pin_numbers (hide yes))")
        names = f"    (pin_names (offset {head.pin_names_offset})"
        lines.append(names + (" (hide yes))" if head.hide_pin_names else ")"))
        fields = [
            ("Reference", _esc(comp.reference_prefix or "U"), 0,
             f"(at {rx} {ry} 0)", just(rjust), False),
            ("Value", name, 1, f"(at {vx} {vy} 0)", just(vjust), False),
            ("Footprint", footprint, 2, "(at 0.0 0.0 0)", "", True),
            ("Datasheet", _esc(comp.datasheet or ""), 3, "(at 0.0 0.0 0)",
             "", True),
        ]
        if comp.description:
            fields.append(("Description", _esc(comp.description), 4,
                           "(at 0.0 0.0 0)", "", True))
        for key, value, fid, at, justify, hide in fields:
            lines.append(f'    (property "{key}" "{value}" (id {fid}) {at}')
            lines.append(f"      (effects (font (size {TEXT_SIZE} {TEXT_SIZE}))"
                         f"{justify}{' hide' if hide else ''})")
            lines.append("    )")
        for suffix, items in self._child_blocks():
            lines.append(f'    (symbol "{name}_{suffix}"')
            lines.extend(f"      {item}" for item in items)
            lines.append("    )")
        lines += ["  )", ")", ""]
        return "\n".join(lines)

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

        child_base = safe_name.split(":")[-1]
        half_h = unit.height / 2
        lines.append(f'      (symbol "{child_base}_0_1"')
        lines.append(f'        (rectangle (start -{unit.width / 2} {half_h}) '
                     f'(end {unit.width / 2} -{half_h})')
        lines.append('          (stroke (width 0.254) (type default)) '
                     '(fill (type background))))')

        lines.append(f'      (symbol "{child_base}_1_1"')
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
