"""KiCad schematic generator — creates .kicad_sch files from component placements.

Legacy/pipeline layer: chip-library-aware wrappers over the pure emission
primitives in src.ecad.emit, plus hierarchical-project generation used by
the composer. New code should use src.ecad.emit / src.ecad.layout.engine.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.ecad.emit import (  # noqa: F401  (re-exported legacy API)
    ComponentPlacement,
    NetConnection,
    _gen_junction,
    _gen_label,
    _gen_no_connect,
    _gen_power_instance,
    _gen_property,
    _gen_wire,
    _uuid,
    deterministic_uuids,
    gen_symbol_instance,
    get_stub,
    power_symbol_lib_sexp,
)
from src.pipeline.chip_library import generate_lib_symbol_sexp, lookup_chip


def _get_lib_symbol_stub(lib_id: str) -> str:
    """lib_symbols entry: known passive stub, else chip library, else a
    minimal generated 2-pin stub."""
    stub = get_stub(lib_id)
    if stub is not None:
        return stub
    chip = lookup_chip(lib_id)
    if chip is not None:
        return generate_lib_symbol_sexp(chip, lib_id)
    safe_name = lib_id.replace('"', '\\"')
    ref_prefix = lib_id.split(":")[-1][0] if ":" in lib_id else "U"
    return f"""(symbol "{safe_name}"
      (pin_names (offset 1.016))
      (exclude_from_sim no)
      (in_bom yes)
      (on_board yes)
      (property "Reference" "{ref_prefix}" (at 0 1.27 0) (effects (font (size 1.27 1.27))))
      (property "Value" "{safe_name}" (at 0 -1.27 0) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (symbol "{safe_name}_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))))
      (embedded_fonts no))"""


def _gen_component(comp: ComponentPlacement, project_name: str,
                   root_uuid: str) -> str:
    """Legacy wrapper: resolve real IC pin numbers via the chip library."""
    chip = lookup_chip(comp.lib_id)
    nums = [str(p.number) for p in chip.pins] if chip is not None else None
    return gen_symbol_instance(comp, project_name, root_uuid, nums)


@dataclass
class SheetContent:
    """Content of a hierarchical sheet."""
    title: str
    components: list[ComponentPlacement]
    nets: list[NetConnection]
    hierarchical_labels: list[tuple[str, str]]  # (name, direction)


# ---------------------------------------------------------------------------
# S-expression generators
# ---------------------------------------------------------------------------


def _gen_hierarchical_label(name: str, direction: str,
                            x: float = 25.4, y: float = 25.4,
                            angle: int = 180) -> str:
    """Generate a hierarchical_label S-expression for a sub-sheet.

    ``angle`` follows the router's stub convention (0 right, 90 up,
    180 left, 270 down); the text justification mirrors it so the glyph
    always points away from the wire it terminates.
    """
    shape_map = {
        "input": "input",
        "output": "output",
        "bidirectional": "bidirectional",
        "passive": "passive",
    }
    shape = shape_map.get(direction, "bidirectional")
    justify = "right" if angle == 180 else "left"
    return f"""\t(hierarchical_label "{name}"
\t\t(shape {shape})
\t\t(at {x} {y} {angle})
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t\t(justify {justify})
\t\t)
\t\t(uuid "{_uuid()}")
\t)"""


_SHEET_PIN_SHAPES = frozenset(
    {"input", "output", "bidirectional", "tri_state", "passive"})

_SHEET_WIDTH = 20.32      # mm — sheet symbol box width in the root schematic
_SHEET_PIN_DY = 2.54      # mm — vertical pitch of sheet pins
_SHEET_STUB = 2.54        # mm — pin → label stub on the root sheet


def _sheet_pin_point(x: float, y: float, index: int) -> tuple[float, float]:
    """Absolute position of sheet pin ``index`` of a sheet drawn at (x, y)."""
    return (x + _SHEET_WIDTH, y + _SHEET_PIN_DY + index * _SHEET_PIN_DY)


def _gen_sheet_pin_nets(pins: list[tuple[str, str]],
                        x: float, y: float) -> list[str]:
    """Wire + label every sheet pin so the hierarchy is actually connected.

    A sheet pin that touches nothing is an ERC error ("Pin not connected")
    and the sub-sheets never join. Each pin gets a short stub ending in a
    label carrying the net name: identically-named labels on the root sheet
    are one net, which is how sheet A's ``GPS_TX`` reaches sheet B's.
    """
    lines: list[str] = []
    for i, (pin_name, _dir) in enumerate(pins):
        px, py = _sheet_pin_point(x, y, i)
        lines.append(_gen_wire(px, py, px + _SHEET_STUB, py))
        lines.append(_gen_label(
            NetConnection(pin_name, "local", (px + _SHEET_STUB, py))))
    return lines


def _gen_sheet_ref(filename: str, sheet_name: str,
                   pins: list[tuple[str, str]],
                   x: float, y: float,
                   project_name: str, root_uuid: str,
                   page: int) -> str:
    """Generate a sheet reference S-expression in the root schematic.

    The pin SHAPE must equal the shape of the matching hierarchical label
    inside the sub-sheet or KiCad ERC reports a hierarchical-label
    mismatch, so the caller's declared direction is emitted verbatim.
    """
    sheet_uuid = _uuid()
    width = _SHEET_WIDTH
    height = max(10.16, (len(pins) + 1) * _SHEET_PIN_DY)

    pin_lines = []
    for i, (pin_name, pin_dir) in enumerate(pins):
        _px, pin_y = _sheet_pin_point(x, y, i)
        shape = pin_dir if pin_dir in _SHEET_PIN_SHAPES else "bidirectional"
        pin_lines.append(
            f'\t\t(pin "{pin_name}" {shape}\n'
            f'\t\t\t(at {x + width} {pin_y} 0)\n'
            f'\t\t\t(uuid "{_uuid()}")\n'
            f'\t\t\t(effects\n'
            f'\t\t\t\t(font\n'
            f'\t\t\t\t\t(size 1.27 1.27)\n'
            f'\t\t\t\t)\n'
            f'\t\t\t\t(justify right)\n'
            f'\t\t\t)\n'
            f'\t\t)'
        )

    pins_str = "\n".join(pin_lines)

    return f"""\t(sheet
\t\t(at {x} {y})
\t\t(size {width} {height})
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(fields_autoplaced yes)
\t\t(stroke
\t\t\t(width 0.1524)
\t\t\t(type solid)
\t\t)
\t\t(fill
\t\t\t(color 0 0 0 0.0000)
\t\t)
\t\t(uuid "{sheet_uuid}")
\t\t(property "Sheetname" "{sheet_name}"
\t\t\t(at {x} {y - 0.7} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(justify left bottom)
\t\t\t)
\t\t)
\t\t(property "Sheetfile" "{filename}"
\t\t\t(at {x} {y + height + 0.6} 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(justify left top)
\t\t\t)
\t\t)
{pins_str}
\t\t(instances
\t\t\t(project "{project_name}"
\t\t\t\t(path "/{root_uuid}"
\t\t\t\t\t(page "{page}")
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""


# ---------------------------------------------------------------------------
# Project file generators
# ---------------------------------------------------------------------------

def _gen_project_file() -> str:
    """Generate a minimal .kicad_pro project file (JSON format)."""
    import json
    proj = {
        "meta": {
            "filename": "",
            "version": 1,
        },
        "schematic": {
            "drawing": {"default_line_thickness": 6.0},
            "legacy_lib_dir": "",
            "legacy_lib_list": [],
        },
        "boards": [],
        "text_variables": {},
    }
    return json.dumps(proj, indent=2) + "\n"


def _gen_lib_table(table_type: str) -> str:
    """Generate an empty sym-lib-table or fp-lib-table.

    Args:
        table_type: "sym_lib_table" or "fp_lib_table"
    """
    return f"({table_type})\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _generate_passive_wires(
    components: list[ComponentPlacement],
    nets: list[NetConnection],
) -> list[str]:
    """Generate wire segments connecting passive component pins to nearby labels.

    For each passive (R, C, L), draws a short wire from pin 1 (top, y-3.81)
    to the nearest label above, and from pin 2 (bottom, y+3.81) to the nearest
    label below. Labels must be within 15mm to be considered "nearby".
    """
    wires: list[str] = []

    passive_bases = {"R", "C", "L"}
    for comp in components:
        lib_base = comp.lib_id.split(":")[-1] if ":" in comp.lib_id else comp.lib_id
        if lib_base not in passive_bases:
            continue

        cx, cy = comp.position
        pin1_y = cy - 3.81  # top pin
        pin2_y = cy + 3.81  # bottom pin

        # Find labels near pin 1 (above component)
        best_above = None
        best_above_dist = 15.0
        for net in nets:
            nx, ny = net.position
            dist = abs(nx - cx) + abs(ny - pin1_y)
            if dist < best_above_dist:
                best_above = net
                best_above_dist = dist

        if best_above:
            wires.append(_gen_wire(cx, pin1_y, best_above.position[0], best_above.position[1]))

        # Find labels near pin 2 (below component)
        best_below = None
        best_below_dist = 15.0
        for net in nets:
            nx, ny = net.position
            dist = abs(nx - cx) + abs(ny - pin2_y)
            if dist < best_below_dist:
                best_below = net
                best_below_dist = dist

        if best_below:
            wires.append(_gen_wire(cx, pin2_y, best_below.position[0], best_below.position[1]))

    return wires


def generate_schematic(
    components: list[ComponentPlacement],
    nets: list[NetConnection],
    title: str = "Generated Schematic",
    paper_size: str = "A4",
) -> str:
    """Generate a .kicad_sch file content from component placements and net connections.

    Args:
        components: List of placed components.
        nets: List of net labels.
        title: Schematic title.
        paper_size: Paper size (A4, A3, etc.).

    Returns:
        String content of a valid .kicad_sch file.
    """
    root_uuid = _uuid()
    project_name = title.replace(" ", "_")

    # Power-typed nets become real generated power symbols, not labels
    # (the old `(power_port ...)` token was not valid KiCad syntax).
    power_nets = [n for n in nets if n.label_type == "power"]
    label_nets = [n for n in nets if n.label_type != "power"]

    # Collect unique lib_ids for lib_symbols section
    lib_ids = sorted({c.lib_id for c in components})
    lib_symbol_entries = [_get_lib_symbol_stub(lid) for lid in lib_ids]
    for name in sorted({n.net_name for n in power_nets}):
        lib_symbol_entries.append(power_symbol_lib_sexp(name))
    lib_symbols = "\n\t\t".join(lib_symbol_entries)

    # Generate component placements
    comp_lines_list = [
        _gen_component(c, project_name, root_uuid) for c in components
    ]
    for i, n in enumerate(power_nets, start=1):
        x, y = n.position
        rot = 180 if n.net_name.upper().startswith(
            ("GND", "VSS", "AGND", "DGND", "PGND")) else 0
        comp_lines_list.append(_gen_power_instance(
            n.net_name, f"#PWR{i:02d}", x, y, rot, project_name, root_uuid))
    comp_lines = "\n".join(comp_lines_list)

    # Generate net labels
    label_lines = "\n".join(_gen_label(n) for n in label_nets)

    # Generate wires connecting passives to labels
    wire_lines = "\n".join(_generate_passive_wires(components, nets))

    return f"""(kicad_sch
\t(version 20250114)
\t(generator "hardware-pipeline")
\t(generator_version "1.0")
\t(uuid "{root_uuid}")
\t(paper "{paper_size}")
\t(lib_symbols
\t\t{lib_symbols}
\t)
{label_lines}
{wire_lines}
{comp_lines}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""


def generate_hierarchical_project(
    sheets: dict[str, SheetContent],
    root_title: str = "Root",
    rendered_sheets: dict[str, str] | None = None,
) -> dict[str, str]:
    """Generate a complete hierarchical KiCad project.

    Creates a root schematic with sheet references (each sheet pin wired to
    a same-named label, so the sub-sheets are really connected) plus the
    sub-sheet files.

    Args:
        sheets: Dict mapping filename (e.g., "power.kicad_sch") to content.
            ``SheetContent.hierarchical_labels`` defines the sheet pins.
        root_title: Title for the root schematic.
        rendered_sheets: Optional filename → complete .kicad_sch text,
            supplied by a caller that already laid the sheet out (the
            composer hands over ``src.ecad.layout.engine.emit`` output).
            Filenames absent from this mapping fall back to the legacy
            placement-list renderer.

    Returns:
        Dict mapping filename -> file content string for all sheets
        including the root.

    UUIDs derive from ``root_title`` (own namespace), so the same project
    regenerates byte-identically.
    """
    project_name = root_title.replace(" ", "_")
    pre_rendered = rendered_sheets or {}

    # Collect all lib_ids across all sheets
    all_lib_ids: set[str] = set()
    for sc in sheets.values():
        for c in sc.components:
            all_lib_ids.add(c.lib_id)

    with deterministic_uuids(f"{root_title}/root"):
        root_uuid = _uuid()
        # Generate root schematic with sheet references
        sheet_refs = []
        x_offset = 50.8
        for page_num, (filename, sc) in enumerate(sheets.items(), start=2):
            pins = sc.hierarchical_labels
            ref = _gen_sheet_ref(
                filename, sc.title, pins,
                x_offset, 40.64,
                project_name, root_uuid,
                page_num,
            )
            sheet_refs.append(ref)
            sheet_refs.extend(_gen_sheet_pin_nets(pins, x_offset, 40.64))
            x_offset += 30.48

        sheet_refs_str = "\n".join(sheet_refs)

        root_content = f"""(kicad_sch
\t(version 20250114)
\t(generator "hardware-pipeline")
\t(generator_version "1.0")
\t(uuid "{root_uuid}")
\t(paper "A4")
\t(lib_symbols)
{sheet_refs_str}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""

    result: dict[str, str] = {}
    project_base = root_title.replace(" ", "_").lower()
    root_filename = project_base + ".kicad_sch"
    result[root_filename] = root_content

    # Generate sub-sheets (pre-rendered engine output wins)
    for filename, sc in sheets.items():
        if filename in pre_rendered:
            result[filename] = pre_rendered[filename]
            continue
        with deterministic_uuids(f"{root_title}/{filename}"):
            result[filename] = _generate_sub_sheet(sc, project_name, all_lib_ids)

    # Generate .kicad_pro (minimal project file)
    result[project_base + ".kicad_pro"] = _gen_project_file()

    # Generate sym-lib-table and fp-lib-table (empty, using global libs)
    result["sym-lib-table"] = _gen_lib_table("sym_lib_table")
    result["fp-lib-table"] = _gen_lib_table("fp_lib_table")

    return result


def _generate_sub_sheet(
    sc: SheetContent,
    project_name: str,
    all_lib_ids: set[str],
) -> str:
    """Generate a sub-sheet .kicad_sch file."""
    sheet_uuid = _uuid()

    power_nets = [n for n in sc.nets if n.label_type == "power"]
    label_nets = [n for n in sc.nets if n.label_type != "power"]

    # lib_symbols for components in this sheet
    sheet_lib_ids = sorted({c.lib_id for c in sc.components})
    lib_symbol_entries = [_get_lib_symbol_stub(lid) for lid in sheet_lib_ids]
    for name in sorted({n.net_name for n in power_nets}):
        lib_symbol_entries.append(power_symbol_lib_sexp(name))
    lib_symbols = "\n\t\t".join(lib_symbol_entries)

    # Component placements
    comp_lines_list = [
        _gen_component(c, project_name, sheet_uuid) for c in sc.components
    ]
    for i, n in enumerate(power_nets, start=1):
        x, y = n.position
        rot = 180 if n.net_name.upper().startswith(
            ("GND", "VSS", "AGND", "DGND", "PGND")) else 0
        comp_lines_list.append(_gen_power_instance(
            n.net_name, f"#PWR{i:02d}", x, y, rot, project_name, sheet_uuid))
    comp_lines = "\n".join(comp_lines_list)

    # Net labels
    label_lines = "\n".join(_gen_label(n) for n in label_nets)

    # Hierarchical labels — spread vertically along left edge
    hlabel_x = 25.4
    hlabel_y_start = 30.0
    hlabel_spacing = 7.62
    hlabel_lines = "\n".join(
        _gen_hierarchical_label(name, direction,
                                x=hlabel_x,
                                y=hlabel_y_start + i * hlabel_spacing)
        for i, (name, direction) in enumerate(sc.hierarchical_labels)
    )

    # Generate wires connecting passives to labels
    wire_lines = "\n".join(_generate_passive_wires(sc.components, sc.nets))

    return f"""(kicad_sch
\t(version 20250114)
\t(generator "hardware-pipeline")
\t(generator_version "1.0")
\t(uuid "{sheet_uuid}")
\t(paper "A4")
\t(lib_symbols
\t\t{lib_symbols}
\t)
{hlabel_lines}
{label_lines}
{wire_lines}
{comp_lines}
\t(sheet_instances
\t\t(path "/"
\t\t\t(page "1")
\t\t)
\t)
\t(embedded_fonts no)
)
"""
