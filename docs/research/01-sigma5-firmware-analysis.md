# Sigma5 Firmware Analysis

## Overview

Sigma5 is a dual-MCU wearable device firmware built on Zephyr RTOS (NCS v2.3.0). It targets fall detection, emergency alerting, and environmental monitoring.

## Hardware Architecture

### Dual Processor System
- **nRF52840** (Application Processor): Sensors, BLE, NFC, fall detection algorithm
- **nRF9160** (Communications Coprocessor): LTE-M/NB-IoT, LoRa, GPS
- **IPC**: LPUART at 460800 baud via `common/ck_ipc/`

### Board Definitions
Located in `ck_boards/boards/arm/`:
- `sigma5_a0` - Rev A0 hardware
- `sigma5_b0` - Rev B0 hardware (current production)
- `rtec` - RTEC variant
- `xtec` - XTEC variant
- `nurble` - Nurble variant

Custom devicetree bindings in `ck_boards/dts/bindings/`.

## Project Structure

```
/home/mateo/work/firmware/sigma5_fw/
├── nrf52840/                    # App processor firmware
│   ├── src/                     # Application source
│   ├── CMakeLists.txt
│   └── prj.conf
├── nrf9160/                     # Comms processor firmware
│   ├── src/                     # LTE/LoRa/GPS source
│   ├── CMakeLists.txt
│   └── prj.conf
├── ck_boards/                   # Custom board definitions
│   ├── boards/arm/              # Board DTS + Kconfig
│   └── dts/bindings/            # Custom DT bindings
├── common/
│   └── ck_ipc/                  # Inter-processor communication
├── .devcontainer/
│   └── devcontainer.json        # Uses containers.ad.corekinect.com/ncs-fw-dev:2.4.2
└── .gitmodules                  # 14 submodules
```

## Submodules (14 total)

All sourced from `git@bitbucket.org:corekinect/`:
- Sensor drivers (lsm6dso, alt_drv, etc.)
- Crypto libraries
- IPC protocol
- Custom board definitions (ck_boards is itself a submodule shared across products)
- Various peripheral drivers

## Key Architectural Details

- **NCS Version**: v2.3.0
- **Build Container**: `containers.ad.corekinect.com/ncs-fw-dev:2.4.2`
- **Multi-image**: MCUBoot + application + coprocessor
- **Fall Detection**: Custom algorithm on nRF52840 using accelerometer data
- **Connectivity**: BLE (nRF52840), LTE-M/NB-IoT + LoRa + GPS (nRF9160)
- **NFC**: Tag emulation for provisioning

## Validation-Relevant Observations

1. **Dual-MCU complexity**: Tests need to handle both processors independently and together
2. **IPC testing**: The LPUART IPC bridge between MCUs is a critical integration point
3. **Board variants**: 5 different board definitions means tests may need per-board overlays
4. **ck_boards shared submodule**: Board definitions are shared across products - changes here cascade
5. **No existing CI/CD**: Builds are manual via devcontainer
6. **14 submodules**: Each is a potential change-trigger point for regression testing
