---
min_role: OPERATOR
---
# Manufacturing Sessions

A session is a production run on a single fixture. You start it, scan panels, watch stage results come in, and end it when the shift is done or the batch is complete. Concord tracks every unit that passes through.

## Starting a Session

Sessions begin from the **Manufacturing** page. Find the fixture card showing **AVAILABLE** status and click **New Session**. (You can also start a session via the API by POSTing to `/v2/manufacturing/sessions` with the product and fixture IDs.)

The session creation wizard asks which test package to run. Pick a released package for production batches, or a development package for dry-running an unreleased build on a dev fixture. The fixture's `purpose` (`DEV` or `RELEASE`) gates the choice: dev packages run only on dev rigs, released packages run only on release rigs. Without an explicit pick the wizard auto-fills the latest released package; if none exists for this product the request is rejected with a 409 — release a package first or pass `testPackageId` explicitly.

The fixture immediately locks -- its status changes from AVAILABLE to **LOCKED**. No other operator can start a second session on the same fixture until you end yours. This prevents two people from driving the same hardware simultaneously.

The session runner page opens with the product name in the header and an **ACTIVE** status badge.

## Scanning Panels

The runner page has a QR code input field at the top. Scan the panel label with a barcode reader, or type the panel identifier manually and press Enter.

Once a QR code is in the field, the **Run Panel** button enables. Click it to begin the manufacturing sequence for that panel.

## Watching Results

After a panel run starts, the panel appears in the session UI. Stage results update in real time as the fixture works through each board:

1. **Electrical** -- power rail checks, current draw verification
2. **Flash** -- firmware programming via J-Link
3. **POST** -- automated hardware checks (sensors, connectivity, peripherals)

Each unit on the panel gets a card showing its current stage and pass/fail status. Green for passed stages, red for failures. A failed stage shows the error message -- things like "BMS check failed" or "Flash verification failed" -- so you know immediately whether to retry or set the board aside.

When all units on the panel finish, a panel summary appears with the pass/fail count.

## Multiple Panels

One session can process many panels. After the first panel completes, scan the next QR code and run again. The **Panel History** section at the bottom of the page tracks every panel in the session with expand/collapse controls. Click a panel row to expand it and see individual unit cards, serial numbers, and per-stage results.

The session header shows aggregate statistics across all panels: total panels run, total units passed, total units failed. These update after each panel completes.

## Ending a Session

Click **End Session** when the batch is finished. A confirmation dialog appears -- it specifically asks you to confirm ending the manufacturing session. Two buttons: **Cancel** (go back) and **End Session** (finalize).

After confirmation:

- The session status changes to **COMPLETED**
- The QR input field and control buttons disappear (the session is read-only now)
- The fixture releases back to **AVAILABLE** for the next operator

## Reviewing Completed Sessions

Completed sessions appear on the Manufacturing page under the **Sessions** tab. Each entry shows the product name, a **COMPLETED** badge, and the panel count (e.g., "1 panel" or "3 panels").

Click a completed session to reopen the detail view. The panel history is still there -- expand any panel to see unit serial numbers and per-stage results. The header still shows the aggregate pass/fail counts from the run. Nothing is lost after the session ends.

## Related

- [Manufacturing configuration](configuration.md) -- setting up stages, firmware source, and pass criteria before operators can run sessions
- [Reading results](reading-results.md) -- filtering and interpreting outcomes across sessions
- [Station setup](station-setup.md) -- physical fixture prep
