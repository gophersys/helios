"""Tests for the electrical rule engine and the power rule pack.

Test discipline, stated up front because this repo has shipped four gates
that could not fail (a lint iterating the wrong collection, a netlist gate
covering one sheet of many, a strapping check returning ``ok=None``, and a
project gate no input could trip):

**Every rule ships with a design that makes it FIRE and a design that is
clean.** Both live in :data:`FIRING` / :data:`CLEAN` and are run by
parametrized tests, so a rule with no failing fixture is a test failure,
not a silently-green rule. :func:`test_every_registered_rule_has_fixtures`
closes the loop: rule N+1 cannot be added without both.

The firing tests assert the finding arrives at the rule's declared
**severity** — a fixture that only provokes an INFO "no data" would
otherwise look like coverage while proving nothing.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from examples.esp32_s3_reference import design as ref
from src.ecad import Design
from src.ecad.component import Component
from src.ecad.model import FootprintRef, PinRole, pin
from src.ecad.rules import (
    PartFacts,
    power,
    RegulatorFacts,
    RuleContext,
    Severity,
    Waiver,
    check,
    load_waivers,
    rules,
)
from src.ecad.rules import cli as rules_cli
from tests.ecad.test_rules_gpio import MERGED_CONTEXT, REFERENCE_STRAP_TARGETS
from src.ecad.rules.engine import (
    WAIVER_STALE,
    is_ground_pin,
    is_power_pin,
    parse_farads,
    parse_volts,
)

_FP = FootprintRef("Package_TO_SOT_SMD", "SOT-23-5")


# ---------------------------------------------------------------------------
# Fixture parts — hand-written so the tests do not depend on generated files
# ---------------------------------------------------------------------------

class Mcu(Component):
    """Two supply pins on one rail, one ground, one GPIO."""

    part_name = "TEST-MCU"
    reference_prefix = "U"
    footprint = _FP
    _PIN_SPECS = (
        pin("1", "VDD", "power_in", "power"),
        pin("2", "VDD", "power_in", "power"),
        pin("3", "GND", "power_in", "ground"),
        pin("4", "IO0", "bidirectional", "gpio"),
    )
    POWER_FACTS = PartFacts(
        part_name="TEST-MCU", voltage_min=3.0, voltage_typ=3.3,
        voltage_max=3.6, abs_max_v=4.0, min_supply_current_a=0.5,
        source="TEST fixture datasheet, Table 1 Recommended Operating "
               "Conditions (3.0/3.3/3.6 V), Table 2 Absolute Maximum (4.0 V)")


class DualDomainMcu(Component):
    """An ESP32-S3-shaped part: a main supply plus the VDD_SPI domain."""

    part_name = "TEST-MCU-DUAL"
    reference_prefix = "U"
    footprint = _FP
    _PIN_SPECS = (
        pin("1", "VDD3P3", "power_in", "power"),
        pin("2", "VDD_SPI", "power_in", "power"),
        pin("3", "GND", "power_in", "ground"),
        pin("4", "IO0", "bidirectional", "gpio"),
    )


class Ldo(Component):
    """3.3 V / 600 mA regulator with a 0.4 V dropout."""

    part_name = "TEST-LDO-3.3"
    reference_prefix = "U"
    footprint = _FP
    _PIN_SPECS = (
        pin("1", "VIN", "power_in", "power"),
        pin("2", "GND", "power_in", "ground"),
        pin("3", "EN", "input", "control"),
        pin("5", "VOUT", "power_out", "power"),
    )
    POWER_FACTS = PartFacts(
        part_name="TEST-LDO-3.3", voltage_min=2.5, voltage_max=6.0,
        abs_max_v=6.5,
        regulator=RegulatorFacts(
            output_v=3.3, dropout_v=0.4, dropout_at_ma=600.0,
            max_output_current_a=0.6, vin_min=2.5, vin_max=6.0,
            source="TEST fixture datasheet, Electrical Characteristics: "
                   "VOUT 3.3 V, IOUT(MAX) 600 mA, VDROP 400 mV max"),
        source="TEST fixture datasheet")


class PlainLdo(Component):
    """A regulator no source says anything about — the "no data" path."""

    part_name = "TEST-LDO-UNSPECIFIED"
    reference_prefix = "U"
    footprint = _FP
    _PIN_SPECS = (
        pin("1", "VIN", "power_in", "power"),
        pin("2", "GND", "power_in", "ground"),
        pin("5", "VOUT", "power_out", "power"),
    )


class MisroledLdo(Component):
    """The audited near-miss: a ground pad named ``AGND`` with role POWER.

    ``ecad_bridge._infer_role`` only matches names that *start* with
    ``GND``/``VSS``, so ``AGND`` becomes ``PinRole.POWER`` and
    ``circuits.ldo_regulator`` — which wires by role — puts it on VIN.
    """

    part_name = "TEST-LDO-MISROLED"
    reference_prefix = "U"
    footprint = _FP
    _PIN_SPECS = (
        pin("1", "VIN", "power_in", "power"),
        pin("2", "AGND", "power_in", "power"),   # <- the defect
        pin("5", "VOUT", "power_out", "power"),
    )


class Cap(Component):
    part_name = "TEST-C"
    reference_prefix = "C"
    footprint = FootprintRef("Capacitor_SMD", "C_0402_1005Metric")
    _PIN_SPECS = (pin("1", "P1", "passive", "passive"),
                  pin("2", "P2", "passive", "passive"))

    def __init__(self, value: str = "100nF") -> None:
        super().__init__()
        self.value = value


class Connector(Component):
    part_name = "TEST-J"
    reference_prefix = "J"
    footprint = FootprintRef("Connector", "TEST")
    _PIN_SPECS = (pin("1", "VBUS", "passive", "power"),
                  pin("2", "GND", "passive", "ground"))


class Unknown(Component):
    """A part no source knows anything about — the "no data" path."""

    part_name = "TEST-MYSTERY"
    reference_prefix = "U"
    footprint = _FP
    _PIN_SPECS = (pin("1", "VDD", "power_in", "power"),
                  pin("2", "GND", "power_in", "ground"),
                  pin("3", "IO", "bidirectional", "gpio"))


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _cap(d: Design, value: str, a: str, b: str) -> Cap:
    c = Cap(value)
    d.add(c)
    d.net(a).connect(c.pin("1"))
    d.net(b).connect(c.pin("2"))
    return c


def _board(*, rail: str = "+3V3", vin: str = "+5V", regulated: bool = True,
           mcu: type[Component] = Mcu, caps: tuple[str, ...] = ("22uF", "100nF",
                                                                "100nF"),
           connector: bool = True, name: str = "t") -> Design:
    """A minimal, well-formed board; every knob is a way to break one rule."""
    d = Design(name)
    u = mcu()
    d.add(u)
    for p in u.pins:
        if p.role is PinRole.GROUND:
            d.net("GND").connect(p)
        elif p.name in ("VDD", "VDD3P3"):
            d.net(rail).connect(p)
    if connector:
        j = Connector()
        d.add(j)
        d.net(vin).connect(j.pin("VBUS"))
        d.net("GND").connect(j.pin("GND"))
    if regulated:
        reg = Ldo()
        d.add(reg)
        d.net(vin).connect(reg.pin("VIN"), reg.pin("EN"))
        d.net("GND").connect(reg.pin("GND"))
        d.net(rail).connect(reg.pin("VOUT"))
        _cap(d, "22uF", vin, "GND")
    for value in caps:
        _cap(d, value, rail, "GND")
    return d


# --- PWR-001 ---------------------------------------------------------------

def _fire_001() -> tuple[Design, dict]:
    return _board(regulated=False, connector=False), {}


def _clean_001() -> tuple[Design, dict]:
    return _board(), {}


# --- PWR-002 ---------------------------------------------------------------

def _fire_002() -> tuple[Design, dict]:
    return _board(caps=()), {}


def _clean_002() -> tuple[Design, dict]:
    return _board(caps=("22uF", "100nF", "100nF")), {}


# --- PWR-003 ---------------------------------------------------------------

def _fire_003() -> tuple[Design, dict]:
    d = _board(mcu=DualDomainMcu)
    u = next(c for c in d.components if isinstance(c, DualDomainMcu))
    d.net("+3V3").connect(u.pin("VDD_SPI"))     # <- the VDD_SPI hazard
    return d, {}


def _clean_003() -> tuple[Design, dict]:
    d = _board(mcu=DualDomainMcu)
    u = next(c for c in d.components if isinstance(c, DualDomainMcu))
    d.net("+1V8").connect(u.pin("VDD_SPI"))
    _cap(d, "1uF", "+1V8", "GND")
    return d, {}


# --- PWR-004 ---------------------------------------------------------------

def _fire_004() -> tuple[Design, dict]:
    # The MCU's own rail is 5 V: outside 3.0-3.6 V and past its 4.0 V
    # absolute maximum.
    return _board(rail="+5V", vin="+5V", regulated=False), {}


def _clean_004() -> tuple[Design, dict]:
    return _board(), {}


# --- PWR-005 ---------------------------------------------------------------

def _fire_005() -> tuple[Design, dict]:
    # 3.5 V in, 3.3 V out = 0.2 V of headroom for a 0.4 V dropout.
    return _board(vin="+3V5"), {}


def _clean_005() -> tuple[Design, dict]:
    return _board(vin="+5V"), {}


# --- PWR-006 ---------------------------------------------------------------

def _fire_006() -> tuple[Design, dict]:
    return _board(caps=("100nF", "100nF")), {}


def _clean_006() -> tuple[Design, dict]:
    return _board(caps=("22uF", "100nF", "100nF")), {}


# --- PWR-007 ---------------------------------------------------------------

#: A 150 mA variant of the fixture LDO, supplied through the explicit-facts
#: channel (which also exercises that channel's precedence over the class).
_SMALL_LDO = PartFacts(
    part_name="TEST-LDO-3.3",
    regulator=RegulatorFacts(
        output_v=3.3, dropout_v=0.4, dropout_at_ma=150.0,
        max_output_current_a=0.15,
        source="TEST fixture datasheet (150 mA variant), IOUT(MAX) 150 mA"),
    source="TEST fixture datasheet (150 mA variant)")


def _fire_007() -> tuple[Design, dict]:
    # A 150 mA LDO feeding an MCU whose datasheet demands a 500 mA supply.
    return _board(), {"facts": {"TEST-LDO-3.3": _SMALL_LDO}}


def _clean_007() -> tuple[Design, dict]:
    return _board(), {}


#: rule id → a design that MUST produce that rule at its declared severity.
FIRING = {
    "PWR-001": _fire_001, "PWR-002": _fire_002, "PWR-003": _fire_003,
    "PWR-004": _fire_004, "PWR-005": _fire_005, "PWR-006": _fire_006,
    "PWR-007": _fire_007,
}

#: rule id → a design that MUST produce nothing above INFO for that rule.
CLEAN = {
    "PWR-001": _clean_001, "PWR-002": _clean_002, "PWR-003": _clean_003,
    "PWR-004": _clean_004, "PWR-005": _clean_005, "PWR-006": _clean_006,
    "PWR-007": _clean_007,
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

    from src.ecad.rules import get_rule
    declared = get_rule(rule_id).severity
    at_severity = [f for f in hits if f.severity is declared]
    assert at_severity, (
        f"{rule_id} fired only at {[f.severity.value for f in hits]}, never at "
        f"its declared {declared.value} — an INFO-only fixture is not coverage")
    assert not report.ok, f"{rule_id} fired but the report still passed"

    # Every finding must be actionable and traceable.
    for f in at_severity:
        assert f.target and f.message and f.citation and f.remediation
        assert f.design == design.name

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


def test_every_registered_rule_has_fixtures() -> None:
    """Rule N+1 of the POWER pack cannot merge without both fixtures.

    Scoped to this pack's own domain now that a second pack exists. The
    registry-wide version of this assertion — no rule id in ANY domain may
    exist without a firing fixture somewhere — lives in
    ``tests/ecad/test_rules_gpio.py``
    (``test_every_registered_rule_has_a_firing_fixture``), so nothing was
    given up by narrowing this one.
    """
    registered = {r.id for r in rules(power.DOMAIN)}
    assert registered, "no power rules are registered at all"
    assert registered <= set(FIRING), (
        f"rules with no FIRING fixture: {sorted(registered - set(FIRING))}")
    assert registered <= set(CLEAN), (
        f"rules with no CLEAN fixture: {sorted(registered - set(CLEAN))}")
    assert set(FIRING) <= registered, "FIRING names an unregistered rule"


def test_clean_board_passes_the_whole_pack() -> None:
    """The well-formed fixture board clears every rule at once."""
    design, kwargs = _clean_007()
    report = check(design, **kwargs)
    assert report.ok, [f.message for f in report.errors]
    assert not report.warnings, [f.message for f in report.warnings]


def test_every_rule_is_cited_and_documented() -> None:
    for rule in rules():
        assert rule.citation(), f"{rule.id} has no citation"
        assert "http" in rule.citation(), f"{rule.id} citation has no source URL"
        assert len(rule.doc.strip()) > 100, f"{rule.id} has no rule doc"
        assert rule.domain and rule.title


def test_pwr002_documents_that_it_cannot_see_proximity() -> None:
    """HDG says "close to the pins"; this engine cannot check placement."""
    from src.ecad.rules import get_rule
    rule = get_rule("PWR-002")
    assert "PRESENCE ONLY" in rule.title
    assert "proximity" in rule.doc.lower()
    design, _ = _fire_002()
    finding = next(f for f in check(design, rule_ids=["PWR-002"]).findings)
    assert "PRESENCE" in finding.citation


# ---------------------------------------------------------------------------
# Rule-specific behaviour the parametrized pair cannot express
# ---------------------------------------------------------------------------

def test_pwr002_warns_when_there_are_fewer_caps_than_power_pins() -> None:
    design = _board(caps=("22uF",))
    findings = check(design, rule_ids=["PWR-002"]).findings
    warn = [f for f in findings if f.severity is Severity.WARNING]
    assert warn and "2 power pin(s)" in warn[0].message
    assert "only 1 capacitor" in warn[0].message


def test_pwr003_catches_the_misroled_ground_pin_shorting_a_rail() -> None:
    """The audited near-miss: ``AGND`` roled POWER, wired to VIN."""
    d = Design("misroled")
    reg = MisroledLdo()
    d.add(reg)
    d.net("+5V").connect(reg.pin("VIN"), reg.pin("AGND"))   # the short
    d.net("+3V3").connect(reg.pin("VOUT"))
    _cap(d, "22uF", "+5V", "GND")
    _cap(d, "22uF", "+3V3", "GND")

    # It is invisible to the syntactic gate: no ERC output conflict, no
    # unconnected power pin.
    assert not [i for i in d.check()
                if i.is_error and i.code == "output-conflict"]

    findings = check(d, rule_ids=["PWR-003"]).errors
    assert findings, "PWR-003 missed a rail tied to a ground pin"
    assert "rail-to-ground short" in findings[0].message
    assert "AGND" in findings[0].message


def test_pwr003_does_not_flag_two_parts_sharing_one_rail() -> None:
    """U1 calling it VDD and U2 calling it VCC is what a rail is for."""
    d = _board()
    second = Unknown()
    d.add(second)
    d.net("+3V3").connect(second.pin("VDD"))
    d.net("GND").connect(second.pin("GND"))
    assert not check(d, rule_ids=["PWR-003"]).findings


def test_pwr004_says_no_data_rather_than_guessing() -> None:
    d = Design("mystery")
    u = Unknown()
    d.add(u)
    d.net("+3V3").connect(u.pin("VDD"))
    d.net("GND").connect(u.pin("GND"), u.pin("IO"))
    _cap(d, "22uF", "+3V3", "GND")
    report = check(d, rule_ids=["PWR-004"])
    assert report.ok
    infos = report.infos
    assert infos and infos[0].message.startswith("no data:")
    assert "NOT checked" in infos[0].message


def test_pwr004_says_no_data_when_the_rail_voltage_is_unknown() -> None:
    d = _board(rail="VMAIN", regulated=False, connector=False)
    report = check(d, rule_ids=["PWR-004"])
    assert report.ok
    assert any("VMAIN has no known voltage" in f.message for f in report.infos)


def test_pwr004_reads_extracted_datasheet_facts(tmp_path) -> None:
    """``data/ingest/<id>/extracted.json`` is consumed as data, not code."""
    root = tmp_path / "ingest"
    (root / "test-mystery").mkdir(parents=True)
    (root / "test-mystery" / "extracted.json").write_text(json.dumps({
        "chip_name": "TEST-MYSTERY",
        "pins": [],
        "power": {"voltage_min": 1.7, "voltage_typ": 1.8, "voltage_max": 1.9,
                  "power_pins": ["VDD"],
                  "decoupling_caps": [{"value": "100nF"}]},
    }))
    d = Design("mystery")
    u = Unknown()
    d.add(u)
    d.net("+3V3").connect(u.pin("VDD"))
    d.net("GND").connect(u.pin("GND"), u.pin("IO"))
    _cap(d, "22uF", "+3V3", "GND")

    without = check(d, rule_ids=["PWR-004"])
    assert without.ok and without.infos          # no data → nothing checked

    with_facts = check(d, rule_ids=["PWR-004"], ingest_root=root)
    assert not with_facts.ok
    assert "outside" in with_facts.errors[0].message
    assert "1.7-1.9 V" in with_facts.errors[0].message
    assert "extracted.json" in with_facts.errors[0].citation


def test_pwr005_reports_no_data_without_a_dropout_spec() -> None:
    d = Design("unspecified-ldo")
    reg = PlainLdo()
    d.add(reg)
    d.net("+5V").connect(reg.pin("VIN"))
    d.net("GND").connect(reg.pin("GND"))
    d.net("+3V3").connect(reg.pin("VOUT"))
    report = check(d, rule_ids=["PWR-005"])
    assert report.ok
    assert any("no source states its dropout" in f.message
               for f in report.infos)


def test_pwr006_errors_below_10uf_and_warns_below_22uf() -> None:
    below = check(_board(caps=("100nF",)), rule_ids=["PWR-006"])
    assert not below.ok
    assert "guideline minimum is 10 uF" in below.errors[0].message

    between = check(_board(caps=("10uF",)), rule_ids=["PWR-006"])
    assert between.ok
    warn = [f for f in between.warnings if f.nets == ("+3V3",)]
    assert warn and "22 uF" in warn[0].message


def test_pwr007_uses_the_regulator_rating_not_a_guess() -> None:
    design, kwargs = _fire_007()
    report = check(design, rule_ids=["PWR-007"], **kwargs)
    err = report.errors[0]
    assert "150 mA" in err.message and "500 mA" in err.message
    assert "no less than 500 mA" in err.citation


# ---------------------------------------------------------------------------
# Engine behaviour: context, waivers, report
# ---------------------------------------------------------------------------

def test_report_ok_is_a_real_boolean_gate() -> None:
    fired, _ = _fire_001()
    clean, _ = _clean_001()
    assert check(fired).ok is False
    assert check(clean).ok is True


def test_waiver_requires_reason_source_and_author() -> None:
    for bad in ({"reason": "", "cited_source": "s", "author": "a"},
                {"reason": "r", "cited_source": "", "author": "a"},
                {"reason": "r", "cited_source": "s", "author": ""}):
        with pytest.raises(ValueError):
            Waiver(rule_id="PWR-001", target="+3V3", **bad)
        with pytest.raises(ValueError):
            Waiver.from_dict({"rule_id": "PWR-001", "target": "+3V3", **bad})


def test_a_cited_waiver_clears_the_gate() -> None:
    design, _ = _fire_001()
    before = check(design, rule_ids=["PWR-001"])
    assert not before.ok
    target = before.errors[0].target

    after = check(design, rule_ids=["PWR-001"], waivers=[Waiver(
        rule_id="PWR-001", target=target,
        reason="rail arrives from the power sheet as a global power symbol",
        cited_source="KiCad global power symbol semantics; "
                     "examples/esp32_s3_reference/design.py 'Cross-sheet net "
                     "convention'",
        author="test")])
    assert after.ok
    assert len(after.waived) == 1
    assert after.waived[0].waiver.author == "test"
    assert not after.findings


def test_a_stale_waiver_is_itself_a_finding() -> None:
    design, _ = _clean_001()
    report = check(design, waivers=[Waiver(
        rule_id="PWR-001", target="NOT-A-NET", reason="obsolete",
        cited_source="an old PR", author="test")])
    stale = [f for f in report.findings if f.rule_id == WAIVER_STALE]
    assert len(stale) == 1
    assert "NOT-A-NET" in stale[0].message
    assert report.ok, "a stale waiver is a warning, not a hard failure"


def test_a_scoped_waiver_is_inert_outside_its_scope() -> None:
    design, _ = _clean_001()
    waiver = Waiver(rule_id="PWR-001", target="+3V3", reason="other sheet",
                    cited_source="doc", author="test", scope="some-other-sheet")
    report = check(design, waivers=[waiver])
    assert not [f for f in report.findings if f.rule_id == WAIVER_STALE]


def test_waivers_round_trip_through_json() -> None:
    w = Waiver(rule_id="PWR-006", target="VBUS", reason="r",
               cited_source="s", author="a", scope="sheet")
    assert Waiver.from_dict(w.as_dict()) == w


def test_context_is_built_once_and_rules_never_touch_the_filesystem() -> None:
    """A missing ingest root is not an error — it means "no extracted facts"."""
    design, _ = _clean_001()
    ctx = RuleContext.build(design, ingest_root="/nonexistent/ingest/root")
    report = check(design, ctx=ctx)
    assert report.ok
    assert ctx.nets and ctx.components


def test_merged_context_does_not_confuse_two_components_named_u1() -> None:
    """Regression: facts were keyed by ref, so a merged board gave the LDO
    the module's absolute-maximum rating and invented an ERROR out of it."""
    a = Design("sheet-a")
    ldo = Ldo()
    a.add(ldo)
    a.net("+5V").connect(ldo.pin("VIN"), ldo.pin("EN"))
    a.net("GND").connect(ldo.pin("GND"))
    a.net("+3V3").connect(ldo.pin("VOUT"))

    b = Design("sheet-b")
    mcu = Mcu()
    b.add(mcu)
    b.net("+3V3").connect(*mcu.pins_named("VDD"))
    b.net("GND").connect(mcu.pin("GND"))

    assert ldo.ref == mcu.ref == "U1"
    ctx = RuleContext.merged({"a": a, "b": b})
    assert ctx.facts_for(ldo).regulator is not None
    assert ctx.facts_for(mcu).regulator is None
    assert ctx.facts_for(ldo).abs_max_v == 6.5
    assert ctx.facts_for(mcu).abs_max_v == 4.0
    assert {ctx.ref(ldo), ctx.ref(mcu)} == {"a/U1", "b/U1"}


def test_merged_context_joins_rails_across_sheets() -> None:
    a = Design("a")
    j = Connector()
    a.add(j)
    a.net("VBUS").connect(j.pin("VBUS"))
    a.net("GND").connect(j.pin("GND"))

    b = Design("b")
    reg = Ldo()
    b.add(reg)
    b.net("VBUS").connect(reg.pin("VIN"), reg.pin("EN"))
    b.net("GND").connect(reg.pin("GND"))
    b.net("+3V3").connect(reg.pin("VOUT"))

    per_sheet = check(b, rule_ids=["PWR-001"])
    assert not per_sheet.ok            # nothing drives VBUS on sheet b alone

    merged = check({"a": a, "b": b}, rule_ids=["PWR-001"])
    assert merged.ok                   # the connector drives it on the board


def test_rail_voltage_precedence_prefers_the_regulator_over_the_net_name() -> None:
    """A net called +3V3 fed by a 1.8 V regulator is 1.8 V, and a defect."""
    d = Design("mislabelled")
    reg = Ldo()
    d.add(reg)
    d.net("+5V").connect(reg.pin("VIN"), reg.pin("EN"))
    d.net("GND").connect(reg.pin("GND"))
    d.net("+3V3").connect(reg.pin("VOUT"))
    small = PartFacts(part_name="TEST-LDO-3.3",
                      regulator=RegulatorFacts(output_v=1.8, dropout_v=0.4,
                                               source="TEST 1.8 V variant"))
    ctx = RuleContext.build(d, facts={"TEST-LDO-3.3": small})
    rail = ctx.rail_voltage("+3V3")
    assert rail is not None and rail.volts == 1.8 and rail.origin == "regulator"


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text,farads", [
    ("100nF", 1e-7), ("0.1uF", 1e-7), ("10uF", 1e-5), ("22uF", 2.2e-5),
    ("22 µF", 2.2e-5), ("10uF/25V", 1e-5), ("1F", 1.0), ("4.7pF", 4.7e-12),
])
def test_parse_farads(text: str, farads: float) -> None:
    assert parse_farads(text) == pytest.approx(farads)


@pytest.mark.parametrize("text", ["", None, "0R", "10", "DNP", "10k", "NC"])
def test_parse_farads_refuses_to_guess(text) -> None:
    assert parse_farads(text) is None


@pytest.mark.parametrize("text,volts", [
    ("+3V3", 3.3), ("3V3", 3.3), ("1V8", 1.8), ("+5V", 5.0), ("5V", 5.0),
    ("3.3V", 3.3),
])
def test_parse_volts(text: str, volts: float) -> None:
    assert parse_volts(text) == pytest.approx(volts)


@pytest.mark.parametrize("text", ["VBUS", "VCC", "GND", "+3V3_LED", "", None])
def test_parse_volts_refuses_to_guess(text) -> None:
    assert parse_volts(text) is None


def test_ground_classification_uses_name_and_role() -> None:
    bad = MisroledLdo()
    agnd = bad.pin("AGND")
    assert agnd.role is PinRole.POWER          # the part model is wrong…
    assert is_ground_pin(agnd)                 # …the engine is not fooled
    assert not is_power_pin(agnd)


# ---------------------------------------------------------------------------
# The reference design — the truth, whatever it is
# ---------------------------------------------------------------------------

#: Errors the reference design produces per sheet, and why each is either the
#: documented cross-sheet convention or a documented strapping decision rather
#: than a defect. Kept as data so the test asserts the EXACT set: a new error
#: cannot hide among them.
#:
#: The GPIO-001 entries are the three strapping pins the design deliberately
#: leaves on the chip's internal pull-ups/pull-downs — exactly the three its
#: own ``STRAPPING`` table marks ``waiver=True``. That correspondence, and the
#: cited waivers covering them, are asserted in
#: ``tests/ecad/test_rules_gpio.py``.
REFERENCE_SHEET_ERRORS = {
    "esp32-s3-ref-power": {("PWR-001", "VBUS")},
    "esp32-s3-ref-mcu": ({("PWR-001", "+3V3")}
                         | {("GPIO-001", t) for t in REFERENCE_STRAP_TARGETS}),
    "esp32-s3-ref-usb": {("PWR-006", "VBUS")},
}

_XSHEET = (
    "examples/esp32_s3_reference/design.py, 'Cross-sheet net convention': "
    "+3V3, GND and VBUS are KiCad global power symbols, which are global "
    "across a hierarchy — the rail is driven on another sheet of the same "
    "project. The merged-board pass (RuleContext.merged) reports it clean."
)

REFERENCE_WAIVERS = [
    Waiver(rule_id="PWR-001", target="VBUS", scope="esp32-s3-ref-power",
           reason="VBUS is driven by the USB-C receptacle J1 on the usb sheet",
           cited_source=_XSHEET, author="stage-g"),
    Waiver(rule_id="PWR-001", target="+3V3", scope="esp32-s3-ref-mcu",
           reason="+3V3 is driven by the AP2112K-3.3 on the power sheet",
           cited_source=_XSHEET, author="stage-g"),
    Waiver(rule_id="PWR-006", target="VBUS", scope="esp32-s3-ref-usb",
           reason="the 10 uF at the power entrance is C1, the LDO input "
                  "capacitor on the power sheet; VBUS is one net across both "
                  "sheets",
           cited_source=_XSHEET + " Corroborated by the design's own note: "
                                  "'HDG Power Supply: at least 10 uF at the "
                                  "main power entrance. The 10 uF is fitted "
                                  "(C1, the LDO input capacitor).'",
           author="stage-g"),
]


#: The same ledger, shipped next to the design so the CLI example works.
REFERENCE_LEDGER = (Path(ref.__file__).parent / "rule_waivers.json")


def test_shipped_waiver_ledger_matches_the_documented_one() -> None:
    """The JSON next to the design and the ledger under test are one thing.

    Restricted to this pack's own entries. The ledger is shared between packs;
    the GPIO-001 entries in it are owned — and asserted verbatim, against the
    reference design's own ``StrappingDecision`` rationales — by
    ``tests/ecad/test_rules_gpio.py``. The final assertion keeps that split
    honest: a waiver for some third rule id could not slip into the ledger
    unowned by either file.
    """
    shipped = load_waivers(REFERENCE_LEDGER)
    assert [w for w in shipped if w.rule_id.startswith("PWR-")] == \
        REFERENCE_WAIVERS
    assert {w.rule_id.split("-")[0] for w in shipped} == {"PWR", "GPIO"}


def test_reference_design_sheets_report_exactly_the_known_cross_sheet_errors():
    for name, design in ref.sheets().items():
        report = check(design)
        got = {(f.rule_id, f.target) for f in report.errors}
        assert got == REFERENCE_SHEET_ERRORS[design.name], (
            f"sheet {name} error set changed: {sorted(got)}")


def test_reference_design_merged_board_is_clean() -> None:
    """The board, as opposed to a sheet: every rail is driven somewhere.

    No longer finding-free, and the test says so rather than being relaxed:
    the merged board still carries the three strapping pins the design leaves
    on the chip's internal pulls, because merging sheets does not connect an
    unconnected pad. Every POWER rule passes with no waiver at all, which is
    what this test has always been about.
    """
    bare = check(ref.sheets(), name=MERGED_CONTEXT)
    assert {(f.rule_id, f.target) for f in bare.errors} == \
        {("GPIO-001", t) for t in REFERENCE_STRAP_TARGETS}, \
        [f.message for f in bare.errors]

    report = check(ref.sheets(), name=MERGED_CONTEXT,
                   waivers=load_waivers(REFERENCE_LEDGER))
    assert report.ok, [f.message for f in report.errors]
    # Be suspicious of a clean run: prove the rules actually had data to work
    # with rather than skipping everything as "no data".
    assert not report.infos, [f.message for f in report.infos]
    warnings = {(f.rule_id, f.target) for f in report.warnings}
    assert warnings == {("PWR-006", "VBUS:preferred")}


def test_reference_design_passes_with_the_documented_waivers() -> None:
    ledger = load_waivers(REFERENCE_LEDGER)
    for design in ref.sheets().values():
        report = check(design, waivers=ledger)
        assert report.ok, [f.message for f in report.errors]
        assert not [f for f in report.findings if f.rule_id == WAIVER_STALE], \
            [f.message for f in report.findings if f.rule_id == WAIVER_STALE]


def test_reference_facts_come_from_the_real_datasheet_numbers() -> None:
    ctx = RuleContext.merged(ref.sheets(), name="m")
    module = next(c for c in ctx.components
                  if c.part_name == "ESP32-S3-WROOM-1")
    facts = ctx.facts_for(module)
    assert (facts.voltage_min, facts.voltage_typ, facts.voltage_max) == \
        (3.0, 3.3, 3.6)
    assert facts.abs_max_v == 3.6
    assert facts.min_supply_current_a == 0.5
    assert "Table 10" in facts.source


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_check_reports_and_exits_nonzero() -> None:
    out = io.StringIO()
    code = rules_cli.main(["check", "examples.esp32_s3_reference"], out=out)
    text = out.getvalue()
    assert code == 1
    assert "PWR-001  ERROR   VBUS feeds" in text
    assert "  -> waive: PWR-001 target \"VBUS\"" in text
    assert "=== merged" in text
    assert text.strip().splitlines()[-1].startswith("FAILED (")


def test_cli_check_passes_with_the_shipped_waiver_file() -> None:
    out = io.StringIO()
    code = rules_cli.main(["check", "examples.esp32_s3_reference",
                           "--waivers", str(REFERENCE_LEDGER),
                           "--quiet-info"], out=out)
    text = out.getvalue()
    assert code == 0, text
    assert "WAIVED" in text
    assert "waived by stage-g" in text
    assert text.strip().splitlines()[-1].startswith("OK (0 errors")


def test_cli_list_shows_every_rule_with_its_citation() -> None:
    out = io.StringIO()
    assert rules_cli.main(["list"], out=out) == 0
    text = out.getvalue()
    for rule in rules():
        assert rule.id in text
    assert text.count("  -> ") == len(rules())


def test_cli_json_output_is_machine_readable() -> None:
    out = io.StringIO()
    rules_cli.main(["check", "examples.esp32_s3_reference", "--json",
                    "--waivers", str(REFERENCE_LEDGER)], out=out)
    payload = json.loads(out.getvalue())
    assert set(payload["reports"]) >= {"merged"}
    assert payload["reports"]["merged"]["ok"] is True
    # Waived findings survive into the JSON with their citation attached —
    # the machine-readable form has to carry the ledger, not hide it.
    waived = payload["reports"]["merged"]["waived"]
    assert {w["waiver"]["target"] for w in waived} == REFERENCE_STRAP_TARGETS


def test_cli_json_output_reports_the_merged_board_failing_unwaived() -> None:
    """Without the ledger the merged board is NOT ok, and the JSON says so."""
    out = io.StringIO()
    rules_cli.main(["check", "examples.esp32_s3_reference", "--json"], out=out)
    merged = json.loads(out.getvalue())["reports"]["merged"]
    assert merged["ok"] is False
    assert {f["target"] for f in merged["findings"]
            if f["rule_id"] == "GPIO-001"} == REFERENCE_STRAP_TARGETS


def test_cli_rejects_a_module_with_no_build() -> None:
    with pytest.raises(SystemExit):
        rules_cli.main(["check", "json"], out=io.StringIO())
