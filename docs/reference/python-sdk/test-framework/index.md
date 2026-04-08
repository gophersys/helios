---
min_role: DEVELOPER
---
# Test Framework

Classes and utilities for writing validation tests against physical hardware.

## Core Classes

| Class | Role |
|-------|------|
| [TestContext](context.md) | Entry point — access to fixtures, devices, and cloud |
| [CloudClient](cloud-client.md) | CoreCloud polling and interaction |
| [UartDemuxer](uart-demuxer.md) | UART capture and demux across device targets |
| [PowerProfiler](power-profiler.md) | INA219 power measurement |
| [StageAssets](stage-assets.md) | Firmware artifact resolution per stage |
| [DevicePersonalizer](device-personalizer.md) | Device identity and EC key provisioning |
| [Reporter](reporter.md) | Pytest plugin — streams results to Concord |
| [POST](post.md) | Manufacturing power-on self test suite |
| [Telemetry](telemetry.md) | Real-time device telemetry access |
