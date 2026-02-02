# Phase 12: Testing & Deployment

**Status:** ⬜ TODO
**Priority:** P1
**Dependencies:** All previous phases

---

## Objectives

1. Implement comprehensive unit test suite with mocks
2. Create integration test framework for real hardware
3. Build mock mode for CI/CD and development
4. Create deployment scripts and configuration
5. Document testing procedures

---

## Deliverables

### D12.1: Unit Test Framework

**Structure:**
```
tests/
├── __init__.py
├── conftest.py           # Shared fixtures
├── mocks/
│   ├── __init__.py
│   ├── hardware.py       # Mock HardwareContext
│   ├── jlink.py          # Mock J-Link
│   ├── odrive.py         # Mock ODrive
│   └── saleae.py         # Mock Logic Analyzer
├── unit/
│   ├── test_hardware_revision.py
│   ├── test_power_handler.py
│   ├── test_motion_handler.py
│   ├── test_debug_handler.py
│   └── ...
└── integration/
    ├── test_power_integration.py
    ├── test_debug_integration.py
    └── ...
```

**conftest.py:**
```python
import pytest
from unittest.mock import Mock, MagicMock
from src.hardware import HardwareContext, HardwareRevision

@pytest.fixture
def mock_hardware_rev_1_1():
    """Mock HardwareContext for REV 1.1."""
    hw = Mock(spec=HardwareContext)
    hw.revision = HardwareRevision.REV_1_1
    hw.specs = HardwareRevision.REV_1_1.value
    hw.has_gpio_expander = False
    hw.has_jlink_mux = False
    hw.has_motor_power_switch = False
    hw.calculate_voltage_wiper.return_value = 64
    return hw

@pytest.fixture
def mock_hardware_rev_1_2():
    """Mock HardwareContext for REV 1.2."""
    hw = Mock(spec=HardwareContext)
    hw.revision = HardwareRevision.REV_1_2
    hw.specs = HardwareRevision.REV_1_2.value
    hw.has_gpio_expander = True
    hw.has_jlink_mux = True
    hw.has_motor_power_switch = True
    hw.calculate_voltage_wiper.return_value = 64
    return hw

@pytest.fixture
def mock_logger():
    """Mock logger."""
    return Mock()

@pytest.fixture
def mock_jlink():
    """Mock J-Link."""
    from tests.mocks.jlink import MockJLink
    return MockJLink()

@pytest.fixture
def mock_odrive():
    """Mock ODrive."""
    from tests.mocks.odrive import MockODrive
    return MockODrive()
```

**Tests:**
```python
# tests/unit/test_hardware_revision.py
import pytest
from src.hardware import HardwareRevision, HardwareSpecs

def test_rev_1_1_specs():
    """REV 1.1 should have correct specs."""
    specs = HardwareRevision.REV_1_1.value
    assert specs.pot_resistance_ohms == 100_000
    assert specs.has_gpio_expander == False
    assert specs.has_jlink_mux == False

def test_rev_1_2_specs():
    """REV 1.2 should have correct specs."""
    specs = HardwareRevision.REV_1_2.value
    assert specs.pot_resistance_ohms == 10_000
    assert specs.has_gpio_expander == True
    assert specs.has_jlink_mux == True

def test_from_string():
    """Should parse revision from string."""
    assert HardwareRevision.from_string("1.1") == HardwareRevision.REV_1_1
    assert HardwareRevision.from_string("REV_1_2") == HardwareRevision.REV_1_2
    assert HardwareRevision.from_string("1.2") == HardwareRevision.REV_1_2

def test_from_string_invalid():
    """Should raise for invalid revision."""
    with pytest.raises(ValueError):
        HardwareRevision.from_string("2.0")
```

---

### D12.2: Mock Hardware Classes

**mocks/jlink.py:**
```python
class MockJLink:
    """Mock J-Link for testing."""

    def __init__(self):
        self.connected = False
        self.target = None
        self._memory = {}
        self._registers = {f'R{i}': 0 for i in range(16)}
        self._registers.update({'PC': 0, 'SP': 0x20010000, 'LR': 0})

    def open(self, serial_no=None):
        self.connected = True

    def close(self):
        self.connected = False

    def connect(self, chip_name):
        if not self.connected:
            raise RuntimeError("Not opened")
        self.target = chip_name

    def disconnect(self):
        self.target = None

    def halt(self):
        pass

    def go(self):
        pass

    def step(self):
        self._registers['PC'] += 4

    def reset(self, halt=True):
        self._registers['PC'] = 0
        self._registers['SP'] = 0x20010000

    def memory_read(self, addr, num_bytes):
        data = bytearray(num_bytes)
        for i in range(num_bytes):
            data[i] = self._memory.get(addr + i, 0)
        return bytes(data)

    def memory_write(self, addr, data):
        for i, byte in enumerate(data):
            self._memory[addr + i] = byte

    def register_read(self, reg_name):
        return self._registers.get(reg_name, 0)

    def register_write(self, reg_name, value):
        self._registers[reg_name] = value

    def breakpoint_set(self, addr):
        return len(self._breakpoints)

    def breakpoint_clear(self, bp_handle):
        pass

    def rtt_start(self):
        self._rtt_running = True
        return True

    def rtt_stop(self):
        self._rtt_running = False

    def rtt_read(self, buffer_index, num_bytes):
        # Return mock RTT data
        return b"[00001234] <inf> main: Hello from mock\n"

    def rtt_write(self, buffer_index, data):
        return len(data)
```

**mocks/odrive.py:**
```python
class MockODrive:
    """Mock ODrive for motion testing."""

    def __init__(self):
        self.axis0 = MockAxis()
        self.axis1 = MockAxis()

class MockAxis:
    def __init__(self):
        self.requested_state = 1  # IDLE
        self.current_state = 1
        self.controller = MockController()
        self.encoder = MockEncoder()
        self.motor = MockMotor()

class MockController:
    def __init__(self):
        self.config = MockControllerConfig()
        self.input_pos = 0.0

class MockControllerConfig:
    def __init__(self):
        self.control_mode = 3  # POSITION
        self.input_mode = 1

class MockEncoder:
    def __init__(self):
        self.pos_estimate = 0.0

class MockMotor:
    def __init__(self):
        self.current_control = MockCurrentControl()

class MockCurrentControl:
    def __init__(self):
        self.Iq_measured = 0.0
```

**mocks/hardware.py:**
```python
class MockHardwareContext:
    """Full mock HardwareContext for testing."""

    def __init__(self, revision: HardwareRevision = HardwareRevision.REV_1_2):
        self.revision = revision
        self.specs = revision.value
        self._gpio_state = {}
        self._motor_power = False
        self._jlink_mux_swapped = False

    @property
    def has_gpio_expander(self) -> bool:
        return self.specs.has_gpio_expander

    @property
    def has_jlink_mux(self) -> bool:
        return self.specs.has_jlink_mux

    @property
    def has_motor_power_switch(self) -> bool:
        return self.specs.has_motor_power_switch

    def init(self):
        pass

    def calculate_voltage_wiper(self, voltage: float) -> int:
        # Simplified calculation for testing
        if voltage <= 1.8:
            return 0
        elif voltage >= 3.3:
            return 127
        else:
            return int((voltage - 1.8) / (3.3 - 1.8) * 127)

    def set_motor_power(self, enable: bool) -> None:
        if not self.has_motor_power_switch:
            return
        self._motor_power = enable

    def get_motor_power(self) -> bool:
        return self._motor_power

    def set_jlink_mux(self, swap: bool) -> None:
        if not self.has_jlink_mux:
            raise RuntimeError("J-Link mux not available")
        self._jlink_mux_swapped = swap
```

---

### D12.3: Handler Unit Tests

**tests/unit/test_power_handler.py:**
```python
import pytest
from src.providers.handlers.power import PowerHandler

def test_power_handler_init(mock_logger, mock_hardware_rev_1_2):
    """Should initialize with hardware context."""
    handler = PowerHandler(mock_logger, mock_hardware_rev_1_2)
    assert handler.hardware == mock_hardware_rev_1_2

def test_set_voltage_uses_hardware_calculation(mock_logger, mock_hardware_rev_1_2):
    """Should use hardware context for voltage calculation."""
    handler = PowerHandler(mock_logger, mock_hardware_rev_1_2)
    mock_hardware_rev_1_2.calculate_voltage_wiper.return_value = 50

    # This would call the internal method
    # handler._set_dut_power_voltage(2.5)

    # Verify hardware calculation was used
    # mock_hardware_rev_1_2.calculate_voltage_wiper.assert_called_with(2.5)

def test_power_status_returns_all_rails(mock_logger, mock_hardware_rev_1_2):
    """Should return status for all power rails."""
    handler = PowerHandler(mock_logger, mock_hardware_rev_1_2)
    # Test PowerStatus RPC returns expected structure
```

**tests/unit/test_motion_handler.py:**
```python
import pytest
from src.providers.handlers.motion import MotionHandler

def test_motion_handler_init(mock_logger, mock_hardware_rev_1_2, mock_odrive):
    """Should initialize with dependencies."""
    handler = MotionHandler(mock_logger, mock_hardware_rev_1_2)
    assert handler.hardware == mock_hardware_rev_1_2

def test_motion_auto_enables_power_rev_1_2(mock_logger, mock_hardware_rev_1_2):
    """REV 1.2 should auto-enable motor power."""
    handler = MotionHandler(mock_logger, mock_hardware_rev_1_2)
    # handler._enable_motor_power(True)
    # mock_hardware_rev_1_2.set_motor_power.assert_called_with(True)

def test_motion_no_power_control_rev_1_1(mock_logger, mock_hardware_rev_1_1):
    """REV 1.1 should not attempt power control."""
    handler = MotionHandler(mock_logger, mock_hardware_rev_1_1)
    mock_hardware_rev_1_1.set_motor_power.assert_not_called()
```

---

### D12.4: Integration Test Framework

**tests/integration/conftest.py:**
```python
import pytest
import grpc
from mtib_v2 import mtib_v2_pb2_grpc

@pytest.fixture(scope="session")
def server_address():
    """Get server address from environment."""
    import os
    return os.environ.get("MTIB_SERVER_ADDRESS", "localhost:50051")

@pytest.fixture(scope="session")
def channel(server_address):
    """Create gRPC channel."""
    return grpc.insecure_channel(server_address)

@pytest.fixture(scope="session")
def stub(channel):
    """Create gRPC stub."""
    return mtib_v2_pb2_grpc.MtibV2Stub(channel)

@pytest.fixture(autouse=True)
def skip_without_hardware(request, stub):
    """Skip integration tests if hardware not available."""
    if request.node.get_closest_marker('requires_hardware'):
        try:
            response = stub.HealthCheck(HealthCheckRequest())
            if not response.healthy:
                pytest.skip("Hardware not healthy")
        except grpc.RpcError:
            pytest.skip("Server not available")
```

**tests/integration/test_power_integration.py:**
```python
import pytest
from mtib_v2 import mtib_v2_pb2 as pb

@pytest.mark.requires_hardware
def test_power_enable_disable(stub):
    """Should enable and disable DUT power."""
    # Enable
    response = stub.DutPowerEnable(pb.DutPowerEnableRequest(
        voltage_v=3.3,
    ))
    assert response.success

    # Check status
    status = stub.DutPowerStatus(pb.Empty())
    assert status.enabled
    assert abs(status.voltage_v - 3.3) < 0.1

    # Disable
    response = stub.DutPowerDisable(pb.Empty())
    assert response.success

@pytest.mark.requires_hardware
def test_power_voltage_range(stub):
    """Should support voltage range 1.8V - 3.3V."""
    for voltage in [1.8, 2.5, 3.0, 3.3]:
        response = stub.DutPowerEnable(pb.DutPowerEnableRequest(
            voltage_v=voltage,
        ))
        assert response.success

        status = stub.DutPowerStatus(pb.Empty())
        assert abs(status.voltage_v - voltage) < 0.15  # 150mV tolerance
```

---

### D12.5: Mock Mode

**src/modes/mock.py:**
```python
"""
Mock mode for running without hardware.

Enable with: MTIB_MOCK_MODE=1
"""
import os
from typing import Optional
from src.hardware import HardwareContext, HardwareRevision

def is_mock_mode() -> bool:
    """Check if mock mode is enabled."""
    return os.environ.get("MTIB_MOCK_MODE", "").lower() in ("1", "true", "yes")

def get_mock_revision() -> HardwareRevision:
    """Get mock hardware revision."""
    rev_str = os.environ.get("MTIB_MOCK_REVISION", "1.2")
    return HardwareRevision.from_string(rev_str)

class MockModeContext:
    """Context manager for mock mode."""

    def __init__(self, revision: Optional[HardwareRevision] = None):
        self.revision = revision or get_mock_revision()
        self._original_env = {}

    def __enter__(self):
        self._original_env = os.environ.copy()
        os.environ["MTIB_MOCK_MODE"] = "1"
        os.environ["MTIB_HARDWARE_REVISION"] = self.revision.name
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        os.environ.clear()
        os.environ.update(self._original_env)
```

**src/main.py (mock mode integration):**
```python
from src.modes.mock import is_mock_mode, get_mock_revision

def main():
    if is_mock_mode():
        logger.info("Running in MOCK MODE")
        from tests.mocks.hardware import MockHardwareContext
        hardware = MockHardwareContext(get_mock_revision())
    else:
        revision = HardwareRevision.resolve()
        hardware = HardwareContext.create(revision=revision, logger=logger)
        hardware.init()

    # ... rest of initialization
```

---

### D12.6: CI/CD Pipeline

**.github/workflows/test.yml:**
```yaml
name: Test

on:
  push:
    branches: [main, feature/*]
  pull_request:
    branches: [main]

jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt

      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --cov=src --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml

  mock-integration:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Start server in mock mode
        run: |
          MTIB_MOCK_MODE=1 python -m src.main &
          sleep 5

      - name: Run smoke tests
        run: |
          pytest tests/smoke/ -v

  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install tools
        run: pip install ruff mypy

      - name: Lint
        run: ruff check src/

      - name: Type check
        run: mypy src/ --ignore-missing-imports
```

---

### D12.7: Deployment Scripts

**scripts/deploy.sh:**
```bash
#!/bin/bash
set -e

# MTIB Server V2 Deployment Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Configuration
SERVICE_NAME="mtib-server-v2"
INSTALL_DIR="/opt/mtib-server-v2"
USER="mtib"

echo "=== MTIB Server V2 Deployment ==="

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo "This script must be run as root"
   exit 1
fi

# Create user if needed
if ! id "$USER" &>/dev/null; then
    useradd -r -s /bin/false "$USER"
    echo "Created user: $USER"
fi

# Stop existing service
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "Stopping existing service..."
    systemctl stop "$SERVICE_NAME"
fi

# Install files
echo "Installing to $INSTALL_DIR..."
mkdir -p "$INSTALL_DIR"
cp -r "$PROJECT_DIR/src" "$INSTALL_DIR/"
cp "$PROJECT_DIR/requirements.txt" "$INSTALL_DIR/"

# Create virtual environment
echo "Setting up Python environment..."
python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt"

# Set permissions
chown -R "$USER:$USER" "$INSTALL_DIR"

# Install systemd service
echo "Installing systemd service..."
cp "$SCRIPT_DIR/mtib-server-v2.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

# Start service
echo "Starting service..."
systemctl start "$SERVICE_NAME"

# Check status
sleep 2
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "=== Deployment successful ==="
    systemctl status "$SERVICE_NAME" --no-pager
else
    echo "=== Deployment failed ==="
    journalctl -u "$SERVICE_NAME" -n 50 --no-pager
    exit 1
fi
```

**scripts/mtib-server-v2.service:**
```ini
[Unit]
Description=MTIB Server V2
After=network.target

[Service]
Type=simple
User=mtib
Group=mtib
WorkingDirectory=/opt/mtib-server-v2
Environment="PYTHONPATH=/opt/mtib-server-v2"
Environment="MTIB_AUTO_DETECT_REVISION=1"
ExecStart=/opt/mtib-server-v2/venv/bin/python -m src.main
Restart=always
RestartSec=5

# Hardware access
SupplementaryGroups=i2c gpio dialout

[Install]
WantedBy=multi-user.target
```

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `tests/conftest.py` | Created | Shared test fixtures |
| `tests/mocks/*.py` | Created | Mock classes |
| `tests/unit/*.py` | Created | Unit tests |
| `tests/integration/*.py` | Created | Integration tests |
| `src/modes/mock.py` | Created | Mock mode support |
| `.github/workflows/test.yml` | Created | CI pipeline |
| `scripts/deploy.sh` | Created | Deployment script |
| `scripts/mtib-server-v2.service` | Created | Systemd service |
| `requirements-dev.txt` | Created | Dev dependencies |

---

## Requirements Files

**requirements-dev.txt:**
```
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-asyncio>=0.21.0
ruff>=0.1.0
mypy>=1.0.0
grpcio-testing>=1.50.0
```

---

## Completion Checklist

- [ ] Unit test framework setup
- [ ] Mock classes for all hardware
- [ ] Handler unit tests (>80% coverage)
- [ ] Integration test framework
- [ ] Integration tests for core RPCs
- [ ] Mock mode implementation
- [ ] CI/CD pipeline working
- [ ] Deployment scripts tested
- [ ] Documentation complete
- [ ] All tests passing on REV 1.1 and REV 1.2
