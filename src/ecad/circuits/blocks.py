"""Circuit topology blocks: small, cited, independently testable sub-circuits.

Each public function here is a *block*: it takes a ``Design`` plus pins or
net names, registers the components and nets that realize one well-known
sub-circuit, and returns a :class:`Block` carrying the components it added,
its named nets, a :class:`Provenance` citation, and free-form ``notes``.

Rules this module holds itself to:

- **Every value is a parameter with a documented default**, and every
  default is either quoted from a source in ``notes`` or explicitly flagged
  ``NOT VERIFIED`` there. No magic numbers.
- **No block invents a part.** Components come from the generated-part
  registry (``src.ecad.library``); when the part does not exist yet the
  block raises :class:`MissingPartError` naming the ``lib_id``, *before*
  mutating the design.
- **Blocks are all-or-nothing**: a block that raises leaves the design
  exactly as it found it.

Dependency-direction note
-------------------------
``src/ecad`` is meant to be importable without ``src/pipeline``. Stage F1
generated ``Device:C``, ``Device:R`` and the rest of the jellybeans into
``src/ecad/library/generic/``, so the passive fallback that used to reach
across to ``src.pipeline.stock_parts`` is gone — the registry serves them.

One part source still lives on the pipeline side: the seed IC library
(``src.pipeline.chip_library``), which :func:`ldo_regulator` needs for parts
like ``AP2112K-3.3`` that no ingest has generated yet. :func:`_registry_class`
reaches for it through a *deferred, function-local* import, the same escape
hatch ``src/ecad/ingest/factory.py`` uses for ``src.pipeline.validate``.
Importing this module never pulls ``src.pipeline`` in.
"""

from __future__ import annotations

import inspect
import math
from collections.abc import Sequence
from dataclasses import dataclass

from ..component import Component, Pin
from ..design import Design
from ..model import ElectricalType, FootprintRef, PinRole
from ..net import Net

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


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Provenance:
    """Where a block's topology and default values come from.

    ``source`` names the document, ``section`` the chapter/figure inside it,
    ``url`` the retrievable location when there is one. A block whose values
    could not be traced to a document says so in ``Block.notes`` rather than
    inventing a citation here.
    """

    source: str
    section: str
    url: str = ""

    def cite(self) -> str:
        """One-line human citation, for READMEs and reports."""
        head = f"{self.source} — {self.section}" if self.section else self.source
        return f"{head} <{self.url}>" if self.url else head


@dataclass
class Block:
    """Handle on one instantiated sub-circuit.

    ``components`` are exactly the components this call registered with the
    design (a component the caller had already added is not repeated).
    ``nets`` maps a block-local role name ("rail", "gnd", "en", ...) to the
    ``Net`` that plays it.
    """

    name: str
    components: tuple[Component, ...]
    nets: dict[str, Net]
    provenance: Provenance
    notes: tuple[str, ...] = ()

    @property
    def refs(self) -> tuple[str, ...]:
        return tuple(c.ref for c in self.components)

    def __repr__(self) -> str:
        return (f"Block({self.name!r}, components={list(self.refs)}, "
                f"nets={sorted(self.nets)})")


class MissingPartError(LookupError):
    """A block needs a typed component that no part source can serve yet.

    Raised *before* the design is touched, so a caller can catch it and skip
    the block without leaving a half-built sub-circuit behind.
    """

    def __init__(self, lib_id: str, *, needed_by: str = "",
                 hint: str = "") -> None:
        self.lib_id = lib_id
        self.needed_by = needed_by
        parts = [f"no typed component available for {lib_id!r}"]
        if needed_by:
            parts.append(f"needed by {needed_by}")
        message = "; ".join(parts)
        if hint:
            message = f"{message}. {hint}"
        super().__init__(message)


# ---------------------------------------------------------------------------
# Provenance constants — the documents these blocks were checked against
# ---------------------------------------------------------------------------

_HDG_S3_URL = (
    "https://docs.espressif.com/projects/esp-hardware-design-guidelines/"
    "en/latest/esp32s3/schematic-checklist.html"
)
_DEVKITC1_URL = (
    "https://dl.espressif.com/dl/schematics/"
    "SCH_ESP32-S3-DevKitC-1_V1.1_20220413.pdf"
)
_AP2112_URL = "https://www.diodes.com/assets/Datasheets/AP2112.pdf"

PROV_DECOUPLING = Provenance(
    source="Espressif ESP32-S3 Hardware Design Guidelines — Schematic Checklist",
    section="Power Supply (Analog Power Supply / Digital Power Supply)",
    url=_HDG_S3_URL,
)
PROV_EN_RC = Provenance(
    source="Espressif ESP32-S3 Hardware Design Guidelines — Schematic Checklist",
    section="Chip Power-up and Reset Timing",
    url=_HDG_S3_URL,
)
PROV_STRAPPING = Provenance(
    source="Espressif ESP32-S3 Hardware Design Guidelines — Schematic Checklist",
    section="Strapping Pins",
    url=_HDG_S3_URL,
)
PROV_BUTTON = Provenance(
    source="Espressif ESP32-S3-DevKitC-1 V1.1 reference schematic",
    section="SW1 (BOOT → IO0) and SW2 (RST → CHIP_PU)",
    url=_DEVKITC1_URL,
)
PROV_LED = Provenance(
    source="Ohm's law; IEC 60063 E24 preferred number series",
    section="series-resistor computation (see Block.notes for the arithmetic)",
)
PROV_AP2112 = Provenance(
    source="Diodes/BCD AP2112 datasheet, Rev. 2.0 (DS39724)",
    section="Typical Application, Figure 21 + Note 4",
    url=_AP2112_URL,
)


# ---------------------------------------------------------------------------
# Passive value helpers
# ---------------------------------------------------------------------------

# IEC 60063 E24 series (±5% preferred numbers), one decade.
_E24: tuple[float, ...] = (
    1.0, 1.1, 1.2, 1.3, 1.5, 1.6, 1.8, 2.0, 2.2, 2.4, 2.7, 3.0,
    3.3, 3.6, 3.9, 4.3, 4.7, 5.1, 5.6, 6.2, 6.8, 7.5, 8.2, 9.1,
)


def e24_nearest(ohms: float) -> float:
    """Nearest E24 (IEC 60063) preferred value to ``ohms``.

    "Nearest" is measured in log space, which is how tolerance bands are
    spaced: 260 Ω sits 8.3 % above 240 Ω and 3.8 % below 270 Ω, so it snaps
    to 270 Ω. Ties go to the smaller value.
    """
    if ohms <= 0:
        raise ValueError(f"resistance must be positive, got {ohms!r}")
    decade = math.floor(math.log10(ohms))
    best_value = 0.0
    best_error = math.inf
    for d in (decade - 1, decade, decade + 1):
        for mantissa in _E24:
            # Round to 6 significant figures: 2.7 * 10**2 is 270.00000000000006
            # in binary floating point, and that noise would leak into the
            # emitted value string.
            candidate = float(f"{mantissa * 10.0 ** d:.6g}")
            error = abs(math.log10(candidate / ohms))
            if error < best_error - 1e-12:
                best_error, best_value = error, candidate
    return best_value


def format_ohms(ohms: float) -> str:
    """``270.0 -> "270R"``, ``4700 -> "4.7k"``, ``1e6 -> "1M"``."""
    if ohms >= 1e6:
        return f"{ohms / 1e6:g}M"
    if ohms >= 1e3:
        return f"{ohms / 1e3:g}k"
    return f"{ohms:g}R"


@dataclass(frozen=True)
class LedResistor:
    """Result of the LED series-resistor computation."""

    supply_v: float
    vf: float
    current_ma: float
    ideal_ohms: float
    ohms: float
    value: str
    actual_ma: float

    @property
    def note(self) -> str:
        return (
            f"R = (Vsupply {self.supply_v:g} V - Vf {self.vf:g} V) / "
            f"I {self.current_ma:g} mA = {self.ideal_ohms:g} ohm; "
            f"nearest E24 (IEC 60063) = {self.ohms:g} ohm ({self.value}) "
            f"-> actual {self.actual_ma:g} mA"
        )


def led_series_resistor(supply_v: float = 3.3, vf: float = 2.0,
                        current_ma: float = 5.0) -> LedResistor:
    """Ohm's law + E24 snap for an indicator LED.

    ``(supply_v - vf) / current`` is the ideal resistance; the returned
    ``ohms`` is the nearest E24 value and ``actual_ma`` the current that
    value really delivers. Defaults are a 3.3 V rail, a generic green LED
    (Vf 2.0 V) and 5 mA — see :func:`indicator_led` notes for why those are
    starting points, not datasheet numbers.
    """
    if current_ma <= 0:
        raise ValueError(f"current_ma must be positive, got {current_ma!r}")
    if vf >= supply_v:
        raise ValueError(
            f"LED forward voltage {vf!r} V must be below the supply "
            f"{supply_v!r} V"
        )
    ideal = (supply_v - vf) / (current_ma / 1000.0)
    ohms = e24_nearest(ideal)
    actual = round((supply_v - vf) / ohms * 1000.0, 3)
    return LedResistor(
        supply_v=supply_v, vf=vf, current_ma=current_ma,
        ideal_ohms=round(ideal, 6), ohms=ohms, value=format_ohms(ohms),
        actual_ma=actual,
    )


# ---------------------------------------------------------------------------
# Part resolution
# ---------------------------------------------------------------------------

# Footprint per (kind, imperial size). Names verified against the installed
# KiCad 10 libraries (Capacitor_SMD.pretty / Resistor_SMD.pretty).
_FOOTPRINTS: dict[tuple[str, str], FootprintRef] = {
    ("C", "0201"): FootprintRef("Capacitor_SMD", "C_0201_0603Metric"),
    ("C", "0402"): FootprintRef("Capacitor_SMD", "C_0402_1005Metric"),
    ("C", "0603"): FootprintRef("Capacitor_SMD", "C_0603_1608Metric"),
    ("C", "0805"): FootprintRef("Capacitor_SMD", "C_0805_2012Metric"),
    ("C", "1206"): FootprintRef("Capacitor_SMD", "C_1206_3216Metric"),
    ("R", "0201"): FootprintRef("Resistor_SMD", "R_0201_0603Metric"),
    ("R", "0402"): FootprintRef("Resistor_SMD", "R_0402_1005Metric"),
    ("R", "0603"): FootprintRef("Resistor_SMD", "R_0603_1608Metric"),
    ("R", "0805"): FootprintRef("Resistor_SMD", "R_0805_2012Metric"),
    ("R", "1206"): FootprintRef("Resistor_SMD", "R_1206_3216Metric"),
}


def _footprint(kind: str, package: str) -> FootprintRef:
    """``("C", "C_0402") -> Capacitor_SMD:C_0402_1005Metric``.

    Accepts ``"0402"``, ``"C_0402"`` or ``"R_0402"`` interchangeably, and
    passes a fully-qualified ``"Lib:Name"`` through untouched (the escape
    hatch for footprints this table does not know).
    """
    if ":" in package:
        lib, name = package.split(":", 1)
        return FootprintRef(lib=lib, name=name)
    size = package.split("_")[-1]
    try:
        return _FOOTPRINTS[(kind, size)]
    except KeyError:
        known = sorted({s for k, s in _FOOTPRINTS if k == kind})
        raise ValueError(
            f"unknown {kind} package {package!r}; known sizes {known} "
            f"(or pass a full 'Lib:Footprint')"
        ) from None


def _registry_class(lib_id: str, *, needed_by: str,
                    hint: str = "") -> type[Component]:
    """Resolve a ``lib_id`` to a typed Component class, or raise.

    Order: generated-part registry → the seed ``chip_library``. The second is
    a deferred import across the ``ecad``/``pipeline`` boundary; see this
    module's docstring.
    """
    from ..library import get as registry_get

    name = lib_id.split(":")[-1]
    for key in (lib_id, name):
        try:
            return registry_get(key)
        except (KeyError, LookupError, ImportError):
            pass

    # Transitional source: the seed chip library (ICs with real pinouts).
    try:
        from src.pipeline.chip_library import lookup_chip
        from src.pipeline.ecad_bridge import chipdef_to_component
    except ImportError:  # pragma: no cover
        pass
    else:
        chip = lookup_chip(lib_id) or lookup_chip(name)
        if chip is not None:
            return type(chipdef_to_component(chip))

    raise MissingPartError(
        lib_id, needed_by=needed_by,
        hint=hint or (
            "Add it to src/ecad/library/generic/ with "
            "src.ecad.ingest.library_parts (installed KiCad symbol, no "
            "datasheet) or run the datasheet factory for it."
        ),
    )


def _passive(kind: str, lib_id: str, value: str, package: str, *,
             needed_by: str) -> Component:
    """Instantiate a passive with a per-instance value and footprint."""
    cls = _registry_class(lib_id, needed_by=needed_by)
    footprint = _footprint(kind, package)
    try:
        params = set(inspect.signature(cls).parameters)
    except (TypeError, ValueError):  # pragma: no cover - exotic callables
        params = set()
    if {"value", "footprint"} <= params:
        return cls(value=value, footprint=footprint)  # type: ignore[call-arg]
    # A generated class takes no constructor arguments; per-instance value
    # and footprint then have to be set as attributes. (Signature inspection
    # rather than try/except TypeError, so a real TypeError raised inside a
    # part's __init__ is not swallowed as "wrong constructor shape".)
    comp = cls()
    comp.value = value  # type: ignore[attr-defined]
    comp.footprint = footprint
    return comp


def _capacitor(value: str, package: str, *, needed_by: str) -> Component:
    return _passive("C", "Device:C", value, package, needed_by=needed_by)


def _resistor(value: str, package: str, *, needed_by: str) -> Component:
    return _passive("R", "Device:R", value, package, needed_by=needed_by)


# ---------------------------------------------------------------------------
# Net / pin plumbing
# ---------------------------------------------------------------------------

def _as_net(design: Design, obj: Net | str | Pin, *, default_name: str,
            what: str) -> Net:
    """Coerce a net name, ``Net`` or ``Pin`` to the design's ``Net``.

    A ``Pin`` that already sits on a net contributes that net; a free pin is
    connected to ``default_name``.
    """
    if isinstance(obj, Net):
        return obj
    if isinstance(obj, str):
        if not obj:
            raise ValueError(f"{what}: net name must be non-empty")
        return design.net(obj)
    if isinstance(obj, Pin):
        if obj.net is not None:
            return obj.net
        net = design.net(default_name)
        net.connect(obj)
        return net
    raise TypeError(
        f"{what}: expected a Net, a net name or a Pin, got "
        f"{type(obj).__name__}"
    )


def _register(design: Design, added: list[Component],
              *components: Component) -> None:
    """``design.add`` the components and record them as this block's."""
    for comp in components:
        design.add(comp)
        added.append(comp)


def _adopt(design: Design, ic: Component, added: list[Component]) -> None:
    """Register ``ic`` if the caller has not already, so a block can be
    instantiated alone in an empty Design."""
    if not any(c is ic for c in design.components):
        design.add(ic)
        added.append(ic)


def _power_pins(ic: Component) -> list[Pin]:
    return [p for p in ic.pins
            if p.role is PinRole.POWER
            or (p.etype is ElectricalType.POWER_IN and p.role is not PinRole.GROUND)]


def _ground_pins(ic: Component) -> list[Pin]:
    return [p for p in ic.pins if p.role is PinRole.GROUND]


def _label(ic: Component) -> str:
    return ic.ref or ic.part_name or type(ic).__name__


def _named_pin(comp: Component, names: Sequence[str], fallback: int) -> Pin:
    """First pin matching one of ``names``, else the pin at ``fallback``.

    Polarised two-pin parts must not be wired by position: KiCad's
    ``Device:LED`` puts the *cathode* on pad 1 and the anode on pad 2, so
    ``pins[0]`` would silently reverse the diode.
    """
    for name in names:
        try:
            return comp.pin(name)
        except KeyError:
            continue
    return comp.pins[fallback]


# ---------------------------------------------------------------------------
# Blocks
# ---------------------------------------------------------------------------

def decoupling(design: Design, ic: Component, rail: Net | str | Pin,
               gnd: Net | str | Pin, *, per_pin: str = "100nF",
               bulk: str | None = "10uF", package: str = "C_0402",
               pins: Sequence[Pin] | None = None) -> Block:
    """One ceramic per power pin plus one bulk capacitor on ``rail``.

    Which pins get decoupled: ``pins`` if given, else every power pin of
    ``ic`` that is already on ``rail`` plus every power pin that is still
    free (those get connected to ``rail``). Ground pins that are still free
    are connected to ``gnd`` — without that the design would not lint, and a
    decoupling cap with no return path is not a decoupling cap.

    Pass ``bulk=None`` to place only the per-pin ceramics (e.g. a second IC
    sharing a rail that already has its bulk).
    """
    added: list[Component] = []
    _adopt(design, ic, added)
    rail_net = _as_net(design, rail, default_name="VCC", what="decoupling rail")
    gnd_net = _as_net(design, gnd, default_name="GND", what="decoupling gnd")

    if pins is None:
        candidates = _power_pins(ic)
        targets = [p for p in candidates if p.net is rail_net or p.net is None]
    else:
        targets = list(pins)
    if not targets:
        raise ValueError(
            f"decoupling: {_label(ic)} has no power pin free for or already "
            f"on {rail_net.name!r}"
        )
    for p in targets:
        if p.net is None:
            rail_net.connect(p)

    for p in _ground_pins(ic):
        if p.net is None:
            gnd_net.connect(p)

    needed_by = f"decoupling({_label(ic)}, {rail_net.name})"
    for _ in targets:
        cap = _capacitor(per_pin, package, needed_by=needed_by)
        _register(design, added, cap)
        rail_net.connect(cap.pin("1"))
        gnd_net.connect(cap.pin("2"))
    if bulk:
        cap = _capacitor(bulk, package, needed_by=needed_by)
        _register(design, added, cap)
        rail_net.connect(cap.pin("1"))
        gnd_net.connect(cap.pin("2"))

    notes = [
        f"{len(targets)} x {per_pin} per-pin ceramic on pads "
        f"{[p.pad for p in targets]}: \"It is recommended to add a 0.1 uF "
        f"capacitor close to the digital power supply pins in the circuit\" "
        f"(ESP32-S3 HDG, Digital Power Supply).",
    ]
    if bulk:
        notes.append(
            f"1 x {bulk} bulk on the rail: \"it is highly recommended to add "
            f"a 10 uF capacitor to the power rail\" / \"add an extra 10 uF "
            f"capacitor at the main power entrance\" (ESP32-S3 HDG, Analog "
            f"Power Supply). Corroborated by the ESP32-S3-DevKitC-1 V1.1 "
            f"schematic: 10 uF + 0.1 uF at the module 3V3 pin."
        )
    notes.append(
        f"package={package!r} is an assembly choice, not a datasheet value; "
        f"a {bulk or '10uF'} bulk in 0402 is buildable but marginal — pass "
        f"package='C_0805' for a mainstream part."
    )
    overridden = []
    if per_pin != "100nF":
        overridden.append(f"per_pin={per_pin}")
    if bulk not in ("10uF", None):
        overridden.append(f"bulk={bulk}")
    if overridden:
        notes.append(
            f"NOT VERIFIED: the quoted guideline values are the defaults; "
            f"this call overrides {', '.join(overridden)}."
        )
    return Block(
        name=f"decoupling:{_label(ic)}:{rail_net.name}",
        components=tuple(added),
        nets={"rail": rail_net, "gnd": gnd_net},
        provenance=PROV_DECOUPLING,
        notes=tuple(notes),
    )


def en_reset_rc(design: Design, en: Net | str | Pin, rail: Net | str | Pin,
                gnd: Net | str | Pin, *, r: str = "10k", c: str = "1uF",
                package: str = "0402", net_name: str = "EN") -> Block:
    """Power-on reset delay on an enable pin: R to ``rail``, C to ``gnd``.

    The defaults are quoted: "The recommended setting for the RC delay
    circuit is usually R = 10 kOhm and C = 1 uF" — ESP32-S3 Hardware Design
    Guidelines, *Chip Power-up and Reset Timing*. That is a 10 ms time
    constant.
    """
    added: list[Component] = []
    en_net = _as_net(design, en, default_name=net_name, what="en_reset_rc en")
    rail_net = _as_net(design, rail, default_name="VCC", what="en_reset_rc rail")
    gnd_net = _as_net(design, gnd, default_name="GND", what="en_reset_rc gnd")

    needed_by = f"en_reset_rc({en_net.name})"
    res = _resistor(r, package, needed_by=needed_by)
    cap = _capacitor(c, package, needed_by=needed_by)
    _register(design, added, res, cap)
    rail_net.connect(res.pin("1"))
    en_net.connect(res.pin("2"), cap.pin("1"))
    gnd_net.connect(cap.pin("2"))

    notes = [
        f"R={r}, C={c}. Default values: \"The recommended setting for the RC "
        f"delay circuit is usually R = 10 kOhm and C = 1 uF\" (ESP32-S3 HDG, "
        f"Chip Power-up and Reset Timing).",
        "Corroborated by the ESP32-S3-DevKitC-1 V1.1 schematic: "
        "10K(1%) pull-up and 1uF/16V to GND on CHIP_PU.",
        "Time constant tau = R*C = 10 ms at the defaults; raise C if the "
        "rail's ramp is slower than that.",
    ]
    if (r, c) != ("10k", "1uF"):
        notes.append(
            f"NOT VERIFIED: this call overrides the quoted defaults with "
            f"R={r}, C={c} — check the resulting delay against the rail's "
            f"ramp time yourself."
        )
    return Block(
        name=f"en_reset_rc:{en_net.name}",
        components=tuple(added),
        nets={"en": en_net, "rail": rail_net, "gnd": gnd_net},
        provenance=PROV_EN_RC,
        notes=tuple(notes),
    )


def pull_resistor(design: Design, net: Net | str | Pin,
                  rail_or_gnd: Net | str | Pin, *, value: str = "10k",
                  package: str = "0402", net_name: str = "NET") -> Block:
    """One resistor between ``net`` and ``rail_or_gnd`` — pull-up or -down.

    The primitive strapping-pin defaults are built from: a pull-up is this
    with ``rail_or_gnd`` = the rail, a pull-down with ``rail_or_gnd`` = GND.
    """
    added: list[Component] = []
    signal = _as_net(design, net, default_name=net_name,
                     what="pull_resistor net")
    anchor = _as_net(design, rail_or_gnd, default_name="VCC",
                     what="pull_resistor rail_or_gnd")
    if anchor is signal:
        raise ValueError(
            f"pull_resistor: {signal.name!r} cannot be pulled to itself"
        )

    res = _resistor(value, package,
                    needed_by=f"pull_resistor({signal.name})")
    _register(design, added, res)
    anchor.connect(res.pin("1"))
    signal.connect(res.pin("2"))

    return Block(
        name=f"pull_resistor:{signal.name}:{anchor.name}",
        components=tuple(added),
        nets={"net": signal, "anchor": anchor},
        provenance=PROV_STRAPPING,
        notes=(
            "\"It is recommended to place a pull-up resistor at the GPIO0 "
            "pin\" (ESP32-S3 HDG, Strapping Pins).",
            f"NOT VERIFIED: that guideline states no resistance value. The "
            f"{value} default is the value Espressif's own ESP32-S3-DevKitC-1 "
            f"V1.1 schematic uses for strapping pull-ups (R14, 10K 1%, "
            f"fitted as DNP). Override `value` when the pin's leakage or "
            f"switching speed calls for something else.",
        ),
    )


def ldo_regulator(design: Design, vin: Net | str | Pin,
                  vout: Net | str | Pin, gnd: Net | str | Pin, *, part: str,
                  cin: str = "10uF", cout: str = "10uF",
                  package: str = "0805") -> Block:
    """A linear regulator with its input and output capacitors.

    ``part`` is resolved through the part sources (generated registry, then
    the seed chip library) — this block never invents a regulator; an
    unresolvable ``part`` raises :class:`MissingPartError`.

    Pin roles decide the wiring: ``power_in`` pins go to ``vin``,
    ``power_out`` to ``vout``, ground-role pins to ``gnd``, and an ``EN`` /
    ``ENABLE`` input is tied to ``vin`` (always-on).
    """
    cls = _registry_class(part, needed_by=f"ldo_regulator(part={part!r})",
                          hint="Add it to src/ecad/library or to "
                               "src.pipeline.chip_library.")
    reg = cls()
    outputs = [p for p in reg.pins if p.etype is ElectricalType.POWER_OUT]
    if not outputs:
        raise ValueError(
            f"ldo_regulator: {part!r} has no power_out pin — it is not a "
            f"regulator model this block can wire"
        )

    added: list[Component] = []
    vin_net = _as_net(design, vin, default_name="VIN", what="ldo vin")
    vout_net = _as_net(design, vout, default_name="VOUT", what="ldo vout")
    gnd_net = _as_net(design, gnd, default_name="GND", what="ldo gnd")
    _register(design, added, reg)

    enable_pins: list[Pin] = []
    for p in reg.pins:
        if p.role is PinRole.GROUND:
            gnd_net.connect(p)
        elif p.etype is ElectricalType.POWER_OUT:
            vout_net.connect(p)
        elif p.etype is ElectricalType.POWER_IN:
            vin_net.connect(p)
        elif (p.etype is ElectricalType.INPUT
              and p.name.upper().replace("_", "") in ("EN", "ENABLE")):
            vin_net.connect(p)
            enable_pins.append(p)

    needed_by = f"ldo_regulator({part})"
    c_in = _capacitor(cin, package, needed_by=needed_by)
    c_out = _capacitor(cout, package, needed_by=needed_by)
    _register(design, added, c_in, c_out)
    vin_net.connect(c_in.pin("1"))
    gnd_net.connect(c_in.pin("2"))
    vout_net.connect(c_out.pin("1"))
    gnd_net.connect(c_out.pin("2"))

    is_ap2112 = "AP2112" in (reg.part_name or part).upper()
    provenance = PROV_AP2112 if is_ap2112 else Provenance(
        source=f"{reg.part_name or part} datasheet",
        section="typical application circuit",
        url=getattr(reg, "datasheet", "") or "",
    )
    notes = [
        f"CIN={cin}, COUT={cout} on {reg.part_name or part}.",
    ]
    if is_ap2112:
        notes.append(
            "AP2112 datasheet Rev. 2.0, Typical Application (Figure 21, "
            "Note 4): CIN = COUT = 1 uF ceramic, X7R or X5R dielectric. That "
            "is the datasheet minimum."
        )
        notes.append(
            f"The {cin}/{cout} defaults deliberately exceed it, following "
            f"\"add an extra 10 uF capacitor at the main power entrance\" "
            f"(ESP32-S3 HDG, Analog Power Supply). Pass cin='1uF', "
            f"cout='1uF' for the bare datasheet configuration."
        )
    else:
        notes.append(
            f"NOT VERIFIED: the {cin}/{cout} defaults were checked against "
            f"the AP2112 datasheet and the ESP32-S3 hardware design "
            f"guidelines, not against the {reg.part_name or part} datasheet. "
            f"Confirm them before manufacturing."
        )
    if enable_pins:
        notes.append(
            "NOT VERIFIED against a specific app note: EN is tied to VIN, "
            "the conventional always-on configuration (and what "
            "src/pipeline/composer.py already does). Drive EN from a GPIO "
            "instead if the rail must be switchable."
        )
    notes.append(
        f"package={package!r} is an assembly choice: 10 uF X5R is a "
        f"mainstream 0805 part, marginal in 0402."
    )

    return Block(
        name=f"ldo_regulator:{reg.part_name or part}",
        components=tuple(added),
        nets={"vin": vin_net, "vout": vout_net, "gnd": gnd_net},
        provenance=provenance,
        notes=tuple(notes),
    )


def push_button(design: Design, net: Net | str | Pin, gnd: Net | str | Pin, *,
                series_r: str | None = None, debounce_c: str | None = None,
                package: str = "0402", net_name: str = "BTN") -> Block:
    """A momentary switch pulling ``net`` to ``gnd`` when pressed.

    Optional ``series_r`` (current limit / ESD) sits between the switch and
    ``net``; optional ``debounce_c`` sits from ``net`` to ``gnd``. Both
    default to absent, which is what Espressif's own DevKit does.

    The switch is ``Switch:SW_Push``, generated into
    ``src/ecad/library/generic/`` from the installed KiCad symbol.
    """
    cls = _registry_class(
        "Switch:SW_Push", needed_by=f"push_button({net!r})",
        hint="Re-run python -m src.ecad.ingest.library_parts ingest "
             "Switch:SW_Push to regenerate it.",
    )

    added: list[Component] = []
    signal = _as_net(design, net, default_name=net_name, what="push_button net")
    gnd_net = _as_net(design, gnd, default_name="GND", what="push_button gnd")

    sw = cls()
    _register(design, added, sw)
    a, b = sw.pins[0], sw.pins[1]
    gnd_net.connect(b)

    needed_by = f"push_button({signal.name})"
    if series_r:
        res = _resistor(series_r, package, needed_by=needed_by)
        _register(design, added, res)
        signal.connect(res.pin("1"))
        design.net(f"{signal.name}_SW").connect(res.pin("2"), a)
    else:
        signal.connect(a)
    if debounce_c:
        cap = _capacitor(debounce_c, package, needed_by=needed_by)
        _register(design, added, cap)
        signal.connect(cap.pin("1"))
        gnd_net.connect(cap.pin("2"))

    return Block(
        name=f"push_button:{signal.name}",
        components=tuple(added),
        nets={"net": signal, "gnd": gnd_net},
        provenance=PROV_BUTTON,
        notes=(
            "ESP32-S3-DevKitC-1 V1.1 schematic: SW1 (BOOT -> IO0) and SW2 "
            "(RST -> CHIP_PU) are bare SPST-NO switches to GND with no "
            "series resistor, and their 0.1uF/50V debounce capacitors "
            "(C13, C14) are marked (NC) = not populated. Hence series_r and "
            "debounce_c both default to None.",
            "The pin the button pulls low is expected to be held high by a "
            "pull-up — pair this with pull_resistor() or the MCU's internal "
            "pull-up.",
        ),
    )


def indicator_led(design: Design, net: Net | str | Pin,
                  gnd: Net | str | Pin, *, color: str = "green",
                  supply_v: float = 3.3, vf: float = 2.0,
                  current_ma: float = 5.0, package: str = "0402",
                  net_name: str = "LED") -> Block:
    """An LED plus its computed series resistor, from ``net`` to ``gnd``.

    The resistor is ``(supply_v - vf) / current_ma`` snapped to the nearest
    E24 value; the full arithmetic lands in ``Block.notes``. Call
    :func:`led_series_resistor` directly to get the number without building
    anything.

    The diode is ``Device:LED``, generated into ``src/ecad/library/generic/``
    from the installed KiCad symbol — pad 1 = K, pad 2 = A, which is why the
    wiring below resolves both ends by NAME.
    """
    calc = led_series_resistor(supply_v=supply_v, vf=vf,
                               current_ma=current_ma)
    cls = _registry_class(
        "Device:LED", needed_by=f"indicator_led({color})",
        hint="Re-run python -m src.ecad.ingest.library_parts ingest "
             "Device:LED to regenerate it.",
    )

    added: list[Component] = []
    signal = _as_net(design, net, default_name=net_name,
                     what="indicator_led net")
    gnd_net = _as_net(design, gnd, default_name="GND",
                      what="indicator_led gnd")

    led = cls()
    led.value = color.upper()  # type: ignore[attr-defined]
    res = _resistor(calc.value, package,
                    needed_by=f"indicator_led({signal.name})")
    _register(design, added, res, led)
    # Device:LED is pad 1 = K, pad 2 = A — never wire this one by position.
    anode = _named_pin(led, ("A", "ANODE", "+"), fallback=1)
    cathode = _named_pin(led, ("K", "C", "CATHODE", "-"), fallback=0)
    signal.connect(res.pin("1"))
    design.net(f"{signal.name}_LED").connect(res.pin("2"), anode)
    gnd_net.connect(cathode)

    return Block(
        name=f"indicator_led:{signal.name}:{color}",
        components=tuple(added),
        nets={"net": signal, "gnd": gnd_net},
        provenance=PROV_LED,
        notes=(
            calc.note,
            f"NOT a datasheet value: vf={vf:g} V is a generic {color} LED "
            f"typical and current_ma={current_ma:g} an indicator-brightness "
            f"choice. Substitute the Vf and If of the LED you actually buy.",
            "For scale, the ESP32-S3-DevKitC-1 V1.1 schematic uses a 1K(1%) "
            "series resistor for its 3V3 power LED.",
        ),
    )
