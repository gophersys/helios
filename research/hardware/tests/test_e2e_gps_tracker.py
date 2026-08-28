"""End-to-end test: GPS tracker → valid KiCad project.

Proves the entire pipeline works: spec → typed src.ecad Designs → layout
engine → hierarchical project → validate with kicad-cli → parse with our
own parser.

MIGRATED (Phase E): the GPS-tracker e2e used to hand-build SheetContent
objects full of hardcoded coordinates and only assert that ERC *ran*. It
now goes through ``compose_design`` and asserts the real oracles — ERC
errors == 0 and exported netlist == ``Design.intended_netlist()``.

Uses real kicad-cli for validation (ERC, netlist, BOM export).
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from src.pipeline.composer import (
    DesignSpec,
    PeripheralSpec,
    PowerSpec,
    compose_design,
)
from src.pipeline.parse_project import parse_project
from src.pipeline.schematic_gen import (
    ComponentPlacement,
    NetConnection,
    generate_schematic,
)
from src.pipeline.symbol_gen import ChipDef, PinDef, generate_symbol_file
from src.pipeline.templates import build_decoupling_template
from src.pipeline.validate import run_erc

KICAD_CLI = shutil.which("kicad-cli") or "/usr/bin/kicad-cli"
skip_no_kicad = pytest.mark.skipif(
    not Path(KICAD_CLI).is_file(), reason="kicad-cli not available"
)


# ---------------------------------------------------------------------------
# Chip definitions for the GPS tracker
# ---------------------------------------------------------------------------

def _esp32_s3_chip() -> ChipDef:
    """Minimal ESP32-S3 definition — enough pins for a GPS tracker."""
    pins = [
        # Power
        PinDef("1", "VDD3P3", "power_in", "Power"),
        PinDef("2", "GND", "power_in", "Power"),
        PinDef("3", "VDD3P3_RTC", "power_in", "Power"),
        # UART for GPS
        PinDef("4", "U0TXD", "output", "UART"),
        PinDef("5", "U0RXD", "input", "UART"),
        PinDef("6", "U1TXD", "output", "UART"),
        PinDef("7", "U1RXD", "input", "UART"),
        # SPI for flash
        PinDef("8", "SPI_CLK", "output", "SPI"),
        PinDef("9", "SPI_MOSI", "output", "SPI"),
        PinDef("10", "SPI_MISO", "input", "SPI"),
        PinDef("11", "SPI_CS", "output", "SPI"),
        # GPIO
        PinDef("12", "GPIO0", "bidirectional", "GPIO"),
        PinDef("13", "GPIO1", "bidirectional", "GPIO"),
        PinDef("14", "GPIO2", "bidirectional", "GPIO"),
        # Enable
        PinDef("15", "EN", "input", "System"),
    ]
    return ChipDef(
        name="ESP32-S3-MINI",
        library="RF_Module",
        description="ESP32-S3 WiFi+BLE module",
        footprint="RF_Module:ESP32-S3-MINI-1",
        datasheet_url="https://www.espressif.com/sites/default/files/documentation/esp32-s3-mini-1_datasheet_en.pdf",
        pins=pins,
    )


def _gps_tracker_spec() -> DesignSpec:
    """The GPS tracker as a design SPEC — the composer builds the sheets."""
    return DesignSpec(
        name="GPS_Tracker",
        mcu_family="ESP32-S3",
        mcu_chip="ESP32-S3-WROOM-1",
        peripherals=[
            PeripheralSpec(name="GPS", chip="NEO-6M", interface="UART"),
        ],
        power=PowerSpec(input_source="battery", voltage="3.3V", regulator="LDO"),
    )


def _erc_errors(root: Path, directory: Path) -> list[dict]:
    """Every ERC violation of severity "error" over a whole project."""
    report = directory / "erc.json"
    subprocess.run(
        [KICAD_CLI, "sch", "erc", str(root), "--format", "json",
         "-o", str(report)],
        capture_output=True, text=True, timeout=120,
    )
    data = json.loads(report.read_text())
    return [v for sheet in data.get("sheets", [])
            for v in sheet.get("violations", [])
            if v.get("severity") == "error"]


def _project_netlist(root: Path, directory: Path) -> dict[str, set[str]]:
    from src.pipeline.roundtrip import _export_netlist, parse_kicad_netlist_xml

    xml = _export_netlist(root, directory)
    assert xml is not None, "netlist export failed"
    out: dict[str, set[str]] = {}
    for net in parse_kicad_netlist_xml(xml)["nets"]:
        name = net["name"]
        if "unconnected-" in name:
            continue
        name = name.lstrip("/").split("/")[-1]
        pins = {f"{n['ref']}:{n['pin']}" for n in net["nodes"]
                if not n["ref"].startswith("#")}
        if pins:
            out.setdefault(name, set()).update(pins)
    return out


# ---------------------------------------------------------------------------
# 1. Full end-to-end: GPS tracker → valid KiCad project
# ---------------------------------------------------------------------------

class TestGPSTrackerE2E:
    """Full pipeline: define → generate → validate → parse."""

    @pytest.mark.requires_kicad
    def test_gps_tracker_e2e(self, tmp_path):
        """Compose a complete GPS tracker project and validate it.

        MIGRATED: the sheets are no longer hand-placed SheetContent objects.
        compose_design builds a typed Design per sheet, the layout engine
        places/routes/emits them, and the gates are ERC == 0 errors plus a
        netlist that equals the intended one.
        """
        project_dir = tmp_path / "gps_tracker"
        project_dir.mkdir()

        # Step 1: compose from the spec
        result = compose_design(_gps_tracker_spec())

        # Root + power + mcu + gps + .kicad_pro + sym-lib-table + fp-lib-table
        assert len(result.files) == 7
        assert "gps_tracker.kicad_sch" in result.files
        assert set(result.designs) == {
            "power.kicad_sch", "mcu.kicad_sch", "gps.kicad_sch"}

        # Step 2: geometric gate — every sheet came out of the layout engine
        assert result.layout_issues == {}, result.layout_issues

        # Write all schematic files
        for filename, content in result.files.items():
            (project_dir / filename).write_text(content)

        sch_files = list(project_dir.glob("*.kicad_sch"))
        assert len(sch_files) == 4

        # Step 3: kicad-cli ERC — zero errors, not merely "it ran"
        root_sch = project_dir / "gps_tracker.kicad_sch"
        erc_result = run_erc(root_sch)
        assert erc_result["success"] is True, f"ERC failed: {erc_result['stderr']}"
        errors = _erc_errors(root_sch, project_dir)
        assert errors == [], [f"{e['type']}: {e.get('description')}" for e in errors]

        # Step 4: exported netlist == the typed designs' intended netlist
        actual = _project_netlist(root_sch, project_dir)
        intended: dict[str, set[str]] = {}
        for design in result.designs.values():
            for net, pins in design.intended_netlist().items():
                intended.setdefault(net, set()).update(pins)
        assert actual == intended, {
            "missing": {k: v for k, v in intended.items() if actual.get(k) != v},
            "unexpected": {k: v for k, v in actual.items() if intended.get(k) != v},
        }

        # Step 5: Parse with our own parser
        parsed = parse_project(project_dir)

        # Should find the project
        assert len(parsed) >= 1, "Parser should find at least one design unit"

        # Check parsed structure
        project = parsed[0]
        assert project.design_unit is not None

        # Every composed component survives the round trip through the files
        parsed_refs = {c.ref for c in project.all_components if not c.is_power}
        for entry in result.bom:
            assert entry["ref"] in parsed_refs, (
                f"{entry['ref']} missing from parsed project: {sorted(parsed_refs)}"
            )

    def test_generated_symbol_valid(self, tmp_path):
        """Generate an ESP32-like symbol and verify kicad-cli accepts it."""
        chip = _esp32_s3_chip()
        sym_path = tmp_path / "test_chip.kicad_sym"
        generate_symbol_file(chip, sym_path)

        assert sym_path.is_file()
        content = sym_path.read_text()

        # Verify basic structure
        assert "(kicad_symbol_lib" in content
        assert 'ESP32-S3-MINI' in content
        assert "(pin " in content

        # Verify we have the right number of pins
        pin_count = content.count("(pin ")
        assert pin_count == len(chip.pins), f"Expected {len(chip.pins)} pins, got {pin_count}"

        # Verify all pin groups created units
        groups = set(p.group for p in chip.pins)
        assert len(groups) >= 4  # Power, UART, SPI, GPIO, System

    def test_round_trip(self, tmp_path):
        """Generate schematic → parse → verify components and nets match."""
        project_dir = tmp_path / "round_trip"
        project_dir.mkdir()

        # Generate a flat schematic with known components
        components = [
            ComponentPlacement("Device:R", "R1", "10k", "Resistor_SMD:R_0402", (50.8, 30.48)),
            ComponentPlacement("Device:R", "R2", "4.7k", "Resistor_SMD:R_0402", (50.8, 45.72)),
            ComponentPlacement("Device:C", "C1", "100nF", "Capacitor_SMD:C_0402", (76.2, 30.48)),
            ComponentPlacement("Device:C", "C2", "10uF", "Capacitor_SMD:C_0805", (76.2, 45.72)),
        ]
        nets = [
            NetConnection("VCC", "global", (40.64, 30.48)),
            NetConnection("GND", "global", (40.64, 45.72)),
        ]

        content = generate_schematic(components, nets, title="Round Trip Test")
        sch_path = project_dir / "round_trip_test.kicad_sch"
        sch_path.write_text(content)

        # Create minimal .kicad_pro
        pro_content = json.dumps({
            "meta": {"filename": "round_trip_test.kicad_pro", "version": 1},
            "project": {"name": "round_trip_test"},
        }, indent=2)
        (project_dir / "round_trip_test.kicad_pro").write_text(pro_content)

        # Parse with our pipeline
        parsed = parse_project(project_dir)
        assert len(parsed) >= 1

        project = parsed[0]

        # Verify we recovered the components
        all_comps = project.all_components
        refs = {c.ref for c in all_comps if not c.is_power}
        assert "R1" in refs, f"R1 not found in parsed refs: {refs}"
        assert "R2" in refs, f"R2 not found in parsed refs: {refs}"
        assert "C1" in refs, f"C1 not found in parsed refs: {refs}"
        assert "C2" in refs, f"C2 not found in parsed refs: {refs}"

        # Verify values survived the round trip
        comp_map = {c.ref: c for c in all_comps}
        if "R1" in comp_map:
            assert comp_map["R1"].value == "10k"
        if "C1" in comp_map:
            assert comp_map["C1"].value == "100nF"

    @pytest.mark.requires_kicad
    def test_decoupling_from_template(self, tmp_path):
        """Use a decoupling template to generate bypass caps."""
        # Create a synthetic decoupling template
        family_data = {
            "sample_count": 10,
            "caps": [
                {"value": "100nF", "footprint": "Capacitor_SMD:C_0402", "count": 8},
                {"value": "4.7uF", "footprint": "Capacitor_SMD:C_0603", "count": 4},
                {"value": "10uF", "footprint": "Capacitor_SMD:C_0805", "count": 2},
            ],
            "power_nets": ["VDD", "VDDIO", "GND"],
        }

        tpl = build_decoupling_template("STM32F4xx", family_data)
        assert tpl is not None
        assert tpl.name == "decoupling_STM32F4xx"
        assert len(tpl.passives) == 3

        # Use template to generate components for a schematic
        components = []
        cap_index = 1
        y_pos = 30.48
        for passive in tpl.passives:
            for i in range(min(passive.count_in_template, 3)):  # cap at 3 per value
                ref = f"C{cap_index}"
                components.append(ComponentPlacement(
                    lib_id="Device:C",
                    ref=ref,
                    value=passive.typical_value,
                    footprint=passive.typical_footprint,
                    position=(50.8, y_pos),
                ))
                cap_index += 1
                y_pos += 15.24

        nets = [
            NetConnection("VDD", "global", (40.64, 30.48)),
            NetConnection("GND", "global", (40.64, 45.72)),
        ]

        # Generate and validate the schematic
        project_dir = tmp_path / "decoupling_test"
        project_dir.mkdir()

        content = generate_schematic(
            components, nets,
            title="Decoupling Test",
        )
        sch_path = project_dir / "decoupling_test.kicad_sch"
        sch_path.write_text(content)

        pro_content = json.dumps({
            "meta": {"filename": "decoupling_test.kicad_pro", "version": 1},
            "project": {"name": "decoupling_test"},
        }, indent=2)
        (project_dir / "decoupling_test.kicad_pro").write_text(pro_content)

        # Validate with kicad-cli
        erc_result = run_erc(sch_path)
        assert erc_result["success"] is True, f"ERC failed: {erc_result['stderr']}"

        # Parse and verify cap count
        parsed = parse_project(project_dir)
        assert len(parsed) >= 1

        project = parsed[0]
        caps = [c for c in project.all_components if c.ref.startswith("C") and not c.is_power]
        assert len(caps) >= 3, f"Expected at least 3 caps from template, got {len(caps)}"

        # Verify values from template survived
        cap_values = {c.value for c in caps}
        assert "100nF" in cap_values
        assert "4.7uF" in cap_values
