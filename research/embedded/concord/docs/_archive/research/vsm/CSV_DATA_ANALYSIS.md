# Alpha Wearable VSM Data Analysis

**Date of Analysis:** 2026-02-09
**Data Source:** Live capture from Alpha wearable device (PAH8151 PPG + LSM6DSO accelerometer, Philips PSP library)
**bio.csv:** 512 rows of vitals data
**pos.csv:** 145 rows of position/motion data

---

## 1. Dataset Overview

### Device Information

| Field | bio.csv | pos.csv |
|-------|---------|---------|
| Device ID | `8121069319214735276` | `70b3d584c01e1fac` |
| ID Format | Decimal integer | Hex string |

The two files use different device ID formats. The bio device ID is a decimal integer (likely derived from a 64-bit identifier), while the pos device ID is a hex string. These likely represent different subsystem identifiers on the same physical device (the VSM sensor subsystem vs. the cellular/GPS module).

### Temporal Coverage

| Metric | bio.csv | pos.csv |
|--------|---------|---------|
| Start (UTC) | 2026-02-09 21:14:49 | 2026-02-09 19:39:24 |
| End (UTC) | 2026-02-09 22:26:57 | 2026-02-09 22:27:53 |
| Duration | 1h 12m 8s | 2h 48m 29s |
| Start (MST) | 2026-02-09 14:14:49 | 2026-02-09 12:39:24 |
| End (MST) | 2026-02-09 15:26:57 | 2026-02-09 15:27:53 |

The position data starts ~1.5 hours before vitals data begins. This indicates either that the VSM sensor was activated later than the position module, or the device was not on-body during the initial position-reporting period.

---

## 2. Heart Rate Analysis

### Distribution Statistics

| Statistic | Value |
|-----------|-------|
| Count | 512 |
| Min | 69 BPM |
| Max | 124 BPM |
| Mean | 91.69 BPM |
| Median | 90 BPM |
| Std Dev | 10.28 BPM |
| P5 | 78 BPM |
| P10 | 80 BPM |
| P25 | 84 BPM |
| P50 | 90 BPM |
| P75 | 98 BPM |
| P90 | 107 BPM |
| P95 | 113 BPM |

The distribution is slightly right-skewed (mean > median) with a reasonable physiological range. No implausible readings (all values 69-124 BPM).

### Most Frequent HR Values (Top 10)

| HR (BPM) | Count | Percentage |
|-----------|-------|------------|
| 82 | 28 | 5.5% |
| 93 | 26 | 5.1% |
| 88 | 24 | 4.7% |
| 84 | 24 | 4.7% |
| 85 | 23 | 4.5% |
| 89 | 21 | 4.1% |
| 91 | 20 | 3.9% |
| 90 | 18 | 3.5% |
| 87 | 18 | 3.5% |
| 94 | 18 | 3.5% |

No single HR value dominates, suggesting real variability rather than a stuck sensor.

### HR Jumps (>15 BPM Between Consecutive Samples)

**Total jumps:** 29 out of 511 consecutive pairs (5.7%)

Notable examples:

| Time (UTC) | From | To | Delta | Conf Before | Conf After |
|------------|------|-----|-------|-------------|------------|
| 21:17:47 | 104 | 85 | 19 | 25 | 25 |
| 21:19:57 | 93 | 110 | 17 | 25 | 75 |
| 21:20:07 | 110 | 89 | 21 | 75 | 75 |
| 21:21:27 | 98 | 81 | 17 | 100 | 50 |
| 21:22:47 | 96 | 78 | 18 | 100 | 100 |
| 21:23:47 | 96 | 80 | 16 | 100 | 75 |
| 21:32:57 | 108 | 89 | 19 | 25 | 25 |
| 21:33:17 | 82 | 101 | 19 | 50 | 50 |

**Key observations:**
- Many jumps occur during low-confidence periods (conf=25), suggesting motion artifact
- Some jumps happen even at conf=100, particularly drops from high HR (~96-100) to lower values (~78-83), which may represent true physiological transitions (e.g., brief exertion ending)
- The largest single jump is 21 BPM (110 to 89 at 21:20:07)

---

## 3. HR Confidence Analysis

| Confidence Level | Count | Percentage |
|-----------------|-------|------------|
| 25 | 31 | 6.1% |
| 50 | 72 | 14.1% |
| 75 | 175 | 34.2% |
| 100 | 234 | 45.7% |

**Mean confidence: 79.88**

The confidence values are discrete at 25-point intervals (25, 50, 75, 100). Nearly 80% of readings are at confidence 75 or 100, indicating generally good signal quality. Only 6.1% are at the lowest confidence level (25).

### Low-Confidence Periods (conf < 50)

| Period | Rows | Duration | Time Range (UTC) | HR Range |
|--------|------|----------|------------------|----------|
| 1 | 0-11 | 188s | 21:14:49 - 21:17:57 | 70-104 |
| 2 | 26 | 0s | 21:19:47 | 93 |
| 3 | 118-123 | 40s | 21:32:17 - 21:32:57 | 89-108 |
| 4 | 148-149 | 10s | 21:36:27 - 21:36:37 | 93-104 |
| 5 | 337-339 | 10s | 22:03:17 - 22:03:27 | 96-106 |
| 6 | 358-361 | 20s | 22:05:57 - 22:06:17 | 107-112 |
| 7 | 386-388 | 20s | 22:09:27 - 22:09:47 | 96-121 |

**Period 1 is notable:** The first 3+ minutes after VSM startup show exclusively low confidence (25). This is the PPG sensor "settling in" period where the Philips PSP algorithm has not yet converged. HR values during this period (70-104) show high variability and should be treated as unreliable.

---

## 4. HSI (Heart Signal Index) Analysis

HSI reflects PPG signal quality from the PAH8151 sensor. Higher values generally indicate stronger signal.

| Statistic | Value |
|-----------|-------|
| Count | 512 |
| Min | 0.20 |
| Max | 3.10 |
| Mean | 1.53 |
| Median | 1.40 |
| Std Dev | 0.55 |

### HSI Distribution

| HSI Range | Count | Percentage | Signal Quality |
|-----------|-------|------------|---------------|
| 0.2-0.8 | 37 | 7.2% | Poor |
| 0.9-1.2 | 149 | 29.1% | Moderate |
| 1.3-1.8 | 184 | 35.9% | Good |
| 1.9-2.4 | 62 | 12.1% | Very Good |
| 2.5-3.1 | 80 | 15.6% | Excellent |

The majority of readings (77.7%) fall in the moderate-to-very-good range (0.9-2.4). The single reading at HSI=0.2 corresponds to the very first measurement at VSM startup.

### HSI Trend Over Session (Quartile Analysis)

| Time Quarter | Time Range (UTC) | Mean HSI | Mean HR Conf |
|-------------|------------------|----------|-------------|
| Q1 (first 25%) | 21:14:49 - 21:33:27 | 1.18 | 81.1 |
| Q2 (25-50%) | 21:33:37 - 21:51:27 | 1.26 | 83.6 |
| Q3 (50-75%) | 21:51:37 - 22:08:57 | 1.81 | 74.4 |
| Q4 (last 25%) | 22:09:07 - 22:26:57 | 1.88 | 80.5 |

**HSI increases over the session** (from mean 1.18 to 1.88), likely due to the skin warming up and improving optical coupling with the PPG sensor. Notably, Q3 shows the highest HR values (mean 96.3) and lowest confidence (74.4) despite increasing HSI, suggesting motion was the primary confidence-degrading factor in that period.

---

## 5. SpO2 Analysis

### Availability

| Metric | Value |
|--------|-------|
| Total readings | 512 |
| Non-zero SpO2 readings | 144 (28.1%) |
| Zero SpO2 readings | 368 (71.9%) |
| SpO2 time range (when active) | 21:18:07 - 22:22:57 UTC |

**SpO2 is NOT always zero.** It produces valid readings 28.1% of the time, but availability is intermittent. The SpO2 measurement cycles on and off throughout the session in blocks ranging from 2 to 22 consecutive samples (10-170 seconds). There is one extended outage of 131 consecutive zero samples (21:57:37 - 22:14:37, approximately 17 minutes).

### SpO2 Value Distribution (Non-Zero Only)

| SpO2 % | Count | Percentage |
|--------|-------|------------|
| 95 | 7 | 4.9% |
| 96 | 29 | 20.1% |
| 97 | 69 | 47.9% |
| 98 | 25 | 17.4% |
| 99 | 5 | 3.5% |
| 100 | 9 | 6.3% |

**Mean: 97.1% -- Range: 95-100%**

All non-zero values are physiologically reasonable. The distribution centers tightly around 97%, consistent with normal healthy blood oxygen levels.

### SpO2 Confidence Distribution (Non-Zero SpO2 Only)

| Confidence | Count | Notes |
|------------|-------|-------|
| 0 | 11 | SpO2 value present but zero confidence |
| 25 | 26 | Low confidence |
| 50 | 7 | Medium confidence |
| 75 | 2 | High confidence |
| 100 | 98 | Full confidence |

**68% of non-zero SpO2 readings have full confidence (100).** However, 11 readings report a non-zero SpO2 value but zero confidence, which is an unusual pattern -- the PSP library may be reporting a "best guess" even when it cannot confirm accuracy.

### SpO2 High-Confidence Summary

When SpO2 confidence >= 75: **100 readings** with SpO2 range 96-100%, mean 97.3%. These are the most trustworthy SpO2 measurements.

### SpO2 Interpretation

SpO2 measurement is enabled but operates intermittently, likely controlled by the PSP library's internal state machine. The algorithm appears to switch between HR-focused and SpO2-focused measurement modes. When SpO2 readings are available, they show healthy oxygenation levels with high confidence.

---

## 6. Temperature Analysis

### Skin Temperature

| Statistic | Value |
|-----------|-------|
| Min | 31.89 C |
| Max | 34.99 C |
| Mean | 34.27 C |
| Std Dev | 0.79 C |
| Range | 3.10 C |

### Skin Temperature Trend

| Quarter | Mean Skin Temp |
|---------|---------------|
| Q1 (21:14 - 21:33) | 33.10 C |
| Q2 (21:33 - 21:51) | 34.34 C |
| Q3 (21:51 - 22:08) | 34.86 C |
| Q4 (22:09 - 22:26) | 34.78 C |

**Skin temperature rises sharply in the first half** (from 33.1 C to 34.9 C), then plateaus. This is consistent with the device being placed on-body at the start of the capture and the skin warming under the sensor. The initial low readings (31.89 C) suggest the device was cold/off-body before the session began.

### Core Temperature (Estimated)

| Statistic | Value |
|-----------|-------|
| Min | 37.00 C |
| Max | 37.36 C |
| Mean | 37.16 C |
| Std Dev | 0.10 C |
| Range | 0.36 C |

Core temperature shows very narrow variance (0.36 C range), which is expected for a healthy individual. The estimate is derived from the PSP algorithm using skin temperature and a thermal model.

### External Temperature

| Statistic | Value |
|-----------|-------|
| Min | 28.51 C |
| Max | 32.39 C |
| Mean | 30.98 C |
| Std Dev | 0.98 C |

External temperature (ambient from on-board sensor) ranges from 28.5 C to 32.4 C, consistent with a warm indoor environment or device-generated heat.

### Temperature-HR Correlation

| Pair | Pearson r |
|------|-----------|
| Skin Temp vs HR | 0.1404 |
| Core Temp vs HR | 0.1840 |

Both correlations are weakly positive, meaning higher skin/core temperature is mildly associated with higher heart rate. This is expected physiologically but the correlation is not strong.

---

## 7. VSM On-Time

| Value (seconds) | Count | Percentage |
|-----------------|-------|------------|
| 3 | 1 | 0.2% |
| 6 | 1 | 0.2% |
| 9 | 24 | 4.7% |
| 10 | 483 | 94.3% |
| 60 | 2 | 0.4% |
| 181 | 1 | 0.2% |

**94.3% of readings show VSM on-time = 10 seconds**, which matches the expected 10-second measurement cadence. The initial readings (3, 6, 9) represent the sensor warming up during the first few measurement cycles. The two readings at 60s and one at 181s suggest the sensor was running continuously for an extended period during those measurements, possibly during a calibration or extended SpO2 measurement cycle.

---

## 8. Temporal Analysis (bio.csv)

### Measurement Interval (Time Between Consecutive Measurements)

| Interval | Count | Percentage |
|----------|-------|------------|
| 0s (duplicate time) | 87 | 17.0% |
| 4s | 1 | 0.2% |
| 6s | 2 | 0.4% |
| 10s (nominal) | 420 | 82.2% |
| 112s (gap) | 1 | 0.2% |

**The nominal measurement interval is 10 seconds**, which accounts for 82.2% of intervals. 17.0% of intervals are 0 seconds, meaning 87 measurement times have exactly two records with the same timestamp.

### Duplicate Records

- **87 measurement times have exactly 2 records** (174 out of 512 total records)
- All 87 duplicate pairs are **value-identical** (same HR, confidence, HSI, SpO2, temperatures)
- The duplicate pairs have **different record times** (mean difference 15.19s, range 1.02s - 67.34s)

**Interpretation:** The device appears to transmit the same measurement twice, arriving at the server at different times (average 15s apart). This could be a retry mechanism in the cellular uplink, or a firmware behavior where the same VSM snapshot is packaged in two consecutive BLE/cellular messages. For analysis purposes, one copy of each duplicate should be deduplicated.

### Gaps in Data

There is **one significant gap** of 112 seconds at 21:17:47 UTC (rows 9-10). This gap falls within the initial low-confidence startup period and may represent a sensor reinitialization.

No other gaps exceed the nominal 10-second interval (beyond duplicates).

### Measurement-to-Received Delay

This measures the time between when the measurement was taken on-device and when it was recorded at the server.

| Bucket | Count | Percentage |
|--------|-------|------------|
| < 10s | 218 | 42.6% |
| 10-20s | 147 | 28.7% |
| 20-30s | 105 | 20.5% |
| 30-60s | 21 | 4.1% |
| > 60s | 21 | 4.1% |

| Statistic | Value |
|-----------|-------|
| Min | 9.35s |
| Max | 210.60s |
| Mean | 19.59s |
| Median | 10.51s |
| Std Dev | 24.42s |

Most measurements arrive within 20 seconds, but ~8% take more than 30 seconds. The maximum delay of 210.6 seconds (3.5 minutes) occurred during Q3 of the session.

### Delay by Session Quarter

| Quarter | Mean Delay | Median Delay | Max Delay |
|---------|-----------|-------------|-----------|
| Q1 | 15.0s | 10.2s | 54.2s |
| Q2 | 17.1s | 13.5s | 73.4s |
| Q3 | 29.7s | 10.9s | 210.6s |
| Q4 | 16.5s | 10.2s | 77.3s |

Q3 has the highest mean delay (29.7s), driven by a few extreme outliers (max 210.6s). Median delays are stable around 10-13s across all quarters.

---

## 9. Environmental Sensors (bio.csv)

### Humidity

| Value (%) | Count | Percentage |
|-----------|-------|------------|
| 16-18 | 237 | 46.3% |
| 19-21 | 228 | 44.5% |
| 22-29 | 43 | 8.4% |
| 33-36 | 2 | 0.4% |

Humidity readings are in the 16-29% range for 99.2% of measurements, indicating a dry indoor environment. The few readings at 33-36% may correspond to changes in microenvironment around the sensor.

### Air Pressure (bio.csv)

All 512 readings report air pressure = **28** (likely inHg, consistent with the Scottsdale, AZ area elevation of ~1200 ft). The integer truncation suggests the bio.csv air pressure field has limited resolution.

### Flags

| Flag | Count | Percentage |
|------|-------|------------|
| 0 | 4 | 0.8% |
| 1 | 508 | 99.2% |

Flag=1 for 99.2% of readings. The 4 readings with flag=0 occur at the very start of the session. The meaning of the flag is not specified in the data but may indicate "measurement valid" or "sensor active."

### HeatSOS ID

All 512 readings have heatsosid=0, indicating no heat stress events were detected.

---

## 10. Position/Motion Data Analysis (pos.csv)

### Motion State Distribution

| State | Count | Percentage |
|-------|-------|------------|
| In Motion (true) | 132 | 91.0% |
| Still (false) | 13 | 9.0% |

The device was in motion for the vast majority of position reports.

### Update Reason Distribution

| Reason | Raw Code | Count | Percentage |
|--------|----------|-------|------------|
| Continuous Motion | 5 | 128 | 88.3% |
| Stop Motion | 2 | 10 | 6.9% |
| Heartbeat | 1 | 3 | 2.1% |
| Unknown: 10 | 10 | 3 | 2.1% |
| Boot | 0 | 1 | 0.7% |

The predominant update reason is "Continuous Motion" (88.3%), meaning most position reports were triggered by ongoing motion detection. "Stop Motion" accounts for 6.9%, appearing at each transition from motion to still. The Boot event marks device power-on, and 3 "Heartbeat" reports are periodic keep-alive messages during still periods.

### Motion State Transitions

**18 total transitions** (9 stop-to-motion, 9 motion-to-stop):

| Time (UTC) | Transition | Duration Until Next |
|------------|-----------|-------------------|
| 21:14:19 | STILL -> MOTION | 9m 9s (motion) |
| 21:23:28 | MOTION -> STILL | 1m 3s (still) |
| 21:24:31 | STILL -> MOTION | 46s (motion) |
| 21:25:17 | MOTION -> STILL | 1m 6s (still) |
| 21:26:23 | STILL -> MOTION | 17m 16s (motion) |
| 21:43:39 | MOTION -> STILL | 1m 21s (still) |
| 21:45:00 | STILL -> MOTION | 1m 43s (motion) |
| 21:46:43 | MOTION -> STILL | 51s (still) |
| 21:47:34 | STILL -> MOTION | 8m 2s (motion) |
| 21:55:36 | MOTION -> STILL | 3m 31s (still) |
| 21:59:07 | STILL -> MOTION | 15m 45s (motion) |
| 22:14:52 | MOTION -> STILL | 55s (still) |
| 22:15:47 | STILL -> MOTION | 3m 1s (motion) |
| 22:18:48 | MOTION -> STILL | 1m 11s (still) |
| 22:19:59 | STILL -> MOTION | 1m 50s (motion) |
| 22:21:49 | MOTION -> STILL | 1m 25s (still) |
| 22:23:14 | STILL -> MOTION | 4m 39s (motion) |
| 22:27:53 | MOTION -> STILL | -- (session end) |

**Pattern:** The user appears to be traveling with frequent short stops (1-3 min still periods) and longer motion stretches (up to 17 min). This is consistent with driving in an urban area with traffic stops.

### GPS Fix Quality

| Fix Type | Count | Percentage |
|----------|-------|------------|
| No Fix | 108 | 74.5% |
| 3D | 36 | 24.8% |
| 2D | 1 | 0.7% |

**74.5% of position reports have no GPS fix.** The device is primarily relying on cell-based positioning (datasource = "cell" for all 145 records). When GPS does lock, it achieves a 3D fix.

**GPS during motion vs. still:**

| Fix Type | During Motion | During Still |
|----------|--------------|-------------|
| No Fix | 97 (73.5%) | 11 (84.6%) |
| 3D | 34 (25.8%) | 2 (15.4%) |
| 2D | 1 (0.8%) | 0 |

Slightly better GPS fix rate during motion (25.8% vs 15.4%), possibly due to GPS antenna positioning or environmental factors during travel.

### Satellite Count

| Satellites | Count | Notes |
|-----------|-------|-------|
| 0 | 108 | No fix |
| 4-8 | 9 | Marginal fix |
| 9-12 | 14 | Good fix |
| 13-17 | 12 | Excellent fix |

When GPS does achieve a fix, it typically sees 9-17 satellites.

### Horizontal Accuracy

When GPS has a fix, horizontal accuracy ranges from **2m to 46m** (good). During no-fix periods, accuracy shows 255 (sentinel value) or high values (135-237m), representing cell-tower-derived position with lower accuracy.

### Position Reporting Interval

| Interval | Count | Percentage |
|----------|-------|------------|
| 29-31s (nominal 30s) | 115 | 79.9% |
| 1-20s | 11 | 7.6% |
| 51-88s | 6 | 4.2% |
| 211s | 1 | 0.7% |
| 2016s (~33 min) | 1 | 0.7% |
| 3600s (1 hour) | 1 | 0.7% |

**The nominal position reporting interval is 30 seconds** (79.9% of intervals). The large gaps (2016s, 3600s) occur early in the capture before the bio data starts, likely when the device was in a low-power still mode with reduced reporting frequency.

### Force Data

**All avgforce and maxforce readings are 0.0.** The accelerometer force metrics are not being populated in this firmware version, despite motion being detected. Motion detection is likely based on a different accelerometer threshold/interrupt mechanism that does not log force magnitude.

### Air Pressure (pos.csv)

| Statistic | Value |
|-----------|-------|
| Min | 28.6914 inHg |
| Max | 28.7852 inHg |
| Mean | 28.7088 inHg |
| Std Dev | 0.0112 inHg |

The pos.csv air pressure has full floating-point precision (unlike the integer-truncated bio.csv value). The narrow range (0.09 inHg) is consistent with stable barometric pressure during the session.

### GPS Location

| Coordinate | Min | Max |
|-----------|-----|-----|
| Latitude | 33.2460774 | 33.3551174 |
| Longitude | -111.9413409 | -111.8917425 |

The GPS coordinates place the device in the **Scottsdale/Tempe, Arizona area** (33.3N, -111.9W). The position spans roughly 12 km north-south and 5 km east-west, consistent with urban travel.

### Battery

| Metric | Value |
|--------|-------|
| Battery % | 82-87% (declining over session) |
| Battery mV | 4250-4325 mV |
| On Charger | false (all readings) |

Battery starts at 87% and declines to 82% over the ~3 hour pos.csv window. This is approximately 1.8% per hour, suggesting reasonable battery performance.

### Ground Speed

Reported ground speeds during 3D GPS fix: 0-107 (units likely km/h or 0.01 m/s). The higher values (76-107) during motion are consistent with vehicle travel on roads.

---

## 11. Cross-Correlation: Bio vs. Motion

### HR During Motion vs. Still

| Metric | During Motion (n=439) | During Still (n=73) |
|--------|----------------------|---------------------|
| Mean HR | 92.3 BPM | 88.2 BPM |
| Median HR | 91 BPM | 88 BPM |
| Std Dev | 10.6 BPM | 6.8 BPM |
| Min | 69 BPM | 77 BPM |
| Max | 124 BPM | 102 BPM |

**HR is ~4 BPM higher during motion** with nearly double the standard deviation. The higher variability during motion is consistent with both physiological response and motion artifact. The motion-period minimum of 69 BPM (vs. 77 during still) and maximum of 124 BPM (vs. 102) show a much wider range during motion.

### HR Confidence During Motion vs. Still

| Confidence | During Motion | During Still |
|-----------|--------------|-------------|
| 25 | 31 (7.1%) | 0 (0%) |
| 50 | 70 (15.9%) | 2 (2.7%) |
| 75 | 164 (37.4%) | 11 (15.1%) |
| 100 | 174 (39.6%) | 60 (82.2%) |
| **Mean** | **77.4** | **94.9** |

**Confidence is significantly degraded during motion.** Mean confidence drops from 94.9 (still) to 77.4 (motion). All 31 lowest-confidence readings (conf=25) occur during motion. During still periods, 82.2% of readings achieve full confidence.

### HSI During Motion vs. Still

| Metric | During Motion | During Still |
|--------|--------------|-------------|
| Mean HSI | 1.55 | 1.41 |
| Median HSI | 1.40 | 1.40 |
| Std Dev | 0.58 | 0.30 |

Paradoxically, mean HSI is slightly **higher** during motion (1.55 vs 1.41). However, HSI standard deviation is nearly double during motion (0.58 vs 0.30), indicating more signal instability. The higher mean may be influenced by the temporal trend (HSI increases over the session as the skin warms).

### HSI Change at Motion Onset (Stop -> Motion Transitions)

| Transition Time | HSI Before (30s avg) | HSI After (30s avg) | Conf Before | Conf After |
|----------------|---------------------|---------------------|-------------|------------|
| 21:24:31 | 1.27 | 1.20 | 100 | 81 |
| 21:26:23 | 1.60 | 0.93 | 94 | 92 |
| 21:45:00 | 1.53 | 1.20 | 100 | 81 |
| 21:47:34 | 1.43 | 1.30 | 83 | 83 |
| 21:59:07 | 1.53 | 1.72 | 92 | 70 |
| 22:15:47 | 1.70 | 1.90 | 83 | 95 |
| 22:19:59 | 1.80 | 1.65 | 100 | 75 |
| 22:23:14 | 1.60 | 2.40 | 58 | 58 |

**Confidence consistently drops at motion onset** in most transitions (6 out of 8 show lower confidence after). HSI behavior is mixed -- it drops in early transitions but sometimes increases in later ones (when baseline HSI is already higher due to skin warming).

### SpO2 During Motion vs. Still

| Metric | During Motion | During Still |
|--------|--------------|-------------|
| Non-zero readings | 104 / 439 (23.7%) | 40 / 73 (54.8%) |
| Mean SpO2 (when present) | 97.2% | 96.9% |

**SpO2 availability is significantly higher during still periods** (54.8% vs 23.7%). The PSP algorithm is more likely to report SpO2 when the sensor is stable. However, when SpO2 is reported during motion, the values are still physiologically valid.

---

## 12. Anomalies and Data Quality Issues

### Issue 1: Duplicate Records (174 of 512 rows, 34%)

87 measurement timestamps appear twice with identical vital signs but different server receive times (average 15s apart). This inflates the dataset by 34%. **Recommendation:** Deduplicate by (deviceid, timeofmeasurement) before analysis.

### Issue 2: Startup Low-Confidence Period

The first 12 samples (~3 minutes) show conf=25 with erratic HR (70-104 BPM range, 19+ BPM jumps). This is the PPG sensor initialization phase. **Recommendation:** Discard or flag measurements where VSM on-time < 10 and confidence <= 25.

### Issue 3: 112-Second Gap

A single gap of 112 seconds occurs at 21:17:47 UTC during the startup phase. No data loss is evident after this gap.

### Issue 4: Force Data Not Populated

All avgforce and maxforce values are 0.0 in pos.csv despite active motion detection. The accelerometer force logging may not be enabled in this firmware build.

### Issue 5: GPS Fix Rate

Only 25.5% of position reports have a GPS fix. The device relies heavily on cell-tower positioning, which provides significantly lower accuracy (100-255m vs 2-46m with GPS).

### Issue 6: Device ID Mismatch Between Files

bio.csv and pos.csv use different device ID formats. Correlation between the two datasets must use time-based joining rather than device ID matching.

### Issue 7: Module Temperature Always Zero

The `temperature` field in pos.csv is 0.0 for all 145 readings, suggesting the GPS/cellular module temperature sensor is not reporting.

### Issue 8: Measurement Delay Outliers

8.2% of measurements have >30s server receive delay, with a maximum of 210.6s. These delays could affect real-time monitoring use cases.

### Issue 9: Date/Time Confirmation

`dateconfirmed` is false for all pos.csv records, and `timeconfirmed` is false for 64.8% of records. This suggests the GPS module has not synchronized its real-time clock via satellite.

---

## 13. Summary Statistics

### Data Quality Scorecard

| Metric | Score | Notes |
|--------|-------|-------|
| HR availability | 100% | All 512 rows have HR |
| HR confidence >= 75 | 79.9% | Good overall |
| HR confidence = 100 | 45.7% | Moderate |
| SpO2 availability | 28.1% | Intermittent |
| SpO2 high confidence (>= 75) | 19.5% (of total) | Limited |
| Measurement cadence (10s) | 82.2% | Good regularity |
| Duplicate rate | 34.0% | Needs dedup |
| GPS fix rate | 25.5% | Poor, cell-tower fallback |
| Data receive < 20s | 71.3% | Acceptable latency |

### Key Findings

1. **HR measurement is reliable** with 79.9% of readings at confidence >= 75. Mean HR of 91.7 BPM with normal physiological range (69-124 BPM).

2. **Motion degrades HR confidence** from a mean of 94.9 (still) to 77.4 (motion), but does not produce implausible values.

3. **SpO2 is enabled but intermittent**, providing valid readings (95-100%, mean 97.1%) for about 28% of samples. Availability is better during still periods (55% vs 24%).

4. **Skin temperature shows expected warm-up pattern**, rising from 31.9 C to 35.0 C over the session with a ~20 minute stabilization period.

5. **34% of records are exact duplicates** that need deduplication for accurate analysis.

6. **GPS fix rate is poor (25.5%)**, with the device relying on cell-tower positioning for most reports.

7. **The first ~3 minutes of VSM data should be discarded** due to sensor initialization (low confidence, erratic readings).

8. **Data latency is acceptable** for most samples (71.3% arrive within 20s) but has occasional outliers up to 3.5 minutes.
