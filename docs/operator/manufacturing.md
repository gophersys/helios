# Manufacturing

## Station Login

Open Concord on the station tablet or monitor. Sign in with your operator credentials. You'll land on the **Manufacturing** page — that's your home screen.

If you can't log in, ask a Maintainer to check your account.

## Scanning a Device

1. Place the board in the fixture (match the alignment pins)
2. Click **Scan** or use the barcode scanner on the device label
3. The screen shows the device serial number and current status

If the scanner doesn't read, type the serial number manually and press Enter.

## Running POST

POST (Production Operational Self-Test) checks everything on the board — power, sensors, connectivity, peripherals.

1. After scanning, click **Run POST**
2. The test runs automatically — takes 2-5 minutes depending on the product
3. Don't touch the fixture while it's running (the progress bar shows current step)

The fixture controls power, presses buttons, and reads sensors automatically. You just watch.

## Reading Results

When POST finishes, you'll see one of two things:

### PASS (green)

All steps passed. Remove the board from the fixture and place it in the "passed" bin. Scan the next board.

### FAIL (red)

One or more steps failed. The screen shows which steps failed and why:

| Failed Step | What It Means |
|-------------|---------------|
| Power check | Board isn't drawing current — check fixture seating |
| UART check | No response from processor — possible soldering issue |
| Sensor check | Sensor readings out of range — component defect |
| Connectivity | Radio not responding — antenna or RF issue |
| Personalization | CoreCloud rejected device keys — network issue, retry |

## Common Failures and What to Do

**"DUT not drawing current"** — The board isn't making good contact with the fixture. Remove it, check the pogo pins, reseat the board, and retry.

**"UART timeout"** — The processor didn't respond. Try reseating. If it fails twice, set the board aside for engineering review.

**"Sensor out of range"** — A sensor reading is outside expected values. This usually means a component defect. Set the board aside.

**"Personalization failed"** — The system couldn't register the device with CoreCloud. This is usually a network issue. Check if other boards are passing — if yes, it's this specific board. If no, call a Maintainer.

**Test hangs / no progress** — If the progress bar hasn't moved for over 2 minutes, click **Cancel** and retry. If it hangs again, call a Maintainer.

## Escalation

| Situation | Who to Call |
|-----------|-------------|
| Same failure on multiple boards in a row | Maintainer — possible fixture issue |
| Test hangs or crashes | Maintainer — possible system issue |
| Board fails a step you haven't seen before | Developer — needs investigation |
| Can't log in or app not loading | Admin or Maintainer |

Don't try to fix fixture hardware yourself. If pogo pins look bent or damaged, stop and call a Maintainer.
