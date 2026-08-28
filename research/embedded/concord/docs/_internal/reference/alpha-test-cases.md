# Alpha Test Cases (PRDTST) — Reference

Extracted from Jira project PRDTST on 2026-02-25.
These test cases are the official product test suite for the Alpha device.
They map to Concord validation Stages 3 and 4.
Total Alpha test cases: 89

## Power / Runtime (7 tests)

- **PRDTST-331**: Test Long-term Sleep Current Consumption Average
  - The device shall consume less than an average of 1.5mA over: 12-hour, 24-hour, 48-hour periods, and 1-week periods of continuous sleep.

- **PRDTST-340**: Test Device Must Operate for 3 Days Under Worst-Case Conditions
  - Verify that the device can operate for 3 days (72 hours) standalone, with continuous biometric and GPS sampling at the worst-case profile, and all messages sent via LTE.

- **PRDTST-341**: Test Device Must Consume Less Than 150mA in Active Mode
  - The device shall consume less than 150mA in active mode.

- **PRDTST-348**: Test Device Must Consume Less than 500µA in Sleep Mode
  - The device shall consume less than an average of 500µA in sleep mode.

- **PRDTST-361**: Test Device Must Consume Less Than 400nA in Lockout Mode
  - The device shall consume less than 400nA when the battery is locked out.

- **PRDTST-363**: Test Device Must Operate for 3 Days Standalone Normal Use
  - Verify that the device can operate for 3 days (72 hours) standalone, with continuous biometric and GPS sampling at

- **PRDTST-404**: Test Device Must Consume Less than 50mA in Normal Use Mode
  - The device shall consume less than 50mA in active mode over a 10 minute period.

## Config Values (Heartbeat, Motion, GPS) (18 tests)

- **PRDTST-328**: Test Motion Stop Acquisition Timeout Default Value
  - Verify that the device can be configured to run GPS for motion stop acquisitions at the default period.

- **PRDTST-330**: Test Heartbeat Acquisition Timeout Default Value
  - Verify that the device can be configured to run GPS for heartbeat acquisitions at the default period (60 seconds).

- **PRDTST-335**: Test Zero Heartbeat Period
  - Verify that the device can be configured to not send heartbeat messages.

- **PRDTST-342**: Test Continuous Motion Period Default Value
  - Verify that the device can be configured to send a continuous motion message at the default period.

- **PRDTST-344**: Test Heartbeat Period Max Value
  - Verify that the device can be configured to send a heartbeat message at the specified period. (2-byte value)

- **PRDTST-347**: Test Stop Motion Timeout Non-Default Value
  - Verify that the device can be configured to send a stop motion message at the specified period.

- **PRDTST-352**: Test Heartbeat Period Default Value
  - Verify that the device can be configured to send a heartbeat message at the default period.

- **PRDTST-353**: Test Start Motion Window Start Default Value
  - Verify that the device can be configured to begin the start motion window at the default period (3 seconds).

- **PRDTST-356**: Test Heartbeat Period Non-Default Value
  - Verify that the device can be configured to send a heartbeat message at the specified period.

- **PRDTST-359**: Test Heartbeat Acquisition Timeout Non-Default Value
  - Verify that the device can be configured to run GPS for heartbeat acquisitions at the specified period.

- **PRDTST-364**: Test Continuous Motion Disabled
  - Verify that the device can be configured to not send continuous motion messages.

- **PRDTST-369**: Test Continuous Motion Period Non-Default Value
  - Verify that the device can be configured to send a continuous motion message at the specified period.

- **PRDTST-371**: Test Heartbeat Period Min Value
  - Verify that the device can be configured to send a heartbeat message at the specified period.

- **PRDTST-374**: Test Ground Mode Config sent on boot
  - Verify that the device sends its current Ground Mode Config Message to the server on boot.

- **PRDTST-387**: Test Continuous Motion Period Min Value
  - Verify that the device can be configured using a continuous motion period of 1 second.

**TODO/TBD/NOTE:** Application/device behavior at this setting is undefined and should.

- **PRDTST-388**: Test Default Ground Mode Config Values
  - Verify that a fresh device has the default Ground Mode Config V2 Message values.

- **PRDTST-394**: Test Continuous Motion Period Max Value
  - Verify that the device can be configured using a continuous motion period of 65535 seconds (approximately 18.2 hours).

- **PRDTST-399**: Test Stop Motion Timeout Default Value
  - Verify that the device can be configured to send a stop motion message at the default period (2 minutes)

## Motion Detection (5 tests)

- **PRDTST-324**: Test Ignore motion below acceleration threshold
  - The device shall not detect motion when the acceleration is below the threshold, even if the duration is above the threshold.

- **PRDTST-326**: Test Detect motion above thresholds with default config
  - The device shall detect motion when the acceleration is above the threshold and the duration is above the threshold.

- **PRDTST-375**: Test Ignore motion below duration threshold
  - Verify the device does not detect motion when not moved over the time duration threshold but exceeding the acceleration threshold.

- **PRDTST-389**: Test Axis independence
  - The device shall detect motion in all three axes independently, meaning that motion in one axis should not affect the detection of motion in another axis.

- **PRDTST-393**: Test Respect motion start window
  - The device shall not detect motion until the start motion window has elapsed, even if the acceleration is above the threshold and the duration is above the threshold.

## Charging / BMS (29 tests)

- **PRDTST-332**: Test Charge Controller Temperature Measurement Short Circuit Start Charging
  - Verify that the charge controller will not charge the battery when the TS pin is shorted at the start of charging.

- **PRDTST-334**: Test State of Charge (SoC) Reporting
  - When the battery is discharged to 0% SoC, the device shall report SoC within ±2% of the true value as measured by external test equipment.

- **PRDTST-338**: Test Device Must Communicate Charge Level via LEDs when button is pressed once
  - The device shall communicate the charge level via the status LEDs across the entire battery SoC range when the button is pressed once (less than a 1 second press).

- **PRDTST-339**: Test Charge Controller Temperature Measurement Short Circuit while
  - Verify that the charge controller will not charge the battery when the TS pin is shorted.

- **PRDTST-349**: Test No FUOTA on low battery
  - Verify that FUOTAs can not complete when the battery is critically low (3.7v)

- **PRDTST-350**: Test Battery Temperature Reported in Position Message
  - The device shall report the battery temperature via the Position Message

- **PRDTST-351**: Test Device Must Not charge at negative temperatures
  - The device shall not charge the battery when the battery temperature is below 0°C.

- **PRDTST-354**: Test Connecting Charger Must Delatch Device from Lockout
  - The device shall wake up and start charging the battery when the charger is connected, even when the battery is locked out.

- **PRDTST-355**: Test Device Must Communicate On-Charger State via LEDs
  - The device shall communicate the on-charger state via the status LEDs across the entire battery SoC range.

- **PRDTST-365**: Test Device Must Charge Using Charge Ladder
  - The device shall charge the battery using a charge ladder to maximize cycle life.

- **PRDTST-366**: Test BMS Battery SoC and Temp Reported in Position Message
  - Verify that the device reports the battery SoC and temperature via the Position Message while in motion and on-skin

- **PRDTST-367**: Test BMS Temperature Measurement Accuracy
  - Verify the BMS reports the board temperature to within ±2°C of the value measured by an external calibrated thermometer, across the operating temperature range.

- **PRDTST-368**: Test Device Must Report On-Charger State in Position Message
  - The device shall report the on-charger state via the Position Message when the device is connected to a charger.

- **PRDTST-370**: Test Device Must Charge from 3.5V to 4.2V in Under 3 Hours
  - The device shall charge the battery from 3.5V to 4.2V in under three hours.

- **PRDTST-372**: Test Device Must Not Charge Above 45°C
  - The device shall not charge the battery when the battery temperature is above 45°C, measured at the battery terminals via the external thermistor wired to the charge controller.

- **PRDTST-373**: Test Device Must Communicate Charge Level via LEDs while charging
  - The device shall communicate the charge level via the status LEDs across the entire battery SoC range.

- **PRDTST-381**: Test BMS Parameter Retention and Application
  - Verify that the BMS retains and/or applies the correct configuration after a power cycle.

- **PRDTST-383**: Test Device Must Not Charge Below 10°C
  - The device shall not charge the battery when the battery temperature is below 10°C, measured at the battery terminals via the external thermistor wired to the charge controller.

- **PRDTST-385**: Test Device Must Lockout Battery Discharge at 3.5V
  - The device shall lock out battery discharge when the battery voltage falls below 3.5V.

- **PRDTST-386**: Test Device Must Detect Charger Connection Low Battery Not Charging
  - The device should detect on-charger state when the battery is not charging.

- **PRDTST-390**: Test Charge Controller Temperature Measurement Open Circuit Start Charging
  - Verify that the charge controller will not charge the battery when the TS pin is open circuit at the start of charging.

- **PRDTST-391**: Test Device Must Stop Charging at 4.3V with 10mA Termination Current
  - The device shall stop charging the battery at 4.3V with a 20mA termination current.

- **PRDTST-392**: Test Device Must Trickle Charge Below 3.5V
  - The device shall trickle charge the battery at 10mA when the battery voltage is below 3.5V.

- **PRDTST-397**: Test Device Must Detect Charger Connection Full Battery
  - The device shall detect when it is connected to a charger when the battery is fully charged.

- **PRDTST-402**: Test Device Must Detect Charger Connection Low Battery
  - The device should detect on-charger state across the entire battery voltage range.

- **PRDTST-407**: Test Charge Controller Temperature Measurement Accuracy
  - Verify that the charg controller reports the battery temperature within ±2°C of the value measured by an external calibrated thermometer, across the operating temperature range.

- **PRDTST-409**: Test Charge Controller Temperature Measurement Open Circuit while Charging
  - Verify that the charg controller will not charge the battery when the TS pin is open circuit.

- **PRDTST-411**: Test BMS Recovery Voltage Behavior
  - Verify the BMS clears the empty detection flag once the battery voltage rises above the recovery voltage (3.88 V).

- **PRDTST-412**: Test Button Press to Check Battery Status
  - Verify the device reports it's battery level when the button is pressed once.

## Environmental Sensors (BME280, MLX90614) (7 tests)

- **PRDTST-329**: Test Altitude Ceiling Measurement
  - The device must measure the altitude ceiling with in ±25 meters (±0.0295 inHg or ≈ ±1.0 hPa) accuracy, when compared to a calibrated altimeter.

- **PRDTST-336**: Test Detect elevation change
  - The device shall detect a 3 meter elevation change.

- **PRDTST-345**: Test Absolute Temperature Measurement
  - The device must calculate the absolute temperature with in ±0.5°C accuracy, when compared to a calibrated thermometer.

- **PRDTST-357**: Test Absolute Pressure Measurement
  - The device must calculate the absolute pressure with in ±0.05 inHg (≈ ±1.7 hPa) accuracy, when compared to a calibrated barometer.

- **PRDTST-398**: Test Absolute Humidity Measurement
  - The device must calculate the absolute humidity with in ±3%RH accuracy, when compared to a calibrated hygrometer.

Accuracy at 20%, 40%, 60%, and 80% RH is within ±3%RH.

- **PRDTST-405**: Test Detect humidity change
  - The device shall detect a 5% change in relative humidity.

- **PRDTST-406**: Test Detect temperature change
  - The device shall detect a 0.1°C change in relative temperature.

## GNSS (7 tests)

- **PRDTST-333**: Test GNSS Position Based Heading Estimate
  - The device shall be able to estimate its heading based on GNSS position fixes with an accuracy of 10 degrees.

- **PRDTST-343**: Test GNSS Position Fix Cold Start Aiding Disabled, Minimum Requirements
  - The device shall be able to acquire a position fix within 1 minutes, under clear sky conditions, with an accuracy of 6 meter or better.

- **PRDTST-358**: Test GNSS Position Based Speed Estimate
  - The device shall be able to estimate its speed based on GNSS position fixes with an accuracy of 20%.

- **PRDTST-360**: Test GNSS Position Fix Warm Start Aiding Disabled
  - When GPS-Aiding is disabled, and the device is preforming a warm boot where the device has a valid position fix, the device shall be able to acquire a position fix within 30 seconds, under clear sky conditions, with an accuracy of 1 meter or better.

- **PRDTST-378**: Test GNSS Position Fix Cold Start Aiding Enabled
  - When GPS-Aiding is enabled, the device shall be able to acquire a position fix within 30 seconds, under clear sky conditions, with an accuracy of 1 meter or better.

- **PRDTST-384**: Test GNSS Position Fix Cold Start Aiding Disabled, Extended Requirements
  - The device shall be able to acquire a position fix within 3 minutes, under clear sky conditions, with an accuracy of 1 meter or better.

- **PRDTST-396**: Test GNSS Position Fix Warm Start Aiding Enabled
  - When GPS-Aiding is enabled, and the device is preforming a warm boot where the device has a valid position fix, the device shall be able to acquire a position fix within 30 seconds, under clear sky conditions, with an accuracy of 1 meter or better.

## On-Skin / Biometrics (3 tests)

- **PRDTST-327**: Test Biometric Data Messages Sent When On-Skin
  - The device shall send biometric data messages when it is on-skin.

- **PRDTST-379**: Test Position Messages Sent When On-Skin
  - The device shall send position messages when it is on-skin.

- **PRDTST-400**: Test On-Skin Detection
  - The device shall detect when it is on-skin and when it is not.

## Button / SOS / Haptic (9 tests)

- **PRDTST-325**: Negative Test Button Press to Enter SOS Emergency Mode
  - The device shall not enter SOS emergency mode when the button is pressed for less than 3 seconds or more than 6 seconds.

- **PRDTST-346**: Test Button Press to Hard Reset Device
  - Verify the device performs a hard reset when the button is pressed 7 times in quick succession.

**TODO/TBD:** Need a way to verify that the VSM rebooted.

- **PRDTST-362**: Test Haptic Feedback on SOS Emergency Mode Entry
  - Verify the device provides haptic feedback when it enters SOS emergency mode.

- **PRDTST-377**: Test  Button Press to Enter Manufacturing Test Mode
  - Verify the device enters manufacturing test mode when the button is double-clicked.

- **PRDTST-380**: Test Haptic Feedback on SOS Acknowledgement
  - Verify the device provides haptic feedback when it receives an SOS acknowledgement message.

- **PRDTST-382**: Test Button Press to Enter SOS Emergency Mode
  - `The device shall enter SOS emergency mode when the button is pressed and held for between 3 and 6 seconds.`

- **PRDTST-395**: Negative Test Haptic Feedback on Button Press for 3 Seconds
  - The device shall not provide haptic feedback when the button is pressed for less than 3 seconds.

- **PRDTST-403**: Test Haptic Feedback on Manufacturing Test Entry and Exit
  - Verify the device provides haptic feedback when it enters and exits manufacturing test mode.

- **PRDTST-408**: Test Haptic Feedback on Button Press for 3 Seconds
  - Verify the device provides haptic feedback when the button is pressed for 3 seconds.

## NFC (1 tests)

- **PRDTST-337**: Test NFC Broadcast Device ID
  - Verify device broadcasts it's unique ID via NFC.

## FUOTA (1 tests)

- **PRDTST-376**: Test FUOTA from previous release to current
  - Verify the device can successfully FUOTA from the previous release to this build.

## VSM / IPC (1 tests)

- **PRDTST-410**: Test VSM Power Cut-off Switch
  - Verify that the VSM power cut-off switch is functional and can cut off power to the VMS.

## Operating Temperature (1 tests)

- **PRDTST-401**: Test Device Must Operate Within -20°C to +60°C
  - The device shall operate within a temperature range of -20°C to +60°C.
  - **Note:** Miscategorized as "Cloud Messages" in Jira. Correctly belongs under Power/Runtime (see arch-stage4 Section 5.1).

