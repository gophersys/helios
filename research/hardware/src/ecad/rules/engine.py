"""Electrical rule engine: the *semantic* oracle.

Every other gate in this repo is syntactic. Netlist equivalence proves the
emitted file says what the author typed; ``lint_placed`` proves wires are
orthogonal and do not overlap; KiCad ERC proves pin *electrical types* do
not conflict. None of them knows what a circuit **is** — which is why a
badly-named ground pin could once have shorted VIN to GND with every gate
green, and why tying ``VDD_SPI`` to a 3.3 V rail (destroying the
ESP32-S3's 1.8 V flash option) is invisible to all of them.

This module holds the machinery; the rules themselves live in the domain
modules (:mod:`src.ecad.rules.power` today) and register themselves on
import.

Design contract
---------------
**A rule never touches the filesystem.** :class:`RuleContext` is built once,
resolves everything a rule could need — nets, the pins on them, the
capacitors bridging them, the part models, extracted datasheet facts, rail
voltages — and hands rules a pure in-memory view. A rule that re-parsed a
file would be re-deriving state the context already owns, and would run
once per rule instead of once per design.

**Errors are a hard gate.** :attr:`Report.ok` is ``errors == 0`` *after*
waivers. A waiver carries ``reason`` + ``cited_source`` + ``author`` and is
validated exactly like :meth:`src.ecad.ingest.crossverify.Evidence.waive`,
so the two ledgers read as one system. A waiver that matches nothing is
itself reported: a stale waiver is a finding, because a waiver that
silently stops applying is how a real defect gets back in.

Merged views
------------
:meth:`RuleContext.merged` builds a context over several ``Design`` objects
at once, joining their nets **by name**. That is not a convenience: this
repo's designs are one ``Design`` per schematic *sheet*, and power rails
cross sheets as KiCad global power symbols. Checking a sheet alone
correctly reports its rails as undriven; checking the merged view is what
answers "is the *board* sound?". The CLI prints both.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from ..component import Component, Pin
from ..design import Design
from ..model import ElectricalType, PinRole

__all__ = [
    "CapView",
    "Finding",
    "NetView",
    "PartFacts",
    "RailVoltage",
    "RegulatorFacts",
    "Report",
    "Rule",
    "RuleContext",
    "Severity",
    "Waiver",
    "check",
    "facts_providers",
    "get_rule",
    "is_ground_name",
    "parse_farads",
    "parse_volts",
    "register_facts",
    "register_rule",
    "rules",
]


# ---------------------------------------------------------------------------
# Severity, findings, waivers
# ---------------------------------------------------------------------------

class Severity(str, Enum):
    """How much a finding matters. ERROR fails the gate; nothing else does."""

    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass(frozen=True)
class Finding:
    """One thing a rule noticed, named precisely enough to act on.

    ``target`` is the *waiver key*: a stable, human-readable identifier for
    the exact thing found (``"U1:VDD_SPI@+3V3"``), not a message. Messages
    get reworded; targets must not, or every reword invalidates a ledger of
    cited waivers.
    """

    rule_id: str
    severity: Severity
    target: str
    message: str
    remediation: str = ""
    citation: str = ""
    refs: tuple[str, ...] = ()
    pins: tuple[str, ...] = ()
    nets: tuple[str, ...] = ()
    design: str = ""

    @property
    def is_error(self) -> bool:
        return self.severity is Severity.ERROR

    def key(self) -> tuple[str, str]:
        return (self.rule_id, self.target)

    def format(self) -> str:
        return f"{self.rule_id:<8} {self.severity.value:<7} {self.message}"


@dataclass(frozen=True)
class Waiver:
    """A cited human decision to accept one finding.

    Same three fields, same validation and the same meaning as
    :meth:`src.ecad.ingest.crossverify.Evidence.waive` — a waiver without a
    ``cited_source`` is an opinion, and an opinion is not evidence.
    """

    rule_id: str
    target: str
    reason: str
    cited_source: str
    author: str
    #: Optional context name this waiver belongs to (a sheet's design name).
    #: A scoped waiver is inert outside its scope: neither applied nor
    #: reported stale. Without this, running the same ledger over three
    #: sheets would report each sheet's waivers as stale on the other two,
    #: and a wall of false staleness is how a genuinely stale waiver hides.
    scope: str = ""

    def __post_init__(self) -> None:
        if not (self.rule_id and self.target):
            raise ValueError("waiver requires rule_id and target")
        if not (self.reason and self.cited_source and self.author):
            raise ValueError("waiver requires reason, cited_source and author")

    def key(self) -> tuple[str, str]:
        return (self.rule_id, self.target)

    def applies_to(self, context_name: str) -> bool:
        return not self.scope or self.scope == context_name

    @classmethod
    def from_dict(cls, payload: Mapping[str, str]) -> "Waiver":
        missing = [k for k in ("rule_id", "target", "reason", "cited_source",
                               "author") if not payload.get(k)]
        if missing:
            raise ValueError(f"waiver is missing {missing}: {dict(payload)!r}")
        return cls(rule_id=str(payload["rule_id"]),
                   target=str(payload["target"]),
                   reason=str(payload["reason"]),
                   cited_source=str(payload["cited_source"]),
                   author=str(payload["author"]),
                   scope=str(payload.get("scope", "")))

    def as_dict(self) -> dict[str, str]:
        out = {"rule_id": self.rule_id, "target": self.target,
               "reason": self.reason, "cited_source": self.cited_source,
               "author": self.author}
        if self.scope:
            out["scope"] = self.scope
        return out


def load_waivers(path: Path) -> list[Waiver]:
    """Read a waiver ledger: a JSON list, or ``{"waivers": [...]}``."""
    payload = json.loads(Path(path).read_text())
    items = payload["waivers"] if isinstance(payload, dict) else payload
    return [Waiver.from_dict(w) for w in items]


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------

_SI = {"p": 1e-12, "n": 1e-9, "u": 1e-6, "m": 1e-3, "": 1.0}
# A capacitance needs a unit: an SI prefix (optionally followed by F) or a
# bare F. A bare number is rejected — see parse_farads.
_CAP_RE = re.compile(
    r"^\s*(\d*\.?\d+)\s*(?:([pnuµμm])\s*F?|F)(?![0-9A-Za-z])", re.IGNORECASE)
# "3V3" / "1V8" — the R-notation where the unit replaces the decimal point.
_VOLT_R_RE = re.compile(r"^[+-]?(\d+)V(\d+)$", re.IGNORECASE)
_VOLT_PLAIN_RE = re.compile(r"^[+-]?(\d+(?:\.\d+)?)\s*V$", re.IGNORECASE)
_GROUND_NAME_RE = re.compile(r"^(GND|VSS|AGND|DGND|PGND|GNDA|VSSA|EARTH)\w*$",
                             re.IGNORECASE)


def parse_farads(value: str | None) -> float | None:
    """``"100nF" -> 1e-7``. Returns ``None`` when the string is not a value.

    Tolerant of the suffixes real BOM values carry (``"10uF/25V"``,
    ``"22 µF"``) and of the SI micro sign in either Unicode spelling.
    Deliberately *not* tolerant of a bare number: ``"10"`` could be 10 F,
    10 µF or a part number, and guessing which is how a rule starts lying.
    """
    if not value:
        return None
    m = _CAP_RE.match(str(value))
    if not m:
        return None
    prefix = (m.group(2) or "").lower()
    prefix = "u" if prefix in ("µ", "μ") else prefix
    return float(m.group(1)) * _SI[prefix]


def parse_volts(name: str | None) -> float | None:
    """``"+3V3" -> 3.3``, ``"5V" -> 5.0``, ``"1V8" -> 1.8``; else ``None``.

    Only *name-encoded* voltages. ``"VBUS"`` and ``"VCC"`` name a rail
    without stating its voltage and correctly return ``None`` — a rule that
    guessed 5 V or 3.3 V from those would be inventing a number.
    """
    if not name:
        return None
    text = str(name).strip()
    m = _VOLT_R_RE.match(text)
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = _VOLT_PLAIN_RE.match(text)
    if m:
        return float(m.group(1))
    return None


def is_ground_name(name: str) -> bool:
    """Ground-family net or pin name (GND, VSS, AGND, DGND, PGND, EARTH…)."""
    return bool(_GROUND_NAME_RE.match(str(name or "")))


# ---------------------------------------------------------------------------
# Datasheet facts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RegulatorFacts:
    """What a regulator part model states about itself."""

    output_v: float | None = None
    dropout_v: float | None = None          # worst case the source gives
    dropout_at_ma: float | None = None      # the load the dropout is quoted at
    max_output_current_a: float | None = None
    vin_min: float | None = None
    vin_max: float | None = None
    source: str = ""


@dataclass(frozen=True)
class PartFacts:
    """Electrical facts about one part, with the citation they came from.

    Every field is optional. A rule that needs a field it does not have
    emits ``INFO`` "no data" — it never substitutes a plausible number.
    ``source`` names where the numbers came from and is quoted verbatim in
    findings, so a number can always be traced back to a document.
    """

    part_name: str = ""
    voltage_min: float | None = None
    voltage_typ: float | None = None
    voltage_max: float | None = None
    abs_max_v: float | None = None
    min_supply_current_a: float | None = None
    decoupling_caps: tuple[str, ...] = ()
    strapping: tuple[str, ...] = ()
    power_pins: tuple[str, ...] = ()
    #: pin name (upper) → supply-domain id. Positive evidence that two power
    #: pins of this part belong to *different* domains (PWR-003).
    domains: Mapping[str, str] = field(default_factory=dict)
    regulator: RegulatorFacts | None = None
    source: str = ""

    def merge(self, other: "PartFacts") -> "PartFacts":
        """``self`` wins; ``other`` fills the gaps (precedence, not override)."""
        def pick(a, b):
            return a if a not in (None, (), "", {}) else b
        return PartFacts(
            part_name=pick(self.part_name, other.part_name),
            voltage_min=pick(self.voltage_min, other.voltage_min),
            voltage_typ=pick(self.voltage_typ, other.voltage_typ),
            voltage_max=pick(self.voltage_max, other.voltage_max),
            abs_max_v=pick(self.abs_max_v, other.abs_max_v),
            min_supply_current_a=pick(self.min_supply_current_a,
                                      other.min_supply_current_a),
            decoupling_caps=pick(self.decoupling_caps, other.decoupling_caps),
            strapping=pick(self.strapping, other.strapping),
            power_pins=pick(self.power_pins, other.power_pins),
            domains=pick(dict(self.domains), dict(other.domains)),
            regulator=pick(self.regulator, other.regulator),
            source=" + ".join(s for s in (self.source, other.source) if s),
        )


#: A facts provider answers "what do we know about this part?" or ``None``.
FactsProvider = Callable[[Component], PartFacts | None]

_FACTS_PROVIDERS: list[FactsProvider] = []


def register_facts(provider: FactsProvider) -> FactsProvider:
    """Register a datasheet-facts source (highest priority registers last).

    Providers are consulted newest-first and merged with :meth:`PartFacts.merge`,
    so a curated citation can fill gaps an extraction left and vice versa.
    Domain modules register their cited tables here at import time, which is
    what keeps ``engine`` from importing ``power`` (and creating a cycle).
    """
    _FACTS_PROVIDERS.append(provider)
    return provider


def facts_providers() -> tuple[FactsProvider, ...]:
    return tuple(_FACTS_PROVIDERS)


def _class_facts(comp: Component) -> PartFacts | None:
    """Facts a part model declares about itself.

    A generated part carries no electrical envelope today, but a
    hand-written class or an ``*_overrides.py`` can set ``POWER_FACTS`` and
    this reads it — which is what "where the part model provides it" means.
    """
    declared = getattr(type(comp), "POWER_FACTS", None)
    if isinstance(declared, PartFacts):
        return declared
    return None


def _extracted_facts(comp: Component, root: Path) -> PartFacts | None:
    """Read ``data/ingest/<id>/extracted.json`` as *data*, never as code.

    The datasheet extractor's ``power`` object (``voltage_min`` /
    ``voltage_typ`` / ``voltage_max`` / ``power_pins`` /
    ``decoupling_caps``) and ``strapping_pins`` are picked up when present.
    Anything missing simply stays ``None``: this reader never repairs or
    back-fills the extraction, because the extractor is owned elsewhere.
    """
    ident = _ingest_id(comp)
    path = root / ident / "extracted.json"
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError):
        return None
    power = payload.get("power")
    power = power if isinstance(power, dict) else {}

    def num(key: str) -> float | None:
        raw = power.get(key)
        try:
            v = float(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return v or None

    caps = tuple(
        str(c.get("value", "")) if isinstance(c, dict) else str(c)
        for c in power.get("decoupling_caps", []) or ()
    )
    return PartFacts(
        part_name=str(payload.get("chip_name", "") or comp.part_name),
        voltage_min=num("voltage_min"), voltage_typ=num("voltage_typ"),
        voltage_max=num("voltage_max"),
        decoupling_caps=tuple(c for c in caps if c),
        strapping=tuple(str(s) for s in payload.get("strapping_pins", []) or ()),
        power_pins=tuple(str(p) for p in power.get("power_pins", []) or ()),
        source=f"extracted datasheet facts ({path})",
    )


def _ingest_id(comp: Component) -> str:
    """``ESP32-S3-WROOM-1`` → ``esp32-s3-wroom-1`` (the ingest record id)."""
    return re.sub(r"[^0-9A-Za-z]+", "-", comp.part_name or "").strip("-").lower()


# ---------------------------------------------------------------------------
# Resolved views a rule reads
# ---------------------------------------------------------------------------

_CONNECTOR_PREFIXES = frozenset({"J", "P", "X"})
_PASSIVE_PREFIXES = frozenset({"C", "R", "L", "FB", "D", "SW", "Y", "TP"})


def is_ground_pin(pin: Pin) -> bool:
    """Ground by declared role *or* by name.

    Both, deliberately. The near-miss that motivated this engine was a
    ground pin whose *role* was wrong — ``_infer_role`` only matches names
    that *start* with ``GND``/``VSS``, so a pad called ``AGND`` gets
    ``PinRole.POWER`` and ``ldo_regulator`` would wire it to VIN. Name and
    role together catch that; either alone does not.
    """
    return pin.role is PinRole.GROUND or is_ground_name(pin.name)


def is_power_pin(pin: Pin) -> bool:
    """A pin that supplies or consumes a rail. Ground pins are never one.

    Ground wins over the supply test on purpose: a mis-roled ``AGND`` pin
    must read as ground here, so that PWR-003 sees a ground pin sitting on
    a rail instead of two supply pins agreeing with each other.
    """
    if is_ground_pin(pin):
        return False
    return (pin.role is PinRole.POWER
            or pin.etype in (ElectricalType.POWER_IN, ElectricalType.POWER_OUT))


@dataclass(frozen=True)
class CapView:
    """A two-pin capacitor, seen from one of the two nets it bridges."""

    ref: str
    value: str
    farads: float | None
    other_net: str
    component: Component


@dataclass(frozen=True)
class NetView:
    """Everything a rule can ask about one net, resolved once.

    Holds pins rather than a ``Net`` object on purpose: a merged
    multi-sheet context joins nets by *name*, and there is no single ``Net``
    to point at.
    """

    name: str
    pins: tuple[Pin, ...]
    is_ground: bool
    power_pins: tuple[Pin, ...]
    ground_pins: tuple[Pin, ...]
    drivers: tuple[Pin, ...]
    consumers: tuple[Pin, ...]
    connector_power_pins: tuple[Pin, ...]
    caps: tuple[CapView, ...]

    @property
    def is_rail(self) -> bool:
        """A non-ground net that at least one part treats as a supply."""
        return not self.is_ground and bool(self.power_pins)

    def caps_to(self, net_name: str) -> tuple[CapView, ...]:
        return tuple(c for c in self.caps if c.other_net == net_name)


@dataclass(frozen=True)
class RailVoltage:
    """A rail's nominal voltage plus *where the number came from*."""

    volts: float
    origin: str          # "declared" | "regulator" | "net-name" | "alias"
    source: str = ""     # citation, for the finding


#: Rails whose voltage is fixed by a standard rather than by their name.
#: Each entry cites the standard; nothing else may be added without one.
STANDARD_RAILS: dict[str, RailVoltage] = {
    "VBUS": RailVoltage(
        5.0, "alias",
        "USB Type-C Cable and Connector Specification R2.0 (Aug 2019), "
        "Table 4-3: vSafe5V source output 4.75-5.5 V, nominal 5 V"),
}


class RuleContext:
    """Everything the rules read — resolved once, per design (or per board).

    Built by :meth:`build` (one ``Design``) or :meth:`merged` (several,
    joined by net name). A rule receives one of these and nothing else; it
    never opens a file, walks the library or re-parses a netlist.
    """

    def __init__(self, *, name: str, designs: tuple[Design, ...],
                 components: tuple[Component, ...],
                 nets: tuple[NetView, ...],
                 facts: Mapping[int, PartFacts],
                 rail_voltages: Mapping[str, RailVoltage],
                 power_sources: frozenset[str],
                 sheet_of: Mapping[int, str] | None = None) -> None:
        self.name = name
        self.designs = designs
        self.components = components
        self.nets = nets
        #: id(component) → facts. Keyed by identity, NOT by ref: refs are
        #: unique within one Design, and a merged board routinely has two
        #: different U1s. Keying by ref silently gave the LDO the module's
        #: absolute-maximum rating — a false ERROR built out of real data.
        self.facts = dict(facts)
        self._rails = dict(rail_voltages)
        self.power_sources = power_sources
        self._sheet_of = dict(sheet_of or {})
        self._by_name = {n.name: n for n in nets}
        self._net_of_pin: dict[int, str] = {
            id(p): n.name for n in nets for p in n.pins}
        self._labels = self._label_map(components, self._sheet_of)

    @staticmethod
    def _label_map(components: Sequence[Component],
                   sheet_of: Mapping[int, str]) -> dict[int, str]:
        """Unique display name per component (``U1`` or ``mcu/U1``)."""
        by_ref: dict[str, list[Component]] = {}
        for c in components:
            by_ref.setdefault(c.ref, []).append(c)
        out: dict[int, str] = {}
        for ref, comps in by_ref.items():
            for c in comps:
                sheet = sheet_of.get(id(c), "")
                out[id(c)] = (f"{sheet}/{ref}" if len(comps) > 1 and sheet
                              else ref)
        return out

    # ── construction ────────────────────────────────────────────────────────

    @classmethod
    def build(cls, design: Design, **kwargs) -> "RuleContext":
        return cls.merged({design.name: design}, name=design.name, **kwargs)

    @classmethod
    def merged(cls, designs: Mapping[str, Design], *, name: str = "",
               ingest_root: Path | str | None = None,
               facts: Mapping[str, PartFacts] | None = None,
               rail_voltages: Mapping[str, RailVoltage] | None = None,
               power_sources: Iterable[str] = ()) -> "RuleContext":
        """Resolve one context over one or more designs, joined by net name.

        ``ingest_root`` defaults to ``data/ingest`` under the repo root and
        is read for ``<id>/extracted.json``; a missing directory is not an
        error, it simply means no extracted facts (rules then say "no data").
        """
        sheets = tuple(designs.values())
        components: list[Component] = []
        sheet_of: dict[int, str] = {}
        seen: set[int] = set()
        for sheet_name, d in designs.items():
            for c in d.components:
                if id(c) not in seen:
                    seen.add(id(c))
                    components.append(c)
                    sheet_of[id(c)] = sheet_name
        registered = {id(c) for c in components}

        # Group pins by net NAME across every design.
        grouped: dict[str, list[Pin]] = {}
        for d in sheets:
            for net in d.nets:
                bucket = grouped.setdefault(net.name, [])
                for p in net.pins:
                    if id(p.owner) in registered:
                        bucket.append(p)

        net_of_pin = {id(p): n for n, ps in grouped.items() for p in ps}
        caps_by_net = cls._capacitors(components, net_of_pin)

        nets = tuple(
            cls._net_view(net_name, pins, caps_by_net.get(net_name, ()))
            for net_name, pins in sorted(grouped.items())
        )

        root = Path(ingest_root) if ingest_root is not None else _default_ingest_root()
        resolved = cls._facts(components, root, facts or {})
        rails = cls._rail_voltages(nets, resolved, net_of_pin,
                                   dict(rail_voltages or {}))
        return cls(name=name or (sheets[0].name if sheets else ""),
                   designs=sheets, components=tuple(components), nets=nets,
                   facts=resolved, rail_voltages=rails,
                   power_sources=frozenset(power_sources), sheet_of=sheet_of)

    @staticmethod
    def _capacitors(components: Sequence[Component],
                    net_of_pin: Mapping[int, str]) -> dict[str, list[CapView]]:
        out: dict[str, list[CapView]] = {}
        for comp in components:
            if comp.reference_prefix != "C" or len(comp.pins) != 2:
                continue
            a, b = comp.pins
            na, nb = net_of_pin.get(id(a)), net_of_pin.get(id(b))
            if na is None or nb is None or na == nb:
                continue
            value = str(getattr(comp, "value", "") or "")
            farads = parse_farads(value)
            for here, there in ((na, nb), (nb, na)):
                out.setdefault(here, []).append(
                    CapView(ref=comp.ref, value=value, farads=farads,
                            other_net=there, component=comp))
        return out

    @staticmethod
    def _net_view(name: str, pins: Sequence[Pin],
                  caps: Sequence[CapView]) -> NetView:
        power = tuple(p for p in pins if is_power_pin(p))
        grounds = tuple(p for p in pins if is_ground_pin(p))
        # A net carrying BOTH kinds is not a ground net — it is a short, and
        # calling it "ground" would mute every rail rule that should shout.
        ground = is_ground_name(name) or (bool(grounds) and not power)
        return NetView(
            name=name,
            pins=tuple(pins),
            is_ground=ground,
            power_pins=power,
            ground_pins=grounds,
            drivers=tuple(p for p in pins
                          if p.etype is ElectricalType.POWER_OUT),
            consumers=tuple(p for p in power
                            if p.etype is ElectricalType.POWER_IN),
            connector_power_pins=tuple(
                p for p in power
                if p.owner.reference_prefix in _CONNECTOR_PREFIXES),
            caps=tuple(sorted(caps, key=lambda c: (c.other_net, c.ref))),
        )

    @staticmethod
    def _facts(components: Sequence[Component], root: Path,
               explicit: Mapping[str, PartFacts]) -> dict[int, PartFacts]:
        out: dict[int, PartFacts] = {}
        for comp in components:
            candidates: list[PartFacts] = []
            for key in (comp.ref, comp.part_name):
                if key and key in explicit:
                    candidates.append(explicit[key])
                    break
            declared = _class_facts(comp)
            if declared is not None:
                candidates.append(declared)
            extracted = _extracted_facts(comp, root)
            if extracted is not None:
                candidates.append(extracted)
            for provider in reversed(_FACTS_PROVIDERS):
                got = provider(comp)
                if got is not None:
                    candidates.append(got)
            if not candidates:
                continue
            merged = candidates[0]
            for extra in candidates[1:]:
                merged = merged.merge(extra)
            out[id(comp)] = merged
        return out

    @staticmethod
    def _rail_voltages(nets: Sequence[NetView],
                       facts: Mapping[int, PartFacts],
                       net_of_pin: Mapping[int, str],
                       explicit: dict[str, RailVoltage]) -> dict[str, RailVoltage]:
        """Precedence: caller > regulator output > net name > cited standard.

        A caller who knows the rail beats everything. A regulator that
        states its output voltage beats the net's *name*, because a net
        called ``+3V3`` fed by a 1.8 V regulator is a defect the name would
        hide. Nothing else is inferred: an unnamed, unregulated rail has no
        voltage and rules say "no data".
        """
        out: dict[str, RailVoltage] = {}
        for net in nets:
            if net.is_ground:
                continue
            if net.name in explicit:
                out[net.name] = explicit[net.name]
                continue
            from_reg: RailVoltage | None = None
            for driver in net.drivers:
                reg = (facts.get(id(driver.owner)) or PartFacts()).regulator
                if reg is not None and reg.output_v is not None:
                    from_reg = RailVoltage(reg.output_v, "regulator",
                                           reg.source)
                    break
            if from_reg is not None:
                out[net.name] = from_reg
                continue
            named = parse_volts(net.name)
            if named is not None:
                out[net.name] = RailVoltage(
                    named, "net-name",
                    f"net name {net.name!r} encodes its nominal voltage")
                continue
            standard = STANDARD_RAILS.get(net.name.upper())
            if standard is not None:
                out[net.name] = standard
        return out

    # ── queries rules use ───────────────────────────────────────────────────

    def net(self, name: str) -> NetView | None:
        return self._by_name.get(name)

    def net_of(self, pin: Pin) -> NetView | None:
        name = self._net_of_pin.get(id(pin))
        return self._by_name.get(name) if name else None

    def rail_voltage(self, net_name: str) -> RailVoltage | None:
        return self._rails.get(net_name)

    def facts_for(self, comp: Component) -> PartFacts:
        return self.facts.get(id(comp), PartFacts(part_name=comp.part_name))

    def ref(self, comp: Component) -> str:
        """Unique display name for a component within this context.

        ``U1`` normally; ``power/U1`` when a merged board has two different
        components with the same ref (refs are unique per ``Design``, not
        per board). Findings and waiver targets use this, so a target never
        points at two different parts.
        """
        return self._labels.get(id(comp), comp.ref)

    def pin_label(self, pin: Pin) -> str:
        return f"{self.ref(pin.owner)}.{pin.name}"

    def ics(self) -> tuple[Component, ...]:
        """Components that are integrated circuits, not jellybeans.

        "IC" here means: has at least one supply pin, is not a two-pin
        passive, and is not a connector. Connectors carry power pins but
        nothing decouples a connector — the entry-point bulk capacitance is
        :func:`PWR-006`'s job, not PWR-002's.
        """
        out = []
        for comp in self.components:
            if comp.reference_prefix in _CONNECTOR_PREFIXES:
                continue
            if comp.reference_prefix in _PASSIVE_PREFIXES and len(comp.pins) <= 2:
                continue
            if any(is_power_pin(p) for p in comp.pins):
                out.append(comp)
        return tuple(out)

    def regulators(self) -> tuple[Component, ...]:
        """Components with a ``power_out`` pin — the things that make rails."""
        return tuple(c for c in self.components
                     if any(p.etype is ElectricalType.POWER_OUT
                            for p in c.pins))

    def __repr__(self) -> str:
        return (f"RuleContext({self.name!r}, components={len(self.components)},"
                f" nets={len(self.nets)}, facts={len(self.facts)})")


def _default_ingest_root() -> Path:
    return Path(__file__).resolve().parents[3] / "data" / "ingest"


# ---------------------------------------------------------------------------
# Rules and the registry
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Rule:
    """One electrical rule: an id, a citation, and a check.

    ``severity`` is the rule's *default*; a finding may lower itself (a
    stricter corroborating source reported as WARNING, a missing-data skip
    reported as INFO). ``provenance`` is the same
    :class:`src.ecad.circuits.blocks.Provenance` the circuit blocks carry —
    a rule with no traceable source does not belong in the pack.
    """

    id: str
    domain: str
    severity: Severity
    title: str
    provenance: object            # blocks.Provenance (duck-typed: .cite())
    check: Callable[[RuleContext], Iterable[Finding]]
    doc: str = ""

    def citation(self) -> str:
        cite = getattr(self.provenance, "cite", None)
        return cite() if callable(cite) else str(self.provenance)

    def run(self, ctx: RuleContext) -> tuple[Finding, ...]:
        """Run the check and stamp every finding with the design's name."""
        out = []
        for f in self.check(ctx):
            if f.rule_id != self.id:
                raise AssertionError(
                    f"rule {self.id} emitted a finding tagged {f.rule_id!r}")
            out.append(f if f.design else
                       Finding(**{**f.__dict__, "design": ctx.name}))
        return tuple(out)


_RULES: dict[str, Rule] = {}


def register_rule(rule: Rule) -> Rule:
    """Add a rule to the global registry (ids are unique and stable)."""
    if rule.id in _RULES:
        raise ValueError(f"duplicate rule id {rule.id!r}")
    _RULES[rule.id] = rule
    return rule


def rules(domain: str | None = None) -> tuple[Rule, ...]:
    """Registered rules, sorted by id (optionally one domain)."""
    return tuple(r for _, r in sorted(_RULES.items())
                 if domain is None or r.domain == domain)


def get_rule(rule_id: str) -> Rule:
    return _RULES[rule_id]


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------

WAIVER_STALE = "WAIVER-STALE"
_STALE_CITATION = ("this engine's own contract: a waiver that matches nothing "
                   "is reported, because a waiver that silently stops applying "
                   "is how a real defect gets back in")


@dataclass(frozen=True)
class WaivedFinding:
    finding: Finding
    waiver: Waiver


@dataclass
class Report:
    """Result of one run: findings, waived findings, counts, and the gate."""

    name: str
    findings: tuple[Finding, ...]                 # active, not waived
    waived: tuple[WaivedFinding, ...]
    rules_run: tuple[str, ...]

    @property
    def errors(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.ERROR)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.WARNING)

    @property
    def infos(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.severity is Severity.INFO)

    @property
    def ok(self) -> bool:
        """The gate: zero errors after waivers. Never ``None``, never falsy-by-accident."""
        return len(self.errors) == 0

    def by_rule(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {r: [] for r in self.rules_run}
        for f in self.findings:
            out.setdefault(f.rule_id, []).append(f)
        return out

    def counts(self) -> dict[str, int]:
        return {"findings": len(self.findings), "errors": len(self.errors),
                "warnings": len(self.warnings), "infos": len(self.infos),
                "waived": len(self.waived)}

    def summary(self) -> str:
        c = self.counts()
        verdict = "OK" if self.ok else "FAILED"
        return (f"{verdict} ({c['errors']} errors, {c['warnings']} warnings, "
                f"{c['waived']} waived)")

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "ok": self.ok,
            "counts": self.counts(),
            "findings": [f.__dict__ | {"severity": f.severity.value}
                         for f in self.findings],
            "waived": [{"finding": w.finding.__dict__
                        | {"severity": w.finding.severity.value},
                        "waiver": w.waiver.as_dict()} for w in self.waived],
        }


def check(design: Design | Mapping[str, Design], *,
          waivers: Sequence[Waiver | Mapping[str, str]] | None = None,
          domain: str | None = None,
          rule_ids: Sequence[str] | None = None,
          ctx: RuleContext | None = None,
          **ctx_kwargs) -> Report:
    """Run the rule pack over a design (or a mapping of sheets) and report.

    ``waivers`` accepts :class:`Waiver` objects or plain dicts; a dict
    missing ``reason``/``cited_source``/``author`` raises rather than being
    accepted as a bare mute. Waivers that match no finding are reported as
    ``WAIVER-STALE`` findings.
    """
    if ctx is None:
        if isinstance(design, Mapping):
            ctx = RuleContext.merged(design, **ctx_kwargs)
        else:
            ctx = RuleContext.build(design, **ctx_kwargs)

    selected = [r for r in rules(domain)
                if rule_ids is None or r.id in set(rule_ids)]
    found: list[Finding] = []
    for rule in selected:
        found.extend(rule.run(ctx))

    ledger = [w for w in (w if isinstance(w, Waiver) else Waiver.from_dict(w)
                          for w in (waivers or ()))
              if w.applies_to(ctx.name)]
    by_key: dict[tuple[str, str], Waiver] = {w.key(): w for w in ledger}
    used: set[tuple[str, str]] = set()

    active: list[Finding] = []
    waived: list[WaivedFinding] = []
    for f in found:
        w = by_key.get(f.key())
        if w is None:
            active.append(f)
        else:
            used.add(w.key())
            waived.append(WaivedFinding(finding=f, waiver=w))

    for w in ledger:
        if w.key() in used:
            continue
        active.append(Finding(
            rule_id=WAIVER_STALE, severity=Severity.WARNING,
            target=f"{w.rule_id}:{w.target}",
            message=(f"stale waiver: nothing matched {w.rule_id} "
                     f"target {w.target!r} (author {w.author})"),
            remediation=("delete the waiver, or fix the target if the finding "
                         "it covered was renamed"),
            citation=_STALE_CITATION, design=ctx.name))

    return Report(name=ctx.name, findings=tuple(active), waived=tuple(waived),
                  rules_run=tuple(r.id for r in selected))
