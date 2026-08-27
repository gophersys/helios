"""Tests for the GPIO / strapping rule pack (GPIO-001 … GPIO-005).

Same discipline as :mod:`tests.ecad.test_rules_power`, and for the same
reason — this repo has shipped five gates that could not fail (a lint
iterating the wrong collection, a netlist gate covering one sheet of many, a
strapping check returning ``ok=None``, a project gate no input could trip,
and a ``factory status`` that validated stale artifacts):

**Every rule ships with a design that makes it FIRE at its declared severity
and a design that is clean.** Both live in :data:`FIRING` / :data:`CLEAN`.
:func:`test_every_registered_rule_has_a_firing_fixture` closes the loop
across *both* packs, so no rule in any domain can be registered without one.

The pack is also **mutation-checked**: :func:`test_mutation_neutering_each_
rule_turns_the_suite_red` neuters each rule's check function in turn and
asserts this file's own firing fixture stops passing. A test that survives
its subject being replaced by ``lambda ctx: ()`` was never testing anything.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from examples.esp32_s3_reference import design as ref
from src.ecad import Design
from src.ecad.component import Component
from src.ecad.model import FootprintRef, PinRole, pin
from src.ecad.rules import (
    PartFacts,
    Severity,
    Waiver,
    check,
    get_rule,
    load_waivers,
    rules,
)
from src.ecad.rules.engine import WAIVER_STALE
from src.ecad.rules.gpio import (
    ADC_FILTER_F,
    DOMAIN,
    STRAP_CAP_MAX_F,
    gpio_key,
    is_input_only,
    strapping_pins,
    waiver_target,
)

_FP = FootprintRef("Package_QFP", "TQFP-32_7x7mm_P0.8mm")


# ---------------------------------------------------------------------------
# Fixture parts — hand-written, so the tests do not depend on generated files
# ---------------------------------------------------------------------------

class StrapMcu(Component):
    """An ESP32-S3-shaped part: two strapping pads and one ordinary GPIO.

    The roles mirror ``src/ecad/library/espressif/esp32_s3_wroom_1.py``, where
    the factory now emits ``PinRole.STRAPPING`` for IO0/IO3/IO45/IO46.
    """

    part_name = "TEST-STRAP-MCU"
    reference_prefix = "U"
    footprint = _FP
    _PIN_SPECS = (
        pin("1", "VDD", "power_in", "power"),
        pin("2", "GND", "power_in", "ground"),
        pin("3", "IO0", "bidirectional", "strapping", gpio=0),
        pin("4", "IO45", "bidirectional", "strapping", gpio=45),
        pin("5", "IO4", "bidirectional", "gpio", gpio=4),
    )


class InputOnlyMcu(Component):
    """A part with an input-only GPIO, exactly as ESP32-S2's GPIO46 is modelled.

    ``src/ecad/library/espressif/esp32_s2.py`` line for pad 55::

        PinSpec(pad='55', name='GPIO46', etype=ElectricalType.INPUT,
                role=PinRole.GPIO, gpio=46, functions=('GPIO46',))

    ``EN`` is here on purpose: it is *also* ``input``, and it must NOT be
    treated as an input-only GPIO — it has no GPIO number.
    """

    part_name = "TEST-INPUT-ONLY-MCU"
    reference_prefix = "U"
    footprint = _FP
    _PIN_SPECS = (
        pin("1", "VDD", "power_in", "power"),
        pin("2", "GND", "power_in", "ground"),
        pin("3", "IO46", "input", "gpio", gpio=46, functions=("GPIO46",)),
        pin("4", "IO4", "bidirectional", "gpio", gpio=4),
        pin("5", "EN", "input", "control"),
    )


class AdcMcu(Component):
    """A part with an analog-only ADC pad and an ADC-*capable* digital one.

    Both shapes come straight out of ``src/ecad/library/espressif/esp32.py``:
    ``SENSOR_VP`` is ``INPUT``/``ANALOG``/``ADC1_CH0`` (analog only), while
    ``GPIO25`` is ``BIDIRECTIONAL``/``GPIO``/``ADC2_CH8`` (merely capable).
    GPIO-005 must fire on the first and never on the second.
    """

    part_name = "TEST-ADC-MCU"
    reference_prefix = "U"
    footprint = _FP
    _PIN_SPECS = (
        pin("1", "VDD", "power_in", "power"),
        pin("2", "GND", "power_in", "ground"),
        pin("3", "SENSOR_VP", "input", "analog",
            functions=("GPIO36", "ADC1_CH0", "RTC_GPIO0")),
        pin("4", "GPIO25", "bidirectional", "gpio", gpio=25,
            functions=("GPIO25", "ADC2_CH8", "DAC_1")),
    )


class Res(Component):
    part_name = "TEST-R"
    reference_prefix = "R"
    footprint = FootprintRef("Resistor_SMD", "R_0402_1005Metric")
    _PIN_SPECS = (pin("1", "P1", "passive", "passive"),
                  pin("2", "P2", "passive", "passive"))

    def __init__(self, value: str = "10k") -> None:
        super().__init__()
        self.value = value


class Cap(Component):
    part_name = "TEST-C"
    reference_prefix = "C"
    footprint = FootprintRef("Capacitor_SMD", "C_0402_1005Metric")
    _PIN_SPECS = (pin("1", "P1", "passive", "passive"),
                  pin("2", "P2", "passive", "passive"))

    def __init__(self, value: str = "100nF") -> None:
        super().__init__()
        self.value = value


class Led(Component):
    part_name = "TEST-LED"
    reference_prefix = "D"
    footprint = FootprintRef("LED_SMD", "LED_0603_1608Metric")
    _PIN_SPECS = (pin("1", "A", "passive", "passive"),
                  pin("2", "K", "passive", "passive"))


class Button(Component):
    """A momentary switch — the thing GPIO-001 must NOT accept as a pull."""

    part_name = "TEST-SW"
    reference_prefix = "SW"
    footprint = FootprintRef("Button_Switch_SMD", "SW_SPST_TL3342")
    _PIN_SPECS = (pin("1", "1", "passive", "passive"),
                  pin("2", "2", "passive", "passive"))


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

RAIL = "+3V3"
GND = "GND"


def _two_pin(d: Design, part: Component, a: str, b: str) -> Component:
    d.add(part)
    d.net(a).connect(part.pins[0])
    d.net(b).connect(part.pins[1])
    return part


def _powered(d: Design, u: Component) -> Component:
    """Add ``u`` with its supply pins wired, plus the decoupling PWR-002 wants."""
    d.add(u)
    for p in u.pins:
        if p.role is PinRole.GROUND:
            d.net(GND).connect(p)
        elif p.name == "VDD":
            d.net(RAIL).connect(p)
    _two_pin(d, Cap("22uF"), RAIL, GND)
    _two_pin(d, Cap("100nF"), RAIL, GND)
    return u


def _strap_board(*, boot_pull: bool = True, tie_io45: bool = True,
                 boot_cap: str | None = None, boot_button: bool = False,
                 name: str = "strap") -> Design:
    """A board whose every knob is a way to break exactly one GPIO rule."""
    d = Design(name)
    u = _powered(d, StrapMcu())
    if boot_pull:
        d.net("BOOT").connect(u.pin("IO0"))
        _two_pin(d, Res("10k"), "BOOT", RAIL)
    if boot_button:
        d.net("BOOT").connect(u.pin("IO0"))
        _two_pin(d, Button(), "BOOT", GND)
    if boot_cap is not None:
        d.net("BOOT").connect(u.pin("IO0"))
        _two_pin(d, Cap(boot_cap), "BOOT", GND)
    if tie_io45:
        d.net(GND).connect(u.pin("IO45"))
    return d


# --- GPIO-001 --------------------------------------------------------------

def _fire_001() -> tuple[Design, dict]:
    # IO45 left unconnected: its reset level is whatever the internal pull
    # does, which is not a decision this schematic records.
    return _strap_board(tie_io45=False), {}


def _clean_001() -> tuple[Design, dict]:
    return _strap_board(), {}


# --- GPIO-002 --------------------------------------------------------------

def _declaration(*pins: str, note: str = "TEST fixture strapping table") \
        -> dict:
    return {"facts": {"TEST-STRAP-MCU": PartFacts(
        part_name="TEST-STRAP-MCU", strapping=pins, source=note)}}


def _fire_002() -> tuple[Design, dict]:
    # The model marks GPIO0 + GPIO45; the declaration says GPIO0 + GPIO46.
    # That is one undeclared model pin AND one unmodelled declared pin — the
    # drift this rule exists to catch, in both directions at once.
    return _strap_board(), _declaration("GPIO0", "GPIO46")


def _clean_002() -> tuple[Design, dict]:
    # Deliberately spelled three ways: the rule compares pins, not notation.
    return _strap_board(), _declaration("IO0", "45")


# --- GPIO-003 --------------------------------------------------------------

def _input_only_board(*, led: bool = False, pull: bool = False,
                      name: str = "inputs") -> Design:
    d = Design(name)
    u = _powered(d, InputOnlyMcu())
    if led:
        # The textbook mistake: an indicator hung off a pad that can only be
        # read. Series resistor in between, exactly as circuits.indicator_led
        # builds it — so the LED is never on the pin's own net.
        d.net("LED_A").connect(u.pin("IO46"))
        _two_pin(d, Res("1k"), "LED_A", "LED_K")
        _two_pin(d, Led(), "LED_K", GND)
    if pull:
        # Legitimate and common: these pads have no internal pulls.
        d.net("SENSE").connect(u.pin("IO46"))
        _two_pin(d, Res("10k"), "SENSE", RAIL)
    return d


def _fire_003() -> tuple[Design, dict]:
    return _input_only_board(led=True), {}


def _clean_003() -> tuple[Design, dict]:
    return _input_only_board(pull=True), {}


# --- GPIO-004 --------------------------------------------------------------

def _fire_004() -> tuple[Design, dict]:
    # 100 nF of debounce on the strap — at the threshold, and the classic way
    # a board wakes up in download mode.
    return _strap_board(boot_cap="100nF", boot_button=True), {}


def _clean_004() -> tuple[Design, dict]:
    # A 1 nF snubber is two decades below the threshold and must not fire.
    return _strap_board(boot_cap="1nF", boot_button=True), {}


# --- GPIO-005 --------------------------------------------------------------

def _adc_board(*, filter_cap: str | None, name: str = "adc") -> Design:
    d = Design(name)
    u = _powered(d, AdcMcu())
    d.net("VSENSE").connect(u.pin("SENSOR_VP"))
    _two_pin(d, Res("100k"), "VSENSE", RAIL)      # a divider off the rail
    _two_pin(d, Res("100k"), "VSENSE", GND)
    d.net("IO25").connect(u.pin("GPIO25"))        # ADC-capable, used digitally
    _two_pin(d, Res("10k"), "IO25", RAIL)
    if filter_cap is not None:
        _two_pin(d, Cap(filter_cap), "VSENSE", GND)
    return d


def _fire_005() -> tuple[Design, dict]:
    return _adc_board(filter_cap=None), {}


def _clean_005() -> tuple[Design, dict]:
    return _adc_board(filter_cap="100nF"), {}


#: rule id → a design that MUST produce that rule at its declared severity.
FIRING = {
    "GPIO-001": _fire_001, "GPIO-002": _fire_002, "GPIO-003": _fire_003,
    "GPIO-004": _fire_004, "GPIO-005": _fire_005,
}

#: rule id → a design that MUST produce nothing above INFO for that rule.
CLEAN = {
    "GPIO-001": _clean_001, "GPIO-002": _clean_002, "GPIO-003": _clean_003,
    "GPIO-004": _clean_004, "GPIO-005": _clean_005,
}


# ---------------------------------------------------------------------------
# The two halves of the discipline
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("rule_id", sorted(FIRING))
def test_rule_fires(rule_id: str) -> None:
    """The firing fixture produces the rule at its declared severity."""
    design, kwargs = FIRING[rule_id]()
    report = check(design, rule_ids=[rule_id], **kwargs)
    hits = [f for f in report.findings if f.rule_id == rule_id]
    assert hits, f"{rule_id} produced NO finding on its firing fixture"

    declared = get_rule(rule_id).severity
    at_severity = [f for f in hits if f.severity is declared]
    assert at_severity, (
        f"{rule_id} fired only at {[f.severity.value for f in hits]}, never at "
        f"its declared {declared.value} — an INFO-only fixture is not coverage")

    for f in at_severity:
        assert f.target and f.message and f.citation and f.remediation
        assert f.design == design.name
        assert f.refs, f"{rule_id} finding names no component"

    # And the whole pack must surface it too — a rule that only fires when
    # selected by id is a rule that never runs in anger.
    assert any(f.rule_id == rule_id for f in check(design, **kwargs).findings)


@pytest.mark.parametrize("rule_id", sorted(CLEAN))
def test_rule_clean(rule_id: str) -> None:
    """The clean fixture produces nothing above INFO for that rule."""
    design, kwargs = CLEAN[rule_id]()
    report = check(design, rule_ids=[rule_id], **kwargs)
    noise = [f for f in report.findings if f.severity is not Severity.INFO]
    assert not noise, (
        f"{rule_id} false-positived on its clean fixture: "
        f"{[f.message for f in noise]}")


def test_error_rules_actually_fail_the_gate() -> None:
    """A rule whose declared severity is ERROR must be able to fail ``ok``."""
    for rule_id, build in sorted(FIRING.items()):
        if get_rule(rule_id).severity is not Severity.ERROR:
            continue
        design, kwargs = build()
        assert not check(design, rule_ids=[rule_id], **kwargs).ok, (
            f"{rule_id} is declared ERROR but its firing fixture still passed")


def test_every_registered_rule_has_a_firing_fixture() -> None:
    """Across EVERY pack: no rule id may exist without a firing fixture.

    Scoped to the whole registry rather than to this pack's domain on
    purpose — a per-domain check would let a third pack ship with no fixtures
    at all, which is the shape of gate this repo keeps having to un-ship.

    The power pack's table is imported inside the function, not at module
    scope: ``test_rules_power`` imports :data:`REFERENCE_STRAP_TARGETS` from
    here, and a module-level import in both directions is a cycle.
    """
    from tests.ecad.test_rules_power import FIRING as POWER_FIRING

    registered = {r.id for r in rules()}
    covered = set(FIRING) | set(POWER_FIRING)
    assert registered, "no rules are registered at all"
    assert registered <= covered, (
        f"registered rules with no FIRING fixture anywhere: "
        f"{sorted(registered - covered)}")
    assert set(FIRING) <= registered, "FIRING names an unregistered rule"
    assert set(FIRING) == set(CLEAN), "every rule needs both fixtures"
    assert set(FIRING) == {r.id for r in rules(DOMAIN)}


def test_mutation_neutering_each_rule_turns_the_suite_red() -> None:
    """Neuter each rule's check in turn; its firing fixture must stop firing.

    This is the guard against the class of bug the pack was written to avoid:
    a fixture that "passes" because some *other* rule fired, or a rule whose
    findings nothing actually asserts on. If replacing the check body with a
    generator that yields nothing leaves the fire test green, the test was
    never testing that rule.
    """
    survivors = []
    for rule_id in sorted(FIRING):
        rule = get_rule(rule_id)
        original = rule.check
        object.__setattr__(rule, "check", lambda ctx: iter(()))
        try:
            design, kwargs = FIRING[rule_id]()
            report = check(design, rule_ids=[rule_id], **kwargs)
            if [f for f in report.findings if f.rule_id == rule_id]:
                survivors.append(rule_id)
        finally:
            object.__setattr__(rule, "check", original)
    assert not survivors, (
        f"neutering these rules did NOT turn their firing fixture red: "
        f"{survivors}")


def test_remediation_that_quotes_a_waiver_target_quotes_the_REAL_one() -> None:
    """A copy-pasteable "waive this" hint that names the wrong key is a trap.

    Caught a real defect: GPIO-001's remediation printed the pin *label*
    (``U2.IO3``) where the waiver key is ``ESP32-S3-WROOM-1:IO3``, so anyone
    following the instruction would have written a waiver that matched nothing
    and been told it was stale.
    """
    findings = []
    for build in FIRING.values():
        design, kwargs = build()
        findings += list(check(design, domain=DOMAIN, **kwargs).findings)
    for design in ref.sheets().values():
        findings += list(check(design, domain=DOMAIN).findings)
    assert findings, "no findings to inspect"

    for f in findings:
        if "target" not in f.remediation:
            continue
        assert f.target in f.remediation, (
            f"{f.rule_id} tells the reader to waive a target it did not "
            f"emit: remediation says {f.remediation!r}, target is {f.target!r}")


def test_every_gpio_rule_is_cited_and_documented() -> None:
    for rule in rules(DOMAIN):
        assert rule.citation(), f"{rule.id} has no citation"
        assert "http" in rule.citation(), f"{rule.id} citation has no source URL"
        assert len(rule.doc.strip()) > 100, f"{rule.id} has no rule doc"
        assert rule.domain == DOMAIN and rule.title


# ---------------------------------------------------------------------------
# Reading the part model, not a hardcoded chip list
# ---------------------------------------------------------------------------

def test_strapping_role_is_read_off_the_generated_part_model() -> None:
    """The premise of the whole pack: the factory now assigns STRAPPING.

    Before it did, GPIO-001 would have been a gate that could not fire.
    """
    from src.ecad.library import get as registry_get

    module = registry_get("ESP32-S3-WROOM-1")()
    straps = {p.name for p in strapping_pins(module)}
    # DS v1.8 Table 4-1: GPIO0, GPIO3, GPIO45, GPIO46 — and nothing else.
    assert straps == {"IO0", "IO3", "IO45", "IO46"}
    assert {p.spec.gpio for p in strapping_pins(module)} == {0, 3, 45, 46}


@pytest.mark.parametrize("part,expected", [
    ("ESP32", {"GPIO34", "GPIO35", "GPIO36", "GPIO37", "GPIO38", "GPIO39"}),
    ("ESP32-S2", {"GPIO46"}),
])
def test_input_only_pins_come_from_the_part_model(part: str,
                                                  expected: set) -> None:
    """GPIO-003's chip knowledge is data, never a list baked into the rule."""
    from src.ecad.library import get as registry_get
    from src.ecad.rules.gpio import _pin_key

    comp = registry_get(part)()
    got = {_pin_key(p) for p in comp.pins if is_input_only(p)}
    assert got == expected
    # And the near-miss: EN / CHIP_PU are `input` too and must not qualify.
    assert not any(is_input_only(p) for p in comp.pins
                   if p.name in ("EN", "CHIP_PU"))


@pytest.mark.parametrize("text,key", [
    ("GPIO0", "GPIO0"), ("IO0", "GPIO0"), ("0", "GPIO0"), ("io45", "GPIO45"),
    ("GPIO046", "GPIO46"), ("VDD_SPI", "VDD_SPI"),
])
def test_gpio_key_normalises_the_three_spellings(text: str, key: str) -> None:
    assert gpio_key(text) == key


# ---------------------------------------------------------------------------
# Rule-specific behaviour the parametrized pair cannot express
# ---------------------------------------------------------------------------

def test_gpio001_does_not_accept_a_button_as_a_pull() -> None:
    """A strap defined only while someone holds a switch is not defined."""
    d = _strap_board(boot_pull=False, boot_button=True)
    errors = check(d, rule_ids=["GPIO-001"]).errors
    assert {f.target for f in errors} == {"TEST-STRAP-MCU:IO0"}
    assert "nothing holds at a defined level" in errors[0].message


def test_gpio001_accepts_a_pull_resistor_a_direct_tie_and_a_driver() -> None:
    """All three of the ways DS v1.8 p. 13 names, and nothing else."""
    # pull resistor + direct tie
    assert check(_strap_board(), rule_ids=["GPIO-001"]).ok

    # a driver: another part holding the net. DS v1.8 p. 13: "If the ESP32-S3
    # is used as a device by a host MCU, the strapping pin voltage levels can
    # also be controlled by the host MCU."
    class Host(Component):
        part_name = "TEST-HOST"
        reference_prefix = "U"
        footprint = _FP
        _PIN_SPECS = (pin("1", "OUT", "output", "signal"),)

    d = _strap_board(boot_pull=False)
    u = next(c for c in d.components if isinstance(c, StrapMcu))
    host = Host()
    d.add(host)
    d.net("BOOT").connect(u.pin("IO0"), host.pin("OUT"))
    assert check(d, rule_ids=["GPIO-001"]).ok


def test_gpio001_findings_are_waivable_and_the_waiver_clears_the_gate() -> None:
    design, _ = _fire_001()
    before = check(design, rule_ids=["GPIO-001"])
    assert not before.ok
    after = check(design, rule_ids=["GPIO-001"], waivers=[Waiver(
        rule_id="GPIO-001", target=before.errors[0].target,
        reason="the internal weak pull-down already gives the level we want",
        cited_source="ESP32-S3-WROOM-1 DS v1.8 Table 4-1: GPIO45 Weak "
                     "pull-down, bit value 0",
        author="test")])
    assert after.ok and len(after.waived) == 1


def test_gpio002_reports_drift_in_both_directions() -> None:
    design, kwargs = _fire_002()
    errors = check(design, rule_ids=["GPIO-002"], **kwargs).errors
    targets = {f.target for f in errors}
    assert targets == {"TEST-STRAP-MCU:GPIO45:undeclared",
                       "TEST-STRAP-MCU:GPIO46:unmodelled"}
    undeclared = next(f for f in errors if f.target.endswith("undeclared"))
    assert "does not mention it" in undeclared.message
    unmodelled = next(f for f in errors if f.target.endswith("unmodelled"))
    assert "marks no such pin" in unmodelled.message


def test_gpio002_is_silent_when_a_design_declares_nothing() -> None:
    """No declaration is not a defect — there is nothing to disagree with."""
    assert not check(_strap_board(), rule_ids=["GPIO-002"]).findings


def test_gpio003_ignores_a_pull_up_but_catches_the_load_behind_a_resistor():
    """The series resistor is the whole point: the LED is one hop away."""
    assert check(_input_only_board(pull=True), rule_ids=["GPIO-003"]).ok
    err = check(_input_only_board(led=True), rule_ids=["GPIO-003"]).errors
    assert len(err) == 1
    assert "input-only pad" in err[0].message
    assert "LED/diode" in err[0].message
    assert err[0].target == "TEST-INPUT-ONLY-MCU:IO46@LED_A"


def test_gpio003_does_not_flag_a_bidirectional_gpio_driving_the_same_load():
    """The defect is the pin's direction, not the topology around it."""
    d = Design("bidir-led")
    u = _powered(d, InputOnlyMcu())
    d.net("LED_A").connect(u.pin("IO4"))          # bidirectional, not input
    _two_pin(d, Res("1k"), "LED_A", "LED_K")
    _two_pin(d, Led(), "LED_K", GND)
    assert check(d, rule_ids=["GPIO-003"]).ok


def test_gpio004_threshold_is_cited_and_says_espressif_give_no_number() -> None:
    design, _ = _fire_004()
    warns = check(design, rule_ids=["GPIO-004"]).warnings
    assert len(warns) == 1
    assert warns[0].target == "TEST-STRAP-MCU:IO0@BOOT:100nF"
    assert "download mode" in warns[0].message
    # The rule must not pretend the HDG gave it a number.
    assert "the HDG states NO capacitance value" in warns[0].citation
    assert "0.1uF/50V(10%)(NC)" in warns[0].citation
    assert "DevKitC-1" in warns[0].citation
    assert STRAP_CAP_MAX_F == 0.1e-6


def test_gpio004_discriminates_around_the_threshold() -> None:
    """A gate that fired at every capacitance would not be a threshold."""
    for value, fires in (("1nF", False), ("10nF", False), ("0.1uF", True),
                         ("100nF", True), ("1uF", True)):
        report = check(_strap_board(boot_cap=value), rule_ids=["GPIO-004"])
        assert bool(report.warnings) is fires, f"{value} misjudged"


def test_gpio004_never_guesses_an_unparseable_value() -> None:
    d = _strap_board(boot_cap="DNP")
    assert not check(d, rule_ids=["GPIO-004"]).findings


def test_gpio004_ignores_a_capacitor_on_a_non_strapping_net() -> None:
    """HDG's warning is about strapping pins; EN and ordinary GPIO are not."""
    d = _strap_board()
    u = next(c for c in d.components if isinstance(c, StrapMcu))
    d.net("IO4").connect(u.pin("IO4"))
    _two_pin(d, Cap("1uF"), "IO4", GND)
    assert not check(d, rule_ids=["GPIO-004"]).findings


def test_gpio005_fires_only_on_analog_only_pads() -> None:
    design, _ = _fire_005()
    warns = check(design, rule_ids=["GPIO-005"]).warnings
    assert len(warns) == 1, [f.message for f in warns]
    assert warns[0].target == "TEST-ADC-MCU:SENSOR_VP@VSENSE"
    assert "ADC1_CH0" in warns[0].message
    assert "0.1 μF filter capacitor" in warns[0].citation
    assert ADC_FILTER_F == 0.1e-6
    # GPIO25 is ADC-capable and pulled up with no capacitor, and must NOT be
    # flagged: capability is not use.
    assert not any("GPIO25" in f.target for f in warns)


def test_gpio005_is_silent_when_the_model_carries_no_functions() -> None:
    """No ADC data → no finding at all, rather than a guess or an INFO wall."""
    from src.ecad.library import get as registry_get

    d = Design("wroom")
    module = registry_get("ESP32-S3-WROOM-1")()
    _powered(d, module)
    assert not check(d, rule_ids=["GPIO-005"]).findings


# ---------------------------------------------------------------------------
# Waiver targets survive the project layer's renumbering
# ---------------------------------------------------------------------------

def test_waiver_targets_are_stable_across_reference_renumbering() -> None:
    """A ref-keyed target would silently go stale — the exact failure mode
    the engine's stale-waiver reporting exists to catch.

    ``sheets()`` gives the module ``U1``; ``build()`` renumbers it into the
    project namespace and it becomes ``U2``. Both are documented ways to check
    this design (``src/ecad/rules/cli.py`` uses the latter), so a waiver
    written against one must apply to the other.
    """
    from_sheets = {f.target for f in check(ref.sheets()["mcu"]).errors
                   if f.rule_id == "GPIO-001"}
    project = ref.build()
    from_build = set()
    for design in project.designs.values():
        from_build |= {f.target for f in check(design).errors
                       if f.rule_id == "GPIO-001"}
    assert from_sheets == from_build == REFERENCE_STRAP_TARGETS

    # …and the refs really did differ, or this test proves nothing.
    sheet_refs = {c.ref for c in ref.sheets()["mcu"].components
                  if c.part_name == ref.MODULE}
    build_refs = {c.ref for d in project.designs.values()
                  for c in d.components if c.part_name == ref.MODULE}
    assert sheet_refs != build_refs, (
        "the project layer no longer renumbers; this test's premise is gone")


def test_waiver_target_is_derived_from_the_part_not_the_designator() -> None:
    u = StrapMcu()
    assert waiver_target(u, u.pin("IO0")) == "TEST-STRAP-MCU:IO0"
    assert waiver_target(u, u.pin("IO0"), "@BOOT") == "TEST-STRAP-MCU:IO0@BOOT"


# ---------------------------------------------------------------------------
# The reference design — the truth, whatever it is
# ---------------------------------------------------------------------------

#: The three strapping pins GPIO-001 reports on the reference design. They are
#: exactly the three the design's own STRAPPING table marks ``waiver=True``,
#: which is asserted below rather than assumed.
REFERENCE_STRAP_TARGETS = {
    "ESP32-S3-WROOM-1:IO3",
    "ESP32-S3-WROOM-1:IO45",
    "ESP32-S3-WROOM-1:IO46",
}

#: The name ``src/ecad/rules/cli.py`` gives the merged-board context for this
#: example (``f"{module} (merged)"``). Scoped waivers key off the context
#: name, so the shipped ledger and every test that checks the merged board
#: have to agree on one spelling — this is it.
MERGED_CONTEXT = "examples.esp32_s3_reference (merged)"


def test_reference_design_gpio001_matches_the_designs_own_waiver_flags() -> None:
    """The rule and the design agree, independently, on which pins are waived.

    ``examples/esp32_s3_reference/design.py`` declares a ``STRAPPING`` table of
    ``StrappingDecision``s straight out of DS v1.8 Table 4-1, and marks three
    of the four ``waiver=True`` — GPIO3 (floating, no internal pull), GPIO45
    and GPIO46 (held only by the chip's internal weak pull-down). GPIO0 gets a
    real 10 kΩ pull-up.

    GPIO-001 was written without reading those flags: it looks only at the
    netlist and the part model. That it reports precisely the ``waiver=True``
    set, and clears GPIO0, is the strongest available evidence that the rule
    is measuring what the design's author was reasoning about.
    """
    declared_waived = {f"ESP32-S3-WROOM-1:IO{d.gpio}"
                       for d in ref.STRAPPING if d.waiver}
    declared_held = {f"ESP32-S3-WROOM-1:IO{d.gpio}"
                     for d in ref.STRAPPING if not d.waiver}
    assert declared_waived and declared_held, "the design's table changed shape"

    report = check(ref.sheets()["mcu"], rule_ids=["GPIO-001"])
    fired = {f.target for f in report.errors}
    assert fired == declared_waived == REFERENCE_STRAP_TARGETS
    assert not (fired & declared_held), (
        "GPIO-001 flagged a pin the design holds with a real resistor")


def test_reference_design_gpio002_agrees_with_the_verified_part_model() -> None:
    """The design's declared table vs the regenerated part model.

    The declaration is read out of the reference design READ-ONLY and handed
    to the engine through ``PartFacts.strapping``, which is the channel
    GPIO-002 documents.
    """
    declared = tuple(f"GPIO{d.gpio}" for d in ref.STRAPPING)
    facts = {ref.MODULE: PartFacts(
        part_name=ref.MODULE, strapping=declared,
        source="examples/esp32_s3_reference/design.py STRAPPING, authored "
               "from ESP32-S3-WROOM-1 DS v1.8 Table 4-1")}
    report = check(ref.sheets()["mcu"], rule_ids=["GPIO-002"], facts=facts)
    assert report.ok, [f.message for f in report.errors]
    assert not report.findings, [f.message for f in report.findings]
    assert set(declared) == {"GPIO0", "GPIO3", "GPIO45", "GPIO46"}


def test_reference_design_gpio002_catches_a_dropped_strapping_role() -> None:
    """Positive control: drop one row and the cross-check must notice."""
    declared = tuple(f"GPIO{d.gpio}" for d in ref.STRAPPING if d.gpio != 46)
    facts = {ref.MODULE: PartFacts(part_name=ref.MODULE, strapping=declared,
                                   source="TEST: a table missing GPIO46")}
    errors = check(ref.sheets()["mcu"], rule_ids=["GPIO-002"],
                   facts=facts).errors
    assert {f.target for f in errors} == {"ESP32-S3-WROOM-1:GPIO46:undeclared"}


def test_reference_design_gpio_pack_reports_exactly_these_findings() -> None:
    """The whole GPIO pack over every sheet, as data — nothing may hide.

    GPIO-002/003/004/005 are silent here and that is a real result, not a
    skip: the design declares no strapping table through ``PartFacts`` (002),
    the ESP32-S3-WROOM-1 model has no input-only GPIO pads (003), the design
    deliberately fits no capacitor on BOOT (004), and the module's model
    carries no ADC functions (005). Each is asserted separately below so a
    silent rule cannot be mistaken for a passing one.
    """
    expected = {
        "esp32-s3-ref-power": set(),
        "esp32-s3-ref-mcu": {("GPIO-001", t) for t in REFERENCE_STRAP_TARGETS},
        "esp32-s3-ref-usb": set(),
    }
    for design in ref.sheets().values():
        report = check(design, domain=DOMAIN)
        got = {(f.rule_id, f.target) for f in report.findings}
        assert got == expected[design.name], (
            f"sheet {design.name} GPIO findings changed: {sorted(got)}")


def test_reference_design_silent_rules_are_silent_for_stated_reasons() -> None:
    """Prove each quiet rule had no data, rather than having been skipped."""
    from src.ecad.library import get as registry_get
    from src.ecad.rules.gpio import _adc_only_pins

    module = registry_get(ref.MODULE)()
    # 003: no input-only GPIO pads on this module.
    assert not [p for p in module.pins if is_input_only(p)]
    # 005: the module's model lists no alternate functions at all.
    assert not _adc_only_pins(module)
    assert not any(p.spec.functions for p in module.pins)
    # 004: BOOT carries no capacitor.
    mcu_sheet = ref.sheets()["mcu"]
    boot = next(n for n in mcu_sheet.nets if n.name == "BOOT")
    assert not [p for p in boot.pins if p.owner.reference_prefix == "C"]
    # …and the strapping pins the rule looked at really were four.
    assert len(strapping_pins(module)) == 4


def test_reference_design_gpio_findings_are_covered_by_the_shipped_ledger():
    """Every GPIO error the reference design produces has a cited waiver.

    Both passes the CLI makes are covered: the per-sheet run and the merged
    board. The merged pass needs its own scope because a waiver's scope is the
    *context* name, and ``src/ecad/rules/cli.py`` names the merged context
    after the module. Nothing is unscoped: an unscoped waiver would be
    reported stale on the two sheets that have no strapping pins, and a wall
    of false staleness is how a genuinely stale waiver hides.
    """
    ledger = load_waivers(Path(ref.__file__).parent / "rule_waivers.json")
    gpio_waivers = [w for w in ledger if w.rule_id.startswith("GPIO-")]
    assert {w.target for w in gpio_waivers} == REFERENCE_STRAP_TARGETS
    for w in gpio_waivers:
        assert "Table 4-1" in w.cited_source, (
            f"waiver for {w.target} does not cite the datasheet table")
        assert w.reason and w.author and w.scope

    for design in ref.sheets().values():
        report = check(design, domain=DOMAIN, waivers=gpio_waivers)
        assert report.ok, [f.message for f in report.errors]
        assert not [f for f in report.findings if f.rule_id == WAIVER_STALE], (
            [f.message for f in report.findings])

    merged = check(ref.sheets(), name=MERGED_CONTEXT, domain=DOMAIN,
                   waivers=gpio_waivers)
    assert merged.ok, [f.message for f in merged.errors]
    assert not [f for f in merged.findings if f.rule_id == WAIVER_STALE]
    assert len(merged.waived) == len(REFERENCE_STRAP_TARGETS)


def test_shipped_gpio_waivers_quote_the_designs_own_rationale() -> None:
    """A waiver must carry the design's reasoning, not a bare mute.

    Each of the three cites the DS Table 4-1 row it relies on, and the design
    itself already wrote that reasoning down in its ``StrappingDecision``
    rationale — so the ledger and the design say the same thing about the same
    pin, and drift between them is visible.
    """
    ledger = load_waivers(Path(ref.__file__).parent / "rule_waivers.json")
    by_target = {}
    for w in ledger:
        if w.rule_id.startswith("GPIO-"):
            by_target.setdefault(w.target, []).append(w)

    for decision in ref.STRAPPING:
        target = f"ESP32-S3-WROOM-1:IO{decision.gpio}"
        if not decision.waiver:
            assert target not in by_target, (
                f"GPIO{decision.gpio} is held by a real resistor; it must not "
                f"carry a waiver")
            continue
        waivers = by_target.get(target)
        assert waivers, f"GPIO{decision.gpio} is waived by the design but has "\
                        f"no cited waiver in the ledger"
        for w in waivers:
            assert "Table 4-1" in w.cited_source
            assert str(decision.level) in w.cited_source or \
                decision.level == "floating"
