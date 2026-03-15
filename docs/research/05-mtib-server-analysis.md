# MTIB Server Analysis

## Overview

The MTIB (Manufacturing Test & Integration Bench) is a gRPC server running on embedded hardware (Verdin iMX8M Mini) that provides physical access to device-under-test (DUT) hardware. Two versions exist; V2 is the current/active one.

## Hardware Platform

- **SoM**: Verdin iMX8M Mini (ARM Cortex-A53)
- **OS**: Custom Yocto (Torizon-based) with K3s
- **Current Revision**: REV 1.2
- **Previous**: REV 1.1

### REV 1.2 Hardware
- MCP4017 potentiometer (10kΩ)
- TCA9534A GPIO expander (I2C 0x38)
- EEPROM (I2C 0x50)
- J-Link mux via TCA9534A P0
- Motor power switch via TCA9534A P2
- Fixed UART pin assignments

### REV 1.1 Hardware
- Different potentiometer (100kΩ)
- No GPIO expander, EEPROM, or J-Link mux
- Reversed UART pins (required DTS overlay)

## Server Versions

### V1 (Legacy)
- **Location**: `apps/edge/mtib-server/`
- **Port**: 50053 (gRPC)
- **Protocol**: ~338 lines, ~20 RPCs
- **Used by**: Current sigma5 validation

### V2 (Current)
- **Location**: `apps/edge/mtib-server-v2/`
- **Port**: 50052 (gRPC)
- **Protocol**: 1,481 lines, 71 RPCs
- **Protocol File**: `libs/protocols/mtib_v2/mtib_v2.proto`

## V2 Protocol - Complete RPC Categories

### 1. Debug Probe Interface
- `DebugConnect`, `DebugHalt`, `DebugResume`, `DebugReset`
- Register access, memory read/write
- Breakpoints, watchpoints, backtrace
- Supports: J-Link, CMSIS-DAP, STLink

### 2. Flash Programming
- `FlashInfo`, `FlashErase`, `FlashWrite`, `FlashProgram`
- Full-chip or sector erase
- Auto-verify and reset after flash

### 3. RTT (Real-Time Transfer)
- Segger RTT protocol
- Bidirectional streaming on multiple channels
- Zero-overhead logging from firmware

### 4. UART Interface
- Configurable baud, parity, flow control
- Bidirectional streaming with timestamps
- Essential for Twister console harness

### 5. Power Measurement
- 4+ channels: MAIN, VBAT, 3V3, 1V8, custom
- High-speed sampling (up to 100kHz, PPK2-class)
- Current/voltage with statistics (avg, min, max, energy_µJ)

### 6. Digital Signal Analyzer
- Multi-backend: Saleae, sigrok, simulation
- Configurable capture: sample rate, duration, trigger, memory limit
- Protocol decoding: I2C, SPI, UART, CAN, LIN, I2S, PWM
- Export: CSV, VCD, native formats

### 7. GPIO Control
- Configure, read, write, watch edges
- Used for button simulation, LED verification

### 8. Bus Masters
- I2C, SPI, CAN transactional access
- Direct bus access bypassing DUT firmware

### 9. BLE Interface
- Scan, connect, GATT discovery
- Characteristic read/write
- For testing BLE functionality

### 10. Zephyr Integration
- **Shell command execution**: Send commands to Zephyr shell
- **Logging capture**: Filter and capture Zephyr log output
- **Devicetree inspection**: Query DT nodes at runtime
- **Thread state monitoring**: Check Zephyr thread states
- **Twister test execution**: `mtib_twister_run` RPC

### 11. Observability
- Real-time streaming of power, GPIO, UART, system metrics
- InfluxDB integration for telemetry storage

## MCP Server

- **Location**: `apps/edge/mtib-mcp-server/`
- **22 tools** for AI-assisted debugging
- Wraps MTIB V2 gRPC client with natural language interface

## Deployment

### Edge Deployment (Validation)
File: `deploy/edge/mtib-server/validation.yaml`

```yaml
nodeSelector:
  corekinect.com/role: edge
  corekinect.com/purpose: validation
tolerations:
  - key: "corekinect.com/role"
    value: "edge"
    effect: "NoSchedule"
securityContext:
  privileged: true  # Hardware access
resources:
  requests: { cpu: 1000m, memory: 1000Mi }
  limits: { cpu: 2000m, memory: 2000Mi }
volumes:
  - /dev              # Device access
  - /var/log/runner   # Test logs
  - /var/fw_files/    # Firmware staging
  - /sys/class/gpio   # GPIO sysfs
  - /sys/bus/iio      # IIO sensors
```

### V2 Dev Deployment
File: `deploy/edge/mtib-server-v2/dev.yaml`

- Pinned to specific hardware: `verdin-imx8mm-15702160`
- Init container: remounts /sys as writable
- Hardware revision: 1.2
- Optional InfluxDB metrics

### Dockerfile (V2)
```
FROM ubuntu:22.04
+ J-Link SDK V796j
+ nRF command-line tools 10.24.2 + nrfjprog
+ Python 3 + gRPC + libgpiod + i2c-tools
+ FluidNC motion support
EXPOSE 50052
CMD ["python3", "src/main.py"]
```

## Yocto OS (MTIB Hardware)

Location: `concord-os-yocto/meta-corekinect/`

```
SUMMARY = "CoreKinect MTIB Image"
DISTRO_FEATURES += " k3s seccomp virtualization"
INIT_MANAGER = "systemd"
IMAGE_ROOTFS_EXTRA_SPACE = "2097152"  # 2GB for containers
IMAGE_INSTALL:append = " packagegroup-k3s-node corekinect-provisioning"
```

- Torizon Easy Installer for deployment
- K3s embedded for container orchestration
- Custom device tree overlays for UART, GPIO
- CA certificate provisioning

## Key Integration Point: `mtib_twister_run`

The MTIB V2 protocol includes a Twister test execution RPC. This means:
- **Twister tests can be triggered remotely** via gRPC from K8s pods
- The MTIB server handles:
  - Firmware flashing (via J-Link)
  - UART connection (for console harness)
  - Power control (DUT power cycle)
  - Test output capture

This is the bridge between K8s-orchestrated tests and physical hardware.

## Validation-Relevant Observations

1. **`mtib_twister_run` exists**: Direct Twister integration is already in the protocol
2. **71 RPCs**: Comprehensive hardware control - power, GPIO, UART, BLE, bus mastering
3. **UART streaming**: Essential for Twister console harness - bidirectional with timestamps
4. **Power measurement**: Can validate power consumption during tests (up to 100kHz)
5. **Protocol decoding**: Can decode I2C/SPI traffic for driver-level validation
6. **Dual revision support**: Tests may need to account for REV 1.1 vs 1.2 hardware differences
7. **Privileged containers**: Required for hardware access - security consideration
8. **MCP server**: 22 tools for AI-assisted debugging - could augment test failure analysis
9. **J-Link integration**: Flash and debug any nRF target directly
10. **RTT support**: Zero-overhead logging alternative to UART for high-speed data capture
