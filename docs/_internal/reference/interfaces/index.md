# Interface & Contract Specifications

This folder holds per-component interface specs that define the contract between hardware components and their firmware drivers/services. Each spec documents the electrical interface, communication protocol, data formats, timing constraints, and validation criteria for one BOM component.

## Planned Specs

| Component | Status | Notes |
|-----------|--------|-------|
| LSM6DSO (6-axis IMU) | Planned | SPI interface, FIFO protocol, interrupt contract |
| MAX30101 (PPG sensor) | Planned | I2C interface, FIFO read protocol |
| BQ25180 (charger) | Planned | I2C register interface, charging state machine |
| NRF52840 (SoC) | Planned | GPIO/peripheral allocation, power domains |
| W25Q128 (flash) | Planned | QSPI interface, sector/block layout |
| BME280 (env sensor) | Planned | I2C/SPI interface, compensation algorithm |
| NFC (ST25DV) | Planned | I2C mailbox protocol, RF interface |

## Template

Each interface spec should cover:

1. **Electrical interface** -- bus type, pins, voltage levels, speed
2. **Protocol** -- register map, command sequences, FIFO behavior
3. **Timing constraints** -- startup time, sampling rates, interrupt latency
4. **Error modes** -- what can go wrong, how to detect it, recovery
5. **Validation criteria** -- what Stage 2/3 tests must verify for this component
