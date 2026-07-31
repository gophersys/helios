"""Pure KiCad schematic S-expression emitters.

The canonical low-level emission primitives for .kicad_sch content:
deterministic UUIDs, placed symbols, labels, wires, junctions,
no-connects, and generated power symbols. Everything here is a pure
function of its arguments — no library lookups, no pipeline imports.
`src/pipeline/schematic_gen.py` layers the legacy lookup-aware wrappers
on top (dependency direction: pipeline → ecad, never the reverse).
"""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from dataclasses import dataclass


# Optional deterministic UUID factory (set by the layout engine so that the
# same design always emits byte-identical files). Default: random uuid4.
_uuid_factory = None
_uuid_counter = 0


def _uuid() -> str:
    """Generate a UUID string (deterministic when a factory is installed)."""
    global _uuid_counter
    if _uuid_factory is not None:
        _uuid_counter += 1
        return _uuid_factory(f"auto/{_uuid_counter}")
    return str(uuid.uuid4())


@contextmanager
def deterministic_uuids(design_name: str):
    """Within this context every emitted UUID derives from the design name
    and an emission counter — same input, byte-identical output."""
    from .layout.uuidgen import UuidGen

    global _uuid_factory, _uuid_counter
    gen = UuidGen(design_name)
    prev, prev_count = _uuid_factory, _uuid_counter
    _uuid_factory, _uuid_counter = gen.for_path, 0
    try:
        yield
    finally:
        _uuid_factory, _uuid_counter = prev, prev_count


# ---------------------------------------------------------------------------
# Minimal lib_symbols stubs for common component types
# ---------------------------------------------------------------------------



_LIB_SYMBOL_STUBS: dict[str, str] = {
    "Device:R": """(symbol "Device:R"
      (pin_numbers (hide yes))
      (pin_names (offset 0))
      (exclude_from_sim no)
      (in_bom yes)
      (on_board yes)
      (property "Reference" "R" (at 2.032 0 90) (effects (font (size 1.27 1.27))))
      (property "Value" "R" (at 0 0 90) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at -1.778 0 90) (effects (font (size 1.27 1.27)) (hide yes)))
      (property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (property "Description" "Resistor" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (symbol "R_0_1"
        (rectangle (start -1.016 -2.54) (end 1.016 2.54)
          (stroke (width 0.254) (type default)) (fill (type none))))
      (symbol "R_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))))
      (embedded_fonts no))""",
    "Device:C": """(symbol "Device:C"
      (pin_numbers (hide yes))
      (pin_names (offset 0.254))
      (exclude_from_sim no)
      (in_bom yes)
      (on_board yes)
      (property "Reference" "C" (at 0.635 2.54 0) (effects (font (size 1.27 1.27)) (justify left)))
      (property "Value" "C" (at 0.635 -2.54 0) (effects (font (size 1.27 1.27)) (justify left)))
      (property "Footprint" "" (at 0.9652 -3.81 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (property "Description" "Unpolarized capacitor" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (symbol "C_0_1"
        (polyline (pts (xy -2.032 0.762) (xy 2.032 0.762))
          (stroke (width 0.508) (type default)) (fill (type none)))
        (polyline (pts (xy -2.032 -0.762) (xy 2.032 -0.762))
          (stroke (width 0.508) (type default)) (fill (type none))))
      (symbol "C_1_1"
        (pin passive line (at 0 3.81 270) (length 2.794)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 2.794)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))))
      (embedded_fonts no))""",
    "Device:L": """(symbol "Device:L"
      (pin_numbers (hide yes))
      (pin_names (offset 1.016))
      (exclude_from_sim no)
      (in_bom yes)
      (on_board yes)
      (property "Reference" "L" (at -1.016 0 90) (effects (font (size 1.27 1.27))))
      (property "Value" "L" (at 1.016 0 90) (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (property "Datasheet" "~" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (property "Description" "Inductor" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (symbol "L_0_1"
        (arc (start 0 -2.54) (mid 0.6323 -1.905) (end 0 -1.27)
          (stroke (width 0) (type default)) (fill (type none)))
        (arc (start 0 -1.27) (mid 0.6323 -0.635) (end 0 0)
          (stroke (width 0) (type default)) (fill (type none)))
        (arc (start 0 0) (mid 0.6323 0.635) (end 0 1.27)
          (stroke (width 0) (type default)) (fill (type none)))
        (arc (start 0 1.27) (mid 0.6323 1.905) (end 0 2.54)
          (stroke (width 0) (type default)) (fill (type none))))
      (symbol "L_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))))
      (embedded_fonts no))""",
}




def get_stub(lib_id: str) -> str | None:
    """Static lib_symbols stub for known passives, else None."""
    return _LIB_SYMBOL_STUBS.get(lib_id)


def gen_passive_stub(lib_id: str) -> str:
    """Minimal generated 2-pin stub (pins at (0, +-3.81)) for lib_ids with
    no static stub — every placed symbol MUST have a lib_symbols entry."""
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
      (symbol "{safe_name.split(':')[-1]}_1_1"
        (pin passive line (at 0 3.81 270) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27)))))
        (pin passive line (at 0 -3.81 90) (length 1.27)
          (name "~" (effects (font (size 1.27 1.27))))
          (number "2" (effects (font (size 1.27 1.27))))))
      (embedded_fonts no))"""


@dataclass
class ComponentPlacement:
    """A placed component in a schematic."""
    lib_id: str
    ref: str
    value: str
    footprint: str
    position: tuple[float, float]
    unit: int = 1
    rotation: int = 0  # degrees: 0/90/180/270


@dataclass
class NetConnection:
    """A net label placed in the schematic."""
    net_name: str
    label_type: str  # "local", "global", "power"
    position: tuple[float, float]
    angle: int = 0   # 0 = text extends right, 180 = text extends left




def _gen_property(key: str, value: str, prop_id: int, x: float, y: float,
                  hide: bool = False, justify: str = "") -> str:
    """Generate a property S-expression."""
    effects = '(effects (font (size 1.27 1.27))'
    if justify:
        effects += f' (justify {justify})'
    if hide:
        effects += ' (hide yes)'
    effects += ')'
    return f'\t\t(property "{key}" "{value}"\n\t\t\t(at {x} {y} 0)\n\t\t\t{effects}\n\t\t)'




def gen_symbol_instance(comp: ComponentPlacement, project_name: str,
                        root_uuid: str,
                        pin_numbers: list[str] | None = None) -> str:
    """Generate a placed symbol S-expression (pure — pin numbers are
    supplied by the caller; None means a generic 2-pin part)."""
    x, y = comp.position
    sym_uuid = _uuid()

    nums = pin_numbers if pin_numbers is not None else ["1", "2"]
    pin_section = "\n".join(
        f'\t\t(pin "{n}"\n\t\t\t(uuid "{_uuid()}")\n\t\t)' for n in nums
    )

    return f"""\t(symbol
\t\t(lib_id "{comp.lib_id}")
\t\t(at {x} {y} {comp.rotation})
\t\t(unit {comp.unit})
\t\t(exclude_from_sim no)
\t\t(in_bom yes)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(fields_autoplaced yes)
\t\t(uuid "{sym_uuid}")
{_gen_property("Reference", comp.ref, 0, x + 2.54, y - 1.27, justify="left")}
{_gen_property("Value", comp.value, 1, x + 2.54, y + 1.27, justify="left")}
{_gen_property("Footprint", comp.footprint, 2, x, y, hide=True)}
{_gen_property("Datasheet", "~", 3, x, y, hide=True)}
{pin_section}
\t\t(instances
\t\t\t(project "{project_name}"
\t\t\t\t(path "/{root_uuid}"
\t\t\t\t\t(reference "{comp.ref}")
\t\t\t\t\t(unit {comp.unit})
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""




def _gen_label(net: NetConnection) -> str:
    """Generate a net label S-expression."""
    x, y = net.position
    label_uuid = _uuid()

    if net.label_type == "global":
        return f"""\t(global_label "{net.net_name}"
\t\t(shape input)
\t\t(at {x} {y} 0)
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t\t(justify left)
\t\t)
\t\t(uuid "{label_uuid}")
\t\t(property "Intersheetref" "${{INTERSHEET_REFS}}"
\t\t\t(at 0 0 0)
\t\t\t(effects
\t\t\t\t(font
\t\t\t\t\t(size 1.27 1.27)
\t\t\t\t)
\t\t\t\t(hide yes)
\t\t\t)
\t\t)
\t)"""
    elif net.label_type == "power":
        # Power nets are emitted as generated power symbols by the callers
        # (generate_schematic / _generate_sub_sheet); reaching here means a
        # caller forgot to split them out. Emit a global label as a safe,
        # loadable fallback rather than the invalid (power_port ...) token.
        return _gen_label(NetConnection(net.net_name, "global", net.position))
    else:
        # local label; angle 180 justifies right so text extends leftward
        justify = "right bottom" if net.angle == 180 else "left bottom"
        return f"""\t(label "{net.net_name}"
\t\t(at {x} {y} {net.angle})
\t\t(effects
\t\t\t(font
\t\t\t\t(size 1.27 1.27)
\t\t\t)
\t\t\t(justify {justify})
\t\t)
\t\t(uuid "{label_uuid}")
\t)"""


def _gen_junction(x: float, y: float) -> str:
    """Generate a junction dot (required where 3+ wire ends meet)."""
    return (f'\t(junction\n\t\t(at {x} {y})\n\t\t(diameter 0)\n'
            f'\t\t(color 0 0 0 0)\n\t\t(uuid "{_uuid()}")\n\t)')


def _gen_no_connect(x: float, y: float) -> str:
    """Generate a no-connect marker (required on unused pins for ERC 0)."""
    return f'\t(no_connect\n\t\t(at {x} {y})\n\t\t(uuid "{_uuid()}")\n\t)'


def power_symbol_lib_sexp(net_name: str) -> str:
    """lib_symbols entry for a generated power symbol ``power:<net>``.

    The single hidden power_in pin is NAMED after the net — that is what
    makes the net global in KiCad. Grounds get the triangle glyph, rails
    the bar glyph. PWR_FLAG (net_name="PWR_FLAG") gets the flag glyph and
    a power_out pin so ERC sees the rail as driven.
    """
    safe = net_name.replace('"', '\\"')
    is_flag = net_name == "PWR_FLAG"
    # Must agree with layout.graph_build._GROUND_RE (which also taps EARTH
    # down) or a ground net renders with the upside-down rail glyph.
    is_gnd = net_name.upper().startswith(
        ("GND", "VSS", "AGND", "DGND", "PGND", "EARTH"))
    pin_type = "power_out" if is_flag else "power_in"
    if is_gnd:
        graphics = (
            '        (polyline (pts (xy -1.27 0) (xy 1.27 0)) '
            '(stroke (width 0) (type default)) (fill (type none)))\n'
            '        (polyline (pts (xy -0.762 0.508) (xy 0.762 0.508)) '
            '(stroke (width 0) (type default)) (fill (type none)))\n'
            '        (polyline (pts (xy -0.254 1.016) (xy 0.254 1.016)) '
            '(stroke (width 0) (type default)) (fill (type none)))'
        )
        value_at = "(at 0 2.54 0)"
    elif is_flag:
        graphics = (
            '        (polyline (pts (xy 0 0) (xy 0 -1.27) (xy -1.016 -1.905) '
            '(xy 0 -2.54) (xy 1.016 -1.905) (xy 0 -1.27)) '
            '(stroke (width 0) (type default)) (fill (type none)))'
        )
        value_at = "(at 0 -4.318 0)"
    else:
        graphics = (
            '        (polyline (pts (xy 0 0) (xy 0 -1.27)) '
            '(stroke (width 0) (type default)) (fill (type none)))\n'
            '        (polyline (pts (xy -0.762 -1.27) (xy 0.762 -1.27)) '
            '(stroke (width 0) (type default)) (fill (type none)))'
        )
        value_at = "(at 0 -2.54 0)"
    return f"""(symbol "power:{safe}"
      (power)
      (pin_names (offset 0))
      (exclude_from_sim no)
      (in_bom yes)
      (on_board yes)
      (property "Reference" "#PWR" (at 0 1.27 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (property "Value" "{safe}" {value_at} (effects (font (size 1.27 1.27))))
      (property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (property "Datasheet" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))
      (symbol "{safe}_0_1"
{graphics})
      (symbol "{safe}_1_1"
        (pin {pin_type} line (at 0 0 90) (length 0) (hide yes)
          (name "{safe}" (effects (font (size 1.27 1.27))))
          (number "1" (effects (font (size 1.27 1.27))))))
      (embedded_fonts no))"""


def _gen_power_instance(net_name: str, ref: str, x: float, y: float,
                        rotation: int, project_name: str,
                        root_uuid: str) -> str:
    """A placed power symbol instance (#PWR ref, invisible in BOM)."""
    safe = net_name.replace('"', '\\"')
    return f"""\t(symbol
\t\t(lib_id "power:{safe}")
\t\t(at {x} {y} {rotation})
\t\t(unit 1)
\t\t(exclude_from_sim no)
\t\t(in_bom no)
\t\t(on_board yes)
\t\t(dnp no)
\t\t(fields_autoplaced yes)
\t\t(uuid "{_uuid()}")
{_gen_property("Reference", ref, 0, x, y + 1.27, hide=True)}
{_gen_property("Value", safe, 1, x, y - 2.54)}
\t\t(pin "1"\n\t\t\t(uuid "{_uuid()}")\n\t\t)
\t\t(instances
\t\t\t(project "{project_name}"
\t\t\t\t(path "/{root_uuid}"
\t\t\t\t\t(reference "{ref}")
\t\t\t\t\t(unit 1)
\t\t\t\t)
\t\t\t)
\t\t)
\t)"""


def _gen_wire(x1: float, y1: float, x2: float, y2: float) -> str:
    """Generate a wire S-expression."""
    return f"""\t(wire
\t\t(pts
\t\t\t(xy {x1} {y1}) (xy {x2} {y2})
\t\t)
\t\t(stroke
\t\t\t(width 0)
\t\t\t(type default)
\t\t)
\t\t(uuid "{_uuid()}")
\t)"""


