"""Capability and Feature definitions for the validation platform.

Capabilities describe what a test bench can physically do (hardware wiring).
Features describe what a DUT can do (device functionality).
FEATURE_REQUIREMENTS maps features to the bench capabilities needed to test them.

These are platform-level concepts used by:
- Test scheduling (backend assigns fixtures based on capabilities)
- Test gating (tests skip when capabilities are missing)
- Profile definitions (fixture profiles declare their capabilities)

Usage:
    from corekinect.capabilities import Capability, Feature, FEATURE_REQUIREMENTS

    if Capability.JLINK in fixture.capabilities:
        flash_firmware(...)

    required = FEATURE_REQUIREMENTS[Feature.BIOMETRIC]
    if fixture.has_all_capabilities(required):
        run_biometric_tests(...)
"""

from enum import Enum
from typing import Dict, List


# =============================================================================
# Capabilities -- what a test bench can physically do
# =============================================================================


class Capability(str, Enum):
    """Physical capabilities a test bench may have.

    These represent actual hardware or instruments that must be present
    on the fixture or MTIB node. Capabilities are checked before tests
    run -- missing capabilities cause graceful skip, never crash.

    Static capabilities (physical wiring, don't change between runs):
        POWER, BUTTON, PELTIER, CHARGER_RELAY, PPG_SERVO, PPG_LED,
        LED_PHOTODIODE, NFC_READER, MOTION_ACTUATOR, HAPTIC_SENSOR

    Dynamic capabilities (may change between runs, probed at connect):
        JLINK, JOULESCOPE, BATTERY

    External capabilities (require equipment outside the fixture):
        GNSS_SIMULATOR, ENVIRONMENTAL_CHAMBER
    """

    # Always present on any MTIB
    POWER = "power"  # INA219 power monitoring (basic mA resolution)
    BUTTON = "button"  # GPIO to drive DUT button

    # Fixture hardware (static, depends on wiring)
    PELTIER = "peltier"  # Heater for temperature simulation
    CHARGER_RELAY = "charger_relay"  # Relay to connect/disconnect charger
    PPG_SERVO = "ppg_servo"  # Servo for PPG IR blocker
    PPG_LED = "ppg_led"  # Green LED array for HR simulation
    LED_PHOTODIODE = "led_photodiode"  # ADC channels for LED color detection
    NFC_READER = "nfc_reader"  # I2C NFC reader
    MOTION_ACTUATOR = "motion_actuator"  # FluidNC linear rail
    HAPTIC_SENSOR = "haptic_sensor"  # Vibration detection sensor

    # MTIB instruments (dynamic, probed at connect)
    JLINK = "jlink"  # J-Link SWD debug probes for flashing
    JOULESCOPE = "joulescope"  # High-precision current measurement (nA/uA)

    # DUT state (depends on fixture configuration)
    BATTERY = "battery"  # Real battery installed in DUT (enables charging tests)

    # External equipment
    GNSS_SIMULATOR = "gnss_simulator"  # RF GPS signal generator
    ENVIRONMENTAL_CHAMBER = "environmental_chamber"  # Temperature/humidity control


# =============================================================================
# Features -- what a DUT can do
# =============================================================================


class Feature(str, Enum):
    """Device features that can be tested.

    These represent functional capabilities of the DUT itself.
    Different product revisions have different feature sets.
    """

    # Core (all devices)
    POWER = "power"
    BUTTON = "button"
    LED = "led"

    # Sensors
    BIOMETRIC = "biometric"  # PPG on-skin detection
    ENVIRONMENTAL = "environmental"  # BME280 + MLX90614
    MOTION = "motion"  # Accelerometer/IMU
    NFC = "nfc"  # NFC tag

    # Connectivity
    CELLULAR = "cellular"  # LTE modem
    GNSS = "gnss"  # GPS

    # Power management
    CHARGING = "charging"  # BQ25180 BMS
    HAPTIC = "haptic"  # Vibration motor


# Feature -> Required capabilities mapping
# A test for a feature can only run if the bench has ALL required capabilities
FEATURE_REQUIREMENTS: Dict[Feature, List[Capability]] = {
    Feature.POWER: [],  # INA219 always present
    Feature.BUTTON: [Capability.BUTTON],
    Feature.LED: [Capability.LED_PHOTODIODE],
    Feature.BIOMETRIC: [Capability.PPG_SERVO, Capability.PPG_LED],
    Feature.ENVIRONMENTAL: [],  # peltier enhances but not required
    Feature.MOTION: [Capability.MOTION_ACTUATOR],
    Feature.NFC: [Capability.NFC_READER],
    Feature.CELLULAR: [],  # uses DUT's own modem
    Feature.GNSS: [],  # uses DUT's own GPS (GNSS_SIMULATOR enhances but not required)
    Feature.CHARGING: [Capability.CHARGER_RELAY, Capability.BATTERY],
    Feature.HAPTIC: [Capability.HAPTIC_SENSOR],
}
