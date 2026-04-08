# Alpha PRDTST Traceability Matrix

**Generated:** 2026-04-01
**Product:** Alpha B0
**Total PRD Tests:** 89
**Implemented:** 46 | **Blocked:** 39 | **Not Started:** 4

## Status Legend

| Status | Meaning |
|--------|---------|
| PASS | Test implemented and passing on hardware |
| IMPLEMENTED | Test code written but not yet run against hardware |
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
| PRDTST-328 | Motion stop acquisition timeout default value | test_config.py | TestConfigDefaults::test_motion_stop_acquisition_timeout_default | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-330 | Heartbeat acquisition timeout default (60s) | test_config.py | TestConfigDefaults::test_heartbeat_acquisition_timeout_default | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-335 | Zero heartbeat period (disable heartbeats) | test_config.py | TestConfigOverrides::test_zero_heartbeat_disables | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-342 | Continuous motion period default value | test_config.py | TestConfigDefaults::test_continuous_motion_period_default | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-344 | Heartbeat period max value (2-byte) | test_config.py | TestConfigOverrides::test_heartbeat_period_max | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-347 | Stop motion timeout non-default value | test_config.py | TestConfigOverrides::test_stop_motion_timeout_non_default | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-352 | Heartbeat period default value | test_config.py | TestConfigDefaults::test_gps_heartbeat_period_default | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-353 | Start motion window start default (3s) | test_config.py | TestConfigDefaults::test_start_motion_window_start_default | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-356 | Heartbeat period non-default value | test_config.py | TestConfigOverrides::test_heartbeat_period_non_default | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-359 | Heartbeat acquisition timeout non-default value | test_config.py | TestConfigOverrides::test_heartbeat_timeout_non_default | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-364 | Continuous motion disabled | test_config.py | TestConfigOverrides::test_continuous_motion_disabled | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-369 | Continuous motion period non-default value | test_config.py | TestConfigOverrides::test_continuous_motion_non_default | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-371 | Heartbeat period min value | test_config.py | TestConfigOverrides::test_heartbeat_period_min | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-374 | Ground mode config sent on boot | test_boot.py | test_power_cycle_produces_bootmsg, test_boot_reports_firmware_version | PASS | — |
| PRDTST-387 | Continuous motion period min (1s) | test_config.py | TestConfigOverrides::test_continuous_motion_min | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-388 | Default ground mode config values | test_config.py | TestConfigDefaults::test_all_defaults_match | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-394 | Continuous motion period max (65535s) | test_config.py | TestConfigOverrides::test_continuous_motion_max | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |
| PRDTST-399 | Stop motion timeout default (2 min) | test_config.py | TestConfigDefaults::test_stop_motion_timeout_default | IMPLEMENTED | Implemented — uses CloudClient.get_ground_mode_config() |

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
| PRDTST-333 | GNSS position-based heading estimate (within 10 deg) | test_gnss.py | TestGNSS::test_heading_accuracy | IMPLEMENTED | Implemented — skips gracefully without GPS signal |
| PRDTST-343 | GNSS cold start fix (within 1 min, 6m accuracy, aiding disabled) | test_gnss.py | TestGNSS::test_cold_start_fix_1min_6m | IMPLEMENTED | Implemented — skips gracefully without GPS signal |
| PRDTST-358 | GNSS position-based speed estimate (within 20%) | test_gnss.py | TestGNSS::test_speed_accuracy | IMPLEMENTED | Implemented — skips gracefully without GPS signal |
| PRDTST-360 | GNSS warm start fix (within 30s, 1m accuracy, aiding disabled) | test_gnss.py | TestGNSS::test_warm_start_fix_30s_1m | IMPLEMENTED | Implemented — skips gracefully without GPS signal |
| PRDTST-378 | GNSS cold start fix (within 30s, 1m accuracy, aiding enabled) | test_gnss.py | TestGNSS::test_cold_start_fix_30s_with_aiding | IMPLEMENTED | Implemented — skips gracefully without GPS signal |
| PRDTST-384 | GNSS cold start fix extended (within 3 min, 1m accuracy, aiding disabled) | test_gnss.py | TestGNSS::test_cold_start_fix_3min_1m | IMPLEMENTED | Implemented — skips gracefully without GPS signal |
| PRDTST-396 | GNSS warm start fix (within 30s, 1m accuracy, aiding enabled) | test_gnss.py | TestGNSS::test_warm_start_fix_30s_with_aiding | IMPLEMENTED | Implemented — skips gracefully without GPS signal |

### On-Skin / Biometrics (3 tests)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-327 | Biometric data messages sent when on-skin | test_biometric.py | test_on_skin_detected, test_biometric_includes_temperature | PASS | — |
| PRDTST-379 | Position messages sent when on-skin | test_biometric_advanced.py | TestBiometricAdvanced::test_position_message_on_skin | IMPLEMENTED | — |
| PRDTST-400 | On-skin detection (on and off) | test_biometric.py | test_on_skin_detected, test_off_skin_detected | PASS | — |

### Button / SOS / Haptic (9 tests)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-325 | Negative test: no SOS for <3s or >6s press | test_button.py | test_short_press_no_power_off | PASS | Partial: verifies short press does not power off; SOS-specific negative verification NOT_STARTED |
| PRDTST-346 | Hard reset on 7 rapid presses | test_button_advanced.py | TestButtonAdvanced::test_hard_reset_on_seven_presses | IMPLEMENTED | — |
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
| PRDTST-376 | FUOTA from previous release to current | test_01_mfg_to_mfg_fuota.py | TestMfgToMfgFuota | IMPLEMENTED | — |

### VSM / IPC (1 test)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-410 | VSM power cut-off switch | — | — | NOT_STARTED | Requires GPIO-controlled VSM power switch + current verification |

### Operating Temperature (1 test)

| PRDTST ID | Description | Test File | Test Method | Status | Blocker |
|-----------|-------------|-----------|-------------|--------|---------|
| PRDTST-401 | Operate within -20C to +60C | — | — | BLOCKED | Requires environmental chamber for temperature sweep |

## Summary by Category

| Category | Total | PASS | IMPLEMENTED | XFAIL | SKIP | BLOCKED | NOT_STARTED |
|----------|-------|------|-------------|-------|------|---------|-------------|
| Power / Runtime | 7 | 2 | 0 | 0 | 0 | 5 | 0 |
| Config Values | 18 | 1 | 17 | 0 | 0 | 0 | 0 |
| Motion Detection | 5 | 0 | 0 | 0 | 4 | 1 | 0 |
| Charging / BMS | 29 | 0 | 0 | 2 | 0 | 27 | 0 |
| Environmental Sensors | 7 | 4 | 0 | 0 | 0 | 0 | 3 |
| GNSS | 7 | 0 | 7 | 0 | 0 | 0 | 0 |
| On-Skin / Biometrics | 3 | 2 | 1 | 0 | 0 | 0 | 0 |
| Button / SOS / Haptic | 9 | 3 | 1 | 0 | 0 | 5 | 0 |
| NFC | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| FUOTA | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| VSM / IPC | 1 | 0 | 0 | 0 | 0 | 0 | 1 |
| Operating Temperature | 1 | 0 | 0 | 0 | 0 | 1 | 0 |
| **TOTAL** | **89** | **12** | **27** | **2** | **5** | **39** | **4** |

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

### Software / Integration Blockers (Resolved)

| Blocker | Affected Tests | Count | Status |
|---------|---------------|-------|--------|
| ~~CoreCloud config message parsing not implemented~~ | PRDTST-328, 330, 335, 342, 344, 347, 352, 353, 356, 359, 364, 369, 371, 387, 388, 394, 399 | 17 | RESOLVED — uses CloudClient.get_ground_mode_config() |
| ~~GNSS simulator or clear sky test location needed~~ | PRDTST-333, 343, 358, 360, 378, 384, 396 | 7 | RESOLVED — skips gracefully without GPS signal |
| ~~FUOTA test automation not written~~ | PRDTST-376 | 1 | RESOLVED — test_01_mfg_to_mfg_fuota.py |

## Test File Index

| Test File | Path | PRDTST Coverage |
|-----------|------|-----------------|
| test_boot.py | apps/validation/alpha/tests/regression/test_boot.py | PRDTST-341, 374, 404 |
| test_power.py | apps/validation/alpha/tests/regression/test_power.py | General power budget (no direct PRDTST mapping) |
| test_motion.py | apps/validation/alpha/tests/regression/test_motion.py | PRDTST-324, 326, 375, 393 |
| test_environmental.py | apps/validation/alpha/tests/regression/test_environmental.py | PRDTST-345, 357, 398, 406 |
| test_biometric.py | apps/validation/alpha/tests/regression/test_biometric.py | PRDTST-327, 400 |
| test_biometric_advanced.py | apps/validation/alpha/tests/regression/test_biometric_advanced.py | PRDTST-379 |
| test_button.py | apps/validation/alpha/tests/regression/test_button.py | PRDTST-325, 338, 377, 382, 412 |
| test_button_advanced.py | apps/validation/alpha/tests/regression/test_button_advanced.py | PRDTST-346 |
| test_config.py | apps/validation/alpha/tests/regression/test_config.py | PRDTST-328, 330, 335, 342, 344, 347, 352, 353, 356, 359, 364, 369, 371, 387, 388, 394, 399 |
| test_gnss.py | apps/validation/alpha/tests/regression/test_gnss.py | PRDTST-333, 343, 358, 360, 378, 384, 396 |
| test_nfc.py | apps/validation/alpha/tests/regression/test_nfc.py | PRDTST-337 |
| test_01_mfg_to_mfg_fuota.py | apps/validation/alpha/tests/regression/test_01_mfg_to_mfg_fuota.py | PRDTST-376 |
| test_corecloud_integration.py | apps/validation/alpha/tests/regression/test_corecloud_integration.py | Infrastructure (no direct PRDTST mapping) |
| test_smoke_mtib.py | apps/validation/alpha/tests/test_smoke_mtib.py | Infrastructure (no direct PRDTST mapping) |
