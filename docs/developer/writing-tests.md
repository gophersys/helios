# Writing Tests

## The corekinect Library

All test code uses the `corekinect` Python library. Install it from the internal PyPI:

```bash
pip install corekinect --index-url https://pypi.concord.local/simple/
```

The library gives you:

- **TestContext** — test session state, device info, fixture handle, firmware assets
- **CloudClient** — CoreCloud REST API wrapper (device registration, FUOTA, telemetry)
- **UartDemuxer** — UART stream parsing for multiple targets
- **PowerProfiler** — power measurement and assertions
- **StageAssets** — firmware artifact resolution from the build pipeline
- **Reporter** — test result reporting back to Concord

## Project Structure

A test package looks like this:

```
my-product-tests/
  concord.test.yaml        # Package manifest
  fixtures/
    alpha_b0/
      fixture.yaml         # Hardware layout
      controller.py        # Fixture driver
  tests/
    smoke/
      test_boot.py         # Smoke stage tests
      test_power.py
    post/
      test_sensors.py      # POST stage tests
      test_connectivity.py
    fuota/
      test_fuota.py        # FUOTA stage tests
```

### concord.test.yaml

The manifest tells Concord what's in the package:

```yaml
product: alpha-b0
revision: B0
version: 1.0.0
stages:
  - smoke
  - post
  - functional
  - fuota
fixtures:
  - alpha_b0
dependencies:
  - corekinect>=2.0.0
  - pytest>=7.0
```

## Fixture Controllers

Each product needs a fixture controller — a Python class that wraps the MTIB hardware for your specific board.

```python
from corekinect.test.fixture import BaseFixture

class AlphaB0Fixture(BaseFixture):
    """Alpha B0 fixture on MTIB REV 1.2."""

    def power_on(self):
        """Power on DUT at 4.5V (batteryless mode, ch0 only)."""
        # GPIO 0+1 must be LOW before power-on
        self.gpio_config(0, output=True)
        self.gpio_config(1, output=True)
        self.gpio_write(0, False)
        self.gpio_write(1, False)
        self.power_enable(channel=0, voltage=4.5)
        time.sleep(3)  # Wait for boot

    def press_button(self, duration_s: float = 0.5):
        """Press the membrane button via GPIO 2 (active LOW)."""
        self.gpio_write(2, False)
        time.sleep(duration_s)
        self.gpio_write(2, True)

    def verify_powered(self) -> bool:
        """Check DUT is drawing current. Returns True if >5mA on ch0."""
        reading = self.power_read(channel=0)
        return reading.current_ma > 5.0
```

The fixture config YAML maps hardware pins. The controller uses those mappings.

## Writing Tests

Tests are standard pytest. Use the `ctx` fixture (provided by the corekinect pytest plugin) to access the test context:

```python
import pytest
from corekinect.test.context import TestContext

def test_dut_boots(ctx: TestContext):
    """DUT powers on and draws expected current."""
    ctx.fixture.power_on()
    assert ctx.fixture.verify_powered(), "DUT not drawing current after boot"

def test_uart_output(ctx: TestContext):
    """DUT emits boot logs on UART."""
    # UARTs must be opened BEFORE power-on
    ctx.uart.open(target="app")
    ctx.fixture.power_on()

    output = ctx.uart.wait_for("MCUboot", timeout=10)
    assert output, "No MCUboot banner on UART"

def test_button_press(ctx: TestContext):
    """Button press triggers expected behavior."""
    ctx.fixture.power_on()
    ctx.fixture.press_button(duration_s=1.0)

    output = ctx.uart.wait_for("BUTTON_PRESSED", timeout=5)
    assert output, "No button press event on UART"
```

### Running Tests Locally

Point at a live MTIB and run pytest directly:

```bash
MTIB_HOST=10.4.45.33 MTIB_PORT=50053 \
PYTHONPATH=libs/python:libs:libs/protocols \
pytest tests/smoke/ -v
```

You'll need network access to the MTIB. VPN or direct LAN connection required.

## corectl CLI

`corectl` is the CLI for managing test packages:

```bash
# Upload a test package
corectl validate upload ./my-product-tests/

# List available versions
corectl validate versions alpha-b0

# Trigger a run from the CLI
corectl validate run alpha-b0 --stage smoke --fixture bench-33

# Download test results
corectl validate results <run-id> --format json
```

Install corectl:

```bash
pip install corectl --index-url https://pypi.concord.local/simple/
```
