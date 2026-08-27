"""Acceptance gates for examples/ — the reference designs.

This is the end-to-end test for the whole stack: verified parts → circuit
blocks → a composed multi-sheet design → the layout engine → a schematic
KiCad loads without complaint.

Every sheet is gated on the same ladder the layout-engine fixtures use
(``tests/ecad/test_layout_engine.py``), and gated **per sheet** rather than
on a sample of one: a defect that ties a signal pin to a rail shows up as a
netlist difference on exactly one sheet, and a suite that only exports the
first sheet never sees it.

Ladder, per sheet:

1. ``Design.check()`` — zero errors, modulo the one documented waiver
   (``single-pin-net`` on a declared cross-sheet exit; see the design
   module's "Cross-sheet net convention").
2. geometric lint on the placed IR, then file lint on the emitted text.
3. ``kicad-cli`` loads it and ERC reports **zero errors**.
4. the exported netlist equals ``Design.intended_netlist()`` exactly.

Then a layer the geometry cannot see — *design intent*: the module's power
pins are actually decoupled, EN actually has an RC to ground, every
strapping pin has a level or a documented waiver, and USB D+/D- land on the
pads the **verified part model** reports rather than on remembered numbers.
"""

import shutil
from pathlib import Path

import pytest

from examples.esp32_s3_reference import design as ref
from src.ecad import Component, Design, ElectricalType, PinRole
from src.ecad.layout.engine import emit
from src.ecad.layout.lints import lint_placed, lint_schematic_text
from src.ecad.library import get as registry_get

KICAD_CLI = shutil.which("kicad-cli") or "/usr/bin/kicad-cli"
skip_no_kicad = pytest.mark.skipif(
    not Path(KICAD_CLI).is_file(), reason="kicad-cli not available"
)

SHEETS = ref.SHEETS


# ---------------------------------------------------------------------------
# Helpers (same shape as tests/ecad/test_layout_engine.py)
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sheets() -> dict[str, Design]:
    return ref.sheets()


def _gates(name: str, design: Design):
    """Geometric hard gates: placed IR lint, then emitted-file lint."""
    placed = ref.layout_sheet(name, design)
    geo = lint_placed(placed)
    assert geo == [], geo
    sheet = emit(placed, design, title=design.name)
    file_lints = lint_schematic_text(sheet.text)
    assert file_lints == [], file_lints
    return placed, sheet


def _netlist_of(text: str, tmp: Path) -> dict[str, set[str]]:
    """kicad-cli netlist export → ``{net: {"REF:pad"}}``."""
    from src.pipeline.roundtrip import _export_netlist, parse_kicad_netlist_xml

    sch = tmp / "sheet.kicad_sch"
    sch.write_text(text)
    xml = _export_netlist(sch, tmp)
    assert xml is not None, "netlist export failed"
    out: dict[str, set[str]] = {}
    for net in parse_kicad_netlist_xml(xml)["nets"]:
        nm = net["name"].lstrip("/")
        if nm.startswith("unconnected-"):
            continue  # KiCad pseudo-nets for no_connect pins
        pins = {f"{n['ref']}:{n['pin']}" for n in net["nodes"]
                if not n["ref"].startswith("#")}
        if pins:
            out[nm] = pins
    return out


def _module_of(design: Design) -> Component:
    return next(c for c in design.components
                if c.part_name == ref.MODULE)


def _capacitors_on(design: Design, net_name: str) -> list[Component]:
    net = next((n for n in design.nets if n.name == net_name), None)
    if net is None:
        return []
    return [p.owner for p in net.pins
            if p.owner.reference_prefix == "C"]


# ---------------------------------------------------------------------------
# Shape of the thing
# ---------------------------------------------------------------------------

def test_build_returns_one_design_per_sheet(sheets):
    assert sorted(sheets) == sorted(SHEETS)
    for name, d in sheets.items():
        assert isinstance(d, Design), name
        assert d.components, f"{name} sheet is empty"


def test_every_component_is_a_part_some_source_can_serve(sheets):
    """No block invents a part: every lib_id on every sheet resolves.

    Through the block layer's resolver, which is the generated registry
    first and the seed ``chip_library`` second — the AP2112K-3.3 has no
    generated module yet and is served by the latter (documented in
    ``src/ecad/circuits/blocks.py``).
    """
    from src.ecad.circuits import blocks as blocks_mod

    generated = 0
    for name, d in sheets.items():
        for comp in d.components:
            assert comp.lib_id, f"{name}: {comp.ref} has no lib_id"
            assert blocks_mod._registry_class(
                comp.lib_id, needed_by=f"{name}/{comp.ref}") is not None
            assert comp.footprint is not None, f"{name}: {comp.ref}"
            try:
                registry_get(comp.lib_id)
            except (KeyError, LookupError):
                assert "AP2112" in comp.lib_id, (
                    f"{name}: {comp.ref} ({comp.lib_id}) is not a generated "
                    f"part and is not the one documented exception")
            else:
                generated += 1
    assert generated, "nothing came from the generated registry at all"


# ---------------------------------------------------------------------------
# Gate 1 — definition lint, per sheet
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", SHEETS)
def test_definition_lint_clean(name, sheets):
    errors = ref.check_errors(name, sheets[name])
    assert errors == [], [str(e) for e in errors]


@pytest.mark.parametrize("name", SHEETS)
def test_the_only_waived_errors_are_the_declared_sheet_exits(name, sheets):
    """The waiver is not a blanket one: the set of errors it swallows must
    be exactly the cross-sheet nets the design declares, no more."""
    waived = {i.net for i in sheets[name].check()
              if i.is_error and i.code == "single-pin-net"}
    assert waived == set(ref.HIER_NETS[name]), name


def test_cross_sheet_signal_nets_appear_on_two_sheets(sheets):
    """A declared exit is only meaningful if something on another sheet
    carries the same net name — otherwise it is a dangling wire."""
    where: dict[str, set[str]] = {}
    for name, d in sheets.items():
        for net in d.nets:
            where.setdefault(net.name, set()).add(name)
    for name, nets in ref.HIER_NETS.items():
        for net in nets:
            assert len(where[net]) >= 2, (
                f"{net} declared as a {name} sheet exit but only appears on "
                f"{where[net]}")


def test_power_rails_are_shared_by_name_across_sheets(sheets):
    """+3V3 / GND / VBUS cross as global power symbols, so the *names* have
    to match exactly — a "+3.3V" on one sheet and "+3V3" on another is a
    silently disconnected board."""
    from src.ecad.layout.graph_build import is_power_net

    def carriers(rail: str) -> set[str]:
        return {n for n, d in sheets.items()
                if any(net.name == rail for net in d.nets)}

    assert carriers("GND") == set(SHEETS)          # every sheet
    assert carriers(ref.RAIL) == {"power", "mcu"}  # the LDO feeds the module
    assert carriers("VBUS") == {"usb", "power"}    # connector feeds the LDO
    # ...and all three must classify as rails, or the engine would try to
    # route them as signals and they would not cross sheets at all.
    assert all(is_power_net(r) for r in (ref.RAIL, "GND", "VBUS"))


# ---------------------------------------------------------------------------
# Gate 2 — geometry, per sheet
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", SHEETS)
def test_layout_and_file_lints_clean(name, sheets):
    _gates(name, sheets[name])


@pytest.mark.parametrize("name", SHEETS)
def test_every_sheet_exit_has_a_label_anchor(name, sheets):
    """A hierarchy stage promotes these anchors to hierarchical labels; a
    declared exit with no anchor would vanish from the emitted file."""
    from src.ecad.layout.engine import label_anchors

    placed = ref.layout_sheet(name, sheets[name])
    anchors = label_anchors(placed)
    for net in ref.HIER_NETS[name]:
        assert anchors.get(net), f"{name}: no label anchor for {net}"


# ---------------------------------------------------------------------------
# Gate 3+4 — kicad-cli: ERC and the netlist oracle, per sheet
# ---------------------------------------------------------------------------

@skip_no_kicad
@pytest.mark.parametrize("name", SHEETS)
def test_sheet_loads_and_erc_is_clean(name, sheets, tmp_path):
    """ERC on a lone sheet is a valid oracle for these three.

    It would not be for a sheet whose nets arrive through *hierarchical*
    labels — KiCad cannot see the other end and reports the driver as
    missing. Here nothing does: the rails cross as global power symbols
    (which ERC resolves within the sheet, with the engine's PWR_FLAG
    supplying the driver), and the two cross-sheet signals are ordinary
    local labels on a stub. So zero ERC errors is a real gate on all three
    sheets, not a sampled one.
    """
    from src.pipeline.validate import run_erc

    _placed, sheet = _gates(name, sheets[name])
    sch = tmp_path / f"{name}.kicad_sch"
    sch.write_text(sheet.text)
    erc = run_erc(sch)
    assert erc["success"], erc
    assert erc["errors"] == 0, erc["details"]


@skip_no_kicad
@pytest.mark.parametrize("name", SHEETS)
def test_exported_netlist_equals_intended_netlist(name, sheets, tmp_path):
    """The load-bearing oracle, run on EVERY sheet.

    A wiring defect — a signal pin dragged onto +3V3, a satellite cap that
    lost its junction — is invisible to lint and to ERC but changes the
    exported netlist. Gating one sheet and trusting the rest is how such a
    defect survives a green suite.
    """
    _placed, sheet = _gates(name, sheets[name])
    actual = _netlist_of(sheet.text, tmp_path)
    intended = sheets[name].intended_netlist()
    assert actual == intended, {
        "sheet": name,
        "differing": {k: {"intended": v, "actual": actual.get(k)}
                      for k, v in intended.items() if actual.get(k) != v},
        "extra": {k: v for k, v in actual.items() if k not in intended},
    }


# ---------------------------------------------------------------------------
# Design intent — what the geometry cannot see
# ---------------------------------------------------------------------------

def test_usb_pads_come_from_the_verified_part_model():
    """The pad numbers are read from the generated class, and the generated
    class agrees with the datasheet (DS v1.8 Table 3-1: IO19/pin 13 =
    USB_D-, IO20/pin 14 = USB_D+)."""
    pads = ref.usb_pads()
    mcu = registry_get(ref.MODULE)()
    assert pads == {"USB_D+": mcu.pin("USB_D+").pad,
                    "USB_D-": mcu.pin("USB_D-").pad}
    assert pads == {"USB_D+": "14", "USB_D-": "13"}


def test_usb_data_lands_on_the_pads_the_part_model_reports(sheets):
    """The design's USB nets touch exactly those module pads — never a
    remembered pad number."""
    mcu_sheet = sheets["mcu"]
    mcu = _module_of(mcu_sheet)
    pads = ref.usb_pads(mcu)
    netlist = mcu_sheet.intended_netlist()
    for name, local in (("USB_D+", "ESP_D+"), ("USB_D-", "ESP_D-")):
        assert f"{mcu.ref}:{pads[name]}" in netlist[local], (name, netlist[local])
        # ... and that local net continues, through one series part, to the
        # net that leaves the sheet.
        series = {p.split(":")[0] for p in netlist[local]} - {mcu.ref}
        assert len(series) == 1, series
        assert {p.split(":")[0] for p in netlist[name]} == series


def test_usb_connector_pairs_both_orientations(sheets):
    """A Type-C receptacle carries D+/D- twice; missing one makes the board
    work only with the cable one way up."""
    usb = sheets["usb"]
    j = next(c for c in usb.components if c.reference_prefix == "J")
    netlist = usb.intended_netlist()
    assert netlist["USB_D+"] == {f"{j.ref}:{p.pad}" for p in j.DP}
    assert netlist["USB_D-"] == {f"{j.ref}:{p.pad}" for p in j.DN}
    assert len(j.DP) == 2 and len(j.DN) == 2


def test_cc_pins_have_sink_pulldowns(sheets):
    """5.1 kOhm Rd on both CC pins, or a Type-C source never enables VBUS."""
    usb = sheets["usb"]
    j = next(c for c in usb.components if c.reference_prefix == "J")
    for pin in (j.CC1, j.CC2):
        assert pin.net is not None, pin.name
        others = [p.owner for p in pin.net.pins if p.owner is not j]
        assert len(others) == 1, (pin.name, others)
        res = others[0]
        assert res.reference_prefix == "R"
        assert res.value == "5.1k"
        other_pin = next(p for p in res.pins if p is not
                         next(q for q in res.pins if q.net is pin.net))
        assert other_pin.net.name == "GND"


def test_every_module_power_pin_sits_on_a_decoupled_rail(sheets):
    """Each power/ground pin of the module is on a named rail, and the
    positive rail carries both a per-pin ceramic and a bulk capacitor."""
    mcu_sheet = sheets["mcu"]
    mcu = _module_of(mcu_sheet)
    power_pins = [p for p in mcu.pins
                  if p.etype is ElectricalType.POWER_IN
                  or p.role in (PinRole.POWER, PinRole.GROUND)]
    assert power_pins
    for p in power_pins:
        assert p.net is not None, f"{mcu.ref}.{p.name} (pad {p.pad}) floats"

    rail_pins = [p for p in mcu.pins if p.role is PinRole.POWER]
    assert rail_pins, "the module model reports no positive supply pin"
    for p in rail_pins:
        assert p.net.name == ref.RAIL
        values = {c.value for c in _capacitors_on(mcu_sheet, p.net.name)}
        assert "100nF" in values, (p.name, values)          # HF ceramic
        assert any(v.endswith("uF") for v in values), (p.name, values)  # bulk

    for p in mcu.pins:
        if p.role is PinRole.GROUND:
            assert p.net.name == "GND", (p.pad, p.net.name)


def test_en_has_an_rc_to_ground(sheets):
    """EN gets a pull-up to the rail and a capacitor to GND — the power-on
    reset delay. Without the capacitor the chip can boot before the rail
    settles; without the resistor EN floats, which the guideline forbids."""
    mcu_sheet = sheets["mcu"]
    mcu = _module_of(mcu_sheet)
    en_net = mcu.EN.net
    assert en_net is not None, "EN must not be left floating"

    owners = [p.owner for p in en_net.pins if p.owner is not mcu]
    resistors = [c for c in owners if c.reference_prefix == "R"]
    caps = [c for c in owners if c.reference_prefix == "C"]
    assert resistors, "EN has no pull-up"
    assert caps, "EN has no capacitor"

    def other_net(comp, net):
        return next(p.net.name for p in comp.pins if p.net is not net)

    assert any(other_net(r, en_net) == ref.RAIL for r in resistors), \
        "no EN resistor reaches the rail"
    assert any(other_net(c, en_net) == "GND" for c in caps), \
        "no EN capacitor reaches ground"
    # ...and the RC is the cited 10k / 1uF.
    assert "10k" in {r.value for r in resistors}
    assert "1uF" in {c.value for c in caps}


def test_reset_and_boot_buttons_exist(sheets):
    """A RESET button on EN and a BOOT button that can pull GPIO0 low."""
    mcu_sheet = sheets["mcu"]
    mcu = _module_of(mcu_sheet)
    switches = [c for c in mcu_sheet.components
                if c.reference_prefix == "SW"]
    assert len(switches) == 2, [c.ref for c in switches]

    reached = set()
    for sw in switches:
        nets = {p.net.name for p in sw.pins if p.net is not None}
        assert "GND" in nets, (sw.ref, nets)
        reached |= nets
    assert "EN" in reached or "EN_SW" in reached
    assert "BOOT" in reached
    # BOOT is the net GPIO0 sits on.
    assert mcu.gpio(0).net is not None
    assert mcu.gpio(0).net.name == "BOOT"


@pytest.mark.parametrize("decision", ref.STRAPPING,
                         ids=lambda d: f"GPIO{d.gpio}")
def test_every_strapping_pin_is_decided(decision, sheets):
    """Defined level or explicit documented exception — never silence."""
    mcu_sheet = sheets["mcu"]
    mcu = _module_of(mcu_sheet)
    pin = mcu.gpio(decision.gpio)
    assert len(decision.rationale) > 80, "a waiver needs a real reason"

    if decision.waiver:
        assert decision.external is None
        assert "WAIVER" in decision.rationale
        # a waived pin relies on the internal pull, so nothing external
        # may be quietly holding it somewhere else
        assert pin.net is None or pin.net.name in (
            "BOOT",), (decision.gpio, pin.net)
    else:
        assert decision.external is not None
        assert pin.net is not None, f"GPIO{decision.gpio} has no net"
        pulls = [p.owner for p in pin.net.pins
                 if p.owner.reference_prefix == "R"]
        assert pulls, f"GPIO{decision.gpio} has no pull resistor"
        anchors = {p.net.name for r in pulls for p in r.pins
                   if p.net is not pin.net}
        assert decision.external in anchors, (decision.gpio, anchors)


def test_the_strapping_plan_covers_every_strapping_pin():
    """The four are GPIO0/3/45/46 (DS v1.8 Table 4-1). A fifth appearing in
    a future part model must not silently go undecided."""
    assert {d.gpio for d in ref.STRAPPING} == {0, 3, 45, 46}
    assert len({d.gpio for d in ref.STRAPPING}) == len(ref.STRAPPING)


def test_indicator_leds_have_computed_series_resistors(sheets):
    """Two LEDs, each behind a resistor sized by Ohm's law, never bare."""
    mcu_sheet = sheets["mcu"]
    leds = [c for c in mcu_sheet.components if c.reference_prefix == "D"]
    assert len(leds) == 2, [c.ref for c in leds]
    for led in leds:
        nets = {p.pad: p.net for p in led.pins}
        # Device:LED is pad 1 = K, pad 2 = A — the cathode goes to ground.
        assert nets["1"].name == "GND", (led.ref, nets["1"].name)
        series = [p.owner for p in nets["2"].pins if p.owner is not led]
        assert len(series) == 1 and series[0].reference_prefix == "R"
        assert series[0].value.endswith("R"), series[0].value


def test_ldo_converts_vbus_to_the_rail(sheets):
    """The power sheet actually regulates: VBUS in, +3V3 out, caps on both."""
    power = sheets["power"]
    reg = next(c for c in power.components
               if any(p.etype is ElectricalType.POWER_OUT for p in c.pins))
    assert ref.REGULATOR in (reg.part_name or "")
    out = [p for p in reg.pins if p.etype is ElectricalType.POWER_OUT]
    assert {p.net.name for p in out} == {ref.RAIL}
    # POWER_IN covers the ground pin too on this model, so filter by role.
    ins = [p for p in reg.pins if p.etype is ElectricalType.POWER_IN
           and p.role is not PinRole.GROUND]
    assert {p.net.name for p in ins} == {"VBUS"}
    assert {p.net.name for p in reg.pins if p.role is PinRole.GROUND} == {"GND"}
    assert _capacitors_on(power, "VBUS"), "no input capacitor"
    assert _capacitors_on(power, ref.RAIL), "no output capacitor"


# ---------------------------------------------------------------------------
# Provenance
# ---------------------------------------------------------------------------

def test_every_decision_carries_a_citation():
    assert ref.PROVENANCE
    for c in ref.PROVENANCE:
        assert c.sheet in SHEETS, c
        assert c.provenance.source, c.block
        assert c.provenance.section, c.block
        assert c.notes, c.block
        assert c.provenance.cite()


def test_every_sheet_contributes_provenance():
    covered = {c.sheet for c in ref.PROVENANCE}
    assert covered == set(SHEETS), covered


def test_unverified_claims_are_labelled_not_hidden():
    """Values that could not be traced to a document must say so. This is a
    gate on honesty: it fails if someone strips the caveats."""
    flagged = [c for c in ref.PROVENANCE if c.unverified]
    assert flagged, "not one caveat survives — that is not credible"
    for c in flagged:
        for note in c.unverified:
            assert len(note) > 60, (c.block, note)


def test_provenance_table_renders():
    table = ref.provenance_table()
    assert table.startswith("| Sheet | Block | Refs | Source |")
    assert table.count("\n") >= len(ref.PROVENANCE) + 1
    assert "documentation.espressif.com" in table


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", SHEETS)
def test_byte_determinism(name):
    """Build twice from scratch → byte-identical schematic text."""
    a = ref.sheets()[name]
    b = ref.sheets()[name]
    ta = emit(ref.layout_sheet(name, a), a, title=a.name).text
    tb = emit(ref.layout_sheet(name, b), b, title=b.name).text
    assert ta == tb


def test_refs_are_unique_within_each_sheet(sheets):
    for name, d in sheets.items():
        refs = [c.ref for c in d.components]
        assert all(refs), f"{name}: unassigned refs"
        assert len(refs) == len(set(refs)), f"{name}: {sorted(refs)}"
