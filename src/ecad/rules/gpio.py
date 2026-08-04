"""GPIO and strapping-pin rules (GPIO-001 … GPIO-005).

Same contract as :mod:`src.ecad.rules.power`: every rule carries a
:class:`~src.ecad.circuits.blocks.Provenance` pointing at a real document,
every threshold is quoted in the rule's ``doc`` rather than being a magic
number, and a rule that lacks the data it needs says so instead of guessing.

Why this pack exists now
------------------------
``PinRole.STRAPPING`` was never assigned by any pin path until the part
factory started emitting it, so a strapping rule would have been a gate that
could not fire. It now is assigned:
``src/ecad/library/espressif/esp32_s3_wroom_1.md`` carries a "Unit 2:
Strapping" listing IO0/IO3/IO45/IO46 with ``role: strapping``, matching the
datasheet.

Sources, quoted verbatim where a rule depends on the wording
------------------------------------------------------------
HDG
    Espressif *ESP32-S3 Hardware Design Guidelines — Schematic Checklist*,
    https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html

    *Strapping Pins*: "At each startup or reset, a chip requires some initial
    configuration parameters, such as in which boot mode to load the chip,
    etc. These parameters are passed over via the strapping pins. After
    reset, the strapping pins work as normal function pins." — "GPIO0, GPIO3,
    GPIO45, and GPIO46 are strapping pins." — and, under *Attention*: "It is
    recommended to place a pull-up resistor at the GPIO0 pin." / "Do not add
    high-value capacitors at GPIO0, or the chip may enter download mode."

    *GPIO → IO Pin Default Configuration*: GPIO0 is "IE, WPU", GPIO45 and
    GPIO46 are "IE, WPD", and **GPIO3 is "IE" alone — no WPU, no WPD**.
    Also: "For unused pins in the high-impedance state without an internal
    pull-up or pull-down, it is recommended to add a pull-up or pull-down
    resistor or enable the internal pull during software initialization…"

    *ADC*: "Please add a 0.1 μF filter capacitor between ESP pins and ground
    when using the ADC function to improve accuracy."

DS
    Espressif *ESP32-S3-WROOM-1 & ESP32-S3-WROOM-1U Datasheet* **v1.8**,
    Chapter 4 *Boot Configurations*
    (``data/datasheets/esp32-s3-wroom-1.pdf``).

    Table 4-1 *Default Configuration of Strapping Pins* (p. 13), verbatim::

        Strapping Pin | Default Configuration | Bit Value
        GPIO0         | Weak pull-up          | 1
        GPIO3         | Floating              | –
        GPIO45        | Weak pull-down        | 0
        GPIO46        | Weak pull-down        | 0

    Surrounding text (p. 13): "The default values of the strapping pins,
    namely the logic levels, are determined by pins' internal weak
    pull-up/pull-down resistors at reset if the pins are not connected to any
    circuit, or connected to an external high-impedance circuit." and "To
    change the bit values, the strapping pins should be connected to external
    pull-down/pull-up resistances. If the ESP32-S3 is used as a device by a
    host MCU, the strapping pin voltage levels can also be controlled by the
    host MCU."

    Sec. 4.4 *JTAG Signal Source Control* (p. 15), about GPIO3: "This pin does
    not have any internal pull resistors and the strapping value must be
    controlled by the external circuit that cannot be in a high impedance
    state."

DevKitC-1
    Espressif *ESP32-S3-DevKitC-1 V1.1* reference schematic (2022-04-13),
    https://dl.espressif.com/dl/schematics/SCH_ESP32-S3-DevKitC-1_V1.1_20220413.pdf
    — the GPIO0 button network reserves **C13, marked
    "0.1uF/50V(10%)(NC)"**: the footprint exists and is deliberately *not
    populated*. This is the only numeric anchor Espressif give for the
    "high-value capacitor" warning; see :data:`STRAP_CAP_MAX_F`.

What this pack does NOT check
-----------------------------
Anything about *intent*. A part model states a pin's role and its alternate
functions; it cannot state what the firmware will do with it. GPIO-005
therefore fires only on pins the model says can be **nothing but** an analog
input, and says so in its finding. Nothing here checks placement either —
"close to the chip" is a layout property, exactly as for PWR-002.

There is deliberately no GPIO-006. The obvious candidate is the HDG's "For
unused pins in the high-impedance state … it is recommended to add a pull-up
or pull-down resistor", but "unused" is not a property a ``Design`` records:
every unrouted pin of a 41-pin module would trip it, and the guideline itself
offers "or enable the internal pull during software initialization" as an
equally valid answer that no schematic can show. A rule that fires on every
board and can be satisfied in firmware is noise, not a gate.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from ..circuits.blocks import Provenance
from ..component import Component, Pin
from ..model import ElectricalType, PinRole
from .engine import (
    Finding,
    NetView,
    Rule,
    RuleContext,
    Severity,
    is_ground_name,
    is_ground_pin,
    is_power_pin,
    register_rule,
)

__all__ = [
    "ADC_FILTER_F",
    "DOMAIN",
    "STRAP_CAP_MAX_F",
    "adc_functions",
    "gpio_key",
    "is_input_only",
    "strapping_pins",
    "waiver_target",
]

DOMAIN = "gpio"

_HDG_URL = (
    "https://docs.espressif.com/projects/esp-hardware-design-guidelines/"
    "en/latest/esp32s3/schematic-checklist.html"
)
_DS_URL = ("https://documentation.espressif.com/"
           "esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf")
_DEVKIT_URL = (
    "https://dl.espressif.com/dl/schematics/"
    "SCH_ESP32-S3-DevKitC-1_V1.1_20220413.pdf"
)

PROV_HDG_STRAPPING = Provenance(
    source="Espressif ESP32-S3 Hardware Design Guidelines — Schematic Checklist",
    section="Strapping Pins (incl. the 'Attention' box)",
    url=_HDG_URL,
)
PROV_HDG_GPIO = Provenance(
    source="Espressif ESP32-S3 Hardware Design Guidelines — Schematic Checklist",
    section="GPIO → IO Pin Default Configuration",
    url=_HDG_URL,
)
PROV_HDG_ADC = Provenance(
    source="Espressif ESP32-S3 Hardware Design Guidelines — Schematic Checklist",
    section="ADC → ADC Functions",
    url=_HDG_URL,
)
PROV_DS_STRAPPING = Provenance(
    source="Espressif ESP32-S3-WROOM-1 & ESP32-S3-WROOM-1U Datasheet v1.8 "
           "(data/datasheets/esp32-s3-wroom-1.pdf)",
    section="Chapter 4 Boot Configurations, Table 4-1 'Default Configuration "
            "of Strapping Pins' (p. 13) and Sec. 4.4 JTAG Signal Source "
            "Control (p. 15)",
    url=_DS_URL,
)
PROV_DEVKIT_GPIO0 = Provenance(
    source="Espressif ESP32-S3-DevKitC-1 V1.1 reference schematic (2022-04-13)",
    section="GPIO0 button network — C13 '0.1uF/50V(10%)(NC)': the 0.1 uF "
            "footprint is reserved and deliberately left unpopulated",
    url=_DEVKIT_URL,
)

#: Verbatim quotes the findings carry, so a number can always be traced.
_Q_NO_HIGH_CAPS = ("HDG Strapping Pins, Attention: \"Do not add high-value "
                   "capacitors at GPIO0, or the chip may enter download "
                   "mode.\"")
_Q_PULLUP_GPIO0 = ("HDG Strapping Pins, Attention: \"It is recommended to "
                   "place a pull-up resistor at the GPIO0 pin.\"")
_Q_DS_DEFAULTS = (
    "DS v1.8 p. 13: \"The default values of the strapping pins, namely the "
    "logic levels, are determined by pins' internal weak pull-up/pull-down "
    "resistors at reset if the pins are not connected to any circuit, or "
    "connected to an external high-impedance circuit. To change the bit "
    "values, the strapping pins should be connected to external "
    "pull-down/pull-up resistances. If the ESP32-S3 is used as a device by a "
    "host MCU, the strapping pin voltage levels can also be controlled by the "
    "host MCU.\" Table 4-1: GPIO0 Weak pull-up = 1, GPIO3 Floating = –, "
    "GPIO45 Weak pull-down = 0, GPIO46 Weak pull-down = 0"
)
_Q_DS_GPIO3 = (
    "DS v1.8 Sec. 4.4: \"This pin does not have any internal pull resistors "
    "and the strapping value must be controlled by the external circuit that "
    "cannot be in a high impedance state.\" Corroborated by HDG's IO Pin "
    "Default Configuration table, where GPIO3 is \"IE\" alone while GPIO0 is "
    "\"IE, WPU\" and GPIO45/GPIO46 are \"IE, WPD\""
)
_Q_ADC_FILTER = ("HDG ADC: \"Please add a 0.1 μF filter capacitor between ESP "
                 "pins and ground when using the ADC function to improve "
                 "accuracy.\"")


# ---------------------------------------------------------------------------
# Thresholds — each with the source that fixes it
# ---------------------------------------------------------------------------

#: The capacitance at or above which GPIO-004 calls a capacitor on a strapping
#: net "high-value".
#:
#: **Espressif state no number.** The HDG says only "Do not add high-value
#: capacitors at GPIO0, or the chip may enter download mode", and the same
#: sentence appears verbatim in the ESP32 and ESP32-S2 checklists with no
#: value attached; the DS says nothing about capacitance on strapping pins at
#: all. Inventing a number would be exactly the failure this repo keeps
#: auditing, so the threshold is taken from the one place Espressif put a
#: capacitor value next to GPIO0: DevKitC-1 V1.1 reserves C13 at the GPIO0
#: button as "0.1uF/50V(10%)(NC)" — a 0.1 uF footprint they lay out and then
#: refuse to populate. 0.1 uF is therefore the smallest capacitance Espressif
#: themselves decline to fit at GPIO0, and this rule flags at or above it.
#: The finding says all of that, including that the HDG gives no value.
STRAP_CAP_MAX_F = 0.1e-6

#: The ADC filter capacitance the HDG names outright (see :data:`_Q_ADC_FILTER`).
ADC_FILTER_F = 0.1e-6

#: Comparison guard band, same reasoning as ``power.BULK_MIN_F``'s: binary
#: floating point makes ``parse_farads("0.1uF")`` 1.0000000000000001e-07, and
#: 0.1 % is far inside any real capacitor tolerance.
_TOLERANCE = 0.999

#: Reference prefixes this pack will conduct a "pull" through. Resistors only:
#: a button (``SW``) or a diode (``D``) between a strap and a rail is not a
#: pull, and treating one as a pull is how GPIO-001 would pass a board whose
#: strap is defined only while a button is held.
_RESISTOR_PREFIXES = frozenset({"R"})

#: Prefixes whose pins reach circuitry this design does not model.
_CONNECTOR_PREFIXES = frozenset({"J", "P", "X"})

#: Etypes that can hold a net at a level the design chose.
_DRIVING = frozenset({
    ElectricalType.OUTPUT,
    ElectricalType.TRI_STATE,
    ElectricalType.OPEN_COLLECTOR,
    ElectricalType.OPEN_EMITTER,
    ElectricalType.BIDIRECTIONAL,
})

_GPIO_KEY_RE = re.compile(r"^(?:GPIO|IO)?(\d+)$", re.IGNORECASE)
_ADC_FN_RE = re.compile(r"^ADC\d*_CH\d+$", re.IGNORECASE)
_GPIO_FN_RE = re.compile(r"^GPIO(\d+)$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Reading the part model — never a hardcoded pin list
# ---------------------------------------------------------------------------

def gpio_key(text: object) -> str:
    """Normalise a GPIO reference to one spelling: ``IO0``/``0`` → ``GPIO0``.

    A design's strapping table, a datasheet extraction and a generated part
    model spell the same pin three ways (``GPIO0``, ``IO0``, ``0``). GPIO-002
    compares *sets*, so it has to compare them in one alphabet or every design
    would look like it had drifted from its part.
    """
    raw = str(text).strip()
    m = _GPIO_KEY_RE.match(raw)
    return f"GPIO{int(m.group(1))}" if m else raw.upper()


def _pin_key(pin: Pin) -> str:
    """The GPIO key of a pin, from its declared number or from its name."""
    if pin.spec.gpio is not None:
        return f"GPIO{pin.spec.gpio}"
    for fn in pin.spec.functions:
        m = _GPIO_FN_RE.match(fn)
        if m:
            return f"GPIO{int(m.group(1))}"
    return gpio_key(pin.name)


def strapping_pins(comp: Component) -> tuple[Pin, ...]:
    """Pins the *part model* marks :attr:`~src.ecad.model.PinRole.STRAPPING`."""
    return tuple(p for p in comp.pins if p.role is PinRole.STRAPPING)


def adc_functions(pin: Pin) -> tuple[str, ...]:
    """The ``ADC1_CH0``-style alternate functions the part model lists."""
    return tuple(fn for fn in pin.spec.functions if _ADC_FN_RE.match(fn))


def is_input_only(pin: Pin) -> bool:
    """A GPIO-family pad the part model declares as an *input* electrically.

    This is read off the model, never from a hardcoded chip list: the
    generated ESP32 part gives GPIO34-GPIO39 (``VDET_1``, ``VDET_2``,
    ``SENSOR_VP``, ``SENSOR_VN``, ``SENSOR_CAPP``, ``SENSOR_CAPN``)
    ``ElectricalType.INPUT``, and the ESP32-S2 parts give ``GPIO46``/``IO46``
    the same. The GPIO-family test matters: ``EN``/``CHIP_PU`` are also
    ``INPUT`` and are emphatically not input-only *GPIOs*, so a pin only
    counts when the model gives it a GPIO number or a ``GPIOnn`` function.
    """
    if pin.etype is not ElectricalType.INPUT:
        return False
    if pin.spec.gpio is not None:
        return True
    return any(_GPIO_FN_RE.match(fn) for fn in pin.spec.functions)


# ---------------------------------------------------------------------------
# Small topology helpers
# ---------------------------------------------------------------------------

def waiver_target(comp: Component, pin: Pin, suffix: str = "") -> str:
    """The waiver key for a pin finding: ``ESP32-S3-WROOM-1:IO3``.

    **Deliberately keyed on the part name, not on the designator.** This
    repo's project layer renumbers references into one namespace
    (:func:`src.pipeline.project_assembly.assemble_project`), so the module
    that is ``U1`` when the rules run over ``sheets()`` is ``U2`` when they run
    over ``build()`` — and both are documented ways to check the same design
    (``src/ecad/rules/cli.py`` uses the latter, ``tests/ecad`` the former). A
    ref-keyed target would therefore make every cited waiver in the shipped
    ledger silently stop applying the moment it was loaded the other way,
    which is precisely the failure the engine's stale-waiver reporting exists
    to catch. Part names and net names survive renumbering; designators do
    not.

    Known limitation, stated rather than papered over: a board carrying **two
    instances of the same part** gives both the same target, so one waiver
    covers both pins. The finding's ``refs`` and message still name each
    instance, but a reviewer has to read them. Splitting the target by
    designator would trade that narrow hole for the much wider one above.
    """
    part = comp.part_name or type(comp).__name__
    return f"{part}:{pin.name}{suffix}"


def _is_ground_net(ctx: RuleContext, name: str) -> bool:
    net = ctx.net(name)
    return net.is_ground if net is not None else is_ground_name(name)


def _is_biasing_net(ctx: RuleContext, net: NetView) -> bool:
    """A net that sits at a defined DC level of its own: a rail or a ground."""
    return (net.is_ground
            or bool(net.power_pins)
            or ctx.rail_voltage(net.name) is not None)


def _resistor_neighbours(ctx: RuleContext,
                         net: NetView) -> tuple[tuple[Component, NetView], ...]:
    """``(resistor, far net)`` for every two-pin resistor leaving ``net``."""
    out: list[tuple[Component, NetView]] = []
    for pin in net.pins:
        comp = pin.owner
        if comp.reference_prefix not in _RESISTOR_PREFIXES:
            continue
        if len(comp.pins) != 2:
            continue
        far = next((q for q in comp.pins if q is not pin), None)
        if far is None:
            continue
        far_net = ctx.net_of(far)
        if far_net is not None and far_net.name != net.name:
            out.append((comp, far_net))
    return tuple(out)


def _caps_to_ground(ctx: RuleContext, net: NetView) -> tuple:
    return tuple(c for c in net.caps if _is_ground_net(ctx, c.other_net))


# ---------------------------------------------------------------------------
# GPIO-001 — every strapping pin sits at a defined level
# ---------------------------------------------------------------------------

def _held_by(ctx: RuleContext, pin: Pin,
             net: NetView) -> tuple[str, str] | None:
    """How ``net`` is held at a defined level, or ``None`` if nothing holds it.

    Returns ``(kind, evidence)`` where ``kind`` is ``"direct tie"``,
    ``"pull resistor"`` or ``"driver"`` — the three things DS v1.8 p. 13
    names as ways to set a strapping level from outside the chip.
    """
    if _is_biasing_net(ctx, net):
        what = "ground" if net.is_ground else "a supply rail"
        return ("direct tie", f"{net.name} is {what}")

    for comp, far in _resistor_neighbours(ctx, net):
        if _is_biasing_net(ctx, far):
            return ("pull resistor",
                    f"{ctx.ref(comp)} ({getattr(comp, 'value', '') or '?'}) "
                    f"from {net.name} to {far.name}")

    for other in net.pins:
        if other is pin:
            continue
        if is_power_pin(other) or is_ground_pin(other):
            continue
        if other.etype in _DRIVING and other.owner is not pin.owner:
            return ("driver", f"{ctx.pin_label(other)} "
                              f"({other.etype.value}) drives {net.name}")
        if other.owner.reference_prefix in _CONNECTOR_PREFIXES:
            return ("driver", f"{ctx.pin_label(other)} brings {net.name} in "
                              f"from off-board circuitry")
    return None


def _check_gpio001(ctx: RuleContext) -> Iterable[Finding]:
    for comp in ctx.components:
        for pin in strapping_pins(comp):
            label = ctx.pin_label(pin)
            net = ctx.net_of(pin)
            if net is None:
                yield Finding(
                    rule_id="GPIO-001", severity=Severity.ERROR,
                    target=waiver_target(comp, pin),
                    message=(f"strapping pin {label} (pad {pin.pad}) is not "
                             f"connected to anything — its level at reset is "
                             f"whatever the chip's internal pull does, which "
                             f"is not a decision this schematic records"),
                    remediation=(
                        f"pull {pin.name} to a rail or to GND with a resistor "
                        f"— src.ecad.circuits.pull_resistor(design, "
                        f"{ctx.ref(comp)}.{pin.name}, '+3V3', value='10k') — "
                        f"or waive it citing the datasheet default you are "
                        f"relying on (GPIO-001 target "
                        f"{waiver_target(comp, pin)!r})"),
                    citation=f"{PROV_DS_STRAPPING.cite()} — {_Q_DS_DEFAULTS}. "
                             f"{_Q_DS_GPIO3}",
                    refs=(ctx.ref(comp),), pins=(label,))
                continue
            held = _held_by(ctx, pin, net)
            if held is None:
                yield Finding(
                    rule_id="GPIO-001", severity=Severity.ERROR,
                    target=waiver_target(comp, pin),
                    message=(f"strapping pin {label} sits on {net.name}, which "
                             f"nothing holds at a defined level: no pull "
                             f"resistor to a rail or ground, no direct tie and "
                             f"no driver"),
                    remediation=(
                        f"add a pull resistor from {net.name} to a rail or to "
                        f"GND, tie {net.name} directly, or drive it from a "
                        f"documented output"),
                    citation=f"{PROV_DS_STRAPPING.cite()} — {_Q_DS_DEFAULTS}. "
                             f"{PROV_HDG_STRAPPING.cite()} — {_Q_PULLUP_GPIO0}",
                    refs=(ctx.ref(comp),), pins=(label,), nets=(net.name,))


# ---------------------------------------------------------------------------
# GPIO-002 — the design's declared strapping table vs the part model
# ---------------------------------------------------------------------------

def _check_gpio002(ctx: RuleContext) -> Iterable[Finding]:
    for comp in ctx.components:
        declared_raw = tuple(ctx.facts_for(comp).strapping or ())
        if not declared_raw:
            continue          # no declaration → nothing to cross-check
        model_pins = strapping_pins(comp)
        model = {_pin_key(p): p for p in model_pins}
        declared = {gpio_key(d): str(d) for d in declared_raw}
        source = ctx.facts_for(comp).source or "the design's strapping table"

        for key in sorted(set(model) - set(declared)):
            pin = model[key]
            yield Finding(
                rule_id="GPIO-002", severity=Severity.ERROR,
                target=f"{comp.part_name}:{key}:undeclared",
                message=(f"{ctx.ref(comp)} ({comp.part_name}) part model marks "
                         f"{pin.name} (pad {pin.pad}) role=strapping, but the "
                         f"design's declared strapping table "
                         f"({sorted(declared)}) does not mention it"),
                remediation=(f"add {key} to the design's strapping table with a "
                             f"level and a citation, or correct the part model "
                             f"if {pin.name} is not a strapping pin"),
                citation=f"{PROV_DS_STRAPPING.cite()} — Table 4-1 lists exactly "
                         f"GPIO0, GPIO3, GPIO45 and GPIO46. Declaration read "
                         f"from: {source}",
                refs=(ctx.ref(comp),), pins=(ctx.pin_label(pin),))

        for key in sorted(set(declared) - set(model)):
            yield Finding(
                rule_id="GPIO-002", severity=Severity.ERROR,
                target=f"{comp.part_name}:{key}:unmodelled",
                message=(f"the design declares {declared[key]} as a strapping "
                         f"pin of {ctx.ref(comp)} ({comp.part_name}), but the "
                         f"verified part model marks no such pin "
                         f"role=strapping (model has "
                         f"{sorted(_pin_key(p) for p in model_pins)})"),
                remediation=(f"drop {declared[key]} from the design's strapping "
                             f"table, or fix the part model if it really is a "
                             f"strapping pin"),
                citation=f"{PROV_DS_STRAPPING.cite()} — Table 4-1 lists exactly "
                         f"GPIO0, GPIO3, GPIO45 and GPIO46. Declaration read "
                         f"from: {source}",
                refs=(ctx.ref(comp),))


# ---------------------------------------------------------------------------
# GPIO-003 — an input-only pin is never asked to drive
# ---------------------------------------------------------------------------

def _loads_on(ctx: RuleContext, pin: Pin,
              net: NetView) -> tuple[tuple[str, str], ...]:
    """``(what, where)`` for every thing on ``net`` that must be driven.

    Looks one resistor hop out, because the textbook way to hang a load off a
    GPIO puts a series resistor in between (``indicator_led`` does exactly
    that) and a rule that only looked at the pin's own net would never see the
    LED it is meant to catch.
    """
    out: list[tuple[str, str]] = []
    nets = [net] + [far for _, far in _resistor_neighbours(ctx, net)]
    for hop in nets:
        if hop is not net and _is_biasing_net(ctx, hop):
            continue          # a pull-up's far end is a rail, not a load
        for other in hop.pins:
            if other is pin or is_power_pin(other) or is_ground_pin(other):
                continue
            if other.owner.reference_prefix == "D":
                out.append((f"LED/diode {ctx.pin_label(other)}", hop.name))
            elif (other.etype is ElectricalType.INPUT
                  and other.owner is not pin.owner):
                out.append((f"input pin {ctx.pin_label(other)}", hop.name))
    return tuple(out)


def _has_driver(ctx: RuleContext, pin: Pin, net: NetView) -> bool:
    """Something other than ``pin`` can hold ``net`` at a level."""
    for other in net.pins:
        if other is pin or is_power_pin(other) or is_ground_pin(other):
            continue
        if other.etype in _DRIVING and other.owner is not pin.owner:
            return True
        if other.owner.reference_prefix in _CONNECTOR_PREFIXES:
            return True
    return False


def _check_gpio003(ctx: RuleContext) -> Iterable[Finding]:
    for comp in ctx.components:
        for pin in comp.pins:
            if not is_input_only(pin):
                continue
            net = ctx.net_of(pin)
            if net is None or _is_biasing_net(ctx, net):
                continue      # unconnected, or tied to a rail: not driving
            if _has_driver(ctx, pin, net):
                continue
            loads = _loads_on(ctx, pin, net)
            if not loads:
                continue
            label = ctx.pin_label(pin)
            listed = ", ".join(f"{what} on {where}" for what, where in loads)
            yield Finding(
                rule_id="GPIO-003", severity=Severity.ERROR,
                target=waiver_target(comp, pin, f"@{net.name}"),
                message=(f"{label} ({_pin_key(pin)}, pad {pin.pad}) is an "
                         f"input-only pad, but {net.name} carries {listed} and "
                         f"nothing else on it can drive — the design is asking "
                         f"an input-only pin to be an output"),
                remediation=(f"move this load to a bidirectional GPIO; "
                             f"{_pin_key(pin)} on {comp.part_name} can only be "
                             f"read"),
                citation=(f"the verified {comp.part_name} part model declares "
                          f"pad {pin.pad} ({pin.name}) with electrical type "
                          f"'input', not 'bidirectional' — the same fact the "
                          f"ESP32 datasheet states as GPIO34-GPIO39 being "
                          f"input-only, and the ESP32-S2 datasheet as GPIO46. "
                          f"{PROV_HDG_GPIO.cite()} — the IO Pin Default "
                          f"Configuration table gives these pads 'IE' (input "
                          f"enabled) only"),
                refs=(ctx.ref(comp),), pins=(label,), nets=(net.name,))


# ---------------------------------------------------------------------------
# GPIO-004 — no high-value capacitor on a strapping net
# ---------------------------------------------------------------------------

def _check_gpio004(ctx: RuleContext) -> Iterable[Finding]:
    for comp in ctx.components:
        for pin in strapping_pins(comp):
            net = ctx.net_of(pin)
            if net is None:
                continue
            for cap in _caps_to_ground(ctx, net):
                if cap.farads is None:
                    continue          # unparseable value: never guessed
                if cap.farads < STRAP_CAP_MAX_F * _TOLERANCE:
                    continue
                label = ctx.pin_label(pin)
                yield Finding(
                    rule_id="GPIO-004", severity=Severity.WARNING,
                    target=waiver_target(comp, pin, f"@{net.name}:{cap.value}"),
                    message=(f"{cap.ref} ({cap.value}, {_uf(cap.farads)}) sits "
                             f"from strapping net {net.name} to "
                             f"{cap.other_net}, at or above the "
                             f"{_uf(STRAP_CAP_MAX_F)} threshold — it slows the "
                             f"strap's edge at reset and, on {label} "
                             f"({_pin_key(pin)}), can leave the chip in "
                             f"download mode"),
                    remediation=(
                        f"remove {cap.ref}, or leave its footprint reserved "
                        f"and unpopulated the way DevKitC-1 V1.1 does with "
                        f"C13 at GPIO0; debounce the strap in firmware, or "
                        f"waive with the measured rise time (GPIO-004 "
                        f"target "
                        f"{waiver_target(comp, pin, f'@{net.name}:{cap.value}')})"),
                    citation=(
                        f"{PROV_HDG_STRAPPING.cite()} — {_Q_NO_HIGH_CAPS} "
                        f"NOTE: the HDG states NO capacitance value; the same "
                        f"sentence appears in the ESP32 and ESP32-S2 "
                        f"checklists, also without a number, and the datasheet "
                        f"gives none either. The "
                        f"{_uf(STRAP_CAP_MAX_F)} threshold used here comes "
                        f"from {PROV_DEVKIT_GPIO0.cite()} — the smallest "
                        f"capacitance Espressif themselves lay out at GPIO0 "
                        f"and then decline to populate"),
                    refs=(ctx.ref(comp), cap.ref),
                    pins=(label,), nets=(net.name,))


def _uf(farads: float) -> str:
    return f"{farads * 1e6:g} uF"


# ---------------------------------------------------------------------------
# GPIO-005 — analog-only pins carry the HDG's 0.1 uF filter capacitor
# ---------------------------------------------------------------------------

def _adc_only_pins(comp: Component) -> tuple[Pin, ...]:
    """Pins the model says can be **nothing but** an analog input.

    Three model facts have to agree before this pack will claim a pin is "used
    as ADC": the role is ``ANALOG``, the electrical type is ``input`` (so it
    cannot be a digital output), and the alternate functions name an ADC
    channel. A pin that is merely *ADC-capable* — every ESP32-S3 GPIO1-GPIO20
    is — proves nothing about how the firmware will use it, and guessing there
    would make this rule fire on most of a chip.
    """
    return tuple(p for p in comp.pins
                 if p.role is PinRole.ANALOG
                 and p.etype is ElectricalType.INPUT
                 and adc_functions(p))


def _check_gpio005(ctx: RuleContext) -> Iterable[Finding]:
    for comp in ctx.components:
        for pin in _adc_only_pins(comp):
            net = ctx.net_of(pin)
            if net is None:
                continue          # unused analog pin: nothing to filter
            caps = _caps_to_ground(ctx, net)
            if caps:
                continue
            label = ctx.pin_label(pin)
            fns = ", ".join(adc_functions(pin))
            yield Finding(
                rule_id="GPIO-005", severity=Severity.WARNING,
                target=waiver_target(comp, pin, f"@{net.name}"),
                message=(f"{label} (pad {pin.pad}, {fns}) is an analog-input-"
                         f"only pad in use on {net.name}, with no capacitor to "
                         f"ground; the guideline asks for "
                         f"{_uf(ADC_FILTER_F)}"),
                remediation=(f"add {_uf(ADC_FILTER_F)} from {net.name} to GND "
                             f"— src.ecad.circuits.bypass_capacitor(design, "
                             f"{net.name!r}, 'GND', value='100nF')"),
                citation=f"{PROV_HDG_ADC.cite()} — {_Q_ADC_FILTER} This pin "
                         f"qualifies because the verified {comp.part_name} "
                         f"model gives pad {pin.pad} role=analog, electrical "
                         f"type 'input' and ADC function(s) {fns}, so it "
                         f"cannot be anything but an analog input (PRESENCE "
                         f"only: the HDG's placement is a layout property)",
                refs=(ctx.ref(comp),), pins=(label,), nets=(net.name,))


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

GPIO_001 = register_rule(Rule(
    id="GPIO-001", domain=DOMAIN, severity=Severity.ERROR,
    title="every strapping pin is held at a defined level, or is waived",
    provenance=PROV_DS_STRAPPING, check=_check_gpio001,
    doc="""A strapping pin is sampled once, at reset, and the value latched
    decides how the chip boots. DS v1.8 p. 13: "To change the bit values, the
    strapping pins should be connected to external pull-down/pull-up
    resistances. If the ESP32-S3 is used as a device by a host MCU, the
    strapping pin voltage levels can also be controlled by the host MCU."
    Those are the three ways this rule accepts — a pull resistor to a rail or
    ground, a direct tie, or a pin that can drive the net — plus the fourth
    the engine already provides: a cited waiver.

    **An unconnected strapping pin is an ERROR, on purpose.** DS Table 4-1
    does give defaults (GPIO0 weak pull-up = 1, GPIO45/GPIO46 weak pull-down =
    0), and a design may legitimately rely on them — but relying on an
    internal pull is a *decision*, and the point of this rule is that the
    decision has to be written down. That is what a waiver is: reason,
    cited_source, author. GPIO3 is the case that proves it matters — DS
    Sec. 4.4 says it "does not have any internal pull resistors and the
    strapping value must be controlled by the external circuit that cannot be
    in a high impedance state", and HDG's IO Pin Default Configuration table
    shows GPIO3 as "IE" with neither WPU nor WPD.

    A button to ground is NOT a pull: this rule conducts only through
    resistors (``reference_prefix == "R"``), because a strap defined only
    while someone holds a switch is not defined.""",
))

GPIO_002 = register_rule(Rule(
    id="GPIO-002", domain=DOMAIN, severity=Severity.ERROR,
    title="a declared strapping table and the part model agree, both ways",
    provenance=PROV_DS_STRAPPING, check=_check_gpio002,
    doc="""A design that writes down its strapping plan and a part model that
    marks pins ``role=strapping`` are two independent statements of the same
    fact. This rule requires them to match in both directions: every pin the
    model marks must appear in the declaration, and every pin the declaration
    names must exist in the model as a strapping pin.

    It exists because those two drift silently. The reference design's table
    was authored from DS v1.8 Table 4-1 ("GPIO0 Weak pull-up 1, GPIO3
    Floating –, GPIO45 Weak pull-down 0, GPIO46 Weak pull-down 0"); the part
    model is regenerated from the datasheet and Zephyr by the ingest factory.
    A regeneration that dropped a strapping role, or a hand-edited table that
    lost a row, produces a design whose *documentation* says the straps are
    handled while the pins are not — and every other gate stays green.

    The declaration reaches the rule through ``PartFacts.strapping``, which
    the engine already resolves from a caller's ``facts=``, a part model's
    ``POWER_FACTS`` or ``data/ingest/<id>/extracted.json``'s
    ``strapping_pins``. **No declaration means no finding**: this rule checks
    agreement, and there is nothing to disagree with when a design has not
    stated a plan. Spellings are normalised (``GPIO0``/``IO0``/``0``) so the
    comparison is about pins, not about notation.""",
))

GPIO_003 = register_rule(Rule(
    id="GPIO-003", domain=DOMAIN, severity=Severity.ERROR,
    title="an input-only pad is never asked to drive a load",
    provenance=PROV_HDG_GPIO, check=_check_gpio003,
    doc="""Some GPIOs can only be read. On the ESP32 those are GPIO34-GPIO39;
    on the ESP32-S2 it is GPIO46. This rule does not carry that list: it reads
    the electrical type off the generated part model, where those pads are
    ``input`` while every ordinary GPIO is ``bidirectional``. HDG's IO Pin
    Default Configuration table states the same thing from the other side,
    marking such pads "IE" (input enabled) only.

    Firing condition, stated exactly: the pin sits on a net that is not itself
    a rail or a ground, no other pin on that net can drive it, and the net —
    or a net one series-resistor away — carries something that has to be
    driven: an LED/diode, or another component's input pin. That is the
    signature of a load hung off a pad that can never source or sink it.

    The one-resistor hop is deliberate. ``circuits.indicator_led`` puts a
    series resistor between the GPIO and the LED, so the LED is never on the
    pin's own net; a rule that stopped at the first net would miss the exact
    mistake it exists to catch. Equally deliberate is what does *not* fire: a
    plain pull-up or pull-down on an input-only pad is correct and common
    (these pads have no internal pulls), and the far end of a pull is a rail,
    which this rule skips.""",
))

GPIO_004 = register_rule(Rule(
    id="GPIO-004", domain=DOMAIN, severity=Severity.WARNING,
    title="no high-value capacitor on a strapping net (threshold is cited, "
          "not stated by Espressif)",
    provenance=PROV_HDG_STRAPPING, check=_check_gpio004,
    doc="""HDG, Strapping Pins, Attention: "Do not add high-value capacitors
    at GPIO0, or the chip may enter download mode." A capacitor slows the
    strap's edge; if it has not settled when the latch samples, the chip boots
    the other way.

    **Espressif give no number, and this rule says so in every finding.** The
    identical sentence appears in the ESP32 and ESP32-S2 checklists, also
    without a value, and the ESP32-S3-WROOM-1 datasheet says nothing about
    capacitance on strapping pins at all. The threshold here — 0.1 uF — is
    taken from the one place Espressif put a capacitor value next to GPIO0:
    the ESP32-S3-DevKitC-1 V1.1 schematic reserves C13 at the GPIO0 button as
    "0.1uF/50V(10%)(NC)", laying out a 0.1 uF footprint and deliberately not
    populating it. So 0.1 uF is the smallest capacitance Espressif themselves
    decline to fit there, and this rule flags at or above it.

    WARNING rather than ERROR precisely because the number is inferred. The
    reference design is the positive control: it fits a 100 nF debounce
    capacitor on EN (DS Figure 9-1's C8) and deliberately none on BOOT, noting
    that "HDG's 'do not add high-value capacitors' warning is about GPIO0, not
    EN". Only capacitors to ground count; an unparseable value is skipped
    rather than guessed.""",
))

GPIO_005 = register_rule(Rule(
    id="GPIO-005", domain=DOMAIN, severity=Severity.WARNING,
    title="analog-only pads in use carry the 0.1 uF ADC filter capacitor "
          "(PRESENCE ONLY)",
    provenance=PROV_HDG_ADC, check=_check_gpio005,
    doc="""HDG, ADC: "Please add a 0.1 μF filter capacitor between ESP pins
    and ground when using the ADC function to improve accuracy."

    "When using the ADC function" is a statement about firmware, and no part
    model records firmware. So this rule fires only where the model makes the
    question unanswerable any other way: a pad whose role is ``analog``,
    whose electrical type is ``input`` (it cannot be a digital output) and
    whose alternate functions name an ADC channel. On the generated ESP32
    part that is exactly ``SENSOR_VP``/``SENSOR_VN``/``SENSOR_CAPP``/
    ``SENSOR_CAPN``/``VDET_1``/``VDET_2`` — GPIO36/39/37/38/34/35. A merely
    ADC-*capable* pin (all of ESP32-S3's GPIO1-GPIO20) is never flagged;
    flagging those would fire on most of a chip and prove nothing.

    Where the part model does not carry alternate functions, this rule emits
    nothing at all rather than an INFO per part — the ESP32-S3-WROOM-1 model
    lists no functions, so GPIO-005 is silent on the reference design, and the
    rule table says so instead of the report pretending it looked.

    PRESENCE only, like PWR-002: the HDG's placement of that capacitor is a
    layout property a ``Design`` cannot express.""",
))
