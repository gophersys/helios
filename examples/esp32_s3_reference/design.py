"""ESP32-S3-WROOM-1 reference design — three sheets you can open in KiCad.

This module honours the example contract (``examples/README.md``): ``build()``
returns a :class:`~src.pipeline.composer.GeneratedProject`, the same shape a
composed design returns, so ``scripts/build_examples.py`` renders, ERCs and
bundles this design exactly as it does the GPS tracker::

    from examples.esp32_s3_reference.design import build, sheets
    project = build()         # GeneratedProject: files, bom, designs, ...
    per_sheet = sheets()      # {"power": Design, "mcu": Design, "usb": Design}

:func:`sheets` is the circuit itself — one :class:`~src.ecad.design.Design`
per schematic sheet, which is what the per-sheet gates and the rule engine
work on. :func:`build` adds only the project layer:
:func:`src.pipeline.project_assembly.assemble_project` renumbers references
into one namespace, promotes the cross-sheet signals to hierarchical labels,
and emits the root sheet plus the project files.

The circuit is *authored*, not scraped: a datasheet's typical-application
figure is a drawing, and no text extractor reads topology out of a drawing.
So every component, every value and every net here is a decision with a
citation, aggregated in :data:`PROVENANCE` and rendered by
:func:`provenance_table`. Where a value could not be traced to a document it
says ``NOT VERIFIED`` in the block notes rather than pretending.

Sources
-------
DS
    Espressif *ESP32-S3-WROOM-1 & ESP32-S3-WROOM-1U Datasheet* **v1.8**.
    Section 9 / **Figure 9-1 "Peripheral Schematics"** is the typical
    application circuit this design reproduces; Table 3-1 is the pinout and
    Table 4-1 the strapping defaults.
    https://documentation.espressif.com/esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf
HDG
    Espressif *ESP32-S3 Hardware Design Guidelines — Schematic Checklist*.
    https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32s3/schematic-checklist.html
DevKitC-1
    Espressif *ESP32-S3-DevKitC-1 V1.1* reference schematic (2022-04-13,
    sheet 2 of 2). Note it is a **Micro-USB** board — it corroborates the
    power, reset and LED circuits here, and cannot corroborate anything
    USB-C.
    https://dl.espressif.com/dl/schematics/SCH_ESP32-S3-DevKitC-1_V1.1_20220413.pdf
AP2112
    Diodes/BCD *AP2112* datasheet, **DS39724 Rev. 2 - 2** (June 2017). Its
    typical application circuit is the unnumbered drawing on p. 2 captioned
    "Typical Applications Circuit (Note 4)" — the document contains no
    numbered figures.
Type-C
    *USB Type-C Cable and Connector Specification*, Release 2.0 (Aug 2019),
    §4.11.1, Table 4-25 "Sink CC Termination (Rd) Requirements", p. 236.

The three sheets
----------------
``power``
    USB ``VBUS`` → AP2112K-3.3 LDO → ``+3V3``, 10 µF + 100 nF on each side.
``mcu``
    The module, its decoupling, the EN power-on-reset RC, RESET and BOOT
    buttons, the strapping network, two indicator LEDs and the 0 Ω series
    resistors the datasheet puts in the USB data lines.
``usb``
    A USB-C receptacle: ``VBUS``/``GND``, the 5.1 kΩ sink pull-downs on
    CC1/CC2, and D+/D- shorted across the two connector orientations.

Cross-sheet net convention
--------------------------
A sheet is a standalone ``Design``; nothing in ``src/ecad`` models a sheet
port. Nets therefore cross sheets in exactly two ways:

1. **Power and ground cross as KiCad global power symbols.** ``+3V3``,
   ``GND`` and ``VBUS`` are classified as rails by
   :func:`src.ecad.layout.graph_build.is_power_net`, so the layout engine
   strips them out of the routing graph and emits a power symbol at every
   pin that touches them. Power symbols are global across a KiCad hierarchy
   — same name, same net, no hierarchical label needed. That is real KiCad
   semantics, not a convention invented here.
2. **Cross-sheet signal nets share a name.** Today that is ``USB_D+`` and
   ``USB_D-``, which leave the ``mcu`` sheet and arrive on ``usb``.
   :func:`src.ecad.layout.engine.label_anchors` reports where the engine
   named each one, and the project layer promotes that anchor to a
   ``hierarchical_label`` — the same handshake ``src/pipeline/composer.py``
   already uses.

   Which nets those are is **derived**, not declared:
   :func:`src.pipeline.project_assembly.cross_sheet_nets` calls a net a sheet
   exit exactly when a second sheet carries the same name and the name is not
   a rail. A declaration would have to be written twice — once per end — and
   the ``usb`` end was exactly the half nobody wrote. :data:`HIER_NETS` still
   declares the ``mcu`` end, for two narrower jobs: the hierarchical
   *direction*, and the ``check()`` waiver below.

Consequence, stated plainly: a net declared in :data:`HIER_NETS` has exactly
one pin on the sheet it leaves, and ``Design.check()`` calls a one-pin net an
error. That error is the hierarchy showing through, not a defect, and the
composer waives the identical one (``composer.py``: ``issue.code ==
"single-pin-net" and issue.net in plan.hier``). :func:`check_errors` applies
that one waiver and returns everything else, so the gate can demand zero.

Label-drawn nets
----------------
:data:`LABEL_NETS` names the nets drawn as **labels** rather than wires.
Two different reasons, both design intent rather than router-appeasement:

* On ``usb``, ``USB_D+``/``USB_D-`` each land on two pads of the *same*
  receptacle (the two plug orientations). A net whose ports all sit on one
  node has no channel to route through; a pair of same-named labels is both
  what the engine can express and what a human draws. ``CHASSIS`` joins them
  because it crosses that same congested pin column.
* On ``mcu``, the nets that leave the 41-pin module for a single discrete
  are labelled for the same reason a human labels them: a module symbol with
  a dozen wires radiating out of it is unreadable.

:func:`layout_sheet` applies this by setting ``NetEdge.use_labels``, the
layout IR's documented label-policy field.

Be honest about this: the router also *needs* those labels here. With the
same nets wired it emits collinear overlapping segments that ``lint_placed``
correctly reports as ``net-short``, and the minimal reproduction is one MCU
pin through a resistor into an LED — nothing to do with this circuit. That
is a layout-engine defect; it is reported in the PR rather than papered
over, and the label sets above were chosen to be the smallest that clear it.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.ecad import Component, Design, Pin
from src.ecad.circuits import (
    Block,
    Provenance,
    bypass_capacitor,
    decoupling,
    en_reset_rc,
    indicator_led,
    ldo_regulator,
    pull_resistor,
    push_button,
)
from src.ecad.layout.graph_build import build as build_graph
from src.ecad.layout.ir import PlacedSheet
from src.ecad.library import get as registry_get
from src.pipeline.composer import GeneratedProject
from src.pipeline.project_assembly import SheetSource, assemble_project

__all__ = [
    "HIER_NETS",
    "LABEL_NETS",
    "MODULE",
    "PROJECT",
    "PROVENANCE",
    "RAIL",
    "REGULATOR",
    "SHEETS",
    "SHEET_TITLES",
    "STRAPPING",
    "SUMMARY",
    "TITLE",
    "Citation",
    "StrappingDecision",
    "blocks",
    "build",
    "check_errors",
    "layout_sheet",
    "provenance_table",
    "sheets",
    "usb_pads",
]

TITLE = "ESP32-S3 Reference Design"
SUMMARY = (
    "The ESP32-S3-WROOM-1 typical application circuit, authored from the "
    "datasheet rather than scraped: USB-C in, AP2112K-3.3 LDO, the module "
    "with its decoupling, power-on-reset RC, RESET/BOOT buttons, strapping "
    "plan and indicator LEDs. Every value carries a citation."
)

# ---------------------------------------------------------------------------
# Names the design is built from
# ---------------------------------------------------------------------------

MODULE = "ESP32-S3-WROOM-1"
REGULATOR = "AP2112K-3.3"
USB_RECEPTACLE = "USB_C_Receptacle_USB2.0_16P"

RAIL = "+3V3"
GND = "GND"
VBUS = "VBUS"

SHEETS = ("power", "mcu", "usb")

#: Project name — the root files take its lower-cased form
#: (``esp32_s3_reference.kicad_pro``), which is what the bundle opens.
PROJECT = "ESP32_S3_Reference"

#: sheet → the title KiCad shows on the root sheet symbol. It is also what
#: ``kicad-cli sch export svg`` names the per-sheet SVG after.
SHEET_TITLES: dict[str, str] = {"power": "Power", "mcu": "MCU", "usb": "USB"}

#: GPIO the user LED hangs off. DevKitC-1 V1.1 drives its addressable RGB
#: LED (D6, SK68XXMINI-HS) from GPIO38 through R17 0(1%); this design reuses
#: that same free pin for a plain LED.
USER_LED_GPIO = 38

#: sheet → {net: hierarchical direction} for the nets that leave the sheet
#: *with only one pin on this side*. Two narrow jobs, both documented under
#: "Cross-sheet net convention": it gives the hierarchical direction, and it
#: is the exact set of ``single-pin-net`` errors :func:`check_errors` waives.
#: It does NOT decide which nets cross — that is derived from the sheets.
HIER_NETS: dict[str, dict[str, str]] = {
    "power": {},
    "mcu": {"USB_D+": "bidirectional", "USB_D-": "bidirectional"},
    "usb": {},
}

#: sheet → nets the layout engine must draw as labels, not wires.
LABEL_NETS: dict[str, frozenset[str]] = {
    "power": frozenset(),
    "mcu": frozenset({"BOOT", "EN", "ESP_D+", "ESP_D-", "LED_USER"}),
    "usb": frozenset({"USB_D+", "USB_D-", "CHASSIS"}),
}

_DS_URL = ("https://documentation.espressif.com/"
           "esp32-s3-wroom-1_wroom-1u_datasheet_en.pdf")
_HDG_URL = (
    "https://docs.espressif.com/projects/esp-hardware-design-guidelines/"
    "en/latest/esp32s3/schematic-checklist.html"
)
_DEVKIT_URL = (
    "https://dl.espressif.com/dl/schematics/"
    "SCH_ESP32-S3-DevKitC-1_V1.1_20220413.pdf"
)
_TYPEC_URL = ("https://www.usb.org/sites/default/files/"
              "USB%20Type-C%20Spec%20R2.0%20-%20August%202019.pdf")

PROV_DS_FIG91 = Provenance(
    source="Espressif ESP32-S3-WROOM-1/1U Datasheet v1.8",
    section="Section 9, Figure 9-1 'Peripheral Schematics' "
            "(the typical application circuit)",
    url=_DS_URL,
)
PROV_DS_STRAPPING = Provenance(
    source="Espressif ESP32-S3-WROOM-1/1U Datasheet v1.8",
    section="Chapter 4, Table 4-1 'Default Configuration of Strapping Pins' "
            "and Table 4-3 (boot mode), p. 13-14",
    url=_DS_URL,
)
PROV_TYPEC_CC = Provenance(
    source="USB Type-C Cable and Connector Specification, Release 2.0 "
           "(August 2019)",
    section="Sec. 4.11.1, Table 4-25 'Sink CC Termination (Rd) "
            "Requirements', p. 236",
    url=_TYPEC_URL,
)
PROV_SHIELD = Provenance(
    source="USB Type-C Cable and Connector Specification, Release 2.0 "
           "(August 2019)",
    section="receptacle shell / shield handling",
    url=_TYPEC_URL,
)


# ---------------------------------------------------------------------------
# Provenance ledger
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Citation:
    """One design decision, the block that made it, and where it came from."""

    sheet: str
    block: str
    refs: tuple[str, ...]
    provenance: Provenance
    notes: tuple[str, ...]

    @property
    def name(self) -> str:
        """Display name for the README's provenance list: ``sheet/block``."""
        return f"{self.sheet}/{self.block}"

    @property
    def unverified(self) -> tuple[str, ...]:
        """Notes this block flagged as not traceable to a document."""
        return tuple(n for n in self.notes
                     if n.startswith(("NOT VERIFIED", "NOT a datasheet value")))


def provenance_table(citations: list[Citation] | None = None) -> str:
    """Markdown table of every citation — for the example README / PR body."""
    rows = ["| Sheet | Block | Refs | Source |",
            "| --- | --- | --- | --- |"]
    for c in citations if citations is not None else PROVENANCE:
        rows.append(f"| {c.sheet} | `{c.block}` | {', '.join(c.refs) or '—'} "
                    f"| {c.provenance.cite()} |")
    return "\n".join(rows)


class _Ledger:
    """Collects blocks as the sheets are built."""

    def __init__(self) -> None:
        self.citations: list[Citation] = []

    def record(self, sheet: str, block: Block) -> Block:
        self.citations.append(Citation(
            sheet=sheet, block=block.name, refs=block.refs,
            provenance=block.provenance, notes=block.notes))
        return block

    def note(self, sheet: str, name: str, refs: tuple[str, ...],
             prov: Provenance, *notes: str) -> None:
        """Record a decision made by direct wiring rather than by a block."""
        self.citations.append(Citation(sheet=sheet, block=name, refs=refs,
                                       provenance=prov, notes=tuple(notes)))


# ---------------------------------------------------------------------------
# Strapping plan
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StrappingDecision:
    """What this design does about one ESP32-S3 strapping pin.

    ``level`` is the level the pin sits at when reset is released.
    ``external`` is the net an external resistor holds it at, or ``None``
    when the design deliberately relies on the chip's internal weak
    pull-up/pull-down — which is a *waiver*, and ``waiver`` says so.
    """

    gpio: int
    level: str
    external: str | None
    waiver: bool
    rationale: str


#: Every ESP32-S3 strapping pin, with a defined level or a documented waiver.
#: The set of four and their defaults are Table 4-1 "Default Configuration of
#: Strapping Pins" (DS v1.8, p. 13): GPIO0 weak pull-up = 1, GPIO3 floating,
#: GPIO45 weak pull-down = 0, GPIO46 weak pull-down = 0.
STRAPPING: tuple[StrappingDecision, ...] = (
    StrappingDecision(
        gpio=0, level="1", external=RAIL, waiver=False,
        rationale=(
            "Boot mode. HDG Strapping Pins: \"It is recommended to place a "
            "pull-up resistor at the GPIO0 pin.\" DS Table 4-3: SPI Boot is "
            "GPIO0=1 (GPIO46 any value), Joint Download Boot is GPIO0=0 and "
            "GPIO46=0. A 10k pull-up to +3V3 plus the BOOT button — which "
            "pulls it to GND while held — gives both rows deliberately. HDG "
            "also warns \"Do not add high-value capacitors at GPIO0, or the "
            "chip may enter download mode\", so this design puts no "
            "debounce capacitor on it (DevKitC-1's C13 is marked NC for the "
            "same reason)."),
    ),
    StrappingDecision(
        gpio=3, level="floating", external=None, waiver=True,
        rationale=(
            "JTAG signal source. DS Table 4-1 lists GPIO3's default "
            "configuration as \"Floating\", and DS Sec. 4.4 is explicit: "
            "\"This pin does not have any internal pull resistors and the "
            "strapping value must be controlled by the external circuit that "
            "cannot be in a high impedance state.\" WAIVER: this design "
            "leaves GPIO3 unconnected, so the strap is genuinely undefined "
            "and the eFuse setting decides the JTAG source (USB Serial/JTAG "
            "on a blank part, which is how this board is debugged). "
            "DevKitC-1 V1.1 does the same — GPIO3 runs only to a header. "
            "Drive it deliberately if you must force the JTAG source."),
    ),
    StrappingDecision(
        gpio=45, level="0", external=None, waiver=True,
        rationale=(
            "VDD_SPI voltage select. DS Table 4-1: internal weak pull-down, "
            "default bit value 0 — which selects the 3.3 V VDD_SPI that "
            "ESP32-S3-WROOM-1's in-package flash needs. WAIVER: the level is "
            "held by the chip's internal pull-down, not by a resistor on "
            "this schematic. DevKitC-1 V1.1 fits nothing on GPIO45 either. "
            "Add an external pull-down if board leakage could lift it."),
    ),
    StrappingDecision(
        gpio=46, level="0", external=None, waiver=True,
        rationale=(
            "Boot mode (with GPIO0) and ROM message printing. DS Table 4-1: "
            "internal weak pull-down, default bit value 0. DS Table 4-3 "
            "needs GPIO46=0 only for Joint Download Boot; SPI Boot accepts "
            "any value. WAIVER: the internal pull-down already provides the "
            "0, and DevKitC-1 V1.1 fits no resistor here — GPIO46 runs only "
            "to a header. Add an external pull-down if you need the download "
            "path to survive a leaky board."),
    ),
)


# ---------------------------------------------------------------------------
# Part-model queries — never hardcode a pad number
# ---------------------------------------------------------------------------

def usb_pads(module: Component | None = None) -> dict[str, str]:
    """``{"USB_D+": pad, "USB_D-": pad}`` as the *verified part model* says.

    The generated ``ESP32-S3-WROOM-1`` class is the single source of truth
    for which module pads carry USB; asking it here is what keeps the USB
    wiring from being a guess. (DS Table 3-1 has IO19/pin 13 = USB_D- and
    IO20/pin 14 = USB_D+; the assertion belongs in the test, not here.)
    """
    mcu = module if module is not None else registry_get(MODULE)()
    return {name: mcu.pin(name).pad for name in ("USB_D+", "USB_D-")}


# ---------------------------------------------------------------------------
# Sheets
# ---------------------------------------------------------------------------

def _power_sheet(ledger: _Ledger) -> Design:
    """VBUS → AP2112K-3.3 → +3V3, bulk + HF ceramic on each side."""
    d = Design("esp32-s3-ref-power")

    block = ldo_regulator(d, VBUS, RAIL, GND, part=REGULATOR,
                          cin="10uF", cout="10uF", package="0805")
    block.notes = block.notes + (
        "Corroborated by DevKitC-1 V1.1, which runs the same topology with a "
        "different regulator: U2 SGM2212-3.3 with C7 10uF/25V + C8 0.1uF on "
        "the input and C9 0.1uF + C10 10uF on the output. This design uses "
        "AP2112K-3.3 because that is the LDO the part registry can serve.",
    )
    ledger.record("power", block)

    ledger.record("power", bypass_capacitor(
        d, VBUS, GND, value="100nF", package="0402"))
    ledger.record("power", bypass_capacitor(
        d, RAIL, GND, value="100nF", package="0402"))

    ledger.note(
        "power", "esd_diode_omitted", (), Provenance(
            source="Espressif ESP32-S3 Hardware Design Guidelines — "
                   "Schematic Checklist",
            section="Power Supply", url=_HDG_URL),
        "HDG Power Supply: \"It is suggested to add an ESD protection diode "
        "and at least 10 uF capacitor at the main power entrance.\" The 10 uF "
        "is fitted (C1, the LDO input capacitor).",
        "NOT VERIFIED / NOT IMPLEMENTED: the ESD protection diode is NOT in "
        "this design. DevKitC-1 V1.1 uses LESD5D5.0CT1G TVS devices on VBUS "
        "and on each USB data line; no TVS part exists in the generated "
        "registry yet, and this design refuses to substitute a Schottky for "
        "a TVS just to have something there.",
    )
    return d


def _mcu_sheet(ledger: _Ledger) -> Design:
    """The module: decoupling, reset RC, buttons, strapping, LEDs, USB."""
    d = Design("esp32-s3-ref-mcu")
    mcu = registry_get(MODULE)()

    # DS Figure 9-1 hangs C1 22uF + C3 0.1uF off the module's 3V3 pin. Two
    # calls, so each capacitor gets the package its value really ships in.
    block = decoupling(d, mcu, RAIL, GND, per_pin="100nF", bulk=None,
                       package="C_0402")
    block.notes = block.notes + (
        "The 100nF matches C3 0.1uF at the 3V3 pin of DS Figure 9-1, and "
        "DevKitC-1 V1.1's C2 0.1uF/50V at the same pin.",
    )
    ledger.record("mcu", block)

    block = bypass_capacitor(d, RAIL, GND, value="22uF", package="0805")
    block.notes = block.notes + (
        "22uF is not a guess: DS Figure 9-1 shows C1 22uF on the module's "
        "3V3 pin alongside the 0.1uF. (DevKitC-1 V1.1 uses 10uF/25V there "
        "instead; the datasheet figure is the stronger source.)",
    )
    ledger.record("mcu", block)

    # Power-on reset RC + RESET button, both straight out of DS Figure 9-1.
    block = en_reset_rc(d, mcu.EN, RAIL, GND, net_name="EN")
    block.notes = block.notes + (
        "DS Figure 9-1 draws the same R1/C2 pair at EN with the note \"The "
        "recommended setting for the RC delay circuit is usually R = 10 kOhm "
        "and C = 1 uF\"; DevKitC-1 V1.1 fits R5 10K(1%) and C6 1uF/16V.",
    )
    ledger.record("mcu", block)

    block = push_button(d, "EN", GND, series_r="0R", debounce_c="100nF",
                        net_name="EN")
    block.notes = block.notes + (
        "series_r and debounce_c are set here rather than left at the "
        "block's DevKit-derived defaults because DS Figure 9-1's reset "
        "circuit has both: SW1 to GND through R7 0 Ohm, with C8 0.1uF from "
        "the EN net to GND. HDG's \"do not add high-value capacitors\" "
        "warning is about GPIO0, not EN — the BOOT button below stays bare.",
    )
    ledger.record("mcu", block)

    # Strapping pins that get an external resistor (GPIO0 only — the rest
    # are documented waivers, see STRAPPING).
    for decision in STRAPPING:
        if decision.external is None:
            continue
        net_name = "BOOT" if decision.gpio == 0 else f"IO{decision.gpio}"
        block = pull_resistor(d, mcu.gpio(decision.gpio), decision.external,
                              value="10k", net_name=net_name)
        block.notes = block.notes + (decision.rationale,)
        ledger.record("mcu", block)
    ledger.record("mcu", push_button(d, "BOOT", GND, net_name="BOOT"))

    # USB data lines: 0 Ohm series resistors, per the datasheet's own figure.
    pads = usb_pads(mcu)
    for name, local in (("USB_D+", "ESP_D+"), ("USB_D-", "ESP_D-")):
        res = _series_resistor(d, mcu.pin(name), local, name)
        ledger.note(
            "mcu", f"usb_series:{name}", (res.ref,), PROV_DS_FIG91,
            f"{name} lands on module pad {pads[name]}, read from the "
            f"generated {MODULE} part model rather than hardcoded.",
            "DS Figure 9-1 puts a 0 Ohm resistor in each USB data line "
            "between the connector and the module (R4 on USB_D+ into pin 14, "
            "R6 on USB_D- into pin 13). This design reproduces that.",
            "HDG USB says the same thing with a range: \"It is recommended "
            "to reserve series resistors (initial value can be 22/33 Ohm) "
            "and capacitors to ground on the traces (initially can be "
            "unpopulated), and place them close to the chip.\"",
            "NOT VERIFIED: the shunt capacitors are omitted. Both sources "
            "mark them do-not-populate (DS Figure 9-1: C5/C6 greyed with "
            "\"NC: No component\"), and this model has no DNP field, so "
            "drawing them would claim fitted parts that must not be fitted.",
        )

    # Indicators.
    block = indicator_led(d, RAIL, GND, color="red", vf=1.8, current_ma=2.0,
                          series_net="LED_PWR_A")
    block.notes = block.notes + (
        "Power LED. DevKitC-1 V1.1 uses D5 RED off VCC_3V3 through R11 "
        "5.1K(1%); 2 mA here is brighter than that but still an indicator, "
        "not a lamp.",
    )
    ledger.record("mcu", block)

    block = indicator_led(d, mcu.gpio(USER_LED_GPIO), GND, color="green",
                          net_name="LED_USER", series_net="LED_USER_A")
    block.notes = block.notes + (
        f"User LED on GPIO{USER_LED_GPIO}, the pin DevKitC-1 V1.1 uses for "
        f"its addressable RGB LED (D6 SK68XXMINI-HS via R17). 5 mA is well "
        f"inside an ESP32-S3 GPIO's drive capability.",
    )
    ledger.record("mcu", block)
    return d


def _series_resistor(design: Design, pin: Pin, local_net: str,
                     crossing_net: str) -> Component:
    """A series resistor between an MCU pin and a net that leaves the sheet."""
    from src.ecad.circuits.blocks import _resistor

    res = _resistor("0R", "0402", needed_by=f"usb_series({crossing_net})")
    design.add(res)
    design.net(local_net).connect(pin, res.pin("1"))
    design.net(crossing_net).connect(res.pin("2"))
    return res


def _shield_bridge(design: Design, connector: Component) -> Component:
    """0 Ohm link from the receptacle shell's CHASSIS net to GND."""
    from src.ecad.circuits.blocks import _resistor

    res = _resistor("0R", "0603", needed_by="shield_bridge")
    design.add(res)
    design.net("CHASSIS").connect(connector.SHIELD, res.pin("1"))
    design.net(GND).connect(res.pin("2"))
    return res


def _usb_sheet(ledger: _Ledger) -> Design:
    """USB-C receptacle: VBUS/GND, CC sink terminations, D+/D-."""
    d = Design("esp32-s3-ref-usb")
    j = registry_get(USB_RECEPTACLE)()
    d.add(j)

    d.net(VBUS).connect(j.VBUS)
    d.net(GND).connect(j.GND)
    shield_link = _shield_bridge(d, j)
    ledger.note(
        "usb", "shield_bridge", (j.ref, shield_link.ref), PROV_SHIELD,
        "All four GND pads and all four VBUS pads are commoned — a Type-C "
        "receptacle duplicates them once per orientation.",
        "The receptacle shell (pad SH) reaches GND through a 0 Ohm link on "
        "its own CHASSIS net rather than being welded to it. That is the "
        "standard shell treatment: it keeps the option of a ferrite, an "
        "R//C bridge or a full split open as a fit change instead of a "
        "board respin.",
        "NOT VERIFIED: no source mandates a particular shell treatment for "
        "this board. DevKitC-1 V1.1 cannot settle it — that board carries "
        "two Micro-USB receptacles, not USB-C.",
        "This sheet is also where the per-sheet netlist oracle earned its "
        "keep: with SH wired straight to GND, the layout engine put the "
        "shield's GND power symbol on a point it had already given a VBUS "
        "symbol and KiCad exported VBUS and GND as ONE net — every "
        "geometric lint clean. The engine now deconflicts power-symbol "
        "positions (src/ecad/layout/engine.py, _free_tap); the bridge "
        "stays because it is the better shell treatment either way.",
    )

    d.net("USB_D+").connect(j.DP)
    d.net("USB_D-").connect(j.DN)
    ledger.note(
        "usb", "usb_data_pairs", (j.ref,), PROV_TYPEC_CC,
        f"USB_D+ on pads {[p.pad for p in j.DP]}, USB_D- on pads "
        f"{[p.pad for p in j.DN]} — the two orientations of a Type-C "
        f"receptacle, shorted so a USB 2.0 cable works either way up.",
    )

    for cc, net_name in ((j.CC1, "USB_CC1"), (j.CC2, "USB_CC2")):
        block = pull_resistor(d, cc, GND, value="5.1k", net_name=net_name)
        block.provenance = PROV_TYPEC_CC
        block.notes = (
            "USB Type-C R2.0, Table 4-25 'Sink CC Termination (Rd) "
            "Requirements' (p. 236): a resistor to GND of 5.1 kOhm +/-20% "
            "is the sink Rd. Both CC1 and CC2 need one — the source only "
            "sees whichever the cable orientation lands on. Without Rd a "
            "Type-C source never turns VBUS on.",
            "Corroborated by Espressif's own USB Type-C Hardware Design "
            "Guide: \"In the device design, CC1 and CC2 need to be pulled "
            "down with 5.1 KOhm resistors.\"",
            "NOT VERIFIED: the same table also lists a +/-10% 5.1 kOhm "
            "variant, required if the sink must read the source's advertised "
            "current. This design uses the +/-20% row (it does not read Rp), "
            "and the model carries no tolerance field to record that.",
        )
        ledger.record("usb", block)
    return d


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _build_all() -> tuple[dict[str, Design], list[Citation]]:
    ledger = _Ledger()
    designs = {
        "power": _power_sheet(ledger),
        "mcu": _mcu_sheet(ledger),
        "usb": _usb_sheet(ledger),
    }
    return designs, ledger.citations


def sheets() -> dict[str, Design]:
    """The reference design: one :class:`Design` per sheet.

    Calling this twice produces two independent, structurally identical
    designs — the layout engine's UUIDs derive from the design name, so the
    emitted schematic text is byte-identical between calls.
    """
    return _build_all()[0]


def blocks() -> list[Citation]:
    """Every cited decision, for the example README's provenance section.

    ``scripts/build_examples.py`` reads ``.name`` and ``.provenance`` off
    whatever this returns. A :class:`Citation` carries both, plus the sheet
    it was made on, so the README cites the design at the granularity the
    design actually records it.
    """
    return list(PROVENANCE)


def build() -> GeneratedProject:
    """The whole project: three sheets, a root, and the KiCad project files.

    The example contract (``examples/README.md``). The circuit is
    :func:`sheets`; everything added here is the project layer — one
    designator namespace, hierarchical labels for the signals that cross,
    one PWR_FLAG per undriven rail — and it is
    :func:`~src.pipeline.project_assembly.assemble_project` that adds it,
    the same job ``compose_design`` does for a spec-driven design.

    Deterministic: the same sheets in, the same bytes out.
    """
    designs = sheets()
    sources = [
        SheetSource(
            name=name,
            title=SHEET_TITLES[name],
            design=designs[name],
            # The design's own label policy, not the stock layout: see
            # "Label-drawn nets" above.
            place=lambda d, _n=name: layout_sheet(_n, d),
            directions=HIER_NETS[name],
        )
        for name in SHEETS
    ]
    return assemble_project(PROJECT, sources, wiring_notes=[
        "Power: USB-C VBUS through an AP2112K-3.3 LDO to +3V3.",
        f"Rails ({RAIL}, {GND}, {VBUS}) cross sheets as KiCad global power "
        f"symbols, so they need no hierarchical labels.",
        "USB_D+/USB_D- cross from the mcu sheet to the usb sheet as "
        "hierarchical labels wired through the root sheet.",
    ])


def layout_sheet(name: str, design: Design | None = None) -> PlacedSheet:
    """Lay out one sheet, honouring :data:`LABEL_NETS` for that sheet.

    Everything else is the stock ``layout()`` pipeline; the only thing added
    is setting ``NetEdge.use_labels`` on the nets this design draws as
    labels.
    """
    from src.ecad.layout.engine import layout

    if name not in SHEETS:
        raise KeyError(f"no sheet {name!r}; known sheets: {list(SHEETS)}")
    d = design if design is not None else sheets()[name]
    graph = build_graph(d, sheet=name)
    labelled = LABEL_NETS[name]
    for edge in graph.edges:
        if edge.net in labelled:
            edge.use_labels = True
    return layout(d, sheet=name, graph=graph)


def check_errors(name: str, design: Design) -> list:
    """``design.check()`` errors, minus the declared cross-sheet exits.

    A net in :data:`HIER_NETS` has one pin on the sheet it leaves, which
    ``check()`` reports as ``single-pin-net``. That is the hierarchy showing
    through, not a defect — ``src/pipeline/composer.py`` waives the identical
    issue. Every other error is returned.
    """
    hier = HIER_NETS.get(name, {})
    return [i for i in design.check()
            if i.is_error
            and not (i.code == "single-pin-net" and i.net in hier)]


PROVENANCE: list[Citation] = _build_all()[1]
