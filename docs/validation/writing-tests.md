---
min_role: DEVELOPER
---
# Writing Tests

## The corekinect Library

All validation tests build on `corekinect`. Install from the internal PyPI:

```bash
pip install corekinect --index-url https://pypi.concord.local/simple/
```

The key classes:

- **TestContext** -- session state, device info, fixture handle, firmware assets
- **CloudClient** -- CoreCloud REST wrapper (device registration, FUOTA, telemetry)
- **UartDemuxer** -- parses multiplexed UART streams across APP and COMMS targets
- **PowerProfiler** -- INA219 measurements with threshold assertions
- **StageAssets** -- resolves firmware artifacts from the build system
- **Reporter** -- pushes test results back to Concord

## Package Structure

```
my-product-tests/
  concord.yaml             # Package manifest (schema 1.0)
  pyproject.toml           # Required — runner installs via pip install -e .
  conftest.py              # corekinect.test.autoconf hook
  fixtures/
    alpha_b0/
      fixture.yaml         # Hardware pin mapping
      controller.py        # Fixture driver class
  tests/
    smoke/
      test_boot.py
      test_power.py
    post/
      test_sensors.py
      test_connectivity.py
    fuota/
      test_fuota.py
```

Scaffold a new project with `corectl test init` — see the
[corectl reference](../reference/corectl.md#test-packages).

### concord.yaml

The manifest declares schema version, package metadata, product +
board target, fixture wiring, and per-stage config:

```yaml
schema: "1.0"

package:
  type: validation
  version: "1.0.0"
  framework: ">=0.3.0"

product:
  slug: alpha
  board: alpha_b0
  device:
    type_id: 42
    variant_id: 7

fixture:
  design: "Alpha B0 Validation Fixture"
  revision: "1.0"
  controller: fixtures.alpha_b0.controller.AlphaB0Fixture
  profile: fixtures/alpha_b0/fixture.yaml

stages:
  smoke:
    directory: tests/smoke
    timeout_s: 300
    hardware: [mtib]
  fuota:
    directory: tests/fuota
    timeout_s: 7200
    hardware: [mtib]
```

The `fixture.design` and `fixture.revision` fields name the
FixtureDesign that gets extracted and bound to this package on
upload — every test package owns exactly one design, and
re-uploading a dev package overwrites its design profile in place.

## Fixture Controllers

Each product needs a fixture controller -- a Python class wrapping the MTIB hardware for that specific board layout.

```python
from corekinect.test.fixture import BaseFixture

class AlphaB0Fixture(BaseFixture):
    """Alpha B0 on MTIB REV 1.2."""

    def power_on(self):
        """4.5V batteryless boot -- ch0 only, ch1 stays off."""
        # GPIO 0+1 LOW required before power-on
        self.gpio_config(0, output=True)
        self.gpio_config(1, output=True)
        self.gpio_write(0, False)
        self.gpio_write(1, False)
        self.power_enable(channel=0, voltage=4.5)
        time.sleep(3)  # Wait for boot

    def press_button(self, duration_s: float = 0.5):
        """Membrane button via GPIO 2 (active LOW)."""
        self.gpio_write(2, False)
        time.sleep(duration_s)
        self.gpio_write(2, True)

    def verify_powered(self) -> bool:
        """True if ch0 draws >5mA."""
        reading = self.power_read(channel=0)
        return reading.current_ma > 5.0
```

The `fixture.yaml` maps physical pins. The controller references those mappings.

## Writing Tests

Tests are standard pytest. The `ctx` fixture (injected by the corekinect pytest plugin) gives you the full test context:

```python
import pytest
from corekinect.test.context import TestContext

def test_dut_boots(ctx: TestContext):
    """DUT powers on and draws expected current."""
    ctx.fixture.power_on()
    assert ctx.fixture.verify_powered(), "DUT not drawing current after boot"

def test_uart_output(ctx: TestContext):
    """Boot logs appear on UART."""
    # Open UARTs BEFORE power-on -- boot messages come immediately
    ctx.uart.open(target="app")
    ctx.fixture.power_on()

    output = ctx.uart.wait_for("MCUboot", timeout=10)
    assert output, "No MCUboot banner on UART"

def test_button_press(ctx: TestContext):
    """Button press triggers expected event."""
    ctx.fixture.power_on()
    ctx.fixture.press_button(duration_s=1.0)

    output = ctx.uart.wait_for("BUTTON_PRESSED", timeout=5)
    assert output, "No button press event on UART"
```

### Running Locally

Point pytest at a live MTIB:

```bash
MTIB_HOST=10.4.45.33 MTIB_PORT=50053 \
PYTHONPATH=libs/python:libs:libs/protocols \
pytest tests/smoke/ -v
```

You need network access to the MTIB -- VPN or direct LAN.

## corectl CLI

```bash
# Upload a test package
corectl validate upload ./my-product-tests/

# List versions for a product
corectl validate versions alpha-b0

# Trigger a run
corectl validate run alpha-b0 --stage smoke --fixture bench-33

# Download results as JSON
corectl validate results <run-id> --format json
```

Install:

```bash
pip install corectl --index-url https://pypi.concord.local/simple/
```
