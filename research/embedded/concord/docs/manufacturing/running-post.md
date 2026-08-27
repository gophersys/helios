---
min_role: OPERATOR
---
# Running POST

POST (Power-On Self Test) is the automated sequence that checks every hardware subsystem on a board during manufacturing. A full run takes 2-5 minutes.

## Before You Start

- A manufacturing session must be active (check the session indicator at the top of the Manufacturing page)
- The device must be seated in a registered fixture
- Approved firmware must be available for the product

## Step by Step

1. Place the device in the test fixture -- match the alignment pins
2. Open **Manufacturing** and select the active session
3. Click **Start POST**

The system handles the rest:

- Powers the board
- Flashes the manufacturing firmware via J-Link
- Runs each POST step in sequence
- Reports pass/fail for every step

Don't touch the fixture during the run. The progress bar shows which step is executing.

## What POST Checks

| Step | What It Verifies |
|------|-----------------|
| **Power rails** | Correct voltage on each rail (ch0 at 4.5V, 3.3V reference) |
| **UART** | Both processors respond (nRF52840 APP + nRF9151 COMMS) |
| **Sensors** | Accelerometer, temperature, PPG readings within expected range |
| **Storage** | Flash read/write and EEPROM access at 0x50 |
| **RF** | BLE advertising detected, cellular modem responds to AT commands |
| **Personalization** | EC keypair generated, public key uploaded to CoreCloud |

## After POST

**Passed** -- Remove the board, place it in the passed bin, scan the next one.

**Failed** -- Check the failed step on screen. See [Reading Results](reading-results.md) for how to interpret failures and when to escalate.
