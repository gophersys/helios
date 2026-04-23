---
min_role: DEVELOPER
---
# Stages & Errors

## Validation Stages

| Stage | Name | What Runs | Hardware Required |
|-------|------|-----------|-------------------|
| 1 | Software Tests | Unit tests via Twister — pure host-side, no device needed | No |
| 2 | Driver & HW Tests | Individual driver and peripheral tests against real hardware | Yes |
| 3 | Integration Tests | Cross-subsystem interaction (e.g., BLE + sensor + flash) | Yes |
| 4 | Product Tests | Full product-level functional tests | Yes |
| 5 | FUOTA Tests | Over-the-air firmware update — flash, reboot, verify new image | Yes |

Stages 2-5 run on fixtures with a physical DUT. Stage 1 runs in a container with no hardware dependency.

## Error Codes

Errors follow a hierarchical structure: prefix identifies the subsystem, numeric suffix identifies the specific failure.

### Build Errors

| Code | Category | Meaning |
|------|----------|---------|
| `BUILD_001` | Compilation | Firmware compilation failed |
| `BUILD_002` | Linking | Linker error — unresolved symbol |
| `BUILD_003` | Configuration | Invalid build configuration (missing overlay, bad Kconfig) |

### Validation Errors

| Code | Category | Meaning |
|------|----------|---------|
| `VAL_001` | Timeout | Test exceeded time limit |
| `VAL_002` | Assertion | Test assertion failed |
| `VAL_003` | Infrastructure | Fixture communication error or MTIB unreachable |
| `VAL_004` | Power | Device power anomaly — unexpected current draw or voltage rail failure |

### Manufacturing Errors

| Code | Category | Meaning |
|------|----------|---------|
| `MFG_001` | Flash | Firmware flash via J-Link/SWD failed |
| `MFG_002` | POST | Power-on self test step failed |
| `MFG_003` | Identity | Device personalization failed (key generation or CoreOps upload) |
