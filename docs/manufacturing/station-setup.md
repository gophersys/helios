---
min_role: OPERATOR
---
# Station Setup

## Logging In

Open Concord on the station tablet or monitor. Sign in with your operator credentials -- you'll land on the **Manufacturing** page. That's your home screen for the shift.

If your login doesn't work, ask a Maintainer to check your account.

## Scanning a Device

1. Place the board in the fixture -- match the alignment pins
2. Click **Scan** or use the barcode scanner on the device label
3. The screen shows the device serial number and current status

If the scanner doesn't read, type the serial number manually and press Enter.

## Running POST

POST checks everything on the board: power, sensors, connectivity, peripherals.

1. After scanning, click **Run POST**
2. The test runs automatically -- takes 2-5 minutes depending on the product
3. Don't touch the fixture while it's running (the progress bar shows the current step)

The fixture controls power, presses buttons, and reads sensors on its own. You just watch.

## Reading Results

When POST finishes, you get one of two outcomes:

### PASS (green)

All steps passed. Remove the board from the fixture and place it in the "passed" bin. Scan the next board.

### FAIL (red)

One or more steps failed. The screen shows exactly which steps failed and why:

| Failed Step | Likely Cause |
|-------------|-------------|
| Power check | Board not drawing current -- check fixture seating |
| UART check | No processor response -- possible soldering issue |
| Sensor check | Readings out of range -- component defect |
| Connectivity | Radio not responding -- antenna or RF issue |
| Personalization | CoreCloud rejected device keys -- network issue, retry |

## Troubleshooting Common Failures

**"DUT not drawing current"** -- The board isn't making good contact. Remove it, check the pogo pins, reseat, and retry.

**"UART timeout"** -- The processor didn't respond. Reseat the board. If it fails twice, set it aside for engineering review.

**"Sensor out of range"** -- A sensor reading is outside expected values. Usually a component defect. Set the board aside.

**"Personalization failed"** -- Concord couldn't register the device with CoreCloud. Check whether other boards are passing -- if yes, this board has an issue. If no, it's likely a network problem. Call a Maintainer.

**Test hangs / no progress** -- If the progress bar hasn't moved for over 2 minutes, click **Cancel** and retry. If it hangs again, call a Maintainer.

## When to Escalate

| Situation | Contact |
|-----------|---------|
| Same failure on multiple boards in a row | Maintainer -- likely a fixture issue |
| Test hangs or crashes | Maintainer -- system issue |
| A failure type you haven't seen before | Developer -- needs investigation |
| Can't log in or the app won't load | Admin or Maintainer |

Don't try to fix fixture hardware yourself. If pogo pins look bent or damaged, stop and call a Maintainer.
