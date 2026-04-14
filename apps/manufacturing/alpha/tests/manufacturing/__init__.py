"""Alpha manufacturing tests — electrical, flash, POST.

Three sequential phases run per DUT slot:

  Phase 1: Electrical verification (test_01_electrical)
    01 — UVLO off state: sub-threshold voltage, verify no power
    02 — Nominal power-up: 3.7V, verify DUT boots
    03 — High voltage regulation: 4.5V, verify rails track
    04 — Charger load-sharing: 5V to CHRG, verify handoff

  Phase 2: Firmware flash (test_02_fw_flash)
    01 — Power up DUT for J-Link access
    02 — Flash nRF52840 app processor
    03 — Flash nRF9151 comms processor
    04 — Flash modem firmware (optional)
    05 — Set AP protect on both processors

  Phase 3: POST — power-on self-test (test_03_post)
    01 — Boot device and lock manufacturing shells
    02 — Verify comms processor chip IDs
    03 — Verify app processor chip IDs
    04 — Verify BMS gas gauge
    05 — Verify battery charger IC
    06 — Verify GPS module
    07 — Verify modem firmware version
    08 — Verify IMEI and ICCIDs
    09 — Personalize device via CoreOps
    10 — Rekey IPC encryption
"""
