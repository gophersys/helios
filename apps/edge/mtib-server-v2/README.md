# MTIB Server V2

MTIB (Modular Test Interface Board) Server V2 is a gRPC server that provides a network API for the MTIB hardware. It supports multiple hardware revisions with automatic detection and revision-specific feature handling.

## Features

- **GPIO control:** Control the GPIO pins on the MTIB hardware
- **ADC control:** Read analog voltages from the 8-channel ADC
- **Power control:** Control DUT power with programmable voltage (0.8-5.5V)
- **Current monitoring:** Read DUT and charge current via INA219
- **Sensors:** Read onboard sensors (BME280, BMP390L, LIS2DE12)
- **Motion control:** Control the FluidNC motion system
- **Firmware flashing:** Flash firmware to target devices via J-Link

## Hardware Revisions

The server automatically detects the hardware revision at startup by probing I2C devices.

| Revision | Description | Detection |
|----------|-------------|-----------|
| REV 1.1 | Original hardware (Feb 2025) | Default if no REV 1.2 devices found |
| REV 1.2 | Updated hardware (Dec 2025) | TCA9534A (0x38) or EEPROM (0x50) present |

### Revision Differences

| Feature | REV 1.1 | REV 1.2 |
|---------|---------|---------|
| MCP4017 voltage control | 100kΩ pot | 10kΩ pot |
| GPIO expander (TCA9534A) | Not present | Present |
| EEPROM | Not present | Present |
| J-Link multiplexer | Not present | Present |
| Motor power control | Always on | Switchable |

## Configuration

### Environment Variables

```bash
# Hardware revision override (leave unset for auto-detection)
MTIB_HARDWARE_REVISION=1.2

# Disable auto-detection (use REV 1.1 as default)
MTIB_AUTO_DETECT_REVISION=false

# Server configuration
LOG_LEVEL=20              # 10=DEBUG, 20=INFO, 30=WARNING, 40=ERROR
LOG_PATH=logs
SERVER_PORT=50052
ASSETS_PATH=assets

# Optional features
METRICS_ENABLED=false
METRICS_BROKER_URL="mqtt://localhost:1883"
MOTION_ENABLED=false
```

### Auto-Detection

By default, the server probes I2C bus 1 at startup:

1. Check for TCA9534A at 0x38 → REV 1.2
2. Check for EEPROM at 0x50 → REV 1.2
3. Neither found → REV 1.1

To override auto-detection:
```bash
export MTIB_HARDWARE_REVISION=1.2
```

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    mtib-server-v2                           │
├─────────────────────────────────────────────────────────────┤
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 HardwareContext                        │  │
│  │  - Revision detection (I2C probing)                   │  │
│  │  - Revision-aware voltage calculations                │  │
│  │  - TCA9534A GPIO expander (REV 1.2)                   │  │
│  │  - Feature availability queries                       │  │
│  └───────────────────────────────────────────────────────┘  │
│                           │                                  │
│  ┌─────────┬─────────┬────┴────┬─────────┬─────────┐        │
│  │  Power  │   ADC   │  GPIO   │ Sensors │ Motion  │        │
│  │ Handler │ Handler │ Handler │ Handler │ Handler │        │
│  └────┬────┴────┬────┴────┬────┴────┬────┴────┬────┘        │
│       │         │         │         │         │              │
│  ┌────┴────┬────┴────┬────┴────┬────┴────┬────┴────┐        │
│  │ MCP4017 │ ADS1115 │  gpiod  │   IIO   │ FluidNC │        │
│  │ INA219  │         │TCA9534A │         │         │        │
│  └─────────┴─────────┴─────────┴─────────┴─────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Usage

### Running the Server

```bash
# Install dependencies
pip install -e .

# Run with auto-detection
python -m src.main

# Run with explicit revision
MTIB_HARDWARE_REVISION=1.2 python -m src.main

# Run with debug logging
LOG_LEVEL=10 python -m src.main
```

### Using the Hardware Context in Code

```python
from src.hardware import HardwareRevision, HardwareContext

# Resolve revision from environment or auto-detect
revision = HardwareRevision.resolve()
print(f"Running on {revision}")  # e.g., "REV 1.2 (Dec 2025)"

# Create hardware context
with HardwareContext.create(revision=revision) as hw:
    # Revision-aware voltage calculation
    wiper = hw.calculate_voltage_wiper(3.3)

    # Check feature availability
    if hw.has_jlink_mux:
        hw.set_jlink_mux(swap=False)

    if hw.has_motor_power_switch:
        hw.set_motor_power(enable=True)
```

## Adding New Revisions

To add support for a new hardware revision:

1. Add the revision specs in `src/hardware/revision.py`:

```python
_REV_1_3_SPECS = HardwareSpecs(
    revision_id="1.3",
    revision_name="REV 1.3 (Month Year)",
    mcp4017_pot_ohms=...,
    mcp4017_fixed_ohms=...,
    # ... other specs
    unique_i2c_devices=(I2CDevices.NEW_DEVICE,),
)
```

2. Add the enum member:

```python
class HardwareRevision(Enum):
    REV_1_1 = _REV_1_1_SPECS
    REV_1_2 = _REV_1_2_SPECS
    REV_1_3 = _REV_1_3_SPECS  # New revision
```

3. Update detection logic in `_detect_from_bus()` if needed.

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html
```

### Project Structure

```
mtib-server-v2/
├── src/
│   ├── main.py              # Entry point
│   ├── hardware/            # Hardware abstraction layer
│   │   ├── __init__.py
│   │   ├── revision.py      # HardwareRevision enum and specs
│   │   ├── context.py       # HardwareContext manager
│   │   └── tca9534a.py      # GPIO expander driver
│   ├── providers/
│   │   ├── mtib.py          # gRPC service provider
│   │   └── handlers/        # RPC handlers
│   ├── services/            # Low-level drivers
│   └── shared/              # Shared types
├── test/                    # Tests
├── assets/                  # Firmware files, configs
└── deploy/                  # Deployment scripts
```

## License

Proprietary - CoreKinect
