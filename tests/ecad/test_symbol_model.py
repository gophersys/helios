"""SymbolModel geometry + byte-parity against the legacy emitters."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

from src.ecad import PinRole, Side, SymbolModel
from src.pipeline.chip_library import (
    _generate_lib_symbol_sexp_legacy,
    esp32_s3_wroom_1,
    generate_lib_symbol_sexp,
    neo_6m,
    stm32f411ceu6,
)
from src.pipeline.ecad_bridge import (
    _infer_role,
    chipdef_to_component,
    component_to_chipdef,
)
from src.pipeline.symbol_gen import (
    ChipDef,
    PinDef,
    _generate_symbol_legacy,
    generate_symbol,
)

ALL_CHIPS = [esp32_s3_wroom_1, stm32f411ceu6, neo_6m]


def _lib_to_text(lib) -> str:
    import tempfile

    with tempfile.NamedTemporaryFile("r", suffix=".kicad_sym", delete=False) as f:
        path = f.name
    lib.to_file(path)
    text = Path(path).read_text()
    Path(path).unlink()
    return text


# ── parity: the shims must emit byte-identical output vs legacy ─────────────


def test_kicad_sym_parity_all_chips():
    for factory in ALL_CHIPS:
        chip = factory()
        assert _lib_to_text(generate_symbol(chip)) == _lib_to_text(
            _generate_symbol_legacy(chip)
        ), f"kicad_sym parity broken for {chip.name}"


def test_inline_sexp_parity_all_chips():
    """Byte-parity vs legacy EXCEPT the child-symbol names: legacy emitted
    lib-prefixed child names ("RF_GPS:NEO-6M_0_1"), which KiCad refuses to
    load — the new emitter uses the bare part name ("NEO-6M_0_1"). The
    legacy output is normalized to the fixed form before comparing, which
    proves everything else is unchanged."""
    for factory in ALL_CHIPS:
        chip = factory()
        lib_id = f"{chip.library}:{chip.name}" if chip.library else chip.name
        legacy = _generate_lib_symbol_sexp_legacy(chip, lib_id)
        legacy = legacy.replace(f'(symbol "{lib_id}_', f'(symbol "{chip.name}_')
        assert generate_lib_symbol_sexp(chip, lib_id) == legacy, \
            f"inline sexp parity broken for {chip.name}"


def test_inline_sexp_loads_in_kicad(tmp_path):
    """Regression for the child-name bug: the inline symbol must LOAD."""
    import shutil
    import subprocess

    cli = shutil.which("kicad-cli")
    if cli is None:
        import pytest
        pytest.skip("kicad-cli not available")
    chip = neo_6m()
    entry = generate_lib_symbol_sexp(chip, "RF_GPS:NEO-6M")
    text = ('(kicad_sch\n\t(version 20250114)\n\t(generator "x")\n'
            '\t(generator_version "1.0")\n'
            '\t(uuid "0e5e4c2e-0000-5000-8000-000000000000")\n\t(paper "A4")\n'
            f'\t(lib_symbols\n\t\t{entry}\n\t)\n'
            '\t(sheet_instances\n\t\t(path "/"\n\t\t\t(page "1")\n\t\t)\n\t)\n'
            '\t(embedded_fonts no)\n)\n')
    p = tmp_path / "inline.kicad_sch"
    p.write_text(text)
    r = subprocess.run([cli, "sch", "erc", str(p), "-o",
                        str(tmp_path / "erc.json"), "--format", "json"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-400:]


# ── geometry queries (the layout-engine contract) ───────────────────────────


def test_pin_position_query():
    comp = chipdef_to_component(esp32_s3_wroom_1())
    model = SymbolModel.from_component(comp)
    assert model.pin_count == 41
    loc = model.pin_position("2")  # 3V3 pad
    unit_id = loc.unit_id
    assert unit_id >= 1
    assert loc.x == -(15.24 / 2) - 2.54
    assert loc.side is Side.LEFT
    assert loc.angle == 0 and loc.length == 2.54
    unit = model.unit(unit_id)
    assert any(p.pad == "2" for p in unit.pins)
    assert all(p.side is Side.LEFT for u in model.units for p in u.pins)


def test_units_match_legacy_groups():
    chip = stm32f411ceu6()
    model = SymbolModel.from_component(chipdef_to_component(chip))
    legacy_groups = []
    for p in chip.pins:
        if p.group not in legacy_groups:
            legacy_groups.append(p.group)
    assert [u.name for u in model.units] == legacy_groups


def test_flatten_preserves_pin_order():
    chip = neo_6m()
    model = SymbolModel.from_component(chipdef_to_component(chip))
    flat = model.flatten()
    assert len(flat.units) == 1
    assert [p.pad for p in flat.units[0].pins] == [str(p.number) for p in chip.pins]


def test_chipdef_roundtrip():
    chip = esp32_s3_wroom_1()
    back = component_to_chipdef(chipdef_to_component(chip))
    assert [(p.number, p.name, p.group) for p in back.pins] == [
        (str(p.number), p.name, p.group) for p in chip.pins
    ]
    assert back.footprint == chip.footprint
    assert back.name == chip.name


# ── regressions ─────────────────────────────────────────────────────────────


def test_ep_prefix_does_not_swallow_non_ground_pins():
    """"EP"/"EPAD" is the exposed pad — EPWM/EP0/EPROM are not grounds."""
    assert _infer_role(PinDef("9", "EP", "power_in", "Power")) is PinRole.GROUND
    assert _infer_role(PinDef("9", "EPAD", "power_in", "Power")) is PinRole.GROUND
    assert _infer_role(PinDef("9", "EP_1", "power_in", "Power")) is PinRole.GROUND
    for name in ("EPWM1A", "EP0", "EP1_IN", "EPROM_A0", "EPS_5V"):
        role = _infer_role(PinDef("9", name, "output", "pwm"))
        assert role is not PinRole.GROUND, f"{name} misclassified as ground"


def test_gpio_helper_works_on_bridged_mcu():
    """The documented mcu.gpio(n) workflow must work on shipped factories."""
    mcu = chipdef_to_component(esp32_s3_wroom_1())
    assert mcu.gpio(17).pad == "19"     # GPIO17/ADC2_CH6/DAC1
    assert mcu.gpio(0).name == "GPIO0"  # strapping pin, still addressable
    with pytest.raises(KeyError):
        mcu.gpio(999)


def test_explicit_pindef_gpio_survives_roundtrip():
    chip = ChipDef("T", "Test", "", "fp:FP", "", [
        PinDef("1", "PA5", "bidirectional", "GPIO", gpio=5),
    ])
    comp = chipdef_to_component(chip)
    assert comp.gpio(5).pad == "1"
    assert component_to_chipdef(comp).pins[0].gpio == 5


def test_inline_sexp_escapes_every_interpolated_field():
    """Quotes in datasheet-sourced text must not break out of the literal."""
    chip = ChipDef(
        name='T"X',
        library="Lib",
        description='A 2.5" TFT, 3.3V',
        footprint='fp:C_0402"odd',
        datasheet_url='http://x/a"b',
        pins=[PinDef("1", 'P"1', "passive", "G")],
    )
    out = generate_lib_symbol_sexp(chip, 'Lib:T"X')

    # The real contract: the emitted block must still parse as one
    # S-expression, and the values must survive the round trip intact.
    import sexpdata
    parsed = sexpdata.loads(out)
    props = {p[1]: p[2] for p in parsed
             if isinstance(p, list) and str(p[0]) == "property"}
    assert props["Description"] == 'A 2.5" TFT, 3.3V'
    assert props["Datasheet"] == 'http://x/a"b'
    assert props["Footprint"] == 'fp:C_0402"odd'

    # and the legacy oracle agrees, once its child-symbol names are normalized
    # (see test_inline_sexp_parity_all_chips: legacy emitted lib-prefixed child
    # names, which KiCad refuses to load)
    legacy = _generate_lib_symbol_sexp_legacy(chip, 'Lib:T"X')
    legacy = legacy.replace('(symbol "Lib:T\\"X_', '(symbol "T\\"X_')
    assert out == legacy


def test_inline_sexp_escapes_backslashes():
    chip = ChipDef("T", "Lib", "path C:\\parts", "fp:FP", "", [
        PinDef("1", "P1", "passive", "G"),
    ])
    out = generate_lib_symbol_sexp(chip, "Lib:T")
    assert "C:\\\\parts" in out
    legacy = _generate_lib_symbol_sexp_legacy(chip, "Lib:T")
    legacy = legacy.replace('(symbol "Lib:T_', '(symbol "T_')
    assert out == legacy


def test_zero_pin_component_emits_without_crashing():
    """Degenerate but reachable: a ChipDef whose pin list is empty."""
    chip = ChipDef("Empty", "Lib", "", "fp:FP", "", [])
    model = SymbolModel.from_component(chipdef_to_component(chip))
    assert model.pin_count == 0
    assert model.units == ()
    inline = model.to_inline_sexp("Lib:Empty")
    import sexpdata
    sexpdata.loads(inline)  # must still be a parseable symbol block
    assert model.to_kicad_sym().symbols[0].units == []


def test_flatten_pin_position_is_the_inline_geometry():
    """The docstring points inline consumers at flatten() — verify it."""
    chip = esp32_s3_wroom_1()
    model = SymbolModel.from_component(chipdef_to_component(chip))
    flat = model.flatten()
    loc = flat.pin_position("2")
    assert loc.unit_id == 1
    body = f"(at {loc.x} {loc.y} 0)"
    assert body in flat.to_inline_sexp("RF_Module:ESP32-S3-WROOM-1")
    # multi-unit geometry differs — that asymmetry is the reason for flatten()
    assert model.pin_position("2").y != loc.y


def test_importing_ecad_does_not_mutate_sys_path():
    """src.ecad must not insert tools/ until a kiutils emitter is called."""
    import subprocess
    code = (
        "import sys; before = list(sys.path);"
        "import src.ecad;"
        "print(int(list(sys.path) == before))"
    )
    r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, cwd=str(Path(__file__).resolve().parents[2]))
    assert r.stdout.strip() == "1", f"sys.path mutated on import: {r.stderr}"


def test_both_emitters_agree_on_reference_prefix():
    """to_kicad_sym and to_inline_sexp describe the same part."""
    chip = ChipDef("Cap", "Device", "", "Capacitor_SMD:C_0402_1005Metric", "", [
        PinDef("1", "P1", "passive", "Passive"),
        PinDef("2", "P2", "passive", "Passive"),
    ])
    comp = chipdef_to_component(chip)
    comp.__class__.reference_prefix = "C"
    model = SymbolModel.from_component(comp)
    sym_ref = model.to_kicad_sym().symbols[0].properties[0].value
    assert sym_ref == "C"
    assert f'(property "Reference" "{sym_ref}"' in model.to_inline_sexp("Device:Cap")
