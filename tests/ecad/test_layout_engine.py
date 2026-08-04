"""End-to-end layout-engine fixture gates.

Hard gates per fixture: definition lint clean → geometric lints clean →
kicad-cli loads → ERC errors == 0 → netlist equivalence vs the Design's
intended netlist. Soft metrics asserted with fixture-specific ceilings.
"""

import shutil
from pathlib import Path

import pytest

from src.ecad import Component, Design, FootprintRef, pin
from src.ecad.layout.engine import emit, label_anchors, layout
from src.ecad.layout.ir import PIN_PITCH
from src.ecad.layout.lints import lint_placed, lint_schematic_text
from tests.ecad.test_model import Cap, LDO, TinyMCU

KICAD_CLI = shutil.which("kicad-cli") or "/usr/bin/kicad-cli"
skip_no_kicad = pytest.mark.skipif(
    not Path(KICAD_CLI).is_file(), reason="kicad-cli not available"
)


class GPS(Component):
    part_name = "GPSMOD"
    lib_id = "RF_GPS:GPSMOD"
    footprint = FootprintRef("RF_GPS", "ublox_NEO-6M")
    _PIN_SPECS = (
        pin("1", "VCC", "power_in", "power"),
        pin("2", "GND", "power_in", "ground"),
        pin("3", "TX", "output", "comm"),
        pin("4", "RX", "input", "comm"),
    )


def _ldo_stage() -> Design:
    d = Design("ldo-stage")
    u, cin, cout = d.add(LDO(), Cap(), Cap())
    d.net("VIN").connect(u.VIN, cin.P1, u.EN)
    d.net("3V3").connect(u.VOUT, cout.P1)
    d.net("GND").connect(u.pin("2"), cin.P2, cout.P2)
    return d


def _mcu_gps() -> Design:
    d = Design("mcu-gps")
    mcu, gps, c1 = d.add(TinyMCU(), GPS(), Cap())
    d.net("3V3").connect(mcu.VDD, gps.VCC, c1.P1)
    d.net("GND").connect(mcu.pin("8"), gps.pin("2"), c1.P2)
    d.net("GPS_TX").connect(gps.TX, mcu.gpio(0))
    d.net("GPS_RX").connect(gps.RX, mcu.TX)
    return d


def _gates(design: Design):
    placed = layout(design)
    geo = lint_placed(placed)
    assert geo == [], geo
    sheet = emit(placed, design)
    # emit() generates power-tap, satellite-row and PWR_FLAG wires that never
    # reach the IR — re-run the geometric gate over the FULL wire set.
    geo = lint_placed(placed, sheet)
    assert geo == [], geo
    file_lints = lint_schematic_text(sheet.text)
    assert file_lints == [], file_lints
    return placed, sheet


def _netlist_of(text: str, tmp: Path) -> dict[str, set[str]]:
    from src.pipeline.roundtrip import _export_netlist, parse_kicad_netlist_xml

    sch = tmp / "sheet.kicad_sch"
    sch.write_text(text)
    xml = _export_netlist(sch, tmp)
    assert xml is not None, "netlist export failed"
    parsed = parse_kicad_netlist_xml(xml)
    out: dict[str, set[str]] = {}
    for net in parsed["nets"]:
        name = net["name"].lstrip("/")
        if name.startswith("unconnected-"):
            continue  # KiCad pseudo-nets for no_connect pins
        pins = {f"{n['ref']}:{n['pin']}" for n in net["nodes"]
                if not n["ref"].startswith("#")}
        if pins:
            out[name] = pins
    return out


def test_ldo_stage_layout_metrics():
    placed, sheet = _gates(_ldo_stage())
    m = sheet.metrics
    assert m.crossings == 0
    assert m.alignment == 1.0 or m.routed_nets == 0
    # caps are satellites: not in the routed graph
    assert not any(n.startswith("C") for n in placed.graph.nodes)


def test_mcu_gps_layout_metrics():
    placed, sheet = _gates(_mcu_gps())
    m = sheet.metrics
    # The TX/RX crossover is intrinsic: it resolves as either one wire
    # crossing or one label fallback (backward edge after FAS), never both.
    assert m.crossings + m.labeled_nets <= 1
    assert m.bends <= 12


def test_determinism_byte_identical():
    d1, d2 = _mcu_gps(), _mcu_gps()
    a = emit(layout(d1), d1).text
    b = emit(layout(d2), d2).text
    assert a == b


@skip_no_kicad
def test_ldo_stage_erc_and_netlist(tmp_path):
    from src.pipeline.validate import run_erc

    design = _ldo_stage()
    placed, sheet = _gates(design)
    sch = tmp_path / "ldo.kicad_sch"
    sch.write_text(sheet.text)
    erc = run_erc(sch)
    assert erc["success"], erc
    assert erc["errors"] == 0, erc

    actual = _netlist_of(sheet.text, tmp_path)
    intended = design.intended_netlist()
    assert actual == intended, {
        "missing": {k: v for k, v in intended.items() if actual.get(k) != v},
        "actual": actual,
    }


@skip_no_kicad
def test_mcu_gps_erc_and_netlist(tmp_path):
    from src.pipeline.validate import run_erc

    design = _mcu_gps()
    placed, sheet = _gates(design)
    sch = tmp_path / "gps.kicad_sch"
    sch.write_text(sheet.text)
    erc = run_erc(sch)
    assert erc["success"], erc
    assert erc["errors"] == 0, erc
    assert _netlist_of(sheet.text, tmp_path) == design.intended_netlist()


class Res(Component):
    part_name = "R"
    lib_id = "Device:R"
    reference_prefix = "R"
    footprint = FootprintRef("Resistor_SMD", "R_0402_1005Metric")
    _PIN_SPECS = (
        pin("1", "P1", "passive", "passive"),
        pin("2", "P2", "passive", "passive"),
    )


class Header1(Component):
    part_name = "CONN_1X01"
    lib_id = "Connector_Generic:Conn_01x01"
    reference_prefix = "J"
    footprint = FootprintRef("Connector_PinHeader_2.54mm",
                             "PinHeader_1x01_P2.54mm_Vertical")
    _PIN_SPECS = (pin("1", "P1", "passive", "passive"),)


def test_satellite_caps_keep_footprint():
    """Regression: satellites were emitted with an empty Footprint property,
    so Update-PCB-from-Schematic saw every decoupling cap as unassigned."""
    design = _ldo_stage()
    sheet = emit(layout(design), design)
    assert sheet.text.count(
        '(property "Footprint" "Capacitor_SMD:C_0402_1005Metric"') == 2


def test_single_rank_design_routes_via_labels():
    """Regression: a one-rank graph has no wiring channel (channel_x == [])
    and route() crashed with IndexError instead of falling back to labels."""
    d = Design("two-headers")
    j1, j2 = d.add(Header1(), Header1())
    d.net("SIG").connect(j1.P1, j2.P1)
    placed, _sheet = _gates(d)
    assert "SIG" in placed.routing.labeled_nets


def test_no_ic_design_keeps_caps_placed():
    """Regression: with zero IC units _find_owner self-owned a node that was
    then deleted from the graph, and place.coordinates KeyError'd on it."""
    d = Design("caps-only")
    c1, c2 = d.add(Cap(), Cap())
    d.net("3V3").connect(c1.P1, c2.P1)
    d.net("GND").connect(c1.P2, c2.P2)
    placed, _sheet = _gates(d)
    assert not placed.graph.satellites
    assert set(placed.graph.nodes) == {"C1#1", "C2#1"}


def _series_cap_design() -> Design:
    """MCU with a coupling cap in a signal path plus a decoupling cap —
    both are Device:C but only the latter is a satellite."""
    d = Design("mixed-caps")
    mcu, cs, cd = d.add(TinyMCU(), Cap(), Cap())
    d.net("A").connect(mcu.gpio(0), cs.P1)
    d.net("B").connect(mcu.gpio(1), cs.P2)
    d.net("3V3").connect(mcu.VDD, cd.P1)
    d.net("GND").connect(mcu.pin("8"), cd.P2)
    return d


def test_signal_path_passive_uses_router_geometry():
    """Regression: placed R/C/L emitted the vertical Device stub (pins at
    (0, ±3.81)) while the router wired the readable LEFT/RIGHT ports —
    every wire missed its pin by ~10 mm."""
    d = Design("series-r")
    mcu, r = d.add(TinyMCU(), Res())
    d.net("A").connect(mcu.gpio(0), r.P1)
    d.net("B").connect(mcu.gpio(1), r.P2)
    placed, sheet = _gates(d)
    assert "R1#1" in placed.graph.nodes
    assert '(symbol "Device:R"' in sheet.text
    # no satellites in this design → no vertical stub pins anywhere
    assert "(at 0 3.81 270)" not in sheet.text


def test_placed_and_satellite_same_lib_id_split():
    """A signal-path cap and a satellite cap share Device:C: the satellite
    stub (vertical pins, row wiring depends on them) must be emitted under
    an alias instead of silently reusing the readable symbol."""
    placed, sheet = _gates(_series_cap_design())
    assert "C1#1" in placed.graph.nodes            # signal cap stays placed
    assert '(symbol "Device:C"' in sheet.text      # readable geometry
    assert '(symbol "Device:C_dec"' in sheet.text  # satellite stub alias
    assert '(lib_id "Device:C_dec")' in sheet.text


@skip_no_kicad
def test_signal_passive_erc_and_netlist(tmp_path):
    from src.pipeline.validate import run_erc

    design = _series_cap_design()
    _placed, sheet = _gates(design)
    sch = tmp_path / "mixed.kicad_sch"
    sch.write_text(sheet.text)
    erc = run_erc(sch)
    assert erc["success"], erc
    assert erc["errors"] == 0, erc
    assert _netlist_of(sheet.text, tmp_path) == design.intended_netlist()


def _sheet_exit_design() -> Design:
    """An MCU whose TX leaves the sheet: a net with exactly one pin on it."""
    d = Design("sheet-exit")
    mcu, gps, c1 = d.add(TinyMCU(), GPS(), Cap())
    d.net("3V3").connect(mcu.VDD, gps.VCC, c1.P1)
    d.net("GND").connect(mcu.pin("8"), gps.pin("2"), c1.P2)
    d.net("GPS_TX").connect(gps.TX, mcu.gpio(0))
    d.net("UART_OUT").connect(mcu.TX)          # leaves the sheet
    return d


def test_single_port_net_is_labeled_not_dropped():
    """Regression: a net with one port on the sheet skipped both routing
    branches (route() only routes >= 2 ports) and vanished from the file."""
    design = _sheet_exit_design()
    placed, sheet = _gates(design)
    assert "UART_OUT" in placed.routing.labeled_nets
    assert "UART_OUT" in placed.routing.wires        # got its stub
    assert '(label "UART_OUT"' in sheet.text


def test_hier_labels_replace_local_labels_at_anchors():
    """emit(hier_labels=...) emits the caller's lines and drops its own."""
    design = _sheet_exit_design()
    placed = layout(design)
    anchors = label_anchors(placed)
    assert len(anchors["UART_OUT"]) == 1
    x, y, angle = anchors["UART_OUT"][0]

    line = f'\t(hierarchical_label "UART_OUT" (at {x} {y} {angle}))'
    sheet = emit(placed, design, hier_labels={"UART_OUT": line})
    assert line in sheet.text
    assert '(label "UART_OUT"' not in sheet.text   # suppressed, not duplicated
    assert '(label "GPS_TX"' in sheet.text or "GPS_TX" in sheet.text


def test_flag_rails_restricts_pwr_flag():
    """Only the named rails may carry a PWR_FLAG (one per rail per project:
    power symbols are global, two flags on a net is a driver conflict)."""
    design = _mcu_gps()
    placed = layout(design)
    everything = emit(placed, design).text
    assert everything.count('(lib_id "power:PWR_FLAG")') == 2   # 3V3 + GND

    only_gnd = emit(placed, design, flag_rails=["GND"]).text
    assert only_gnd.count('(lib_id "power:PWR_FLAG")') == 1
    none = emit(placed, design, flag_rails=[]).text
    assert "PWR_FLAG" not in none


def _three_cap_rail() -> Design:
    """One IC decoupled by three caps on the same rail → one satellite row."""
    d = Design("three-caps")
    mcu, c1, c2, c3 = d.add(TinyMCU(), Cap(), Cap(), Cap())
    d.net("3V3").connect(mcu.VDD, c1.P1, c2.P1, c3.P1)
    d.net("GND").connect(mcu.pin("8"), c1.P2, c2.P2, c3.P2)
    d.net("SIG").connect(mcu.gpio(0), mcu.gpio(1))
    return d


def test_satellite_row_junctions_middle_caps():
    """Regression: the middle cap of a 3-cap rail row ended its wire on the
    MIDDLE of the rail wire; without a junction dot KiCad leaves it floating
    (the net lost that pin and ERC reported a not-connected pin)."""
    design = _three_cap_rail()
    _placed, sheet = _gates(design)
    assert sheet.text.count("(junction") >= 1


@skip_no_kicad
def test_satellite_row_netlist_keeps_every_cap(tmp_path):
    from src.pipeline.validate import run_erc

    design = _three_cap_rail()
    _placed, sheet = _gates(design)
    sch = tmp_path / "caps.kicad_sch"
    sch.write_text(sheet.text)
    erc = run_erc(sch)
    assert erc["success"], erc
    assert erc["errors"] == 0, erc
    assert _netlist_of(sheet.text, tmp_path) == design.intended_netlist()


def test_unknown_passive_lib_id_gets_stub():
    """Regression: every placed lib_id must have a lib_symbols definition
    (the get_stub(...) or "" bug emitted empty entries for non-R/C/L)."""
    class OddCap(Cap):
        lib_id = "Device:C_Polarized"

    d = Design("odd")
    u, c = d.add(LDO(), OddCap())
    d.net("VIN").connect(u.VIN, c.P1, u.EN)
    d.net("GND").connect(u.pin("2"), c.P2)
    sheet = emit(layout(d), d)
    assert '(symbol "Device:C_Polarized"' in sheet.text


def _power_symbol_points(text: str) -> dict[tuple[str, str], str]:
    """(x, y) → rail, for every power symbol instance in the emitted file."""
    import re

    out: dict[tuple[str, str], str] = {}
    pattern = r'\(lib_id "power:([^"]+)"\)\s*\n\s*\(at ([-\d.]+) ([-\d.]+)'
    for m in re.finditer(pattern, text):
        out.setdefault((m.group(2), m.group(3)), m.group(1))
    return out


def test_power_taps_never_share_a_point_with_another_rail():
    """Regression: two power symbols on one point silently MERGE their nets.

    A USB-C receptacle stacks GND, SHIELD and four VBUS pads on one side.
    The tap renderer offsets grounds down and rails up by a single pitch, so
    the shield's GND symbol landed exactly where the VBUS symbol of the pad
    two rows below had already gone — and kicad-cli exported VBUS and GND as
    ONE net. Every geometric lint stayed clean: lint_placed never sees these
    wires, because emit() builds them.
    """
    from src.ecad.circuits import pull_resistor
    from src.ecad.library import get as registry_get

    d = Design("usb-c-taps")
    j = registry_get("USB_C_Receptacle_USB2.0_16P")()
    d.add(j)
    d.net("VBUS").connect(j.VBUS)
    d.net("GND").connect(j.GND, j.SHIELD)
    pull_resistor(d, j.CC1, "GND", value="5.1k", net_name="CC1")
    pull_resistor(d, j.CC2, "GND", value="5.1k", net_name="CC2")

    text = emit(layout(d), d).text
    points = _power_symbol_points(text)
    rails = [rail for rail in points.values()]
    assert "VBUS" in rails and "GND" in rails
    # one point, one rail — the dict above collapses duplicates, so compare
    # counts against the raw instance count for the two real rails
    for rail in ("VBUS", "GND"):
        instances = text.count(f'(lib_id "power:{rail}")')
        placed_here = sum(1 for v in points.values() if v == rail)
        assert placed_here == instances, (
            f"{rail}: {instances} symbols emitted but only {placed_here} "
            f"distinct positions — two share a point and their nets merge")
# ── regressions from the adversarial review ─────────────────────────────────


def _three_cap_rail() -> Design:
    """One rail decoupled by three caps — the middle one T-s into the span."""
    d = Design("three-cap-rail")
    u, c1, c2, c3 = d.add(TinyMCU(), Cap(), Cap(), Cap())
    d.net("3V3").connect(u.VDD, c1.P1, c2.P1, c3.P1)
    d.net("GND").connect(u.GND, c1.P2, c2.P2, c3.P2)
    return d


def test_satellite_rail_emits_a_junction_per_cap():
    """Middle caps land mid-segment on the shared rail wire.

    KiCad does not connect a wire endpoint that lands mid-segment without a
    junction dot, so without these the middle cap of a row is electrically
    floating — the exported netlist dropped C2 entirely and ERC reported
    pin_not_connected.
    """
    d = _three_cap_rail()
    pl = layout(d)
    text = emit(pl, d, "three_cap_rail").text

    caps = [c for c in d.components if isinstance(c, Cap)]
    assert len(caps) == 3

    # Every cap stub meeting the rail needs a junction; with 3 caps sharing a
    # rail there must be at least one junction per cap on that row.
    junction_count = text.count("(junction")
    assert junction_count >= len(caps), (
        f"expected >= {len(caps)} junctions for a 3-cap rail, got {junction_count}"
    )


@skip_no_kicad
def test_three_cap_rail_netlist_keeps_every_cap(tmp_path):
    """The real gate: kicad-cli must see all three caps on the rail."""
    d = _three_cap_rail()
    pl = layout(d)
    text = emit(pl, d, "three_cap_rail").text
    p = tmp_path / "three_cap_rail.kicad_sch"
    p.write_text(text)

    from src.pipeline.roundtrip import _export_netlist, parse_kicad_netlist_xml

    xml = _export_netlist(p, tmp_path)
    assert xml is not None, "netlist export failed"
    nets = {}
    for net in parse_kicad_netlist_xml(xml)["nets"]:
        name = net["name"].lstrip("/").split("/")[-1]
        if "unconnected-" in net["name"]:
            continue
        nets.setdefault(name, set()).update(
            f"{n['ref']}:{n['pin']}" for n in net["nodes"]
            if not n["ref"].startswith("#"))
    rail = nets.get("3V3", set())
    cap_pins = {p for p in rail if p.startswith("C")}
    assert len(cap_pins) == 3, f"all three caps must be on 3V3, got {sorted(rail)}"


class ShuntRes(Component):
    """Same lib_id as a plain resistor but much wider readable geometry."""
    part_name = "R_shunt"
    lib_id = "Device:R"
    reference_prefix = "R"
    footprint = FootprintRef("Resistor_SMD", "R_0805_2012Metric")
    _PIN_SPECS = (
        pin("1", "SENSE_HIGH", "passive", "passive"),
        pin("2", "SENSE_LOW_X", "passive", "passive"),
    )


class PlainRes(Component):
    part_name = "R"
    lib_id = "Device:R"
    reference_prefix = "R"
    footprint = FootprintRef("Resistor_SMD", "R_0402_1005Metric")
    _PIN_SPECS = (
        pin("1", "P1", "passive", "passive"),
        pin("2", "P2", "passive", "passive"),
    )


def test_same_lib_id_different_geometry_gets_its_own_symbol():
    """Two components sharing a lib_id may need different symbol geometry.

    Readable width depends on pin-name lengths, so deduping lib_symbols on
    lib_id alone drew the second component with the first's geometry while
    the router had wired to its own — putting its pins millimetres from
    every wire and silently dropping both of its connections.
    """
    d = Design("shared-lib-id")
    u, r1, r2 = d.add(TinyMCU(), PlainRes(), ShuntRes())
    d.net("A").connect(u.TX, r1.P1)
    d.net("B").connect(r1.P2, r2.SENSE_HIGH)
    d.net("C").connect(r2.SENSE_LOW_X, u.IO0)

    text = emit(layout(d), d, "shared_lib_id").text

    import re

    # Map each placed instance's ref -> the lib_id it references.
    ref_to_lib = {}
    for block in text.split("(symbol\n")[1:]:
        lib = re.search(r'\(lib_id "([^"]+)"\)', block)
        ref = re.search(r'\(property "Reference" "([^"]+)"', block)
        if lib and ref:
            ref_to_lib[ref.group(1)] = lib.group(1)
    assert {"R1", "R2"} <= set(ref_to_lib), f"missing instances: {ref_to_lib}"

    # Slice out the lib_symbols entry R2 points at. Child symbols carry the
    # pins and are named by BARE part name ("R_R2_1_1"), while top-level
    # entries are library-qualified ("Device:R_R2") — so the next name
    # containing a colon starts the following entry.
    lib = ref_to_lib["R2"]
    start = text.find(f'(symbol "{lib}"\n')
    assert start >= 0, f"no lib_symbols entry named {lib!r}"
    end = len(text)
    for m in re.finditer(r'\(symbol "([^"]+)"\n', text[start + 1:]):
        if ":" in m.group(1):
            end = start + 1 + m.start()
            break
    shunt_entry = text[start:end]

    # Before the fix R2 pointed at the plain resistor's entry, so its pins sat
    # millimetres from every wire and both connections were lost.
    assert "SENSE_HIGH" in shunt_entry, (
        f"R2 references {lib!r}, whose symbol does not define R2's own pins "
        f"— its geometry is another component's"
    )


def test_rails_in_one_satellite_row_get_distinct_tracks():
    """A row may decouple several rails; each needs its own horizontal track.

    rail_y was derived from tops[0], and every cap in a row shares the same
    cy, so every rail landed on the SAME y. Two rails' horizontal spans then
    overlapped in x and KiCad merged them into one net — shorting the rails
    whenever their caps interleaved.
    """
    import re

    d = Design("two-rail-row")
    u, a1, a2, b1 = d.add(LDO(), Cap(), Cap(), Cap())
    d.net("VIN").connect(u.VIN, a1.P1, a2.P1, u.EN)
    d.net("3V3").connect(u.VOUT, b1.P1)
    d.net("GND").connect(u.pin("2"), a1.P2, a2.P2, b1.P2)

    pl = layout(d)
    # both rails must actually share one satellite row for this to be a test
    rails = {s.rail for sats in pl.graph.satellites.values() for s in sats}
    assert {"VIN", "3V3"} <= rails, f"fixture lost its two rails: {rails}"

    # Rail tracks sit just ABOVE the cap row; the component's own power taps
    # live elsewhere, so restrict to that band or the assertion picks them up.
    row_cy = next(iter(pl.placement.sat_rows.values()))[0][2]
    lo, hi = row_cy - 4 * 2.54, row_cy

    text = emit(pl, d, "two_rail_row").text
    ys: dict[str, set[float]] = {}
    for m in re.finditer(r'\(lib_id "power:([^"]+)"\)\s*\n\s*\(at ([-\d.]+) ([-\d.]+)',
                         text):
        y = float(m.group(3))
        if lo <= y < hi:
            ys.setdefault(m.group(1), set()).add(y)

    assert ys.get("VIN") and ys.get("3V3"), f"no rail tracks found in band: {ys}"
    shared = ys["VIN"] & ys["3V3"]
    assert not shared, (
        f"VIN and 3V3 share horizontal track(s) at y={sorted(shared)} — their "
        f"spans can overlap and merge the two rails into one net"
    )


def test_multi_rail_row_stays_inside_the_reserved_band():
    """place must reserve the row as emit actually draws it.

    The two guards against the interleaved-rail short compose: caps are kept
    contiguous per rail AND each rail gets its own track a pin pitch higher.
    The clearance scan therefore has to grow with the rail count — a fixed
    band only ever matched a single-rail row, and the second rail's track ran
    a pitch above it, back through the pins of whatever place let sit there.
    """
    from src.ecad.layout.place import sat_band_up

    d = Design("two-rail-row")
    u, a1, a2, b1 = d.add(LDO(), Cap(), Cap(), Cap())
    d.net("VIN").connect(u.VIN, a1.P1, a2.P1, u.EN)
    d.net("3V3").connect(u.VOUT, b1.P1)
    d.net("GND").connect(u.pin("2"), a1.P2, a2.P2, b1.P2)

    pl = layout(d)
    sheet = emit(pl, d, "two_rail_row")
    for owner, row in pl.placement.sat_rows.items():
        if not row:
            continue
        rails = {s.rail for s in pl.graph.satellites[owner] if s.rail}
        assert len(rails) >= 2, f"fixture lost its two rails: {rails}"
        cy = row[0][2]
        xs = [x for _ref, x, _y in row]
        lo_x, hi_x = min(xs) - PIN_PITCH, max(xs) + PIN_PITCH
        # window around the row, wide enough to still catch a track drawn
        # outside the reserved band (the owner's own taps sit far above it)
        lo_y, hi_y = cy - 6 * PIN_PITCH, cy + 6 * PIN_PITCH
        top = cy - sat_band_up(len(rails))
        for rail in sorted(rails):
            for w in sheet.wires.get(rail, []):
                if not (lo_x <= w.x1 <= hi_x and lo_x <= w.x2 <= hi_x):
                    continue        # a tap stub elsewhere on the sheet
                if not (lo_y <= w.y1 <= hi_y and lo_y <= w.y2 <= hi_y):
                    continue
                assert min(w.y1, w.y2) >= top, (
                    f"{rail} wire ({w.x1},{w.y1})->({w.x2},{w.y2}) rises above "
                    f"the band place reserved for the row (top {top})"
                )


class DualRailMCU(Component):
    part_name = "DUAL1"
    lib_id = "MCU_Test:DUAL1"
    footprint = FootprintRef("Package_DFN_QFN", "QFN-8")
    _PIN_SPECS = (
        pin("1", "VDD", "power_in", "power"),
        pin("2", "VDDA", "power_in", "power"),
        pin("8", "GND", "power_in", "ground"),
        pin("3", "TX", "output", "comm"),
        pin("4", "IO0", "bidirectional", "gpio", gpio=0),
    )


def _mixed_rail_row() -> Design:
    """One satellite row decoupling two rails, caps interleaved in the
    design (C2 on +1V8 sits between C1 and C3 on +3V3)."""
    d = Design("mixed-rail-row")
    mcu, c1, c2, c3 = d.add(DualRailMCU(), Cap(), Cap(), Cap())
    d.net("+3V3").connect(mcu.VDD, c1.P1, c3.P1)
    d.net("+1V8").connect(mcu.VDDA, c2.P1)
    d.net("GND").connect(mcu.pin("8"), c1.P2, c2.P2, c3.P2)
    return d


def _swapped_cap() -> Design:
    d = Design("swapped-cap")
    mcu, c1 = d.add(TinyMCU(), Cap())
    d.net("3V3").connect(mcu.VDD, c1.P2)
    d.net("GND").connect(mcu.pin("8"), c1.P1)
    return d


@skip_no_kicad
@pytest.mark.parametrize(
    "factory", [_mixed_rail_row, _three_cap_rail, _swapped_cap],
    ids=["mixed-rails", "three-caps", "swapped-pads"])
def test_satellite_rows_erc_and_netlist(factory, tmp_path):
    """Satellite rows must survive the electrical gates: middle caps
    connected, rails never merged, cap pads as the design wired them."""
    from src.pipeline.validate import run_erc

    design = factory()
    _placed, sheet = _gates(design)
    sch = tmp_path / "sat.kicad_sch"
    sch.write_text(sheet.text)
    erc = run_erc(sch)
    assert erc["success"], erc
    assert erc["errors"] == 0, erc["details"]
    assert _netlist_of(sheet.text, tmp_path) == design.intended_netlist()


class SingleUnitMCU(Component):
    part_name = "TINY2"
    lib_id = "MCU_Test:TINY2"
    footprint = FootprintRef("Package_DFN_QFN", "QFN-8")
    _PIN_SPECS = (
        pin("1", "VDD", "power_in", "power"),
        pin("2", "GND", "power_in", "ground"),
        pin("3", "TX", "output", "comm"),
        pin("4", "RX", "input", "comm"),
    )


def _shared_lib_id_design() -> Design:
    d = Design("shared-lib-id")
    mcu, r1, r2 = d.add(SingleUnitMCU(), Res(), ShuntRes())
    d.net("3V3").connect(mcu.VDD)
    d.net("GND").connect(mcu.pin("2"))
    d.net("A").connect(mcu.TX, r1.P1)
    d.net("B").connect(r1.P2, r2.SENSE_HIGH)
    d.net("C").connect(r2.SENSE_LOW_X, mcu.RX)
    return d


def test_shared_lib_id_gets_one_entry_per_geometry():
    """Two components declaring the same lib_id with different pin names
    have different readable widths: one lib_symbols entry would draw the
    second's pins where the first's are."""
    design = _shared_lib_id_design()
    sheet = emit(layout(design), design)
    assert sheet.text.count('(symbol "Device:R"\n') == 1
    assert sheet.text.count('(symbol "Device:R_2"\n') == 1
    # and the two instances reference different entries
    assert '(lib_id "Device:R")' in sheet.text
    assert '(lib_id "Device:R_2")' in sheet.text


@skip_no_kicad
def test_shared_lib_id_netlist(tmp_path):
    design = _shared_lib_id_design()
    _placed, sheet = _gates(design)
    assert _netlist_of(sheet.text, tmp_path) == design.intended_netlist()
