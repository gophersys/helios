<!-- generated-by: corectl/corekinect {{framework_version}} — do not hand-edit; run `corectl test update` to refresh -->

# TestBed Conventions

How to declare and extend a fixture for this repo. Lives in `fixtures/{{board}}/fixture.py`.

## Class shape

```python
from corekinect.testbed import ADC, GPIO, JLink, Power, UART, TestBed


class {{board_class}}TestBed(TestBed):
    name = "{{board}}-{{kind}}"
    revision = "1.0"

    # Class-level resource maps — the platform AST-extracts these at upload
    # to populate the TestBedDesign row. Add entries here when you wire new
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

    # Test-flow helpers — instance methods that orchestrate the fixture for
    # common sequences. Tests call these instead of repeating the wiring.
    def power_on(self, voltage_v: float = 4.5) -> None:
        self.gpios["boot"].config(direction="output").set_low()
        self.power["dut"].enable(voltage_v=voltage_v)
```

## Required class attributes

- **`name`** — extracted into `TestBedDesign.name`. Use `<board>-<kind>` (e.g., `alpha_b0-validation`).
- **`revision`** — extracted into `TestBedDesign.revision`. Bump when the physical fixture's wiring changes.

## Resource map keys are the API

Tests reference resources by the dict key (`slot.adc.read("battery")`). Renaming a key is a test-breaking change. Add new keys for new pins; never reuse old ones for different signals.

## Helpers, not constants

Hard-coded voltages, currents, timeouts belong in a `thresholds` class dict so the test code reads from one place:

```python
thresholds = {
    "uvlo_voltage_v": 3.4,
    "nominal_voltage_v": 3.7,
    "min_boot_current_ma": 5.0,
}
```

Tests use `slot.fixture.thresholds["nominal_voltage_v"]`.

## Multi-slot vs single-slot

Set `multi_slot:` in `concord.yaml` to declare the fixture topology:

- **Manufacturing**: typically `multi_slot: true` (panel of N DUTs, fixture has N MTIBs).
- **Validation**: typically `multi_slot: false` (single DUT bench).

The autoconf plugin parametrizes the `slot` fixture across slots when `multi_slot: true`.

## Validation gate

`corectl test validate` runs the fixture extractor against this file (AST only, no import). It checks:

- `name` and `revision` are class-level string constants.
- Each resource map declares dataclass instances of the right type.
- The fixture class is the one referenced by `concord.yaml fixture.module`.

If extraction fails, fix the file shape — the platform won't accept the package otherwise.
