"""Draughting gates: the drawing must be readable, not merely correct.

Electrical correctness is already gated elsewhere (ERC 0, netlist ==
intended, geometric lints). These are the gates that stop the output
regressing to something no engineer would sign: art that is really the
part's art, page sizes chosen from the content, and text that does not sit
on other text.
"""

import re
import warnings

import pytest

from src.ecad import Design
from src.ecad.ingest.kicad_official import load_official_symbol
from src.ecad.layout.engine import PageOverflow, emit, layout
from src.ecad.layout.page import MARGIN, PAGE_SIZES, TITLE_BLOCK, fit_page
from src.ecad import library as registry
from src.ecad.symbol import SymbolModel
from tests.ecad.test_layout_engine import _ldo_stage, _mcu_gps

pytestmark = pytest.mark.filterwarnings("ignore::UserWarning")

# Parts ingested from official KiCad symbols: their drawing must survive.
ART_PARTS = ("Resistor", "Capacitor", "LED", "SW_Push",
             "USB_C_Receptacle_USB2.0_16P")
#: Draw commands that prove a symbol is more than a featureless box.
_SHAPE_RE = re.compile(r"\((polyline|arc|circle|rectangle|bezier|text)\b")


def _part(name: str):
    cls = registry.get(name)
    assert cls is not None, f"{name} is not in the generated registry"
    return cls()


# ── defect 1: real symbol art ───────────────────────────────────────────────


@pytest.mark.parametrize("name", ART_PARTS)
def test_generated_part_keeps_its_source_artwork(name):
    """The emitted symbol carries the SOURCE symbol's draw commands.

    Before this, every generated part emitted one synthesized body
    rectangle, so a Device:R rendered as an unlabelled box with P1/P2 pin
    stubs. The test is not "has some graphics" — it is "has the graphics the
    official symbol has", counted, so dropping half of a multi-part drawing
    still fails.
    """
    comp = _part(name)
    art = comp.symbol_art
    assert art is not None and art.children, f"{name} carries no source art"
    source = load_official_symbol(comp.lib_id)
    assert source is not None, f"{comp.lib_id} is not installed"
    expected = sum(len(items) for _s, items in source.art.children)
    assert sum(len(items) for _s, items in art.children) == expected

    text = SymbolModel.from_component(comp, style="readable").kicad_sym_text()
    assert len(_SHAPE_RE.findall(text)) >= expected


@pytest.mark.parametrize("name", ("Resistor", "Capacitor"))
def test_unnamed_source_pins_are_not_drawn_with_invented_names(name):
    """KiCad draws Device:R and Device:C pins unnamed; so must we.

    ``P1``/``P2`` are labels this pipeline synthesized so code can address
    the pads. Drawing them put a "P1" and a "P2" next to every resistor.
    """
    comp = _part(name)
    text = SymbolModel.from_component(comp, style="readable").kicad_sym_text()
    assert '(name "P1"' not in text and '(name "P2"' not in text
    assert '(name "~"' in text
    assert "(pin_numbers (hide yes))" in text, "KiCad hides these pin numbers"


def test_signal_path_passive_uses_the_source_pin_coordinates():
    """Preserved art fixes the pins; the layout engine must follow it.

    A laid-flat Device:R is the source drawing turned a quarter turn, so its
    pins sit at (-3.81, 0) and (3.81, 0) — the exact rotation of KiCad's own
    (0, +-3.81). Any other coordinate means the engine is wiring to a guess.
    """
    model = SymbolModel.from_component(_part("Resistor"), style="readable")
    pins = {p.pad: (p.x, p.y, p.angle) for p in model.units[0].pins}
    assert pins == {"1": (-3.81, 0.0, 0), "2": (3.81, 0.0, 180)}
    # ...and the node ports the engine consumes agree with them.
    ports = {pad: off for pad, _n, _e, _s, _i, off in model.node_ports(1)}
    x0, _y0, _x1, y1 = model.units[0].extent()
    assert ports["1"] == (round(-3.81 - x0, 4), round(y1, 4))


def test_upright_variant_keeps_the_decoupling_cap_geometry():
    """A satellite cap must stay vertical AND keep its plates.

    The two requirements pull against each other: the signal-path variant is
    laid flat, so a sheet with both used to give the row a two-pin symbol
    with no body at all.
    """
    upright = SymbolModel.from_component(_part("Capacitor"), style="readable",
                                         lay_flat=False)
    pins = sorted((p.x, p.y) for p in upright.units[0].pins)
    assert pins == [(0.0, -3.81), (0.0, 3.81)]
    entry = upright.to_inline_sexp_multi("Device:C_dec")
    assert entry.count("(polyline") == 2, "the cap lost its plates"


# ── defect 2: text placement ────────────────────────────────────────────────


_TEXT_RE = re.compile(
    r'\(property "(?:Reference|Value)" "([^"]*)"\n\t\t\t'
    r"\(at ([-\d.]+) ([-\d.]+) \d+\)\n\t\t\t\(effects([^\n]*)\)")


def _drawn_fields(text: str) -> list[tuple[str, float, float, str]]:
    out = []
    for value, x, y, effects in _TEXT_RE.findall(text):
        if "hide yes" in effects or not value:
            continue
        out.append((value, float(x), float(y),
                    "left" if "justify left" in effects else ""))
    return out


def _boxes(fields, char_w: float = 1.4, half_h: float = 0.85):
    for value, x, y, just in fields:
        w = len(value) * char_w
        x0 = x if just == "left" else x - w / 2
        yield value, (x0, y - half_h, x0 + w, y + half_h)


@pytest.mark.parametrize("design_of", (_ldo_stage, _mcu_gps),
                         ids=("ldo", "mcu-gps"))
def test_no_two_drawn_fields_share_an_anchor(design_of):
    """Two text items at one point is a placement bug, not a near miss."""
    design = design_of()
    fields = _drawn_fields(emit(layout(design), design).text)
    anchors = [(x, y) for _v, x, y, _j in fields]
    assert len(anchors) == len(set(anchors)), sorted(
        a for a in anchors if anchors.count(a) > 1)


@pytest.mark.parametrize("design_of", (_ldo_stage, _mcu_gps),
                         ids=("ldo", "mcu-gps"))
def test_no_two_drawn_fields_overlap(design_of):
    """References, values and power-symbol names must not cross each other.

    Every one of these is placed by the engine, so every one of them is
    movable — unlike a net label, which is pinned to a wire end.
    """
    design = design_of()
    boxes = list(_boxes(_drawn_fields(emit(layout(design), design).text)))
    clashes = [
        (a, b)
        for i, (a, ba) in enumerate(boxes)
        for b, bb in boxes[i + 1:]
        if ba[0] < bb[2] and bb[0] < ba[2] and ba[1] < bb[3] and bb[1] < ba[3]
    ]
    assert clashes == [], clashes


def test_a_ground_symbol_names_itself_below_its_glyph():
    """A ground hangs its glyph below the wire, so its name goes below that.

    One fixed offset for every power symbol wrote each ground's name across
    the wire arriving at it.
    """
    from src.ecad.emit import power_label_offset

    assert power_label_offset("GND", down=True) > 0
    assert power_label_offset("+3V3", down=False) < 0
    assert power_label_offset("PWR_FLAG", down=False) > 0


# ── defect 3: page size chosen from content ─────────────────────────────────


def test_fit_page_picks_the_smallest_that_holds_the_drawing():
    assert fit_page((MARGIN, MARGIN, 100.0, 100.0)).name == "A4"
    a4_h = PAGE_SIZES[0][2]
    taller = fit_page((MARGIN, MARGIN, 100.0, a4_h - MARGIN + 1))
    assert taller.name == "A3" and taller.fits


def test_fit_page_refuses_to_hide_under_the_title_block():
    w, h = PAGE_SIZES[0][1], PAGE_SIZES[0][2]
    tb_w, tb_h = TITLE_BLOCK
    under = fit_page((MARGIN, MARGIN, w - MARGIN - tb_w / 2,
                      h - MARGIN - tb_h / 2))
    assert under.name != "A4", "content was left sitting on the title block"


def test_fit_page_says_so_when_nothing_fits():
    biggest = PAGE_SIZES[-1]
    fit = fit_page((MARGIN, MARGIN, biggest[1] * 2, biggest[2] * 2))
    assert fit.name == biggest[0]
    assert not fit.fits and fit.overflow


@pytest.mark.parametrize("design_of", (_ldo_stage, _mcu_gps),
                         ids=("ldo", "mcu-gps"))
def test_emitted_sheet_declares_a_page_that_holds_it(design_of):
    design = design_of()
    sheet = emit(layout(design), design)
    assert sheet.page is not None and sheet.page.fits, sheet.page
    assert f'(paper "{sheet.page.name}")' in sheet.text
    assert sheet.warnings == ()


def test_page_overflow_is_reported_loudly():
    """A drawing that fits nothing must warn, not emit a clipped sheet."""
    from src.ecad.layout.engine import _content_box
    from src.ecad.layout.page import PAGE_SIZES as SIZES

    huge = (MARGIN, MARGIN, SIZES[-1][1] * 3, SIZES[-1][2] * 3)
    assert _content_box([huge]) == huge
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        warnings.warn("x", PageOverflow, stacklevel=1)
    assert caught and caught[0].category is PageOverflow
    assert not fit_page(huge).fits


# ── defect 4: the drawing uses the sheet ────────────────────────────────────


def test_placement_never_starts_above_the_page():
    """The y refinement used to push nodes to negative coordinates.

    Nothing downstream can rescue content placed off the top of the paper,
    so placement normalises the drawing onto the frame's top-left corner.
    """
    from src.ecad.layout.place import X_START, Y_START

    for design in (_ldo_stage(), _mcu_gps()):
        placed = layout(design)
        xs = [p[0] for p in placed.placement.origin.values()]
        ys = [p[1] for p in placed.placement.origin.values()]
        assert min(xs) == X_START and min(ys) == Y_START


def test_a_long_column_of_loose_parts_wraps_into_the_page():
    """Twenty pull-ups must not become a 400 mm column."""
    from src.ecad.library.generic.resistor import Resistor
    from src.ecad.layout.place import WRAP_BUDGETS

    design = Design("many-pullups")
    for i in range(20):
        r = Resistor("10k")
        design.add(r)
        design.net("+3V3").connect(r.P1)
        design.net(f"SIG{i}").connect(r.P2)
    placed = layout(design)
    ys = [y for _x, y in placed.placement.origin.values()]
    xs = [x for x, _y in placed.placement.origin.values()]
    assert max(ys) - min(ys) <= max(b for b in WRAP_BUDGETS if b != float("inf"))
    assert len(set(xs)) > 1, "nothing wrapped: still one column"
    sheet = emit(placed, design)
    assert sheet.page is not None and sheet.page.fits
