"""`src.pipeline.project_assembly` — authored sheets → one GeneratedProject.

The three things this layer adds to a set of already-typed sheets are the
three things a hierarchy needs and a standalone sheet does not: one
designator namespace, hierarchical labels for the nets that cross, and one
PWR_FLAG per rail. Each is gated here on the real reference design rather
than on a fixture, because each was a real defect waiting to happen:
duplicate references and a doubly-flagged rail are both project ERC errors
that no per-sheet run can see.

The whole-project ERC itself is gated in ``tests/ecad/test_build_examples.py``
(it needs kicad-cli); everything here runs anywhere.
"""

from __future__ import annotations

import pytest

from examples.esp32_s3_reference import design as ref
from src.ecad import Design, ElectricalType
from src.pipeline.composer import GeneratedProject
from src.pipeline.project_assembly import (
    SheetSource,
    assemble_project,
    cross_sheet_nets,
    flag_owners,
    renumber_refs,
)


@pytest.fixture(scope="module")
def project() -> GeneratedProject:
    return ref.build()


@pytest.fixture
def sources() -> list[SheetSource]:
    designs = ref.sheets()
    return [SheetSource(name=n, title=ref.SHEET_TITLES[n], design=designs[n],
                        directions=ref.HIER_NETS[n])
            for n in ref.SHEETS]


# ---------------------------------------------------------------------------
# One designator namespace
# ---------------------------------------------------------------------------

def test_renumber_makes_references_unique_across_sheets(sources):
    designs = [s.design for s in sources]
    before = [c.ref for d in designs for c in d.components]
    assert len(before) != len(set(before)), (
        "the authored sheets are expected to collide — each numbers its own")

    moved = renumber_refs(designs)
    after = [c.ref for d in designs for c in d.components]
    assert len(after) == len(set(after)), sorted(after)
    assert moved, "nothing was reported as renamed"
    # every reported rename is real, and the prefix never changes
    for old, new in moved.items():
        assert old.split("/")[-1][0] == new[0], (old, new)


def test_renumber_is_deterministic_and_idempotent(sources):
    designs = [s.design for s in sources]
    renumber_refs(designs)
    once = [c.ref for d in designs for c in d.components]
    assert renumber_refs(designs) == {}, "a second pass moved something"
    twice = [c.ref for d in designs for c in d.components]
    assert once == twice

    fresh = ref.sheets()
    renumber_refs([fresh[n] for n in ref.SHEETS])
    assert [c.ref for n in ref.SHEETS for c in fresh[n].components] == once


def test_the_built_project_ships_unique_references(project):
    refs = [e["ref"] for e in project.bom]
    assert len(refs) == len(set(refs)), sorted(
        r for r in refs if refs.count(r) > 1)
    # ...and the BOM is the sheets, nothing invented or dropped
    assert len(refs) == sum(len(d.components) for d in project.designs.values())


# ---------------------------------------------------------------------------
# What crosses a sheet boundary
# ---------------------------------------------------------------------------

def test_cross_sheet_nets_are_derived_not_declared(sources):
    crossing = cross_sheet_nets(sources)
    assert crossing["mcu"] == {"USB_D+", "USB_D-"}
    assert crossing["usb"] == {"USB_D+", "USB_D-"}
    assert crossing["power"] == set()
    # the mcu side is what the design declares; the usb side is the same
    # nets seen from the other end, which no declaration in the module
    # covers — deriving them is what keeps the two ends in step
    assert set(ref.HIER_NETS["mcu"]) == crossing["mcu"]


def test_power_rails_do_not_become_hierarchical_labels(sources):
    """+3V3 / GND / VBUS are carried by two sheets each and must still stay
    out of the hierarchy: they cross as KiCad global power symbols, and a
    hierarchical label on a rail asks the router for an anchor it never
    places."""
    crossing = cross_sheet_nets(sources)
    for rail in (ref.RAIL, "GND", "VBUS"):
        for sheet in ref.SHEETS:
            assert rail not in crossing[sheet], (sheet, rail)


def test_every_crossing_net_is_labelled_on_both_sheets(project):
    """A sheet pin with no matching hierarchical label is a dangling wire."""
    for net in ("USB_D+", "USB_D-"):
        for filename in ("mcu.kicad_sch", "usb.kicad_sch"):
            text = project.files[filename]
            assert f'(hierarchical_label "{net}"' in text, (filename, net)
        assert f'(pin "{net}"' in project.files["esp32_s3_reference.kicad_sch"]


def test_a_receptacle_gets_one_label_per_anchor(project):
    """USB_D+ lands on both orientations of the Type-C receptacle, so the
    usb sheet names it twice — a labelled net is joined only through its
    labels, and naming one anchor would strand the other."""
    usb = project.files["usb.kicad_sch"]
    assert usb.count('(hierarchical_label "USB_D+"') == 2, usb.count(
        '(hierarchical_label "USB_D+"')
    assert usb.count('(hierarchical_label "USB_D-"') == 2


# ---------------------------------------------------------------------------
# One PWR_FLAG per rail
# ---------------------------------------------------------------------------

def test_each_undriven_rail_is_flagged_on_exactly_one_sheet(sources):
    """Power symbols are global across a hierarchy: two PWR_FLAGs on one
    rail is a power-output conflict, none at all is an undriven net.

    ``+3V3`` is absent on purpose — the LDO's ``power_out`` pin already
    drives it, so a flag there would be the second driver.
    """
    owners = flag_owners(sources)
    assert owners == {"VBUS": "power", "GND": "power"}, owners
    assert ref.RAIL not in owners

    reg = next(c for c in sources[0].design.components
               if any(p.etype is ElectricalType.POWER_OUT for p in c.pins))
    assert ref.REGULATOR in reg.part_name, "the +3V3 driver moved"


def test_only_the_owning_sheet_emits_a_power_flag(project):
    """What the rule above means in the emitted files: two flags, both on
    the power sheet, none anywhere else."""
    per_sheet = {
        name: text.count('(lib_id "power:PWR_FLAG")')
        for name, text in project.files.items() if name.endswith(".kicad_sch")
    }
    assert per_sheet == {
        "esp32_s3_reference.kicad_sch": 0,
        "power.kicad_sch": 2,
        "mcu.kicad_sch": 0,
        "usb.kicad_sch": 0,
    }, per_sheet


# ---------------------------------------------------------------------------
# The assembled project as a whole
# ---------------------------------------------------------------------------

def test_assemble_reports_problems_rather_than_smoothing_them(sources):
    """A sheet whose design does not check out must show up in warnings —
    the assembler is not allowed to quietly emit it."""
    broken = Design("broken-sheet")
    from src.ecad.library import get as registry_get

    part = registry_get(ref.MODULE)()
    broken.add(part)
    broken.net("DANGLING").connect(part.gpio(4))

    project = assemble_project("Broken", [
        SheetSource(name="broken", title="Broken", design=broken)])
    assert any("broken.kicad_sch" in w for w in project.warnings), \
        project.warnings


def test_the_project_is_byte_deterministic():
    """Same design in, same project out — the bundle is a build product."""
    a, b = ref.build(), ref.build()
    assert a.files == b.files
    assert [e["ref"] for e in a.bom] == [e["ref"] for e in b.bom]


def test_the_root_names_every_sheet(project):
    root = project.files["esp32_s3_reference.kicad_sch"]
    for name in ref.SHEETS:
        assert f"{name}.kicad_sch" in root
        assert ref.SHEET_TITLES[name] in root
