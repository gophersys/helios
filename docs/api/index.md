# API Reference

Auto-generated documentation for the `corekinect` Python library — the shared framework used by all Concord product validation apps.

## Modules

### Test Framework

The core test framework used by product validation repos (e.g., `alpha-validation`).

| Module | Description |
|--------|-------------|
| [TestContext](test/context.md) | Unified test context — composes MTIB, cloud, UART, power into one object |
| [CloudClient](test/cloud-client.md) | CoreCloud REST API polling for device messages |
| [UartDemuxer](test/uart-demuxer.md) | Dual-target UART capture with command sending |
| [PowerProfiler](test/power-profiler.md) | INA219 power measurement and profiling |
| [StageAssets](test/stage-assets.md) | Pipeline-driven firmware artifact resolution |
| [DevicePersonalizer](test/device-personalizer.md) | Automated re-personalization after J-Link flash |
| [Reporter](test/reporter.md) | Pytest plugin for live test result streaming |
| [POST](test/post.md) | Manufacturing Power-On Self-Test suite |
| [Telemetry](test/telemetry.md) | Real-time telemetry streaming (WebSocket + MinIO) |

### Stages & Errors

| Module | Description |
|--------|-------------|
| [Stages](stages.md) | Validation stage definitions and build matrices |
| [Errors](errors.md) | Error hierarchy for validation failures |

### CoreCloud

| Module | Description |
|--------|-------------|
| [CoreCloud Client](core-cloud/client.md) | Typed CoreCloud REST API client |
| [CoreCloud Models](core-cloud/models.md) | Response dataclasses for CoreCloud API |

### Pytest Integration

| Module | Description |
|--------|-------------|
| [Decorators](test/pytest-integration.md) | `@requires_capability` and test helpers |
