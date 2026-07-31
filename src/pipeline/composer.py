"""Design composer — generates wired KiCad projects from high-level specs.

Takes a design specification (MCU + peripherals + power) and produces a
complete hierarchical KiCad project. Every sheet is a typed
:class:`src.ecad.Design`:

1. parts are resolved from the generated-component registry
   (``src.ecad.library``) first, then the seed ``chip_library``, and only
   then synthesized as a clearly-warned generic placeholder;
2. wiring patterns (``data/patterns/wiring_patterns.json``) or the
   name-based interface fallback become **Design nets on real pins**;
3. decoupling caps are real ``Device:C`` components on the rails — the
   layout engine's satellite rule places them;
4. the layout engine (``src.ecad.layout.engine``) ranks, orders, places,
   routes and emits each sheet. The composer owns hierarchy: it renders
   the hierarchical labels and hands them to ``emit`` as text.

There are no hardcoded coordinates here — geometry belongs to the engine.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from src.ecad import Component, Design, ElectricalType, PinRole
from src.ecad.emit import deterministic_uuids
from src.ecad.layout.engine import emit, label_anchors, layout
from src.ecad.layout.graph_build import is_power_net
from src.ecad.layout.lints import lint_placed
from src.ecad.library import get as registry_get
from src.pipeline.chip_library import lookup_chip
from src.pipeline.classify import extract_ic_family
from src.pipeline.decoupling_gen import decoupling_values
from src.pipeline.ecad_bridge import chipdef_to_component
from src.pipeline.pattern_merge import normalize_ic_family
from src.pipeline.schematic_gen import (
    SheetContent,
    _gen_hierarchical_label,
    generate_hierarchical_project,
)
from src.pipeline.stock_parts import Capacitor, cap_footprint
from src.pipeline.symbol_gen import ChipDef, PinDef

# ---------------------------------------------------------------------------
# Data paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_PATTERNS_PATH = _REPO_ROOT / "data" / "patterns" / "wiring_patterns.json"
_DEFAULT_RULES_PATH = _REPO_ROOT / "data" / "patterns" / "decoupling_rules.json"

# MCU library ID templates by family (identity only — the registry and the
# seed chip library own the actual pin data).
_MCU_LIB_MAP: dict[str, str] = {
    "ESP32-S3": "RF_Module:ESP32-S3-WROOM-1",
    "ESP32": "RF_Module:ESP32-WROOM-32",
    "STM32F7": "MCU_ST:STM32F722RET6",
    "STM32F4": "MCU_ST:STM32F411CEU6",
    "STM32H7": "MCU_ST:STM32H743VIT6",
    "RP2040": "MCU_RaspberryPi:RP2040",
}

# Common regulator symbols: (lib_id, footprint)
_REGULATOR_MAP: dict[str, tuple[str, str]] = {
    "LDO": ("Regulator_Linear:AP2112K-3.3", "Package_TO_SOT_SMD:SOT-23-5"),
    "DCDC": ("Regulator_Switching:TPS563200", "Package_TO_SOT_SMD:SOT-23-6"),
}

# Interface → ordered (role, name candidates) signal plan. The first
# candidate that matches a pin name wins; unmatched roles fall back to a
# free GPIO on the MCU side and are warned about on the peripheral side.
_INTERFACE_SIGNALS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "SPI": (
        ("SCK", ("SCK", "SCLK", "SPI_CLK", "SPICLK", "CLK")),
        ("MOSI", ("MOSI", "SPI_MOSI", "SDI", "DIN", "SDA")),
        ("MISO", ("MISO", "SPI_MISO", "SDO", "DOUT")),
        ("CS", ("CS", "SPI_CS", "NSS", "SSEL", "CSN", "SS")),
    ),
    "I2C": (
        ("SDA", ("SDA", "DDC_SDA", "I2C_SDA", "SDIO")),
        ("SCL", ("SCL", "DDC_SCL", "I2C_SCL", "SCK")),
    ),
    "UART": (
        ("TX", ("TXD", "TX", "TXD0", "UART_TX", "TXO")),
        ("RX", ("RXD", "RX", "RXD0", "UART_RX", "RXI")),
    ),
    "GPIO": (("IO", ("IO", "GPIO", "DATA", "A", "K")),),
}
_DEFAULT_SIGNALS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("DATA", ("DATA", "IO", "SIG")),
)

# UART is the one interface where the two ends cross over: the peripheral's
# TX drives the MCU's RX. Every other interface links same-named roles.
_UART_CROSSOVER = {"TX": "RX", "RX": "TX"}

# Strapping GPIOs are allocated last (they must be free at boot).
_LAST_RESORT_GPIOS = frozenset({0, 3, 45, 46})


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PeripheralSpec:
    """A peripheral to include in the design."""
    name: str              # human name, e.g., "IMU"
    chip: str              # chip name, e.g., "ICM-42688"
    interface: str         # "SPI", "I2C", "UART", "GPIO"


@dataclass
class PowerSpec:
    """Power supply specification."""
    input_source: str      # "USB-C", "battery", "external"
    voltage: str           # "3.3V"
    regulator: str         # "LDO" or "DCDC"


@dataclass
class DesignSpec:
    """Complete design specification."""
    name: str
    mcu_family: str        # "ESP32-S3", "STM32F7"
    mcu_chip: str          # "ESP32-S3-WROOM-1", "STM32F722RET6"
    peripherals: list[PeripheralSpec]
    power: PowerSpec


@dataclass
class GeneratedProject:
    """Output of the composer."""
    name: str
    files: dict[str, str]  # filename -> content (.kicad_sch, .kicad_pro, ...)
    bom: list[dict]        # bill of materials
    wiring_notes: list[str]  # what patterns were used
    warnings: list[str]     # what couldn't be auto-wired
    designs: dict[str, Design] = field(default_factory=dict)
    # filename -> the typed Design that sheet was generated from; the
    # ground truth for netlist checks (``Design.intended_netlist()``).
    layout_issues: dict[str, list[str]] = field(default_factory=dict)
    # filename -> geometric lint findings (empty dict == every sheet clean)


@dataclass
class _SheetPlan:
    """One sub-sheet: its typed design plus the hierarchy it exposes."""
    filename: str
    title: str
    design: Design
    hier: dict[str, str] = field(default_factory=dict)   # net -> direction


# ---------------------------------------------------------------------------
# Pattern loading and lookup
# ---------------------------------------------------------------------------

def _load_wiring_patterns(patterns_path: Path) -> dict:
    """Load and index wiring patterns by IC family pair.

    Returns a dict keyed by (ic_a_family_lower, ic_b_family_lower, interface_lower)
    mapping to the pattern entry with canonical_connections.
    """
    if not patterns_path.is_file():
        return {}

    with open(patterns_path) as f:
        data = json.load(f)

    index: dict[tuple[str, str, str], dict] = {}
    for pattern in data.get("patterns", []):
        a = pattern.get("ic_a_family", "").lower()
        b = pattern.get("ic_b_family", "").lower()
        iface = pattern.get("interface_type", "unknown").lower()
        key = (a, b, iface)
        # Keep the one with highest sample_count
        existing = index.get(key)
        if existing is None or pattern.get("sample_count", 0) > existing.get("sample_count", 0):
            index[key] = pattern

    return index


def _find_pattern(
    patterns: dict,
    mcu_family: str,
    peripheral_family: str,
    interface: str,
) -> dict | None:
    """Find the best matching wiring pattern for an MCU<->peripheral pair.

    Tries exact match first, then falls back to partial matches:
    1. Exact (mcu_family, peripheral_family, interface)
    2. Exact families with "unknown" interface
    3. Any entry with matching families regardless of interface
    """
    mcu_low = mcu_family.lower()
    periph_low = peripheral_family.lower()
    iface_low = interface.lower()

    # Exact match
    exact = patterns.get((mcu_low, periph_low, iface_low))
    if exact:
        return exact

    # Try unknown interface
    unknown = patterns.get((mcu_low, periph_low, "unknown"))
    if unknown:
        return unknown

    # Scan for any matching families
    for (a, b, _iface), pattern in patterns.items():
        if a == mcu_low and b == periph_low:
            return pattern

    # Try with normalized IC family names (e.g., "STM32F7" -> "STM32")
    norm_mcu = normalize_ic_family(mcu_family).lower()
    norm_periph = normalize_ic_family(peripheral_family).lower()

    if norm_mcu != mcu_low or norm_periph != periph_low:
        norm_exact = patterns.get((norm_mcu, norm_periph, iface_low))
        if norm_exact:
            return norm_exact

        for (a, b, _iface), pattern in patterns.items():
            if a == norm_mcu and b == norm_periph:
                return pattern

    # Try with shortened MCU family (e.g., "STM32F7" -> "STM32F")
    if len(mcu_low) > 5:
        short_mcu = mcu_low[:-1]  # drop last char
        for (a, b, _iface), pattern in patterns.items():
            if a.startswith(short_mcu) and b == periph_low:
                return pattern

    return None


# ---------------------------------------------------------------------------
# Part resolution: registry → seed chip library → generic placeholder
# ---------------------------------------------------------------------------

def _generic_chipdef(name: str, lib_id: str,
                     signals: tuple[tuple[str, tuple[str, ...]], ...]) -> ChipDef:
    """Synthesize a placeholder ChipDef: power pins + the interface signals.

    Used only for parts no library knows. The footprint is deliberately
    empty (guessing one would be worse than admitting ignorance) and the
    caller always emits a warning naming the part.
    """
    pins = [
        PinDef(number="1", name="VCC", electrical_type="power_in", group="Power"),
        PinDef(number="2", name="GND", electrical_type="power_in", group="Power"),
    ]
    for i, (role, _cands) in enumerate(signals, start=3):
        pins.append(PinDef(number=str(i), name=role,
                           electrical_type="bidirectional", group="Signal"))
    # A placeholder says so in its lib_id: "Unverified:PCF8563T" is honest
    # where the old "Custom:PCF8563T" 2-pin stub pretended to be a part.
    library = lib_id.split(":")[0] if ":" in lib_id else "Unverified"
    return ChipDef(
        name=name,
        library=library,
        description=f"{name} (placeholder — no verified pin data)",
        footprint="",
        datasheet_url="",
        pins=pins,
    )


def _resolve_component(
    name: str,
    lib_id: str,
    signals: tuple[tuple[str, tuple[str, ...]], ...],
    warnings: list[str],
) -> tuple[Component, bool]:
    """Resolve a part to a typed Component. Returns (component, is_real).

    Order: generated-component registry → seed chip library → synthesized
    placeholder (with a warning naming the part).
    """
    for key in (name, lib_id):
        if not key:
            continue
        try:
            return registry_get(key)(), True
        except (KeyError, LookupError, ImportError):
            pass

    for key in (lib_id, name):
        if not key:
            continue
        chip = lookup_chip(key)
        if chip is not None:
            return chipdef_to_component(chip), True

    warnings.append(
        f"No component definition found for {name} ({lib_id or 'no lib_id'}). "
        f"Using a generic placeholder symbol with no footprint — replace it "
        f"before manufacturing."
    )
    return chipdef_to_component(_generic_chipdef(name, lib_id, signals)), False


# ---------------------------------------------------------------------------
# Pin selection
# ---------------------------------------------------------------------------

def _norm_pin(name: str) -> str:
    return "".join(ch for ch in name.upper() if ch.isalnum())


def _candidate_pins(comp: Component, candidates: tuple[str, ...],
                    used: set[str]) -> list:
    """Pins whose name matches a candidate, best match first.

    Ranking: exact name, then a slash-separated alias (``SDA/DDC_SDA``),
    then a name that merely contains the candidate. Ties break on pad order
    so the choice is deterministic.
    """
    ranked: list[tuple[int, int, object]] = []
    for order, p in enumerate(comp.pins):
        if p.pad in used or p.role is PinRole.NC:
            continue
        norm = _norm_pin(p.name)
        aliases = {_norm_pin(part) for part in p.name.replace("|", "/").split("/")}
        aliases |= {_norm_pin(f) for f in p.spec.functions}
        for rank_base, cand in enumerate(candidates):
            c = _norm_pin(cand)
            if norm == c:
                ranked.append((0 + rank_base * 3, order, p))
                break
            if c in aliases:
                ranked.append((1 + rank_base * 3, order, p))
                break
            if c in norm:
                ranked.append((2 + rank_base * 3, order, p))
                break
    ranked.sort(key=lambda t: (t[0], t[1]))
    return [p for _r, _o, p in ranked]


def _free_gpio(comp: Component, used: set[str]):
    """Lowest unused GPIO pin (strapping pins last), else None."""
    gpios = [p for p in comp.pins
             if p.role is PinRole.GPIO and p.pad not in used]
    if not gpios:
        return None
    gpios.sort(key=lambda p: (
        (p.spec.gpio in _LAST_RESORT_GPIOS) if p.spec.gpio is not None else True,
        p.spec.gpio if p.spec.gpio is not None else 1 << 30,
        p.pad,
    ))
    return gpios[0]


def _pin_by_pad(comp: Component, pad: str):
    """The pin on a physical pad, or None (pattern pads may not exist)."""
    return next((p for p in comp.pins if p.pad == pad), None)


def _rail_pins(comp: Component) -> list:
    """Pins that want the positive rail: power_in that is not a ground."""
    return [p for p in comp.pins
            if p.etype is ElectricalType.POWER_IN and p.role is not PinRole.GROUND]


def _ground_pins(comp: Component) -> list:
    return [p for p in comp.pins if p.role is PinRole.GROUND]


def _direction_of(pin) -> str:
    """Hierarchical-label direction implied by a pin's electrical type."""
    if pin.etype is ElectricalType.OUTPUT or pin.etype is ElectricalType.POWER_OUT:
        return "output"
    if pin.etype is ElectricalType.INPUT:
        return "input"
    return "bidirectional"


# ---------------------------------------------------------------------------
# Decoupling
# ---------------------------------------------------------------------------

def _add_decoupling(design: Design, owner: Component, rail: str,
                    ground: str, rules_path: Path,
                    refs: "_RefAllocator") -> list[Capacitor]:
    """Attach decoupling caps (values from the learned rules) to a rail."""
    caps: list[Capacitor] = []
    for value, footprint_token in decoupling_values(
            owner.lib_id, [rail], rules_path=rules_path):
        cap = Capacitor(value=value, footprint=cap_footprint(footprint_token))
        cap.ref = refs.take("C")
        design.add(cap)
        design.net(rail).connect(cap.P1)
        design.net(ground).connect(cap.P2)
        caps.append(cap)
    return caps


class _RefAllocator:
    """Project-wide reference designators (sheets share one namespace)."""

    def __init__(self) -> None:
        self._counters: dict[str, int] = {}

    def take(self, prefix: str) -> str:
        n = self._counters.get(prefix, 0) + 1
        self._counters[prefix] = n
        return f"{prefix}{n}"


# ---------------------------------------------------------------------------
# Sheet builders
# ---------------------------------------------------------------------------

def _input_net(power: PowerSpec) -> str:
    source = power.input_source.upper()
    if source == "USB-C":
        return "VBUS"
    if source == "BATTERY":
        return "VBAT"
    return "VIN"


def _build_power_sheet(spec: DesignSpec, refs: _RefAllocator,
                       rules_path: Path, warnings: list[str]) -> _SheetPlan:
    """Regulator + input/output bulk caps, wired on real pins."""
    design = Design(f"{spec.name}-power")
    reg_type = spec.power.regulator.upper()
    reg_lib_id, _reg_footprint = _REGULATOR_MAP.get(reg_type, _REGULATOR_MAP["LDO"])
    reg_name = reg_lib_id.split(":")[-1]

    regulator, _real = _resolve_component(reg_name, reg_lib_id, (), warnings)
    regulator.ref = refs.take("U")
    design.add(regulator)

    vin = _input_net(spec.power)
    vout = f"+{spec.power.voltage}"

    for p in _rail_pins(regulator):
        design.net(vin).connect(p)
    for p in regulator.pins:
        if p.etype is ElectricalType.POWER_OUT:
            design.net(vout).connect(p)
        elif p.etype is ElectricalType.INPUT and _norm_pin(p.name) in ("EN", "ENABLE"):
            design.net(vin).connect(p)          # enable tied high to the input
    for p in _ground_pins(regulator):
        design.net("GND").connect(p)

    if not design.net(vout).pins:
        warnings.append(
            f"Regulator {reg_name} exposes no power_out pin; the {vout} rail "
            f"has no driver on the power sheet."
        )

    # Input and output bulk caps (real Device:C parts on the rails)
    for rail in (vin, vout):
        cap = Capacitor(value="10uF", footprint=cap_footprint("C_0805"))
        cap.ref = refs.take("C")
        design.add(cap)
        design.net(rail).connect(cap.P1)
        design.net("GND").connect(cap.P2)

    _add_decoupling(design, regulator, vout, "GND", rules_path, refs)

    return _SheetPlan(filename="power.kicad_sch", title="Power", design=design)


def _wire_interface(
    mcu: Component,
    mcu_design: Design,
    mcu_used: set[str],
    periph: Component,
    periph_design: Design,
    periph_used: set[str],
    peripheral: PeripheralSpec,
    pattern: dict | None,
    warnings: list[str],
) -> tuple[dict[str, str], dict[str, str]]:
    """Create the interface nets on both sheets. Returns (mcu_hier, periph_hier).

    With a learned pattern the pad numbers decide (``ic_a_pad`` is the MCU
    pad, ``ic_b_pad`` the peripheral pad); without one the interface's
    signal plan is matched against pin NAMES, falling back to free GPIOs on
    the MCU side.
    """
    mcu_hier: dict[str, str] = {}
    periph_hier: dict[str, str] = {}

    if pattern is not None:
        for conn in pattern.get("canonical_connections", []):
            net = conn.get("net_name")
            if not net:
                continue
            a_pad, b_pad = str(conn.get("ic_a_pad", "")), str(conn.get("ic_b_pad", ""))
            mcu_pin = _pin_by_pad(mcu, a_pad)
            periph_pin = _pin_by_pad(periph, b_pad)
            if mcu_pin is None or periph_pin is None:
                warnings.append(
                    f"Wiring pattern for {peripheral.name} references pads "
                    f"{a_pad}/{b_pad} that do not exist on "
                    f"{mcu.part_name}/{periph.part_name}; net {net} skipped."
                )
                continue
            if is_power_net(net):
                continue                      # rails are global power symbols
            if mcu_pin.net is not None or periph_pin.net is not None:
                taken = mcu_pin if mcu_pin.net is not None else periph_pin
                warnings.append(
                    f"Wiring pattern for {peripheral.name} wants {net} on "
                    f"{taken.owner_ref}.{taken.name} (pad {taken.pad}), which "
                    f"already carries {taken.net.name}; net {net} skipped."
                )
                continue
            mcu_design.net(net).connect(mcu_pin)
            periph_design.net(net).connect(periph_pin)
            mcu_used.add(mcu_pin.pad)
            periph_used.add(periph_pin.pad)
            mcu_hier[net] = _direction_of(mcu_pin)
            periph_hier[net] = _direction_of(periph_pin)
        return mcu_hier, periph_hier

    iface = peripheral.interface.upper()
    signals = _INTERFACE_SIGNALS.get(iface, _DEFAULT_SIGNALS)
    prefix = peripheral.name.upper().replace(" ", "_")
    for role, candidates in signals:
        net = f"{prefix}_{role}"
        periph_matches = _candidate_pins(periph, candidates, periph_used)
        periph_pin = periph_matches[0] if periph_matches else None
        if periph_pin is None:
            periph_pin = _free_gpio(periph, periph_used)
        if periph_pin is None:
            warnings.append(
                f"{peripheral.chip} has no pin matching {role} for the "
                f"{iface} interface; net {net} not connected on the "
                f"{peripheral.name} sheet."
            )
            continue

        mcu_role = _UART_CROSSOVER.get(role, role) if iface == "UART" else role
        mcu_candidates = dict(signals).get(mcu_role, candidates)
        mcu_matches = _candidate_pins(mcu, mcu_candidates, mcu_used)
        mcu_pin = mcu_matches[0] if mcu_matches else _free_gpio(mcu, mcu_used)
        if mcu_pin is None:
            warnings.append(
                f"{mcu.part_name} has no free pin for {net}; the "
                f"{peripheral.name} {role} line is unconnected on the MCU sheet."
            )
            continue

        periph_used.add(periph_pin.pad)
        mcu_used.add(mcu_pin.pad)
        periph_design.net(net).connect(periph_pin)
        mcu_design.net(net).connect(mcu_pin)
        periph_hier[net] = _direction_of(periph_pin)
        mcu_hier[net] = _direction_of(mcu_pin)

    return mcu_hier, periph_hier


# ---------------------------------------------------------------------------
# BOM
# ---------------------------------------------------------------------------

def _collect_bom(plans: list[_SheetPlan]) -> list[dict]:
    """Collect bill of materials from every sheet design."""
    bom: list[dict] = []
    for plan in plans:
        for comp in plan.design.components:
            bom.append({
                "ref": comp.ref,
                "value": getattr(comp, "value", "") or comp.part_name,
                "lib_id": comp.lib_id,
                "footprint": comp.footprint.lib_id if comp.footprint else "",
                "sheet": plan.title,
            })
    return bom


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _undriven_rails(plans: list[_SheetPlan]) -> dict[str, str]:
    """rail → filename of the ONE sheet that must carry its PWR_FLAG.

    A rail with a real power_out driver (the regulator output) never gets a
    flag; every other rail gets exactly one project-wide, on the first sheet
    that touches it — power symbols are global, so a second flag would be a
    power-output conflict.
    """
    driven: set[str] = set()
    owner: dict[str, str] = {}
    for plan in plans:
        for net in plan.design.nets:
            if not is_power_net(net.name):
                continue
            if any(p.etype is ElectricalType.POWER_OUT for p in net.pins):
                driven.add(net.name)
            owner.setdefault(net.name, plan.filename)
    return {rail: fn for rail, fn in owner.items() if rail not in driven}


def _render_sheet(plan: _SheetPlan, flag_rails: list[str]) -> tuple[str, list[str]]:
    """Lay out and emit one sub-sheet. Returns (text, geometric lint errors)."""
    placed = layout(plan.design, sheet=plan.title)
    issues = lint_placed(placed)
    anchors = label_anchors(placed)
    hier_lines: dict[str, str] = {}
    # Own UUID namespace: same design → same label UUIDs (determinism), but
    # never colliding with the counter emit() runs inside its own context.
    with deterministic_uuids(f"{plan.design.name}/hier"):
        for net, direction in sorted(plan.hier.items()):
            for x, y, angle in anchors.get(net, []):
                hier_lines[net] = _gen_hierarchical_label(
                    net, direction, x, y, angle)
    missing = sorted(set(plan.hier) - set(hier_lines))
    for net in missing:
        issues.append(f"unrouted-hierarchical-net: {net}")
    sheet = emit(placed, plan.design, title=plan.design.name,
                 hier_labels=hier_lines, flag_rails=flag_rails)
    return sheet.text, issues


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compose_design(
    spec: DesignSpec,
    patterns_path: Path | None = None,
    rules_path: Path | None = None,
) -> GeneratedProject:
    """Generate a complete KiCad project from a design spec.

    Steps:
    1. Load the learned wiring patterns.
    2. Resolve every part to a typed Component (registry → chip library →
       warned placeholder).
    3. Build one :class:`src.ecad.Design` per sheet — power, mcu, and one
       per peripheral — wiring patterns or the interface fallback onto real
       pins and hanging real decoupling caps off the rails.
    4. Lay each sheet out with the layout engine and emit it; the composer
       renders the hierarchical labels at the engine's own label anchors.
    5. Build the root sheet (sheet symbols + wired sheet pins) and the
       project files.

    Args:
        spec: Complete design specification.
        patterns_path: Path to wiring_patterns.json (defaults to data/patterns/).
        rules_path: Path to decoupling_rules.json (defaults to data/patterns/).

    Returns:
        GeneratedProject with all files, BOM, notes, warnings, the typed
        Design per sheet and any geometric lint findings.
    """
    patterns = _load_wiring_patterns(patterns_path or _DEFAULT_PATTERNS_PATH)
    r_path = rules_path or _DEFAULT_RULES_PATH

    wiring_notes: list[str] = []
    warnings: list[str] = []
    refs = _RefAllocator()

    voltage_net = f"+{spec.power.voltage}"

    # 1. Power sheet ────────────────────────────────────────────────────────
    power_plan = _build_power_sheet(spec, refs, r_path, warnings)
    wiring_notes.append(
        f"Power: {spec.power.regulator} regulator from {spec.power.input_source} "
        f"to {spec.power.voltage}"
    )

    # 2. MCU sheet ──────────────────────────────────────────────────────────
    mcu_design = Design(f"{spec.name}-mcu")
    mcu_lib_id = _MCU_LIB_MAP.get(spec.mcu_family, "")
    mcu_signals = tuple(
        sig
        for p in spec.peripherals
        for sig in _INTERFACE_SIGNALS.get(p.interface.upper(), _DEFAULT_SIGNALS)
    )
    mcu, _mcu_real = _resolve_component(
        spec.mcu_chip, mcu_lib_id or spec.mcu_chip, mcu_signals, warnings)
    mcu.ref = refs.take("U")
    mcu_design.add(mcu)
    for p in _rail_pins(mcu):
        mcu_design.net(voltage_net).connect(p)
    for p in _ground_pins(mcu):
        mcu_design.net("GND").connect(p)
    _add_decoupling(mcu_design, mcu, voltage_net, "GND", r_path, refs)
    mcu_plan = _SheetPlan(filename="mcu.kicad_sch", title="MCU", design=mcu_design)
    wiring_notes.append(
        f"MCU: {spec.mcu_chip} ({spec.mcu_family}) with decoupling caps"
    )

    # 3. Peripheral sheets ──────────────────────────────────────────────────
    mcu_used: set[str] = {p.pad for p in mcu.pins if p.net is not None}
    plans: list[_SheetPlan] = [power_plan, mcu_plan]

    for peripheral in spec.peripherals:
        periph_family = extract_ic_family(peripheral.chip)
        pattern = _find_pattern(
            patterns, spec.mcu_family, periph_family, peripheral.interface,
        )
        iface = peripheral.interface.upper()
        signals = _INTERFACE_SIGNALS.get(iface, _DEFAULT_SIGNALS)

        design = Design(f"{spec.name}-{peripheral.name}")
        comp, _real = _resolve_component(
            peripheral.chip, "", signals, warnings)
        comp.ref = refs.take("U")
        design.add(comp)
        for p in _rail_pins(comp):
            design.net(voltage_net).connect(p)
        for p in _ground_pins(comp):
            design.net("GND").connect(p)
        _add_decoupling(design, comp, voltage_net, "GND", r_path, refs)

        periph_used = {p.pad for p in comp.pins if p.net is not None}
        mcu_hier, periph_hier = _wire_interface(
            mcu, mcu_design, mcu_used, comp, design, periph_used,
            peripheral, pattern, warnings,
        )
        mcu_plan.hier.update(mcu_hier)

        if pattern:
            projects = pattern.get("seen_in_projects", [])
            wiring_notes.append(
                f"Peripheral '{peripheral.name}' ({peripheral.chip}): "
                f"wired using {pattern.get('interface_type', 'unknown')} "
                f"pattern from {projects}"
            )
        else:
            warnings.append(
                f"No wiring pattern found for {spec.mcu_family} <-> "
                f"{peripheral.chip} ({peripheral.interface}). "
                f"Using default {peripheral.interface} net names."
            )
            wiring_notes.append(
                f"Peripheral '{peripheral.name}' ({peripheral.chip}): "
                f"wired using default {iface} net names "
                f"({', '.join(sorted(periph_hier)) or 'no nets'})"
            )

        filename = f"{peripheral.name.lower().replace(' ', '_')}.kicad_sch"
        plans.append(_SheetPlan(filename=filename, title=peripheral.name,
                                design=design, hier=periph_hier))

    # 4. Render every sub-sheet with the layout engine ──────────────────────
    flag_owner = _undriven_rails(plans)
    rendered: dict[str, str] = {}
    layout_issues: dict[str, list[str]] = {}
    for plan in plans:
        rails = sorted(r for r, fn in flag_owner.items() if fn == plan.filename)
        text, issues = _render_sheet(plan, rails)
        rendered[plan.filename] = text
        if issues:
            layout_issues[plan.filename] = issues
            warnings.extend(f"{plan.filename}: {i}" for i in issues)
        for issue in plan.design.check():
            if issue.is_error and not (
                    issue.code == "single-pin-net" and issue.net in plan.hier):
                warnings.append(f"{plan.filename}: {issue.code}: {issue.message}")

    # 5. Root sheet + project files ─────────────────────────────────────────
    sheets = {
        plan.filename: SheetContent(
            title=plan.title, components=[], nets=[],
            hierarchical_labels=[(net, plan.hier[net]) for net in sorted(plan.hier)],
        )
        for plan in plans
    }
    project_files = generate_hierarchical_project(
        sheets, root_title=spec.name, rendered_sheets=rendered)

    return GeneratedProject(
        name=spec.name,
        files=project_files,
        bom=_collect_bom(plans),
        wiring_notes=wiring_notes,
        warnings=warnings,
        designs={plan.filename: plan.design for plan in plans},
        layout_issues=layout_issues,
    )
