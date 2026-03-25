"""Nightly tests - Stage 4: Comprehensive product validation.

Runs every night via cron. No time limit (typically 30-60 min).
Tests everything that doesn't fit in the 15-minute Gate.

Test categories:
    NIGHTLY-ALPHA-PWR-*   : Power profiling (sleep, active, modem bursts)
    NIGHTLY-ALPHA-SENS-*  : Sensor characterization (accel, PPG, temp, pressure)
    NIGHTLY-ALPHA-GPS-*   : GPS acquisition (cold start, warm start)
    NIGHTLY-ALPHA-CHG-*   : Charger behavior (plug/unplug, charge curve)
    NIGHTLY-ALPHA-STIM-*  : Physical stimulus (button, motion, on-body)
    NIGHTLY-ALPHA-NFC-*   : NFC operations (tag read/write)

Run with:
    pytest tests/nightly/ -v
"""
