"""Tests for design composer — generates wired KiCad projects from high-level specs.

Uses real wiring patterns from data/patterns/wiring_patterns.json and
real decoupling rules from data/patterns/decoupling_rules.json.

Phase E: the composer builds a typed ``src.ecad`` Design per sheet and lets
the layout engine place/route/emit it, so the gates here are the engine's
gates — geometric lint clean, kicad-cli loads, ERC errors == 0, and the
exported netlist equals ``Design.intended_netlist()``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from pathlib import Path

import pytest

from src.pipeline.composer import (
    DesignSpec,
    GeneratedProject,
    PeripheralSpec,
    PowerSpec,
    compose_design,
)

PATTERNS_PATH = Path(__file__).resolve().parent.parent / "data" / "patterns" / "wiring_patterns.json"
RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "patterns" / "decoupling_rules.json"

KICAD_CLI = shutil.which("kicad-cli") or "/usr/bin/kicad-cli"
skip_no_kicad = pytest.mark.skipif(
    not Path(KICAD_CLI).is_file(), reason="kicad-cli not available"
)


def _default_power() -> PowerSpec:
    """Standard 3.3V LDO power spec for tests."""
    return PowerSpec(input_source="USB-C", voltage="3.3V", regulator="LDO")


def _write_project(result: GeneratedProject, directory: Path) -> Path:
    """Write every generated file and return the root schematic path."""
    for filename, content in result.files.items():
        (directory / filename).write_text(content)
    root = directory / f"{result.name.replace(' ', '_').lower()}.kicad_sch"
    assert root.is_file(), f"root schematic missing: {sorted(result.files)}"
    return root


def _erc(root: Path, directory: Path) -> tuple[list[dict], str]:
    """Run kicad-cli ERC over a whole project. Returns (errors, stderr)."""
    report = directory / "erc.json"
    proc = subprocess.run(
        [KICAD_CLI, "sch", "erc", str(root), "--format", "json",
         "-o", str(report)],
        capture_output=True, text=True, timeout=120,
    )
    if not report.is_file():
        return [], proc.stderr
    data = json.loads(report.read_text())
    errors = [v for sheet in data.get("sheets", [])
              for v in sheet.get("violations", [])
              if v.get("severity") == "error"]
    return errors, proc.stderr


def _project_netlist(root: Path, directory: Path) -> dict[str, set[str]]:
    """Exported netlist of a whole project: net name → {"REF:pad"}."""
    return _project_netlist_full(root, directory)[0]


def _project_netlist_full(
    root: Path, directory: Path
) -> tuple[dict[str, set[str]], set[str]]:
    """Exported netlist plus the pins KiCad put on ``unconnected-*`` nets.

    The orphan set matters as much as the netlist. When a pin loses its
    connection — a label that was never emitted, a stub ending in nothing —
    KiCad does not drop the pin, it parks it on a pseudo-net. Discarding
    those silently converts "this pin is wired to nothing" into "this pin
    does not appear", which reads the same as a pin the design never had.
    """
    from src.pipeline.roundtrip import _export_netlist, parse_kicad_netlist_xml

    xml = _export_netlist(root, directory)
    assert xml is not None, "netlist export failed"
    out: dict[str, set[str]] = {}
    orphans: set[str] = set()
    for net in parse_kicad_netlist_xml(xml)["nets"]:
        name = net["name"]
        pins = {f"{n['ref']}:{n['pin']}" for n in net["nodes"]
                if not n["ref"].startswith("#")}
        if "unconnected-" in name:
            orphans |= pins
            continue
        name = name.lstrip("/").split("/")[-1]
        if pins:
            out.setdefault(name, set()).update(pins)
    return out, orphans


def _gps_tracker_spec() -> DesignSpec:
    return DesignSpec(
        name="GPSTracker",
        mcu_family="ESP32-S3",
        mcu_chip="ESP32-S3-WROOM-1",
        peripherals=[
            PeripheralSpec(name="GPS", chip="NEO-6M", interface="UART"),
        ],
        power=PowerSpec(input_source="battery", voltage="3.3V", regulator="LDO"),
    )


# ---------------------------------------------------------------------------
# Test 1: Simple design — ESP32 + LED, generates root + power + mcu sheets
# ---------------------------------------------------------------------------

def test_compose_simple_design():
    """ESP32 + LED → generates at least 3 sheets (root, power, mcu), valid output."""
    spec = DesignSpec(
        name="SimpleLED",
        mcu_family="ESP32",
        mcu_chip="ESP32-WROOM-32",
        peripherals=[
            PeripheralSpec(name="LED", chip="LED_Generic", interface="GPIO"),
        ],
        power=_default_power(),
    )

    result = compose_design(spec, patterns_path=PATTERNS_PATH)

    assert isinstance(result, GeneratedProject)
    assert result.name == "SimpleLED"

    # Should have root + power + mcu + led = 4 files
    assert len(result.files) >= 3, f"Expected >= 3 files, got {len(result.files)}"

    # Root file exists
    root_file = "simpleled.kicad_sch"
    assert root_file in result.files, f"Missing root file, got: {list(result.files.keys())}"

    # Power and MCU sheets exist
    assert "power.kicad_sch" in result.files
    assert "mcu.kicad_sch" in result.files

    # Root contains sheet references
    root_content = result.files[root_file]
    assert "(sheet" in root_content
    assert '"Power"' in root_content
    assert '"MCU"' in root_content

    # All .kicad_sch files are valid S-expressions
    for filename, content in result.files.items():
        if filename.endswith(".kicad_sch"):
            assert content.startswith("(kicad_sch"), f"{filename} doesn't start with (kicad_sch"
            assert content.strip().endswith(")"), f"{filename} doesn't end with )"

    # BOM is populated
    assert len(result.bom) > 0

    # Wiring notes exist
    assert len(result.wiring_notes) > 0

    # Every sub-sheet is a typed Design laid out by the engine, geometry clean
    assert result.layout_issues == {}, result.layout_issues
    assert set(result.designs) == {
        "power.kicad_sch", "mcu.kicad_sch", "led.kicad_sch"}


# ---------------------------------------------------------------------------
# Test 2: SPI peripheral — STM32F + W5500, wiring pattern applied
# ---------------------------------------------------------------------------

@pytest.mark.requires_kicad
@pytest.mark.requires_patterns
def test_compose_with_spi_peripheral():
    """STM32F + W5500 (SPI) → wiring pattern applied, net labels match.

    Requires data/patterns/wiring_patterns.json (extracted from the corpus);
    without that data this test fails exactly as it did before Phase E.
    """
    spec = DesignSpec(
        name="EtherBoard",
        mcu_family="STM32F7",
        mcu_chip="STM32F722RET6",
        peripherals=[
            PeripheralSpec(name="Ethernet", chip="W5500", interface="SPI"),
        ],
        power=_default_power(),
    )

    result = compose_design(spec, patterns_path=PATTERNS_PATH)

    # Should find the STM32F <-> W5500 SPI pattern from wiring_patterns.json
    # Check that no warnings about missing patterns
    w5500_warnings = [w for w in result.warnings if "W5500" in w]
    assert len(w5500_warnings) == 0, (
        f"Should find W5500 pattern but got warnings: {w5500_warnings}"
    )

    # Wiring notes should mention the pattern
    pattern_notes = [n for n in result.wiring_notes if "Ethernet" in n and "W5500" in n]
    assert len(pattern_notes) > 0, "Should have wiring note for W5500"

    # The peripheral sheet should have global labels matching pattern nets
    eth_file = "ethernet.kicad_sch"
    assert eth_file in result.files
    eth_content = result.files[eth_file]

    # Pattern has: CS, SCK, MISO, MOSI nets
    for net_name in ["CS", "SCK", "MISO", "MOSI"]:
        assert f'"{net_name}"' in eth_content, (
            f"Net label {net_name} missing from ethernet sheet"
        )

    # MCU sheet should also have matching labels
    mcu_content = result.files["mcu.kicad_sch"]
    for net_name in ["CS", "SCK", "MISO", "MOSI"]:
        assert f'"{net_name}"' in mcu_content, (
            f"Net label {net_name} missing from MCU sheet"
        )


# ---------------------------------------------------------------------------
# Test 3: I2C peripheral — ESP32-S3 + RTC (PCF8563T), SDA/SCL nets created
# ---------------------------------------------------------------------------

@pytest.mark.requires_kicad
@pytest.mark.requires_patterns
def test_compose_with_i2c_peripheral():
    """ESP32-S3 + RTC (I2C) → SDA/SCL nets created from pattern.

    Pattern-data test: needs data/patterns/wiring_patterns.json on disk.
    """
    spec = DesignSpec(
        name="RTCBoard",
        mcu_family="ESP32-S3",
        mcu_chip="ESP32-S3-WROOM-1",
        peripherals=[
            PeripheralSpec(name="RTC", chip="PCF8563T", interface="I2C"),
        ],
        power=_default_power(),
    )

    result = compose_design(spec, patterns_path=PATTERNS_PATH)

    # Should find the ESP32-S3 <-> PCF8563T I2C pattern
    rtc_warnings = [w for w in result.warnings if "PCF8563T" in w and "pattern" in w]
    assert len(rtc_warnings) == 0, (
        f"Should find PCF8563T pattern but got warnings: {rtc_warnings}"
    )

    # RTC sheet should have I2C nets
    rtc_file = "rtc.kicad_sch"
    assert rtc_file in result.files
    rtc_content = result.files[rtc_file]

    # Pattern has: I2C_SCL, I2C_SDA, RTC_INT nets
    assert '"I2C_SCL"' in rtc_content, "I2C_SCL missing from RTC sheet"
    assert '"I2C_SDA"' in rtc_content, "I2C_SDA missing from RTC sheet"

    # MCU sheet should also have I2C net labels
    mcu_content = result.files["mcu.kicad_sch"]
    assert '"I2C_SCL"' in mcu_content, "I2C_SCL missing from MCU sheet"
    assert '"I2C_SDA"' in mcu_content, "I2C_SDA missing from MCU sheet"


# ---------------------------------------------------------------------------
# Test 4: Unknown peripheral — generates sheet with warning
# ---------------------------------------------------------------------------

def test_compose_unknown_peripheral():
    """Peripheral not in patterns → generates sheet with warning."""
    spec = DesignSpec(
        name="UnknownBoard",
        mcu_family="ESP32-S3",
        mcu_chip="ESP32-S3-WROOM-1",
        peripherals=[
            PeripheralSpec(
                name="CustomSensor",
                chip="XYZ9999-QWERTY",
                interface="SPI",
            ),
        ],
        power=_default_power(),
    )

    result = compose_design(spec, patterns_path=PATTERNS_PATH)

    # Should have a warning about missing pattern
    assert len(result.warnings) > 0, "Should have warnings for unknown peripheral"
    xyz_warnings = [w for w in result.warnings if "XYZ9999" in w]
    assert len(xyz_warnings) > 0, f"Should warn about XYZ9999, got: {result.warnings}"

    # MIGRATED: an unknown part is now a warned generic *placeholder
    # component* (real pads, no footprint) instead of a silent "Custom:"
    # 2-pin stub, so the warning set also names the missing definition.
    assert any("no component definition" in w.lower() for w in xyz_warnings), (
        f"Should warn that no component definition exists: {xyz_warnings}"
    )

    # Peripheral sheet should still be generated with default net names
    sensor_file = "customsensor.kicad_sch"
    assert sensor_file in result.files

    sensor_content = result.files[sensor_file]
    assert "(kicad_sch" in sensor_content

    # Default SPI nets should be present (CUSTOMSENSOR_SCK, etc.)
    assert "CUSTOMSENSOR_SCK" in sensor_content
    assert "CUSTOMSENSOR_MOSI" in sensor_content
    assert "CUSTOMSENSOR_MISO" in sensor_content
    assert "CUSTOMSENSOR_CS" in sensor_content

    # ... on real pins of the placeholder, not as floating decoration
    sensor_design = result.designs[sensor_file]
    intended = sensor_design.intended_netlist()
    for role in ("SCK", "MOSI", "MISO", "CS"):
        assert intended.get(f"CUSTOMSENSOR_{role}"), (
            f"CUSTOMSENSOR_{role} carries no pin: {intended}"
        )


# ---------------------------------------------------------------------------
# Test 5: Generated output passes kicad-cli ERC
# ---------------------------------------------------------------------------

@skip_no_kicad
def test_compose_generates_valid_kicad(tmp_path):
    """MIGRATED: was "ERC must not crash"; the composed project is now built
    from real registry parts, so the gate is ERC errors == 0."""
    spec = DesignSpec(
        name="ValidTest",
        mcu_family="ESP32",
        mcu_chip="ESP32-WROOM-32",
        peripherals=[],
        power=_default_power(),
    )

    result = compose_design(spec, patterns_path=PATTERNS_PATH)
    root = _write_project(result, tmp_path)
    errors, stderr = _erc(root, tmp_path)

    assert "Unable to load" not in stderr, f"kicad-cli could not load file: {stderr}"
    assert errors == [], [f"{e['type']}: {e.get('description')}" for e in errors]


# ---------------------------------------------------------------------------
# Test 6: MCU sheet has bypass caps from decoupling rules
# ---------------------------------------------------------------------------

def test_compose_includes_decoupling():
    """MCU sheet has bypass caps from decoupling rules."""
    spec = DesignSpec(
        name="DecoupTest",
        mcu_family="ESP32-S3",
        mcu_chip="ESP32-S3-WROOM-1",
        peripherals=[],
        power=_default_power(),
    )

    result = compose_design(spec, patterns_path=PATTERNS_PATH)

    mcu_content = result.files["mcu.kicad_sch"]

    # MCU sheet should have capacitors (Device:C)
    assert '"Device:C"' in mcu_content, "MCU sheet should have decoupling caps"

    # Check BOM has caps on MCU sheet
    mcu_caps = [b for b in result.bom if b["sheet"] == "MCU" and b["lib_id"] == "Device:C"]
    assert len(mcu_caps) > 0, "BOM should include MCU decoupling caps"

    # MIGRATED: caps are typed components on the rails, so they must carry a
    # real footprint and sit on +3.3V/GND — the engine's satellite rule then
    # places them next to the MCU (no composer coordinates involved).
    for cap in mcu_caps:
        assert cap["footprint"].startswith("Capacitor_SMD:"), cap

    intended = result.designs["mcu.kicad_sch"].intended_netlist()
    cap_refs = {c["ref"] for c in mcu_caps}
    assert cap_refs <= {p.split(":")[0] for p in intended["+3.3V"]}
    assert cap_refs <= {p.split(":")[0] for p in intended["GND"]}


# ---------------------------------------------------------------------------
# Test 7: BOM includes all components from all sheets
# ---------------------------------------------------------------------------

def test_compose_bom_complete():
    """BOM includes all components from all sheets."""
    spec = DesignSpec(
        name="BOMTest",
        mcu_family="ESP32-S3",
        mcu_chip="ESP32-S3-WROOM-1",
        peripherals=[
            PeripheralSpec(name="RTC", chip="PCF8563T", interface="I2C"),
        ],
        power=_default_power(),
    )

    result = compose_design(spec, patterns_path=PATTERNS_PATH)

    # BOM should have entries
    assert len(result.bom) > 0

    # Collect unique sheets from BOM
    bom_sheets = {entry["sheet"] for entry in result.bom}

    # Should have components from Power, MCU, and RTC sheets
    assert "Power" in bom_sheets, f"BOM missing Power sheet, got: {bom_sheets}"
    assert "MCU" in bom_sheets, f"BOM missing MCU sheet, got: {bom_sheets}"
    assert "RTC" in bom_sheets, f"BOM missing RTC sheet, got: {bom_sheets}"

    # BOM should include the regulator
    reg_entries = [b for b in result.bom if "Regulator" in b["lib_id"]]
    assert len(reg_entries) > 0, "BOM should include the voltage regulator"

    # BOM should include the MCU
    mcu_entries = [b for b in result.bom if b["value"] == "ESP32-S3-WROOM-1"]
    assert len(mcu_entries) > 0, "BOM should include the MCU"

    # BOM should include the peripheral IC
    periph_entries = [b for b in result.bom if b["value"] == "PCF8563T"]
    assert len(periph_entries) > 0, "BOM should include the peripheral IC"

    # All BOM entries should have required fields
    for entry in result.bom:
        assert "ref" in entry
        assert "value" in entry
        assert "lib_id" in entry
        assert "sheet" in entry

    # MIGRATED: refs are allocated project-wide now (one KiCad annotation
    # namespace across sheets), so no two components may share a ref.
    refs = [entry["ref"] for entry in result.bom]
    assert len(refs) == len(set(refs)), f"duplicate refs in BOM: {refs}"

    # Parts that resolved to a real library entry carry a real footprint
    for entry in result.bom:
        if entry["value"] in ("ESP32-S3-WROOM-1", "AP2112K-3.3"):
            assert entry["footprint"], f"{entry} has no footprint"


# ---------------------------------------------------------------------------
# Test 8: Full GPS tracker spec → valid project
# ---------------------------------------------------------------------------

@pytest.mark.requires_kicad
@pytest.mark.requires_patterns
def test_compose_gps_tracker():
    """Full GPS tracker spec → valid project with multiple peripherals."""
    spec = DesignSpec(
        name="GPSTracker",
        mcu_family="ESP32-S3",
        mcu_chip="ESP32-S3-WROOM-1",
        peripherals=[
            PeripheralSpec(name="GPS", chip="NEO-6M", interface="UART"),
            PeripheralSpec(name="RTC", chip="PCF8563T", interface="I2C"),
            PeripheralSpec(name="StatusLED", chip="LED_Generic", interface="GPIO"),
        ],
        power=PowerSpec(
            input_source="battery",
            voltage="3.3V",
            regulator="LDO",
        ),
    )

    result = compose_design(spec, patterns_path=PATTERNS_PATH)

    assert isinstance(result, GeneratedProject)
    assert result.name == "GPSTracker"

    # Root + power + mcu + 3 peripherals = 6 files
    assert len(result.files) >= 6, (
        f"Expected >= 6 files, got {len(result.files)}: {list(result.files.keys())}"
    )

    # Check all expected files exist
    assert "gpstracker.kicad_sch" in result.files, "Missing root schematic"
    assert "power.kicad_sch" in result.files, "Missing power sheet"
    assert "mcu.kicad_sch" in result.files, "Missing MCU sheet"
    assert "gps.kicad_sch" in result.files, "Missing GPS sheet"
    assert "rtc.kicad_sch" in result.files, "Missing RTC sheet"
    assert "statusled.kicad_sch" in result.files, "Missing StatusLED sheet"

    # Root schematic references all sub-sheets
    root = result.files["gpstracker.kicad_sch"]
    for sheet_name in ["Power", "MCU", "GPS", "RTC", "StatusLED"]:
        assert f'"{sheet_name}"' in root, f"Root missing {sheet_name} sheet reference"

    # RTC should use I2C pattern (known in wiring_patterns.json) or, without
    # that data, the name-based I2C fallback (RTC_SDA / RTC_SCL).
    rtc_content = result.files["rtc.kicad_sch"]
    assert '"I2C_SCL"' in rtc_content or '"RTC_SCL"' in rtc_content, (
        "RTC sheet should have I2C net labels"
    )

    # BOM should have entries from all sheets
    bom_sheets = {entry["sheet"] for entry in result.bom}
    assert len(bom_sheets) >= 5, (
        f"BOM should cover >= 5 sheets, got: {bom_sheets}"
    )

    # Power sheet should have battery input
    power_content = result.files["power.kicad_sch"]
    assert '"VBAT"' in power_content, "Battery power should use VBAT net"

    # Wiring notes should document what was done
    assert len(result.wiring_notes) >= 3, (
        f"Expected >= 3 wiring notes, got: {result.wiring_notes}"
    )

    # MIGRATED: every sub-sheet came out of the layout engine, so the
    # geometric gate applies to all of them.
    assert result.layout_issues == {}, result.layout_issues


@skip_no_kicad
def test_compose_gps_tracker_erc_clean(tmp_path):
    """Whole GPS-tracker project: kicad-cli loads it and ERC reports 0 errors.

    Per-sheet PWR_FLAGs would collide (power symbols are global), which is
    why the composer assigns each undriven rail exactly one flag sheet — an
    invariant this gate protects.
    """
    result = compose_design(_gps_tracker_spec(), patterns_path=PATTERNS_PATH)
    root = _write_project(result, tmp_path)

    errors, stderr = _erc(root, tmp_path)
    assert "Unable to load" not in stderr, stderr
    assert errors == [], [f"{e['type']}: {e.get('description')}" for e in errors]


@skip_no_kicad
def test_compose_subsheets_load_individually(tmp_path):
    """Every generated sub-sheet is a file kicad-cli can load on its own."""
    result = compose_design(_gps_tracker_spec(), patterns_path=PATTERNS_PATH)
    _write_project(result, tmp_path)

    for filename in result.designs:
        proc = subprocess.run(
            [KICAD_CLI, "sch", "export", "netlist", str(tmp_path / filename),
             "-o", str(tmp_path / f"{filename}.net")],
            capture_output=True, text=True, timeout=120,
        )
        assert "Unable to load" not in proc.stderr, f"{filename}: {proc.stderr}"
        assert (tmp_path / f"{filename}.net").is_file(), filename


@skip_no_kicad
def test_compose_mcu_sheet_netlist_matches_intended(tmp_path):
    """The MCU sheet's exported netlist equals its Design.intended_netlist().

    Ground truth for the ESP32-S3-WROOM-1 + NEO-6M GPS tracker: pins land on
    the rails and on the cross-sheet UART nets exactly as the typed design
    says, with nothing extra.
    """
    result = compose_design(_gps_tracker_spec(), patterns_path=PATTERNS_PATH)
    root = _write_project(result, tmp_path)

    actual = _project_netlist(root, tmp_path)
    mcu_design = result.designs["mcu.kicad_sch"]
    intended = mcu_design.intended_netlist()
    mcu_refs = {c.ref for c in mcu_design.components}

    restricted: dict[str, set[str]] = {}
    for net, pins in actual.items():
        mine = {p for p in pins if p.split(":")[0] in mcu_refs}
        if mine:
            restricted[net] = mine

    assert restricted == intended, {
        "missing": {k: v for k, v in intended.items() if restricted.get(k) != v},
        "unexpected": {k: v for k, v in restricted.items() if intended.get(k) != v},
    }

    # The whole project netlist is the union of the per-sheet intended ones
    merged: dict[str, set[str]] = {}
    for design in result.designs.values():
        for net, pins in design.intended_netlist().items():
            merged.setdefault(net, set()).update(pins)
    assert actual == merged


def test_compose_uses_registry_parts_no_stubs():
    """No "Custom:" stubs and no empty IC footprints for known parts.

    NEW GATE (Phase E): the MCU resolves to the generated ESP32-S3-WROOM-1
    class from src/ecad/library, with its 41 real pads and its real
    footprint; the regulator resolves through the seed chip library.
    """
    result = compose_design(_gps_tracker_spec(), patterns_path=PATTERNS_PATH)

    for filename, content in result.files.items():
        assert "Custom:" not in content, f"{filename} still emits a Custom: stub"

    mcu = next(c for c in result.designs["mcu.kicad_sch"].components
               if c.reference_prefix == "U")
    assert mcu.part_name == "ESP32-S3-WROOM-1"
    assert mcu.lib_id == "RF_Module:ESP32-S3-WROOM-1"
    assert len(mcu.pins) == 41
    assert mcu.footprint is not None and mcu.footprint.lib_id

    regulator = next(c for c in result.designs["power.kicad_sch"].components
                     if c.reference_prefix == "U")
    assert regulator.part_name == "AP2112K-3.3"
    assert regulator.footprint is not None and regulator.footprint.lib_id

    gps = next(c for c in result.designs["gps.kicad_sch"].components
               if c.reference_prefix == "U")
    assert gps.part_name == "NEO-6M"
    assert len(gps.pins) > 2, "seed parts must not degrade to a 2-pin stub"


def test_compose_wires_uart_crossover_on_real_pins():
    """UART default wiring: the peripheral's TX drives the MCU's RX pin."""
    result = compose_design(_gps_tracker_spec(), patterns_path=PATTERNS_PATH)

    mcu_design = result.designs["mcu.kicad_sch"]
    gps_design = result.designs["gps.kicad_sch"]
    mcu = next(c for c in mcu_design.components if c.reference_prefix == "U")
    gps = next(c for c in gps_design.components if c.reference_prefix == "U")

    assert gps.pin("TXD").net is not None
    assert gps.pin("TXD").net.name == "GPS_TX"
    assert gps.pin("RXD").net.name == "GPS_RX"
    # ESP32-S3-WROOM-1: TXD0 is pad 37, RXD0 pad 36 — TX meets RX
    assert mcu.pin("RXD0").net.name == "GPS_TX"
    assert mcu.pin("TXD0").net.name == "GPS_RX"


def test_compose_pattern_pads_become_pins(tmp_path):
    """A learned pattern's pad numbers wire the real pins on both sheets."""
    patterns = {
        "pattern_count": 1,
        "patterns": [{
            "ic_a_family": "ESP32-S3",
            "ic_b_family": "NEO-6M",
            "interface_type": "UART",
            "canonical_connections": [
                {"ic_a_pad": "37", "ic_b_pad": "21", "net_name": "GPS_UART_TX"},
                {"ic_a_pad": "36", "ic_b_pad": "20", "net_name": "GPS_UART_RX"},
                {"ic_a_pad": "4", "ic_b_pad": "3", "net_name": "GPS_PPS"},
            ],
            "seen_in_projects": ["synthetic"],
            "sample_count": 3,
            "confidence": "high",
        }],
    }
    path = tmp_path / "wiring_patterns.json"
    path.write_text(json.dumps(patterns))

    result = compose_design(_gps_tracker_spec(), patterns_path=path)

    assert not [w for w in result.warnings if "No wiring pattern" in w]
    mcu_intended = result.designs["mcu.kicad_sch"].intended_netlist()
    gps_intended = result.designs["gps.kicad_sch"].intended_netlist()

    mcu_ref = next(c.ref for c in result.designs["mcu.kicad_sch"].components
                   if c.reference_prefix == "U")
    gps_ref = next(c.ref for c in result.designs["gps.kicad_sch"].components
                   if c.reference_prefix == "U")

    assert mcu_intended["GPS_UART_TX"] == {f"{mcu_ref}:37"}
    assert gps_intended["GPS_UART_TX"] == {f"{gps_ref}:21"}
    assert mcu_intended["GPS_PPS"] == {f"{mcu_ref}:4"}
    assert gps_intended["GPS_PPS"] == {f"{gps_ref}:3"}

    # ... and the wiring note records the pattern that was used
    assert any("pattern from ['synthetic']" in n for n in result.wiring_notes), (
        result.wiring_notes
    )


def test_compose_pattern_conflicting_pad_warns(tmp_path):
    """A pattern that wants a pad already on a rail is reported, not fatal."""
    patterns = {
        "pattern_count": 1,
        "patterns": [{
            "ic_a_family": "ESP32-S3",
            "ic_b_family": "NEO-6M",
            "interface_type": "UART",
            # pad 2 of the ESP32-S3-WROOM-1 is 3V3 — already on the rail
            "canonical_connections": [
                {"ic_a_pad": "2", "ic_b_pad": "20", "net_name": "GPS_CLASH"},
            ],
            "seen_in_projects": ["synthetic"],
            "sample_count": 1,
            "confidence": "low",
        }],
    }
    path = tmp_path / "wiring_patterns.json"
    path.write_text(json.dumps(patterns))

    result = compose_design(_gps_tracker_spec(), patterns_path=path)
    assert any("already carries" in w for w in result.warnings), result.warnings
    assert "GPS_CLASH" not in result.designs["mcu.kicad_sch"].intended_netlist()


def test_compose_pattern_with_unknown_pads_warns(tmp_path):
    """Pattern pads that do not exist on the resolved parts are reported."""
    patterns = {
        "pattern_count": 1,
        "patterns": [{
            "ic_a_family": "ESP32-S3",
            "ic_b_family": "NEO-6M",
            "interface_type": "UART",
            "canonical_connections": [
                {"ic_a_pad": "999", "ic_b_pad": "21", "net_name": "GPS_BOGUS"},
            ],
            "seen_in_projects": ["synthetic"],
            "sample_count": 1,
            "confidence": "low",
        }],
    }
    path = tmp_path / "wiring_patterns.json"
    path.write_text(json.dumps(patterns))

    result = compose_design(_gps_tracker_spec(), patterns_path=path)
    assert any("999" in w for w in result.warnings), result.warnings
    assert "GPS_BOGUS" not in result.designs["mcu.kicad_sch"].intended_netlist()


def test_compose_is_deterministic():
    """Same spec → byte-identical files (the engine's determinism gate)."""
    a = compose_design(_gps_tracker_spec(), patterns_path=PATTERNS_PATH)
    b = compose_design(_gps_tracker_spec(), patterns_path=PATTERNS_PATH)
    assert a.files == b.files


def test_compose_writes_no_hardcoded_coordinates():
    """Regression: the composer must not place anything itself.

    Two different peripheral sets must not land their MCU symbol at the same
    old constant (100, 80) — geometry now comes from the layout engine.
    """
    spec = _gps_tracker_spec()
    result = compose_design(spec, patterns_path=PATTERNS_PATH)
    assert "(at 100.0 80.0" not in result.files["mcu.kicad_sch"]
    assert "(at 100.0 80.0" not in result.files["gps.kicad_sch"]


def test_compose_temp_dir_write_roundtrip():
    """Files can be written to disk and read back unchanged (smoke)."""
    result = compose_design(_gps_tracker_spec(), patterns_path=PATTERNS_PATH)
    tmp_dir = Path(tempfile.mkdtemp(prefix="composer_test_"))
    try:
        for filename, content in result.files.items():
            (tmp_dir / filename).write_text(content)
            assert (tmp_dir / filename).read_text() == content
    finally:
        for f in tmp_dir.glob("*"):
            f.unlink(missing_ok=True)
        tmp_dir.rmdir()


@skip_no_kicad
def test_every_sheet_netlist_matches_intended(tmp_path):
    """EVERY sub-sheet's exported netlist equals its Design.intended_netlist().

    This is the load-bearing oracle for the composer. Layout bugs are
    geometric and ERC catches them; composer bugs are wrong parts and wrong
    nets, which ERC reports as perfectly clean. Netlist equivalence is the
    only gate that sees them.

    It is deliberately PER SHEET. The pre-existing project-wide assertion
    compares the union of every sheet's intended netlist against the whole
    exported netlist, and a union hides a per-sheet defect whenever another
    sheet contributes the same pin under the same net name — e.g. a rail
    that every sheet touches. Restricting to each sheet's own refs removes
    that cover.
    """
    result = compose_design(_gps_tracker_spec(), patterns_path=PATTERNS_PATH)
    root = _write_project(result, tmp_path)
    actual, orphans = _project_netlist_full(root, tmp_path)

    problems: dict[str, dict] = {}
    for filename, design in sorted(result.designs.items()):
        refs = {c.ref for c in design.components}
        restricted: dict[str, set[str]] = {}
        for net, pins in actual.items():
            mine = {p for p in pins if p.split(":")[0] in refs}
            if mine:
                restricted[net] = mine
        intended = design.intended_netlist()
        if restricted != intended:
            problems[filename] = {
                "missing": {k: sorted(v) for k, v in intended.items()
                            if restricted.get(k) != v},
                "unexpected": {k: sorted(v) for k, v in restricted.items()
                               if intended.get(k) != v},
            }
    assert not problems, problems


@skip_no_kicad
def test_no_design_pin_is_orphaned(tmp_path):
    """No pin the design wired may land on a KiCad ``unconnected-*`` net.

    A dropped label or a stub ending in nothing does not remove the pin from
    the netlist — KiCad parks it on a pseudo-net, which the netlist helper
    filters out. Without this assertion such a pin simply disappears from
    the comparison and looks like a pin the design never declared.
    """
    result = compose_design(_gps_tracker_spec(), patterns_path=PATTERNS_PATH)
    root = _write_project(result, tmp_path)
    _actual, orphans = _project_netlist_full(root, tmp_path)

    wired: set[str] = set()
    for design in result.designs.values():
        for pins in design.intended_netlist().values():
            wired |= pins

    stranded = sorted(orphans & wired)
    assert not stranded, (
        f"pins the design wired came back unconnected: {stranded}"
    )


def test_every_label_anchor_gets_a_hierarchical_label():
    """A hier net with N label anchors must emit N hierarchical labels.

    ``_render_sheet`` stores the rendered label in ``hier_lines[net]`` — a
    single slot — while looping over every anchor, so only the LAST one
    survived. ``emit`` then skips the router's own local labels for that net
    entirely, and a labeled net is connected ONLY through its labels, so every
    other port was left with a stub ending in nothing.

    Not reachable through DesignSpec today: compose_design puts each
    peripheral on its own sheet, and a net needs >4 ports on ONE sheet to fall
    back to labels. An I2C bus with five devices on a sheet is not exotic
    though, so this is gated at the level where it IS observable rather than
    left until the shape becomes expressible.

    The pre-existing ``missing`` check cannot see it: it only fires when a net
    has ZERO anchors.
    """
    from src.ecad import Component, Design, FootprintRef, pin
    from src.ecad.layout.engine import label_anchors, layout
    from src.pipeline.composer import _render_sheet, _SheetPlan

    class Sensor(Component):
        part_name = "SENS"
        lib_id = "Sensor:SENS"
        footprint = FootprintRef("Package_DFN_QFN", "QFN-8")
        _PIN_SPECS = (
            pin("1", "VCC", "power_in", "power"),
            pin("2", "GND", "power_in", "ground"),
            pin("3", "SDA", "bidirectional", "comm"),
            pin("4", "SCL", "input", "comm"),
        )

    design = Design("i2c-bus")
    parts = design.add(*[Sensor() for _ in range(6)])
    design.net("SDA").connect(*[p.SDA for p in parts])   # 6 ports -> labels
    design.net("SCL").connect(*[p.SCL for p in parts])
    design.net("3V3").connect(*[p.VCC for p in parts])
    design.net("GND").connect(*[p.GND for p in parts])

    anchors = label_anchors(layout(design, sheet="Bus"))
    assert len(anchors.get("SDA", [])) > 1, "fixture must produce a multi-anchor net"

    plan = _SheetPlan(filename="bus.kicad_sch", title="Bus", design=design,
                      hier={"SDA": "bidirectional", "SCL": "input"})
    text, _issues = _render_sheet(plan, flag_rails=[])

    for net in ("SDA", "SCL"):
        want = len(anchors[net])
        got = text.count(f'(hierarchical_label "{net}"')
        assert got == want, (
            f"{net}: {want} label anchors but {got} hierarchical labels — "
            f"{want - got} port(s) left with a stub connected to nothing"
        )


def test_second_bus_device_shares_the_line_instead_of_being_no_connected(tmp_path):
    """A bus is shared, not skipped, when its MCU pad is already wired.

    When a learned pattern named an MCU pad that already carried a net, the
    whole connection was dropped — including the peripheral side. The
    peripheral's bus pin was then left with pin.net is None, so emit() wrote a
    no_connect marker on it and intended_netlist() never mentioned it: a
    powered, decoupled sensor with its bus deliberately marked unconnected.
    Both ERC and netlist equivalence call that clean, which is exactly why it
    needs its own gate.

    A rail is still not shareable — see test_compose_pattern_conflicting_pad_warns.
    """
    shared_pads = [
        {"ic_a_pad": "6", "ic_b_pad": "3", "net_name": "I2C_SDA"},
        {"ic_a_pad": "7", "ic_b_pad": "4", "net_name": "I2C_SCL"},
    ]
    patterns = {
        "pattern_count": 2,
        "patterns": [
            {
                "ic_a_family": "ESP32-S3", "ic_b_family": chip,
                "interface_type": "I2C", "canonical_connections": shared_pads,
                "seen_in_projects": ["synthetic"], "sample_count": 1,
                "confidence": "high",
            }
            for chip in ("PCF8563T", "BMP280")
        ],
    }
    path = tmp_path / "wiring_patterns.json"
    path.write_text(json.dumps(patterns))

    spec = DesignSpec(
        name="TwoBus", mcu_family="ESP32-S3", mcu_chip="ESP32-S3-WROOM-1",
        peripherals=[
            PeripheralSpec(name="RTC", chip="PCF8563T", interface="I2C"),
            PeripheralSpec(name="Baro", chip="BMP280", interface="I2C"),
        ],
        power=_default_power(),
    )
    result = compose_design(spec, patterns_path=path)

    # Both peripheral sheets must carry the bus nets, and neither may have a
    # no_connect marker sitting on a pin the bus was supposed to reach.
    for filename in ("rtc.kicad_sch", "baro.kicad_sch"):
        design = result.designs[filename]
        nets = design.intended_netlist()
        on_bus = {n for n in nets if n.startswith("I2C_")}
        assert on_bus, (
            f"{filename}: bus pins were dropped — nets are {sorted(nets)}"
        )
