---
min_role: DEVELOPER
---
# Python SDK

The `corekinect` package contains everything needed to write validation tests and interact with Concord hardware.

## Test Framework

The [test framework](test-framework/) is the primary interface for validation test development:

- **TestContext** — entry point for fixtures, devices, and cloud services
- **PowerProfiler** — INA219-based power consumption measurement
- **UartDemuxer** — UART capture and parsing across multiple targets
- **CloudClient** — CoreCloud REST client for device interaction
- **StageAssets** — firmware artifact resolution per validation stage

## CoreCloud SDK

The [CoreCloud SDK](corecloud/) wraps the CoreCloud REST API for device communication — client setup, data models for devices, telemetry, and commands.

## Installation

Install from the Concord PyPI server:

```bash
pip install corekinect --index-url https://pypi.concord.local/simple/
```
