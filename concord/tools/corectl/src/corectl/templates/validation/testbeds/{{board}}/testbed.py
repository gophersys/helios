"""TestBed declaration for {{board}} ({{kind}}).

Subclasses :class:`corekinect.testbed.TestBed` and declares this board
revision's DUT-side wiring (MTIB-to-DUT pin map, J-Link, UART, power
rails). The platform AST-extracts ``name``, ``revision``, and the
resource maps from this class at upload time to populate a
``TestBedDesign`` row in Concord.

This is the file referenced by ``concord.yaml`` →
``testbed.module: testbeds.{{board}}.testbed:{{board_class}}TestBed``.

See `.claude/rules/testbed-conventions.md` for the full conventions.
"""

from __future__ import annotations

from corekinect.testbed import ADC, GPIO, JLink, Power, TestBed, UART


class {{board_class}}TestBed(TestBed):
    name = "{{board}}-{{kind}}"
    revision = "1.0"

    # Class-level resource maps — the platform AST-extracts these to
    # populate the TestBedDesign row. Add entries when you wire new
    # DUT pins; remove entries when you rip them out.
    adcs = {
        "battery": ADC(channel=0, signal="VBAT"),
    }
    gpios = {
        "boot": GPIO(pin=0, role="LOW = DUT boots normally"),
    }
    uarts = {
        "app": UART(port=1, target="app-mcu"),
    }
    jlinks = {
        "app": JLink(family="NRF52"),
    }
    power = {
        "dut": Power(rail="DUT_PWR"),
    }

    # Hard-coded numerics live in `thresholds` so tests read from one
    # place. Tests use ``slot.testbed.thresholds["..."]``.
    thresholds = {
        "uvlo_voltage_v": 3.4,
        "nominal_voltage_v": 3.7,
        "min_boot_current_ma": 5.0,
    }

    # Test-flow helpers — instance methods that orchestrate the testbed
    # for common sequences. Tests call these instead of repeating the
    # wiring details.
    def power_on(self, voltage_v: float = 4.5) -> None:
        self.gpios["boot"].config(direction="output").set_low()
        self.power["dut"].enable(voltage_v=voltage_v)

    def power_off(self) -> None:
        self.power["dut"].disable()
