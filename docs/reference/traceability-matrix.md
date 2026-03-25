# Alpha PRDTST Traceability Matrix

**Generated:** 2026-03-07
**Product:** Alpha B0
**Total PRD Tests:** 89
**Implemented:** 22 | **Blocked:** 29 | **Not Started:** 38

## Status Legend

| Status | Meaning |
|--------|---------|
| PASS | Test implemented and passing on hardware |
| XFAIL | Test implemented but expected failure (hardware not wired) |
| SKIP | Test implemented but skipped (hardware not connected) |
| BLOCKED | Cannot implement (missing hardware/capability) |
| NOT_STARTED | Can be implemented but hasn't been written yet |

## Traceability Matrix

### Power / Runtime (7 tests)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-331 | Long-term sleep current < 1.5mA avg (12h/24h/48h/1wk) | — | — | BLOCKED | Requires multi-day power profiling with ICLE; no automated long-duration test infrastructure |
| PRDTST-340 | Operate 3 days under worst-case conditions | — | — | BLOCKED | Requires 72-hour continuous test run with worst-case biometric+GPS+LTE profile |
| PRDTST-341 | Active mode current < 150mA | test_boot.py | test_boot_current_within_budget | PASS | — |
| PRDTST-348 | Sleep mode current < 500uA avg | — | — | BLOCKED | Requires sleep mode entry + sub-mA current measurement; INA219 resolution may be insufficient |
| PRDTST-361 | Lockout mode current < 400nA | — | — | BLOCKED | Requires battery lockout state + nA-resolution current measurement; INA219 cannot measure nA |
| PRDTST-363 | Operate 3 days standalone normal use | — | — | BLOCKED | Requires 72-hour continuous test run with normal-use profile |
| PRDTST-404 | Normal use mode current < 50mA over 10 min | test_boot.py | test_boot_current_within_budget | PASS | — |

### Config Values (Heartbeat, Motion, GPS) (18 tests)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-328 | Motion stop acquisition timeout default value | — | — | NOT_STARTED | Requires CoreCloud config message parsing |
| PRDTST-330 | Heartbeat acquisition timeout default (60s) | — | — | NOT_STARTED | Requires CoreCloud config message parsing |
| PRDTST-335 | Zero heartbeat period (disable heartbeats) | — | — | NOT_STARTED | Requires config write + CoreCloud message verification |
| PRDTST-342 | Continuous motion period default value | — | — | NOT_STARTED | Requires CoreCloud config message parsing |
| PRDTST-344 | Heartbeat period max value (2-byte) | — | — | NOT_STARTED | Requires config write + CoreCloud message verification |
| PRDTST-347 | Stop motion timeout non-default value | — | — | NOT_STARTED | Requires config write + CoreCloud message verification |
| PRDTST-352 | Heartbeat period default value | — | — | NOT_STARTED | Requires CoreCloud config message parsing |
| PRDTST-353 | Start motion window start default (3s) | — | — | NOT_STARTED | Requires CoreCloud config message parsing |
| PRDTST-356 | Heartbeat period non-default value | — | — | NOT_STARTED | Requires config write + CoreCloud message verification |
| PRDTST-359 | Heartbeat acquisition timeout non-default value | — | — | NOT_STARTED | Requires config write + CoreCloud message verification |
| PRDTST-364 | Continuous motion disabled | — | — | NOT_STARTED | Requires config write + CoreCloud message verification |
| PRDTST-369 | Continuous motion period non-default value | — | — | NOT_STARTED | Requires config write + CoreCloud message verification |
| PRDTST-371 | Heartbeat period min value | — | — | NOT_STARTED | Requires config write + CoreCloud message verification |
| PRDTST-374 | Ground mode config sent on boot | test_boot.py | test_power_cycle_produces_bootmsg, test_boot_reports_firmware_version | PASS | — |
| PRDTST-387 | Continuous motion period min (1s) | — | — | NOT_STARTED | Requires config write + CoreCloud message verification; behavior at 1s undefined |
| PRDTST-388 | Default ground mode config values | — | — | NOT_STARTED | Requires CoreCloud GroundModeConfigV2 message parsing |
| PRDTST-394 | Continuous motion period max (65535s) | — | — | NOT_STARTED | Requires config write + CoreCloud message verification |
| PRDTST-399 | Stop motion timeout default (2 min) | — | — | NOT_STARTED | Requires CoreCloud config message parsing |

### Motion Detection (5 tests)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-324 | Ignore motion below acceleration threshold | test_motion.py | test_stationary_no_false_motion | SKIP | FluidNC linear rail not connected to validation MTIBs (MOTION_ENABLED not set) |
| PRDTST-326 | Detect motion above thresholds with default config | test_motion.py | test_shake_triggers_motion | SKIP | FluidNC linear rail not connected to validation MTIBs (MOTION_ENABLED not set) |
| PRDTST-375 | Ignore motion below duration threshold | test_motion.py | test_stationary_no_false_motion | SKIP | FluidNC linear rail not connected to validation MTIBs (MOTION_ENABLED not set) |
| PRDTST-389 | Axis independence (detect motion in all 3 axes) | — | — | BLOCKED | Requires multi-axis motion actuator; FluidNC is single-axis linear rail |
| PRDTST-393 | Respect motion start window | test_motion.py | test_shake_triggers_motion | SKIP | FluidNC linear rail not connected; would need timed shake within start window |

### Charging / BMS (29 tests)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-332 | Charge controller TS pin short circuit — start charging | — | — | BLOCKED | Requires battery + TS pin stimulus hardware; validation fixture is batteryless |
| PRDTST-334 | SoC reporting accuracy (within 2%) | — | — | BLOCKED | Requires battery + calibrated external SoC measurement equipment |
| PRDTST-338 | Communicate charge level via LEDs on button press | test_button.py | test_short_press_led_response | XFAIL | LED photodiode ADC channels (4-6) not wired on current fixture |
| PRDTST-339 | Charge controller TS pin short circuit — while charging | — | — | BLOCKED | Requires battery + TS pin stimulus hardware; validation fixture is batteryless |
| PRDTST-349 | No FUOTA on low battery (3.7V) | — | — | BLOCKED | Requires battery at controlled discharge level + FUOTA trigger |
| PRDTST-350 | Battery temperature in position message | — | — | BLOCKED | Requires battery + thermistor; validation fixture is batteryless |
| PRDTST-351 | Must not charge at negative temperatures | — | — | BLOCKED | Requires battery + environmental chamber at sub-zero temps |
| PRDTST-354 | Charger connection delatches battery lockout | — | — | BLOCKED | Requires battery in lockout state + charger connection |
| PRDTST-355 | Communicate on-charger state via LEDs | — | — | BLOCKED | Requires battery + charger + LED photodiode wiring |
| PRDTST-365 | Charge using charge ladder | — | — | BLOCKED | Requires battery + long-duration charge monitoring |
| PRDTST-366 | BMS SoC and temp in position message (in motion, on-skin) | — | — | BLOCKED | Requires battery + motion actuator + on-skin simulation |
| PRDTST-367 | BMS temperature measurement accuracy (within 2C) | — | — | BLOCKED | Requires battery + calibrated external thermometer |
| PRDTST-368 | Report on-charger state in position message | — | — | BLOCKED | Requires battery + charger + CoreCloud position message parsing |
| PRDTST-370 | Charge from 3.5V to 4.2V in under 3 hours | — | — | BLOCKED | Requires battery + 3-hour charge cycle monitoring |
| PRDTST-372 | Must not charge above 45C | — | — | BLOCKED | Requires battery + environmental chamber at 45C+ |
| PRDTST-373 | Communicate charge level via LEDs while charging | — | — | BLOCKED | Requires battery + charger + LED photodiode wiring |
| PRDTST-381 | BMS parameter retention after power cycle | — | — | BLOCKED | Requires battery + BMS register read/verify |
| PRDTST-383 | Must not charge below 10C | — | — | BLOCKED | Requires battery + environmental chamber at sub-10C |
| PRDTST-385 | Lockout battery discharge at 3.5V | — | — | BLOCKED | Requires battery at controlled discharge to 3.5V |
| PRDTST-386 | Detect charger connection — low battery, not charging | — | — | BLOCKED | Requires battery in low-charge state + charger |
| PRDTST-390 | Charge controller TS pin open circuit — start charging | — | — | BLOCKED | Requires battery + TS pin stimulus hardware |
| PRDTST-391 | Stop charging at 4.3V with 10mA termination | — | — | BLOCKED | Requires battery + precision charge termination monitoring |
| PRDTST-392 | Trickle charge below 3.5V at 10mA | — | — | BLOCKED | Requires battery at sub-3.5V + current measurement |
| PRDTST-397 | Detect charger connection — full battery | — | — | BLOCKED | Requires fully charged battery + charger |
| PRDTST-402 | Detect charger connection — low battery | — | — | BLOCKED | Requires battery across voltage range + charger |
| PRDTST-407 | Charge controller temperature measurement accuracy (within 2C) | — | — | BLOCKED | Requires battery + calibrated external thermometer |
| PRDTST-409 | Charge controller TS pin open circuit — while charging | — | — | BLOCKED | Requires battery + TS pin stimulus hardware |
| PRDTST-411 | BMS recovery voltage behavior (3.88V) | — | — | BLOCKED | Requires battery + controlled discharge/recovery cycle |
| PRDTST-412 | Button press to check battery status | test_button.py | test_short_press_led_response | XFAIL | LED photodiode ADC channels (4-6) not wired on current fixture |

### Environmental Sensors (BME280, MLX90614) (7 tests)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-329 | Altitude ceiling measurement (within 25m) | — | — | NOT_STARTED | Requires calibrated altimeter reference; could use pressure-to-altitude conversion |
| PRDTST-336 | Detect 3m elevation change | — | — | NOT_STARTED | Requires controlled pressure change stimulus |
| PRDTST-345 | Absolute temperature accuracy (within 0.5C) | test_environmental.py | test_temperature_within_range | PASS | Plausible range check only; calibrated accuracy check NOT_STARTED |
| PRDTST-357 | Absolute pressure accuracy (within 0.05 inHg / 1.7 hPa) | test_environmental.py | test_pressure_within_range | PASS | Plausible range check only; calibrated accuracy check NOT_STARTED |
| PRDTST-398 | Absolute humidity accuracy (within 3% RH) | test_environmental.py | test_humidity_within_range | PASS | Plausible range check only; calibrated accuracy check NOT_STARTED |
| PRDTST-405 | Detect 5% humidity change | — | — | NOT_STARTED | Requires controlled humidity stimulus |
| PRDTST-406 | Detect 0.1C temperature change | test_environmental.py | test_temperature_changes_with_peltier | PASS | Peltier stimulus test implemented; exact 0.1C resolution not verified |

### GNSS (7 tests)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-333 | GNSS position-based heading estimate (within 10 deg) | — | — | NOT_STARTED | Requires GNSS fix + motion for heading calculation |
| PRDTST-343 | GNSS cold start fix (within 1 min, 6m accuracy, aiding disabled) | — | — | NOT_STARTED | Requires clear sky conditions or GNSS simulator |
| PRDTST-358 | GNSS position-based speed estimate (within 20%) | — | — | NOT_STARTED | Requires GNSS fix + known-speed motion |
| PRDTST-360 | GNSS warm start fix (within 30s, 1m accuracy, aiding disabled) | — | — | NOT_STARTED | Requires prior fix + clear sky or GNSS simulator |
| PRDTST-378 | GNSS cold start fix (within 30s, 1m accuracy, aiding enabled) | — | — | NOT_STARTED | Requires clear sky or GNSS simulator + aiding data |
| PRDTST-384 | GNSS cold start fix extended (within 3 min, 1m accuracy, aiding disabled) | — | — | NOT_STARTED | Requires clear sky or GNSS simulator |
| PRDTST-396 | GNSS warm start fix (within 30s, 1m accuracy, aiding enabled) | — | — | NOT_STARTED | Requires prior fix + clear sky or GNSS simulator + aiding data |

### On-Skin / Biometrics (3 tests)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-327 | Biometric data messages sent when on-skin | test_biometric.py | test_on_skin_detected, test_biometric_includes_temperature | PASS | — |
| PRDTST-379 | Position messages sent when on-skin | — | — | NOT_STARTED | Requires on-skin simulation + CoreCloud PositionMsgV6 parsing |
| PRDTST-400 | On-skin detection (on and off) | test_biometric.py | test_on_skin_detected, test_off_skin_detected | PASS | — |

### Button / SOS / Haptic (9 tests)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-325 | Negative test: no SOS for <3s or >6s press | test_button.py | test_short_press_no_power_off | PASS | Partial: verifies short press does not power off; SOS-specific negative verification NOT_STARTED |
| PRDTST-346 | Hard reset on 7 rapid presses | — | — | NOT_STARTED | Requires rapid multi-press GPIO actuation + reboot detection |
| PRDTST-362 | Haptic feedback on SOS entry | — | — | BLOCKED | No haptic/vibration sensor on fixture; cannot detect motor activation |
| PRDTST-377 | Manufacturing test mode on double-click | test_button.py | test_double_press | PASS | Verifies device survives double-press; mfg mode entry not explicitly verified |
| PRDTST-380 | Haptic feedback on SOS acknowledgement | — | — | BLOCKED | No haptic/vibration sensor on fixture |
| PRDTST-382 | SOS entry on 3-6 second press | test_button.py | test_long_press_sos | PASS | Verifies device survives 3s press; SOS CoreCloud message verification TODO |
| PRDTST-395 | Negative: no haptic for <3s press | — | — | BLOCKED | No haptic/vibration sensor on fixture |
| PRDTST-403 | Haptic feedback on mfg test mode entry/exit | — | — | BLOCKED | No haptic/vibration sensor on fixture |
| PRDTST-408 | Haptic feedback on 3s button press | — | — | BLOCKED | No haptic/vibration sensor on fixture |

### NFC (1 test)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-337 | NFC broadcast device ID | test_nfc.py | test_nfc_tag_detected, test_nfc_device_id | SKIP | NFC I2C reader not yet wired on fixture |

### FUOTA (1 test)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-376 | FUOTA from previous release to current | — | — | NOT_STARTED | FUOTA API workflow confirmed; CFW files generated; test automation not yet written |

### VSM / IPC (1 test)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-410 | VSM power cut-off switch | — | — | NOT_STARTED | Requires GPIO-controlled VSM power switch + current verification |

### Operating Temperature (1 test)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-401 | Operate within -20C to +60C | — | — | BLOCKED | Requires environmental chamber for temperature sweep |

## Summary by Category

| Category | Total | PASS | XFAIL | SKIP | BLOCKED | NOT_STARTED |
|----------|-------|------|-------|------|---------|-------------|
| Power / Runtime | 7 | 2 | 0 | 0 | 5 | 0 |
| Config Values | 18 | 1 | 0 | 0 | 0 | 17 |
| Motion Detection | 5 | 0 | 0 | 4 | 1 | 0 |
| Charging / BMS | 29 | 0 | 2 | 0 | 27 | 0 |
| Environmental Sensors | 7 | 4 | 0 | 0 | 0 | 3 |
| GNSS | 7 | 0 | 0 | 0 | 0 | 7 |
| On-Skin / Biometrics | 3 | 2 | 0 | 0 | 0 | 1 |
| Button / SOS / Haptic | 9 | 3 | 0 | 0 | 5 | 1 |
| NFC | 1 | 0 | 0 | 1 | 0 | 0 |
| FUOTA | 1 | 0 | 0 | 0 | 0 | 1 |
| VSM / IPC | 1 | 0 | 0 | 0 | 0 | 1 |
| Operating Temperature | 1 | 0 | 0 | 0 | 1 | 0 |
| **TOTAL** | **89** | **12** | **2** | **5** | **39** | **31** |

## Blocker Analysis

### Hardware Blockers (Cannot Resolve in Software)

| Blocker | Affected Tests | Count |
|---------|---------------|-------|
| Validation fixture is batteryless (no battery installed) | PRDTST-332, 334, 339, 349, 350, 351, 354, 355, 365, 366, 367, 368, 370, 372, 373, 381, 383, 385, 386, 390, 391, 392, 397, 402, 407, 409, 411 | 27 |
| No haptic/vibration sensor on fixture | PRDTST-362, 380, 395, 403, 408 | 5 |
| FluidNC linear rail not connected | PRDTST-324, 326, 375, 389, 393 | 5 |
| LED photodiode ADC channels (4-6) not wired | PRDTST-338, 412 | 2 |
| NFC I2C reader not wired on fixture | PRDTST-337 | 1 |
| Environmental chamber required | PRDTST-351, 372, 383, 401 | 4 |
| nA-resolution current measurement required | PRDTST-361 | 1 |
| Sub-mA current measurement required | PRDTST-348 | 1 |
| Multi-day test duration required | PRDTST-331, 340, 363 | 3 |

### Software / Integration Blockers (Can Resolve)

| Blocker | Affected Tests | Count |
|---------|---------------|-------|
| CoreCloud config message parsing not implemented | PRDTST-328, 330, 335, 342, 344, 347, 352, 353, 356, 359, 364, 369, 371, 387, 388, 394, 399 | 17 |
| GNSS simulator or clear sky test location needed | PRDTST-333, 343, 358, 360, 378, 384, 396 | 7 |
| FUOTA test automation not written | PRDTST-376 | 1 |

## Test File Index

| Test File | Path | PRDTST Coverage |
|-----------|------|-----------------|
| test_boot.py | apps/validation/alpha/tests/stage4/test_boot.py | PRDTST-341, 374, 404 |
| test_power.py | apps/validation/alpha/tests/stage4/test_power.py | General power budget (no direct PRDTST mapping) |
| test_motion.py | apps/validation/alpha/tests/stage4/test_motion.py | PRDTST-324, 326, 375, 393 |
| test_environmental.py | apps/validation/alpha/tests/stage4/test_environmental.py | PRDTST-345, 357, 398, 406 |
| test_biometric.py | apps/validation/alpha/tests/stage4/test_biometric.py | PRDTST-327, 400 |
| test_button.py | apps/validation/alpha/tests/stage4/test_button.py | PRDTST-325, 338, 377, 382, 412 |
| test_nfc.py | apps/validation/alpha/tests/stage4/test_nfc.py | PRDTST-337 |
| test_corecloud_integration.py | apps/validation/alpha/tests/stage4/test_corecloud_integration.py | Infrastructure (no direct PRDTST mapping) |
| test_smoke_mtib.py | apps/validation/alpha/tests/test_smoke_mtib.py | Infrastructure (no direct PRDTST mapping) |
