---
min_role: OPERATOR
---
# Reading Results

## Finding a Device's Results

Open **Manufacturing**, select the session, and click a device row. You'll see the full POST report: overall pass/fail, the firmware version that was flashed, and a step-by-step breakdown with timing and measurement data.

Each result records:

- Device serial number
- Firmware version flashed
- Overall status -- passed or failed
- Individual step outcomes (pass/fail, duration, raw measurements)
- Timestamp of the test run

## Filtering the List

Use the filters at the top of the Manufacturing page to narrow down results:

- **Date range** -- find results from a specific shift or day
- **Status** -- show only passed or only failed devices
- **Serial number** -- jump to a specific board
- **Fixture** -- isolate results from one station (useful when diagnosing fixture issues)

## Spotting Patterns

If the same step keeps failing across multiple boards, the fixture is the likely culprit -- not the boards. Filter by fixture and compare failure rates between stations. A spike in "Power check" failures on one fixture usually means bent pogo pins or a loose connector.

If failures are spread evenly across fixtures, it's more likely a batch-level component issue. Escalate to a Developer for investigation.
