"""Power-domain electrical rules (PWR-001 … PWR-007).

Every rule below carries a :class:`~src.ecad.circuits.blocks.Provenance`
pointing at a real document, and every threshold is quoted in the rule's
``doc`` string rather than being a magic number. The two documents that do
most of the work:

HDG
    Espressif *ESP32-S3 Hardware Design Guidelines — Schematic Checklist*,
    https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html
DS
    Espressif *ESP32-S3-WROOM-1 & ESP32-S3-WROOM-1U Datasheet*, the copy in
    ``data/datasheets/esp32-s3-wroom-1.pdf`` (v1.3): Table 9 Absolute
    Maximum Ratings, Table 10 Recommended Operating Conditions, Table 7
    VDD_SPI Voltage Control, Section 6 Peripheral Schematics.

What these rules do NOT check
-----------------------------
Anything geometric. HDG repeatedly says a capacitor must sit "close to the
pins"; proximity is a *layout* property and nothing in a ``Design`` knows
where a part will be placed. PWR-002 therefore checks **presence only**,
and says so in its title and in every finding it emits. A clean PWR-002 is
not a claim that the decoupling is well placed.

Curated part facts
------------------
:data:`DATASHEET_FACTS` is a small table of electrical envelopes read out
of datasheets this repo actually ships (or that ``src/ecad/circuits`` already
cites). It exists because no part model in the library carries an electrical
envelope yet and no ``data/ingest/<id>/extracted.json`` carries a ``power``
object today — without it PWR-004/005/007 could only ever say "no data",
which is a gate that cannot fail. Each entry quotes the table it came from
in its ``source``, and that string is printed verbatim in findings.
"""

from __future__ import annotations

from collections.abc import Iterable

from ..circuits.blocks import Provenance
from ..component import Component
from ..model import ElectricalType
from .engine import (
    Finding,
    PartFacts,
    RegulatorFacts,
    Rule,
    RuleContext,
    Severity,
    is_ground_name,
    is_ground_pin,
    is_power_pin,
    parse_volts,
    register_facts,
    register_rule,
)

__all__ = ["DATASHEET_FACTS", "DOMAIN", "KNOWN_DOMAINS"]

DOMAIN = "power"

_HDG_URL = (
    "https://docs.espressif.com/projects/esp-hardware-design-guidelines/"
    "en/latest/esp32s3/schematic-checklist.html"
)
_DS_URL = ("https://documentation.espressif.com/"
           "esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf")
_AP2112_URL = "https://www.diodes.com/assets/Datasheets/AP2112.pdf"

PROV_HDG_POWER = Provenance(
    source="Espressif ESP32-S3 Hardware Design Guidelines — Schematic Checklist",
    section="Power Supply",
    url=_HDG_URL,
)
PROV_HDG_DIGITAL = Provenance(
    source="Espressif ESP32-S3 Hardware Design Guidelines — Schematic Checklist",
    section="Power Supply → Digital Power Supply",
    url=_HDG_URL,
)
PROV_HDG_ANALOG = Provenance(
    source="Espressif ESP32-S3 Hardware Design Guidelines — Schematic Checklist",
    section="Power Supply → Analog Power Supply",
    url=_HDG_URL,
)
PROV_HDG_VDD_SPI = Provenance(
    source="Espressif ESP32-S3 Hardware Design Guidelines — Schematic Checklist",
    section="Power Supply → Digital Power Supply (VDD_SPI) and "
            "Flash and PSRAM → Off-Package Flash and PSRAM",
    url=_HDG_URL,
)
PROV_DS_OPERATING = Provenance(
    source="Espressif ESP32-S3-WROOM-1 & ESP32-S3-WROOM-1U Datasheet "
           "(data/datasheets/esp32-s3-wroom-1.pdf, v1.3)",
    section="Sec. 4.1 Table 9 Absolute Maximum Ratings and "
            "Sec. 4.2 Table 10 Recommended Operating Conditions",
    url=_DS_URL,
)
PROV_DS_PERIPHERAL = Provenance(
    source="Espressif ESP32-S3-WROOM-1 & ESP32-S3-WROOM-1U Datasheet "
           "(data/datasheets/esp32-s3-wroom-1.pdf, v1.3)",
    section="Sec. 6 Peripheral Schematics (C1 = 22 uF, C3 = 0.1 uF on 3V3)",
    url=_DS_URL,
)
PROV_DS_VDD_SPI = Provenance(
    source="Espressif ESP32-S3-WROOM-1 & ESP32-S3-WROOM-1U Datasheet "
           "(data/datasheets/esp32-s3-wroom-1.pdf, v1.3)",
    section="Sec. 3.3.2 Table 7 'VDD_SPI Voltage Control' (VDD_SPI is "
            "1.8 V or 3.3 V depending on EFUSE_VDD_SPI_FORCE and GPIO45)",
    url=_DS_URL,
)
PROV_AP2112 = Provenance(
    source="Diodes/BCD AP2112 datasheet, DS39724 Rev. 2-2 (June 2017)",
    section="Recommended Operating Conditions + AP2112-3.3 Electrical "
            "Characteristics (VDROP, IOUT(MAX))",
    url=_AP2112_URL,
)


# ---------------------------------------------------------------------------
# Curated, cited datasheet facts
# ---------------------------------------------------------------------------

_WROOM1_SOURCE = (
    "ESP32-S3-WROOM-1 datasheet v1.3 Table 10 (Recommended Operating "
    "Conditions): VDD33 min 3.0 V, typ 3.3 V, max 3.6 V; IVDD (external "
    "supply current) min 0.5 A. Table 9 (Absolute Maximum Ratings): VDD33 "
    "-0.3 V to 3.6 V"
)
_S3_SOURCE = (
    "ESP32-S3 HDG Digital Power Supply: \"operating voltage range of 3.0 V ~ "
    "3.6 V\"; VDD_SPI is a separate domain per DS v1.3 Table 7"
)
_AP2112_SOURCE = (
    "AP2112 datasheet DS39724 Rev. 2-2: Recommended Operating Conditions "
    "VIN 2.5-6.0 V; Absolute Maximum Ratings VCC (power supply voltage) "
    "6.5 V; AP2112-3.3 Electrical Characteristics VOUT 3.3 V, IOUT(MAX) "
    "600 mA (min), VDROP at IOUT = 600 mA typ 250 mV / max 400 mV"
)

#: part_name → cited electrical envelope. Additions REQUIRE a ``source``
#: quoting the table the numbers came from; a number with no quotable
#: source does not go in this table.
DATASHEET_FACTS: dict[str, PartFacts] = {
    "ESP32-S3-WROOM-1": PartFacts(
        part_name="ESP32-S3-WROOM-1",
        voltage_min=3.0, voltage_typ=3.3, voltage_max=3.6, abs_max_v=3.6,
        min_supply_current_a=0.5,
        decoupling_caps=("22uF", "0.1uF"),
        source=_WROOM1_SOURCE,
    ),
    "ESP32-S3-WROOM-1U": PartFacts(
        part_name="ESP32-S3-WROOM-1U",
        voltage_min=3.0, voltage_typ=3.3, voltage_max=3.6, abs_max_v=3.6,
        min_supply_current_a=0.5,
        decoupling_caps=("22uF", "0.1uF"),
        source=_WROOM1_SOURCE,
    ),
    "ESP32-S3": PartFacts(
        part_name="ESP32-S3",
        voltage_min=3.0, voltage_typ=3.3, voltage_max=3.6,
        min_supply_current_a=0.5,
        domains={"VDD_SPI": "VDD_SPI"},
        source=_S3_SOURCE,
    ),
    "AP2112K-3.3": PartFacts(
        part_name="AP2112K-3.3",
        voltage_min=2.5, voltage_max=6.0, abs_max_v=6.5,
        regulator=RegulatorFacts(
            output_v=3.3, dropout_v=0.4, dropout_at_ma=600.0,
            max_output_current_a=0.6, vin_min=2.5, vin_max=6.0,
            source=_AP2112_SOURCE),
        source=_AP2112_SOURCE,
    ),
}


@register_facts
def _curated(comp: Component) -> PartFacts | None:
    """Serve :data:`DATASHEET_FACTS` by part name."""
    return DATASHEET_FACTS.get(comp.part_name)


# ---------------------------------------------------------------------------
# Supply-domain identification (PWR-003)
# ---------------------------------------------------------------------------

#: Pin names that are their own supply domain, with the source that says so.
#: A name only lands here when a document states it can sit at a voltage
#: different from the part's main supply.
KNOWN_DOMAINS: dict[str, tuple[str, str]] = {
    "VDD_SPI": ("VDD_SPI",
                PROV_DS_VDD_SPI.cite() + " — VDD_SPI is 1.8 V or 3.3 V "
                "depending on EFUSE_VDD_SPI_FORCE and the GPIO45 strap. "
                + PROV_HDG_VDD_SPI.cite() + " — \"Pin VDD_SPI serves as the "
                "power supply for the external device at either 1.8 V or "
                "3.3 V (default)\" and \"select the appropriate off-package "
                "flash and RAM according to the power voltage on VDD_SPI "
                "(1.8 V/3.3 V)\""),
    "VDDSPI": ("VDD_SPI", "see VDD_SPI"),
}


#: The domain every supply pin belongs to when nothing says otherwise.
_MAIN = "MAIN"


def _domain(pin, facts: PartFacts) -> tuple[str, str, str]:
    """``(domain_id, evidence_kind, citation)`` for one supply pin.

    ``evidence_kind`` is ``"declared"``, ``"known"``, ``"volts"`` or
    ``"default"``. Distinctness needs *evidence*: two pins named ``VCC``
    and ``VDD`` both land in :data:`_MAIN` because nothing says they
    differ, and a rule that flagged them would fire on every board with two
    differently-named 3.3 V pins.
    """
    name = pin.name.upper()
    declared = dict(facts.domains or {}).get(name)
    if declared:
        return (declared, "declared",
                f"declared by the {facts.part_name or 'part'} model"
                f"{': ' + facts.source if facts.source else ''}")
    known = KNOWN_DOMAINS.get(name.replace("-", "_"))
    if known:
        return (known[0], "known", known[1])
    volts = parse_volts(name)
    if volts is not None:
        return (f"{volts:g}V", "volts",
                f"pin name {pin.name!r} encodes its nominal voltage")
    return (_MAIN, "default",
            f"{pin.name!r} is treated as {facts.part_name or 'the part'}'s "
            f"main supply domain (no source says otherwise)")


# ---------------------------------------------------------------------------
# PWR-001 — every power_in pin sits on a driven net
# ---------------------------------------------------------------------------

def _check_pwr001(ctx: RuleContext) -> Iterable[Finding]:
    for net in ctx.nets:
        if net.is_ground or not net.consumers:
            continue
        if net.drivers or net.connector_power_pins or net.name in ctx.power_sources:
            continue
        sinks = ", ".join(sorted(ctx.pin_label(p) for p in net.consumers))
        yield Finding(
            rule_id="PWR-001", severity=Severity.ERROR,
            target=net.name,
            message=f"{net.name} feeds {sinks} but nothing drives it",
            remediation=(
                "connect a regulator output (power_out), a connector power "
                f"pin, or declare {net.name!r} as an external supply "
                "(power_sources / --power-source) when it arrives as a KiCad "
                "global power symbol from another sheet"),
            citation=PROV_HDG_POWER.cite(),
            refs=tuple(sorted({ctx.ref(p.owner) for p in net.consumers})),
            pins=tuple(sorted(ctx.pin_label(p) for p in net.consumers)),
            nets=(net.name,))


# ---------------------------------------------------------------------------
# PWR-002 — decoupling presence (NOT proximity)
# ---------------------------------------------------------------------------

def _check_pwr002(ctx: RuleContext) -> Iterable[Finding]:
    for comp in ctx.ics():
        per_net: dict[str, list] = {}
        for pin in comp.pins:
            if not is_power_pin(pin) or pin.etype is ElectricalType.POWER_OUT:
                continue
            net = ctx.net_of(pin)
            if net is None:
                continue          # unconnected — Design.check() owns that
            per_net.setdefault(net.name, []).append(pin)

        for net_name, pins in sorted(per_net.items()):
            net = ctx.net(net_name)
            if net is None:
                continue
            decouplers = [c for c in net.caps
                          if _is_ground_net(ctx, c.other_net)]
            names = ", ".join(sorted(f"{p.name}(pad {p.pad})" for p in pins))
            if not decouplers:
                yield Finding(
                    rule_id="PWR-002", severity=Severity.ERROR,
                    target=f"{ctx.ref(comp)}@{net_name}",
                    message=(f"{ctx.ref(comp)} power pins {names} on {net_name} "
                             f"have no decoupling capacitor to ground"),
                    remediation=(
                        f"add a 100 nF ceramic from {net_name} to GND for each "
                        f"of the {len(pins)} pin(s) — src.ecad.circuits.decoupling"
                        f"(design, {ctx.ref(comp)}, {net_name!r}, 'GND')"),
                    citation=PROV_HDG_DIGITAL.cite() + " — \"It is recommended "
                             "to add a 0.1 uF capacitor close to the digital "
                             "power supply pins in the circuit\" (PRESENCE "
                             "only: proximity is a layout property this rule "
                             "cannot see)",
                    refs=(ctx.ref(comp),),
                    pins=tuple(sorted(f"{ctx.ref(comp)}.{p.name}" for p in pins)),
                    nets=(net_name,))
            elif len(decouplers) < len(pins):
                yield Finding(
                    rule_id="PWR-002", severity=Severity.WARNING,
                    target=f"{ctx.ref(comp)}@{net_name}:count",
                    message=(f"{ctx.ref(comp)} has {len(pins)} power pin(s) on "
                             f"{net_name} but only {len(decouplers)} "
                             f"capacitor(s) to ground "
                             f"({', '.join(c.ref for c in decouplers)})"),
                    remediation=(f"one ceramic per power pin: add "
                                 f"{len(pins) - len(decouplers)} more from "
                                 f"{net_name} to GND"),
                    citation=PROV_HDG_DIGITAL.cite() + " — one 0.1 uF per "
                             "digital power supply pin",
                    refs=(ctx.ref(comp),),
                    pins=tuple(sorted(f"{ctx.ref(comp)}.{p.name}" for p in pins)),
                    nets=(net_name,))


def _is_ground_net(ctx: RuleContext, name: str) -> bool:
    net = ctx.net(name)
    return net.is_ground if net is not None else is_ground_name(name)


# ---------------------------------------------------------------------------
# PWR-003 — two distinct supply domains merged onto one net
# ---------------------------------------------------------------------------

def _check_pwr003(ctx: RuleContext) -> Iterable[Finding]:
    # (a) a supply pin and a ground pin on one net is a rail-to-ground short
    #     — the failure mode that motivated this whole engine.
    for net in ctx.nets:
        supplies = [p for p in net.pins if is_power_pin(p)]
        grounds = [p for p in net.pins if is_ground_pin(p)]
        if supplies and grounds:
            s = ", ".join(sorted(ctx.pin_label(p) for p in supplies))
            g = ", ".join(sorted(ctx.pin_label(p) for p in grounds))
            yield Finding(
                rule_id="PWR-003", severity=Severity.ERROR,
                target=f"{net.name}:supply-vs-ground",
                message=(f"{net.name} ties supply pin(s) {s} to ground pin(s) "
                         f"{g} — a rail-to-ground short"),
                remediation=("move the ground pin(s) to the ground net; check "
                             "the part model's pin roles if this looks wrong"),
                citation=PROV_DS_PERIPHERAL.cite() + " — the peripheral "
                         "schematic returns every GND pad to GND and 3V3 to "
                         "the 3.3 V rail; the two are never commoned",
                refs=tuple(sorted({ctx.ref(p.owner) for p in supplies + grounds})),
                pins=tuple(sorted(ctx.pin_label(p)
                                  for p in supplies + grounds)),
                nets=(net.name,))

    # (b) two supply pins of ONE component, in provably different domains,
    #     sharing a net. Scoped to a single component deliberately: two
    #     different parts sharing a rail is what a rail is for, and
    #     comparing across parts would flag every board where U1 calls it
    #     3V3 and U2 calls it VCC. A part pin at the wrong rail voltage is
    #     PWR-004's job, not this one's.
    for comp in ctx.components:
        facts = ctx.facts_for(comp)
        by_net: dict[str, list] = {}
        for pin in comp.pins:
            if not is_power_pin(pin):
                continue
            net = ctx.net_of(pin)
            if net is not None:
                by_net.setdefault(net.name, []).append(pin)
        for net_name, pins in sorted(by_net.items()):
            seen: dict[str, tuple] = {}
            for pin in pins:
                key, kind, why = _domain(pin, facts)
                seen.setdefault(key, (pin, kind, why))
            keys = sorted(seen)
            for i, a_key in enumerate(keys):
                for b_key in keys[i + 1:]:
                    a_pin, a_kind, a_why = seen[a_key]
                    b_pin, b_kind, b_why = seen[b_key]
                    kinds = {a_kind, b_kind}
                    # Evidence gate: a difference is real only when a source
                    # names one of the pins as its own domain, or both names
                    # encode a voltage and the voltages differ.
                    if not (kinds & {"declared", "known"}
                            or kinds == {"volts"}):
                        continue
                    yield Finding(
                        rule_id="PWR-003", severity=Severity.ERROR,
                        target=f"{ctx.ref(comp)}:{a_pin.name}+{b_pin.name}@{net_name}",
                        message=(f"{ctx.ref(comp)} {a_pin.name} ({a_key}) and "
                                 f"{b_pin.name} ({b_key}) are distinct supply "
                                 f"domains but are both tied to {net_name}"),
                        remediation=(f"give {a_pin.name} and {b_pin.name} "
                                     f"separate nets — they are not guaranteed "
                                     f"to sit at the same voltage"),
                        citation=f"{a_why}; {b_why}",
                        refs=(ctx.ref(comp),),
                        pins=(f"{ctx.ref(comp)}.{a_pin.name}",
                              f"{ctx.ref(comp)}.{b_pin.name}"),
                        nets=(net_name,))


# ---------------------------------------------------------------------------
# PWR-004 — rail voltage inside the part's recommended / absolute range
# ---------------------------------------------------------------------------

def _check_pwr004(ctx: RuleContext) -> Iterable[Finding]:
    for comp in ctx.ics():
        facts = ctx.facts_for(comp)
        rails: dict[str, list] = {}
        for pin in comp.pins:
            if not is_power_pin(pin) or pin.etype is ElectricalType.POWER_OUT:
                continue
            net = ctx.net_of(pin)
            if net is not None:
                rails.setdefault(net.name, []).append(pin)
        if not rails:
            continue

        if facts.voltage_min is None and facts.voltage_max is None:
            yield Finding(
                rule_id="PWR-004", severity=Severity.INFO,
                target=f"{ctx.ref(comp)}:no-part-data",
                message=(f"no data: {ctx.ref(comp)} ({comp.part_name}) has no "
                         f"recommended-supply range in the part model, in "
                         f"data/ingest/<id>/extracted.json or in the curated "
                         f"table — rail voltage NOT checked"),
                remediation=("add a cited PartFacts entry, declare POWER_FACTS "
                             "on the part model, or extract the datasheet's "
                             "recommended operating conditions"),
                citation=PROV_DS_OPERATING.cite(),
                refs=(ctx.ref(comp),), nets=tuple(sorted(rails)))
            continue

        for net_name, pins in sorted(rails.items()):
            rail = ctx.rail_voltage(net_name)
            names = ", ".join(sorted(p.name for p in pins))
            if rail is None:
                yield Finding(
                    rule_id="PWR-004", severity=Severity.INFO,
                    target=f"{ctx.ref(comp)}@{net_name}:no-rail-data",
                    message=(f"no data: {net_name} has no known voltage "
                             f"(name does not encode one and no regulator on "
                             f"it declares an output) — {ctx.ref(comp)} {names} "
                             f"NOT checked"),
                    remediation=(f"name the rail with its voltage (+3V3), pass "
                                 f"rail_voltages={{{net_name!r}: ...}}, or give "
                                 f"the regulator driving it a cited output_v"),
                    citation=PROV_DS_OPERATING.cite(),
                    refs=(ctx.ref(comp),), nets=(net_name,))
                continue
            lo, hi = facts.voltage_min, facts.voltage_max
            over_abs = facts.abs_max_v is not None and rail.volts > facts.abs_max_v
            if over_abs:
                yield Finding(
                    rule_id="PWR-004", severity=Severity.ERROR,
                    target=f"{ctx.ref(comp)}@{net_name}",
                    message=(f"{net_name} is {rail.volts:g} V; {ctx.ref(comp)} "
                             f"({comp.part_name}) {names} has an absolute "
                             f"maximum of {facts.abs_max_v:g} V — this "
                             f"destroys the part"),
                    remediation=f"regulate {net_name} down to "
                                f"{facts.voltage_typ or facts.voltage_max:g} V",
                    citation=f"{facts.source} [rail voltage from: {rail.source}]",
                    refs=(ctx.ref(comp),),
                    pins=tuple(sorted(f"{ctx.ref(comp)}.{p.name}" for p in pins)),
                    nets=(net_name,))
            elif (lo is not None and rail.volts < lo) or \
                 (hi is not None and rail.volts > hi):
                yield Finding(
                    rule_id="PWR-004", severity=Severity.ERROR,
                    target=f"{ctx.ref(comp)}@{net_name}",
                    message=(f"{net_name} is {rail.volts:g} V, outside "
                             f"{ctx.ref(comp)} ({comp.part_name}) recommended "
                             f"{_range(lo, hi)} for {names}"),
                    remediation=f"bring {net_name} inside {_range(lo, hi)}",
                    citation=f"{facts.source} [rail voltage from: {rail.source}]",
                    refs=(ctx.ref(comp),),
                    pins=tuple(sorted(f"{ctx.ref(comp)}.{p.name}" for p in pins)),
                    nets=(net_name,))


def _range(lo: float | None, hi: float | None) -> str:
    if lo is not None and hi is not None:
        return f"{lo:g}-{hi:g} V"
    return f"min {lo:g} V" if lo is not None else f"max {hi:g} V"


# ---------------------------------------------------------------------------
# PWR-005 — regulator dropout / headroom
# ---------------------------------------------------------------------------

def _check_pwr005(ctx: RuleContext) -> Iterable[Finding]:
    for comp in ctx.regulators():
        reg = ctx.facts_for(comp).regulator
        vin_nets = sorted({n.name for n in (ctx.net_of(p) for p in comp.pins
                                            if p.etype is ElectricalType.POWER_IN)
                           if n is not None and not n.is_ground})
        vout_nets = sorted({n.name for n in (ctx.net_of(p) for p in comp.pins
                                             if p.etype is ElectricalType.POWER_OUT)
                            if n is not None})
        if reg is None or reg.dropout_v is None:
            yield Finding(
                rule_id="PWR-005", severity=Severity.INFO,
                target=f"{ctx.ref(comp)}:no-dropout-data",
                message=(f"no data: {ctx.ref(comp)} ({comp.part_name}) is a "
                         f"regulator but no source states its dropout voltage "
                         f"— headroom NOT checked"),
                remediation=("add a cited RegulatorFacts(dropout_v=...) entry "
                             "or declare POWER_FACTS on the part model"),
                citation=PROV_AP2112.cite(),
                refs=(ctx.ref(comp),), nets=tuple(vin_nets + vout_nets))
            continue
        if not vin_nets or not vout_nets:
            continue
        vin_v = ctx.rail_voltage(vin_nets[0])
        vout_v = ctx.rail_voltage(vout_nets[0])
        if vin_v is None or vout_v is None:
            unknown = vin_nets[0] if vin_v is None else vout_nets[0]
            yield Finding(
                rule_id="PWR-005", severity=Severity.INFO,
                target=f"{ctx.ref(comp)}:no-rail-data",
                message=(f"no data: {ctx.ref(comp)} headroom NOT checked — "
                         f"{unknown} has no known voltage"),
                remediation=f"name {unknown} with its voltage or pass "
                            f"rail_voltages",
                citation=PROV_AP2112.cite(),
                refs=(ctx.ref(comp),), nets=(unknown,))
            continue
        headroom = vin_v.volts - vout_v.volts
        if headroom < reg.dropout_v:
            at = (f" at {reg.dropout_at_ma:g} mA" if reg.dropout_at_ma
                  else "")
            yield Finding(
                rule_id="PWR-005", severity=Severity.ERROR,
                target=f"{ctx.ref(comp)}:{vin_nets[0]}->{vout_nets[0]}",
                message=(f"{ctx.ref(comp)} ({comp.part_name}) has "
                         f"{headroom:.3g} V headroom "
                         f"({vin_nets[0]} {vin_v.volts:g} V - "
                         f"{vout_nets[0]} {vout_v.volts:g} V) but needs "
                         f"{reg.dropout_v:g} V dropout{at} — it will not "
                         f"regulate"),
                remediation=(f"raise {vin_nets[0]} above "
                             f"{vout_v.volts + reg.dropout_v:g} V or choose a "
                             f"lower-dropout regulator"),
                citation=f"{reg.source} [{vin_nets[0]}: {vin_v.source}; "
                         f"{vout_nets[0]}: {vout_v.source}]",
                refs=(ctx.ref(comp),), nets=(vin_nets[0], vout_nets[0]))


# ---------------------------------------------------------------------------
# PWR-006 — bulk capacitance at the entry point and per rail
# ---------------------------------------------------------------------------

#: HDG minimum. "It is suggested to add an ESD protection diode and at least
#: 10 uF capacitor at the main power entrance"; and for the analog rail "it
#: is highly recommended to add a 10 uF capacitor to the power rail".
BULK_MIN_F = 10e-6
#: The stricter corroborating source: DS v1.3 Sec. 6 Peripheral Schematics
#: fits C1 = 22 uF on 3V3. Reported as WARNING, never ERROR — two Espressif
#: documents disagree and the engine does not get to pick a winner silently.
BULK_PREFERRED_F = 22e-6
#: Comparison guard band. ``parse_farads("10uF")`` is 1.0000000000000002e-05
#: in binary floating point, so a bare ``<`` reports a fitted 10 uF part as
#: short of a 10 uF minimum. 0.1 % is far inside any real capacitor's
#: tolerance (X5R/X7R ship at +/-10 % to +/-20 %), so nothing physical hides
#: in it.
_TOLERANCE = 0.999


def _short_of(total: float, target: float) -> bool:
    return total < target * _TOLERANCE


def _check_pwr006(ctx: RuleContext) -> Iterable[Finding]:
    for net in ctx.nets:
        if net.is_ground:
            continue
        entry = bool(net.connector_power_pins)
        if not (net.consumers or net.drivers or entry):
            continue
        bulk = [c for c in net.caps
                if _is_ground_net(ctx, c.other_net) and c.farads is not None]
        total = sum(c.farads for c in bulk if c.farads is not None)
        listed = ", ".join(f"{c.ref} {c.value}" for c in bulk) or "none"
        where = "power entry point " if entry else "rail "
        if _short_of(total, BULK_MIN_F):
            yield Finding(
                rule_id="PWR-006", severity=Severity.ERROR,
                target=net.name,
                message=(f"{where}{net.name} has {_uf(total)} of bulk "
                         f"capacitance to ground ({listed}); the guideline "
                         f"minimum is {_uf(BULK_MIN_F)}"),
                remediation=(f"add {_uf(BULK_MIN_F - total)} more from "
                             f"{net.name} to GND — "
                             f"src.ecad.circuits.bypass_capacitor("
                             f"design, {net.name!r}, 'GND', value='10uF')"),
                citation=PROV_HDG_POWER.cite() + " — \"It is suggested to add "
                         "an ESD protection diode and at least 10 uF capacitor "
                         "at the main power entrance (where the external power "
                         "supply enters the PCB)\"; " + PROV_HDG_ANALOG.cite()
                         + " — \"it is highly recommended to add a 10 uF "
                           "capacitor to the power rail\"",
                nets=(net.name,),
                refs=tuple(c.ref for c in bulk))
        elif _short_of(total, BULK_PREFERRED_F):
            yield Finding(
                rule_id="PWR-006", severity=Severity.WARNING,
                target=f"{net.name}:preferred",
                message=(f"{where}{net.name} has {_uf(total)} of bulk "
                         f"capacitance ({listed}); it clears the 10 uF "
                         f"guideline minimum but is below the "
                         f"{_uf(BULK_PREFERRED_F)} the datasheet's own "
                         f"application circuit fits"),
                remediation=(f"raise {net.name} to {_uf(BULK_PREFERRED_F)}, or "
                             f"waive citing the guideline minimum"),
                citation=PROV_DS_PERIPHERAL.cite() + " — two Espressif "
                         "documents disagree (HDG says at least 10 uF, DS "
                         "Sec. 6 fits 22 uF); the stricter one is reported as "
                         "a WARNING, not an ERROR",
                nets=(net.name,),
                refs=tuple(c.ref for c in bulk))


def _uf(farads: float) -> str:
    return f"{farads * 1e6:g} uF"


# ---------------------------------------------------------------------------
# PWR-007 — the regulator can actually supply the rail's declared load
# ---------------------------------------------------------------------------

def _check_pwr007(ctx: RuleContext) -> Iterable[Finding]:
    for net in ctx.nets:
        if net.is_ground or not net.drivers:
            continue
        sources = []
        for driver in net.drivers:
            reg = ctx.facts_for(driver.owner).regulator
            if reg is not None and reg.max_output_current_a is not None:
                sources.append((driver.owner, reg))
        demand: list[tuple[str, float]] = []
        for pin in net.consumers:
            need = ctx.facts_for(pin.owner).min_supply_current_a
            if need is not None and not any(r == ctx.ref(pin.owner)
                                            for r, _ in demand):
                demand.append((ctx.ref(pin.owner), need))
        if not sources or not demand:
            if net.consumers and net.drivers:
                missing = "regulator current rating" if not sources \
                    else "load current requirement"
                yield Finding(
                    rule_id="PWR-007", severity=Severity.INFO,
                    target=f"{net.name}:no-current-data",
                    message=(f"no data: {net.name} current budget NOT checked "
                             f"— no {missing} is stated by any source"),
                    remediation=("add cited RegulatorFacts(max_output_current_a"
                                 "=...) / PartFacts(min_supply_current_a=...)"),
                    citation=PROV_HDG_POWER.cite(),
                    nets=(net.name,))
            continue
        comp, reg = sources[0]
        total = sum(a for _, a in demand)
        if total > (reg.max_output_current_a or 0.0):
            listed = ", ".join(f"{r} {a * 1000:g} mA" for r, a in sorted(demand))
            yield Finding(
                rule_id="PWR-007", severity=Severity.ERROR,
                target=f"{net.name}:{ctx.ref(comp)}",
                message=(f"{ctx.ref(comp)} ({comp.part_name}) can supply "
                         f"{reg.max_output_current_a * 1000:g} mA on "
                         f"{net.name} but its loads need {total * 1000:g} mA "
                         f"({listed})"),
                remediation=(f"choose a regulator rated above "
                             f"{total * 1000:g} mA for {net.name}"),
                citation=PROV_HDG_POWER.cite() + " — \"When using a single "
                         "power supply, the recommended power supply voltage "
                         "is 3.3 V and the output current is no less than 500 "
                         "mA\"; " + PROV_DS_OPERATING.cite() + " — Table 10 "
                         "IVDD min 0.5 A. Regulator rating: " + reg.source,
                refs=(ctx.ref(comp),) + tuple(r for r, _ in sorted(demand)),
                nets=(net.name,))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

PWR_001 = register_rule(Rule(
    id="PWR-001", domain=DOMAIN, severity=Severity.ERROR,
    title="every power_in pin sits on a driven rail",
    provenance=PROV_HDG_POWER, check=_check_pwr001,
    doc="""A net that feeds a ``power_in`` pin must have something that
    drives it: a ``power_out`` pin, a connector power pin (power arriving
    from off-board — the PWR_FLAG equivalent), or an explicit declaration
    in ``power_sources``. KiCad ERC's own "power input not driven" check is
    the same idea; this one runs on the typed model, before emission.

    Sheets: this repo's designs are one ``Design`` per schematic sheet and
    rails cross sheets as global power symbols, so a per-sheet run
    correctly reports the incoming rail as undriven. Check the merged
    context (or declare the rail) to see the board's answer.""",
))

PWR_002 = register_rule(Rule(
    id="PWR-002", domain=DOMAIN, severity=Severity.ERROR,
    title="each IC power pin has a decoupling capacitor to ground (PRESENCE ONLY)",
    provenance=PROV_HDG_DIGITAL, check=_check_pwr002,
    doc="""HDG, Digital Power Supply: "It is recommended to add a 0.1 uF
    capacitor close to the digital power supply pins in the circuit."

    **This rule checks presence, not proximity, and that is a real
    limitation.** "Close to the pins" is a placement property; a ``Design``
    holds no coordinates, so a capacitor on the far side of the board reads
    identically to one under the pad. A clean PWR-002 says the capacitor
    exists on the right two nets — nothing more. Proximity belongs to a
    layout-domain rule with a placed sheet in hand.

    ERROR when a power pin's rail has no capacitor to ground at all;
    WARNING when there are fewer capacitors than power pins on that rail
    (the guideline is one per pin). Connectors are excluded — nothing
    decouples a connector; its entry capacitance is PWR-006's job.""",
))

PWR_003 = register_rule(Rule(
    id="PWR-003", domain=DOMAIN, severity=Severity.ERROR,
    title="two distinct supply domains are never merged onto one net",
    provenance=PROV_DS_VDD_SPI, check=_check_pwr003,
    doc="""Two failure modes, one rule:

    (a) a supply pin and a ground pin on the same net — a rail-to-ground
    short. This is the near-miss that motivated the engine: a regulator
    whose GND pad was mis-roled would have been wired to VIN, and every
    syntactic gate stayed green.

    (b) two supply pins from provably different voltage domains on one net.
    The canonical case is the ESP32-S3's ``VDD_SPI``: DS v1.3 Table 7
    "VDD_SPI Voltage Control" makes it 1.8 V or 3.3 V depending on
    EFUSE_VDD_SPI_FORCE and the GPIO45 strap, so tying it to a 3.3 V rail
    destroys the 1.8 V flash option. HDG: "select the appropriate
    off-package flash and RAM according to the power voltage on VDD_SPI
    (1.8 V/3.3 V)".

    Distinctness requires evidence — an explicit domain on the part model,
    the cited ``KNOWN_DOMAINS`` table, or two pin names that encode
    different voltages. ``VCC`` and ``VDD`` on one net are NOT flagged:
    nothing says they differ, and a rule that guessed would fire on every
    board.""",
))

PWR_004 = register_rule(Rule(
    id="PWR-004", domain=DOMAIN, severity=Severity.ERROR,
    title="rail voltage inside the part's recommended / absolute-maximum range",
    provenance=PROV_DS_OPERATING, check=_check_pwr004,
    doc="""ESP32-S3-WROOM-1 DS v1.3, Table 10 Recommended Operating
    Conditions: VDD33 min 3.0 V, typ 3.3 V, max 3.6 V. Table 9 Absolute
    Maximum Ratings: VDD33 -0.3 V to 3.6 V — "exceeding the absolute
    maximum ratings may cause permanent damage to the device".

    The rail's voltage comes from (in order) the caller, a regulator on the
    net that declares its output, the net's own name (``+3V3`` → 3.3 V), or
    a cited standard (``VBUS`` → 5 V, USB Type-C R2.0 Table 4-3). When none
    of those answer, or the part has no stated range, the rule emits INFO
    "no data" and checks nothing. It never guesses a voltage — a rule that
    invented 3.3 V because the part "looked like" a 3.3 V part would be
    worse than no rule.""",
))

PWR_005 = register_rule(Rule(
    id="PWR-005", domain=DOMAIN, severity=Severity.ERROR,
    title="regulator input headroom covers its dropout voltage",
    provenance=PROV_AP2112, check=_check_pwr005,
    doc="""Vin - Vout must be at least the regulator's dropout voltage, or
    the output silently follows the input down and the "3.3 V" rail is not
    3.3 V. AP2112 DS39724 Rev. 2-2, AP2112-3.3 Electrical Characteristics:
    VDROP at IOUT = 600 mA is 250 mV typical, 400 mV maximum — this rule
    uses the maximum, because a design that only works at typical is not a
    design.

    Only runs where a source states the dropout; otherwise INFO "no
    data".""",
))

PWR_006 = register_rule(Rule(
    id="PWR-006", domain=DOMAIN, severity=Severity.ERROR,
    title="bulk capacitance at the power entry point and on each rail",
    provenance=PROV_HDG_POWER, check=_check_pwr006,
    doc="""HDG, Power Supply: "It is suggested to add an ESD protection
    diode and at least 10 uF capacitor at the main power entrance (where
    the external power supply enters the PCB)." HDG, Analog Power Supply:
    "there may be a sudden increase in the current draw, causing power rail
    collapse. Therefore, it is highly recommended to add a 10 uF capacitor
    to the power rail."

    Two sources disagree about the number and the engine does not get to
    pick a winner silently: below 10 uF is an ERROR (the guideline
    minimum); between 10 uF and the 22 uF that DS v1.3 Sec. 6 Peripheral
    Schematics actually fits (C1) is a WARNING. Both citations travel with
    the finding.""",
))

PWR_007 = register_rule(Rule(
    id="PWR-007", domain=DOMAIN, severity=Severity.ERROR,
    title="the regulator on a rail can supply that rail's declared load",
    provenance=PROV_HDG_POWER, check=_check_pwr007,
    doc="""HDG, Power Supply: "When using a single power supply, the
    recommended power supply voltage is 3.3 V and the output current is no
    less than 500 mA." Corroborated by the part's own datasheet:
    ESP32-S3-WROOM-1 DS v1.3 Table 10 lists IVDD, the external supply
    current, with a **minimum** of 0.5 A — it is a requirement on the
    supply, not a consumption figure.

    So: sum the declared ``min_supply_current_a`` of every consumer on a
    rail and compare it with the driving regulator's rated output. INFO "no
    data" when either side is unstated.""",
))
