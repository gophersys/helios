"""SymbolModel geometry + byte-parity against the legacy emitters."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "tools"))

from src.ecad import Side, SymbolModel
from src.pipeline.chip_library import (
    _generate_lib_symbol_sexp_legacy,
    esp32_s3_wroom_1,
    generate_lib_symbol_sexp,
    neo_6m,
    stm32f411ceu6,
)
from src.pipeline.ecad_bridge import chipdef_to_component, component_to_chipdef
from src.pipeline.symbol_gen import _generate_symbol_legacy, generate_symbol

ALL_CHIPS = [esp32_s3_wroom_1, stm32f411ceu6, neo_6m]


def _lib_to_text(lib) -> str:
    import io
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
    for factory in ALL_CHIPS:
        chip = factory()
        lib_id = f"{chip.library}:{chip.name}" if chip.library else chip.name
        assert generate_lib_symbol_sexp(chip, lib_id) == \
            _generate_lib_symbol_sexp_legacy(chip, lib_id), \
            f"inline sexp parity broken for {chip.name}"


# ── geometry queries (the layout-engine contract) ───────────────────────────


def test_pin_position_query():
    comp = chipdef_to_component(esp32_s3_wroom_1())
    model = SymbolModel.from_component(comp)
    assert model.pin_count == 41
    unit_id, x, y = model.pin_position("2")  # 3V3 pad
    assert unit_id >= 1
    assert x == -(15.24 / 2) - 2.54
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
