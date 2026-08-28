"""Core value types for the typed design model.

Everything here is a frozen dataclass or enum: component *specifications*
are immutable and shared; mutable runtime state (a pin's net) lives on the
per-instance objects in `component.py` / `net.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ElectricalType(str, Enum):
    """KiCad pin electrical types (matches symbol_gen.VALID_PIN_TYPES)."""

    INPUT = "input"
    OUTPUT = "output"
    BIDIRECTIONAL = "bidirectional"
    TRI_STATE = "tri_state"
    PASSIVE = "passive"
    FREE = "free"
    UNSPECIFIED = "unspecified"
    POWER_IN = "power_in"
    POWER_OUT = "power_out"
    OPEN_COLLECTOR = "open_collector"
    OPEN_EMITTER = "open_emitter"
    NO_CONNECT = "no_connect"

    @classmethod
    def parse(cls, raw: str, *, strict: bool = False) -> ElectricalType:
        """Normalize a free-form pin type string (legacy-compatible).

        Lenient by default: unknown values become UNSPECIFIED, matching
        symbol_gen._normalize_pin_type so corpus ingestion never hard-fails.
        Pass strict=True on hand-authored paths, where a typo silently
        becoming UNSPECIFIED would also disable that pin's design lint.
        """
        value = raw.lower().strip()
        aliases = {
            "power": "power_in",
            "pwr_in": "power_in",
            "pwr_out": "power_out",
            "bidi": "bidirectional",
            "bidir": "bidirectional",
            "tristate": "tri_state",
            "tri-state": "tri_state",
            "open_drain": "open_collector",
            "nc": "no_connect",
        }
        value = aliases.get(value, value)
        try:
            return cls(value)
        except ValueError:
            if strict:
                raise ValueError(
                    f"unknown electrical type {raw!r}; expected one of "
                    f"{sorted(m.value for m in cls)}"
                ) from None
            return cls.UNSPECIFIED


class PinRole(str, Enum):
    """Semantic role of a pin, orthogonal to its electrical type.

    Drives design lint, unit auto-planning, and layout decisions
    (power taps, satellite ownership, symbol side rules).
    """

    POWER = "power"
    GROUND = "ground"
    GPIO = "gpio"
    STRAPPING = "strapping"
    ANALOG = "analog"
    RF = "rf"
    NC = "nc"
    CONTROL = "control"
    COMM = "comm"
    PASSIVE = "passive"
    SIGNAL = "signal"


class UnitStrategy(str, Enum):
    SINGLE = "single"      # one unit containing every pin (passives, small ICs)
    EXPLICIT = "explicit"  # unit_plan on the component class defines units


@dataclass(frozen=True)
class PinSpec:
    """Immutable specification of one physical pad."""

    pad: str                       # physical pad/ball, e.g. "41", "AB12"
    name: str                      # primary name only, e.g. "IO4"
    etype: ElectricalType
    role: PinRole = PinRole.SIGNAL
    gpio: int | None = None        # logical GPIO number, MCUs only
    functions: tuple[str, ...] = ()  # alternate functions, e.g. ("ADC1_CH3",)

    def __post_init__(self) -> None:
        if not self.pad:
            raise ValueError("PinSpec.pad must be non-empty")
        if not self.name:
            raise ValueError(f"PinSpec {self.pad!r}: name must be non-empty")
        if not isinstance(self.etype, ElectricalType):
            object.__setattr__(self, "etype", ElectricalType.parse(str(self.etype)))
        if not isinstance(self.role, PinRole):
            object.__setattr__(self, "role", PinRole(str(self.role)))


@dataclass(frozen=True)
class UnitDef:
    """One schematic unit: a named, ordered subset of pads."""

    name: str
    pads: tuple[str, ...]


@dataclass(frozen=True)
class PinArt:
    """Where the SOURCE symbol puts one pin, in library space (+Y up).

    ``x``/``y`` is the pin's CONNECTION point (the tip a wire attaches to);
    ``angle`` is KiCad's pin rotation, from which the body side follows:
    0 = LEFT, 180 = RIGHT, 270 = TOP, 90 = BOTTOM.
    """

    pad: str
    x: float
    y: float
    angle: int
    length: float
    style: str = "line"
    #: True when the SOURCE symbol draws this pin unnamed (``~``). The typed
    #: model still needs a name to address the pad by, and ingest synthesizes
    #: ``P<pad>`` — but drawing that invented label is what put a "P1" and a
    #: "P2" on every resistor. Emitters write ``~`` for these.
    unnamed: bool = False


@dataclass(frozen=True)
class SymbolArt:
    """The drawing of a symbol as its SOURCE library draws it.

    A generated part that was ingested from an official KiCad symbol carries
    this so the pipeline can emit KiCad's own artwork instead of a generic
    body rectangle — a ``Device:R`` looks like a resistor because it *is*
    KiCad's resistor.

    ``children`` mirrors KiCad's own sub-symbol split: ``(suffix, draw
    commands)`` where suffix is ``"<unit>_<style>"`` (``"0_1"`` = shared by
    every unit of body style 1) and each draw command is a one-line
    S-expression in library space.

    ``pins`` is the SOURCE pin geometry. It is the geometry, not a hint: the
    art and the pins must agree or the wires would meet nothing, so whoever
    consumes the art must place pins here too.

    ``bbox`` is ``(x0, y0, x1, y1)`` in library space over the art *and* the
    pin connection points.
    """

    children: tuple[tuple[str, tuple[str, ...]], ...] = ()
    pins: tuple[PinArt, ...] = ()
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
    hide_pin_numbers: bool = False
    hide_pin_names: bool = False
    pin_names_offset: float = 1.016

    def pin(self, pad: str) -> PinArt | None:
        for p in self.pins:
            if p.pad == pad:
                return p
        return None


@dataclass(frozen=True)
class FootprintRef:
    """Reference to a footprint, either from the installed KiCad library
    or a custom .kicad_mod (the escape hatch)."""

    lib: str
    name: str
    source: str = "kicad"          # "kicad" | "custom"
    path: str | None = None       # custom source only

    @property
    def lib_id(self) -> str:
        return f"{self.lib}:{self.name}" if self.lib else self.name


@dataclass(frozen=True)
class SourcingInfo:
    manufacturer: str = ""
    mpn: str = ""
    lcsc: str = ""
    datasheet_url: str = ""


@dataclass(frozen=True)
class Issue:
    """One finding from Design.check()."""

    severity: str                  # "error" | "warning"
    code: str                      # stable machine code, e.g. "unconnected-power"
    message: str
    ref: str = ""                  # component ref if applicable
    net: str = ""                  # net name if applicable

    @property
    def is_error(self) -> bool:
        return self.severity == "error"


# Convenience for tests and callers building specs from legacy strings.
def pin(pad: str, name: str, etype: str | ElectricalType,
        role: str | PinRole = PinRole.SIGNAL, gpio: int | None = None,
        functions: tuple[str, ...] = ()) -> PinSpec:
    """Terse PinSpec constructor accepting legacy string types.

    Strict on etype: this is the hand-authoring path, and PinRole below
    already rejects unknown roles — silently downgrading a typo'd etype to
    UNSPECIFIED would be the odd one out, and would mute lint on that pin.
    """
    if isinstance(etype, str):
        etype = ElectricalType.parse(etype, strict=True)
    if isinstance(role, str):
        role = PinRole(role)
    return PinSpec(pad=pad, name=name, etype=etype, role=role,
                   gpio=gpio, functions=functions)
