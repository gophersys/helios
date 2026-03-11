"""Device and fixture profile definitions for validation testing.

Single source of truth for:
- DeviceProfile: What features a DUT revision supports
- FixtureProfile: What capabilities a test bench has wired
- Feature requirements: Which capabilities are needed to test each feature

This module provides the core data model for dynamic test scheduling
and capability-based test skipping.
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Set
import json


# ═══════════════════════════════════════════════════════════════════════════════
# Capabilities — what a test bench can physically do
# ═══════════════════════════════════════════════════════════════════════════════


class Capability(str, Enum):
    """Physical capabilities a test bench may have.

    These represent actual hardware that must be wired on the fixture.
    Not all benches have all capabilities — depends on what's installed.
    """

    # Always present on any MTIB
    POWER = "power"  # INA219 power monitoring
    BUTTON = "button"  # GPIO to drive DUT button

    # Optional hardware
    PELTIER = "peltier"  # Heater for temperature simulation
    CHARGER_RELAY = "charger_relay"  # Relay to connect/disconnect charger
    PPG_SERVO = "ppg_servo"  # Servo for PPG IR blocker
    PPG_LED = "ppg_led"  # Green LED array for HR simulation
    LED_PHOTODIODE = "led_photodiode"  # ADC channels for LED color detection
    NFC_READER = "nfc_reader"  # I2C NFC reader
    MOTION_ACTUATOR = "motion_actuator"  # FluidNC linear rail
    HAPTIC_SENSOR = "haptic_sensor"  # Vibration detection sensor


# ═══════════════════════════════════════════════════════════════════════════════
# Features — what a DUT can do
# ═══════════════════════════════════════════════════════════════════════════════


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


# Feature → Required capabilities mapping
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
    Feature.GNSS: [],  # uses DUT's own GPS
    Feature.CHARGING: [Capability.CHARGER_RELAY],  # also needs battery
    Feature.HAPTIC: [Capability.HAPTIC_SENSOR],
}


# ═══════════════════════════════════════════════════════════════════════════════
# Hardware Configuration Blocks
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass(frozen=True)
class ButtonConfig:
    """Button stimulus configuration."""

    gpio_pin: int
    active_low: bool = True


@dataclass(frozen=True)
class PpgSimulatorConfig:
    """PPG skin contact simulator configuration."""

    servo_pwm_pin: int
    servo_blocked_duty_us: int
    servo_exposed_duty_us: int
    hr_led_gpio_pin: int


@dataclass(frozen=True)
class PeltierConfig:
    """Peltier heater configuration."""

    gpio_pin: int
    temp_adc_channel: int


@dataclass(frozen=True)
class ChargerRelayConfig:
    """Charger relay configuration."""

    gpio_pin: int
    active_high: bool = True


@dataclass(frozen=True)
class LedSensorConfig:
    """LED photodiode sensor configuration."""

    red_adc_channel: int
    green_adc_channel: int
    blue_adc_channel: int


@dataclass(frozen=True)
class NfcReaderConfig:
    """NFC reader configuration."""

    interface: str = "i2c"
    bus: int = 1


@dataclass(frozen=True)
class MotionConfig:
    """Motion actuator configuration."""

    enabled: bool = False


@dataclass(frozen=True)
class PowerConfig:
    """Power supply configuration."""

    battery_installed: bool
    dut_voltage: float = 4.5
    charger_voltage: float = 5.0
    boot_settle_s: float = 10.0


@dataclass(frozen=True)
class DutConfig:
    """DUT identity configuration."""

    device_id: str
    snr: str
    imei: Optional[str] = None
    iccids: Optional[List[str]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# FixtureProfile — what hardware is wired on a test bench
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class FixtureProfile:
    """Physical test bench configuration.

    Single source of truth for:
    - Station identity (station_id, mtib address)
    - Product compatibility (what DUT is installed)
    - Capabilities (what hardware is wired)
    - Pin mappings (GPIO/ADC assignments)

    Capabilities are EXPLICIT — only listed capabilities are available.
    Tests check capabilities before attempting hardware operations.
    """

    # Identity
    station_id: str
    product: str
    board: str
    mtib_revision: str

    # Capabilities — explicit list of what's wired
    capabilities: Set[Capability]

    # Power configuration (always present)
    power: PowerConfig

    # DUT identity
    dut: DutConfig

    # Hardware blocks — only present if capability is listed
    button: Optional[ButtonConfig] = None
    ppg_simulator: Optional[PpgSimulatorConfig] = None
    peltier: Optional[PeltierConfig] = None
    charger_relay: Optional[ChargerRelayConfig] = None
    led_sensor: Optional[LedSensorConfig] = None
    nfc_reader: Optional[NfcReaderConfig] = None
    motion: Optional[MotionConfig] = None

    # Convenience properties for common power config access
    @property
    def battery_installed(self) -> bool:
        """Whether battery is installed (from power config)."""
        return self.power.battery_installed

    @property
    def boot_settle_s(self) -> float:
        """Boot settle time in seconds (from power config)."""
        return self.power.boot_settle_s

    @property
    def dut_voltage(self) -> float:
        """DUT voltage (from power config)."""
        return self.power.dut_voltage

    @property
    def charger_voltage(self) -> float:
        """Charger voltage (from power config)."""
        return self.power.charger_voltage

    def has_capability(self, cap: Capability) -> bool:
        """Check if this fixture has a specific capability."""
        return cap in self.capabilities

    def has_all_capabilities(self, caps: List[Capability]) -> bool:
        """Check if this fixture has all specified capabilities."""
        return all(cap in self.capabilities for cap in caps)

    def missing_capabilities(self, caps: List[Capability]) -> List[Capability]:
        """Return list of capabilities not present on this fixture."""
        return [cap for cap in caps if cap not in self.capabilities]

    @classmethod
    def from_json(cls, path: str) -> "FixtureProfile":
        """Load fixture profile from JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)

    @classmethod
    def from_api(
        cls,
        bench_id: str,
        api_url: str,
        api_key: str,
    ) -> "FixtureProfile":
        """Load fixture profile from Concord API.

        Args:
            bench_id: TestBench ID (CUID) or station_id string
            api_url: Base URL of Concord API (e.g., https://staging.concord.corekinect.cloud)
            api_key: API key for authentication (ck_run_* format)

        Returns:
            FixtureProfile loaded from API response

        Raises:
            ValueError: If bench not found or API request fails
        """
        import requests

        # API keys starting with ck_ use "ApiKey" prefix, not "Bearer"
        auth_prefix = "ApiKey" if api_key.startswith("ck_") else "Bearer"
        headers = {"Authorization": f"{auth_prefix} {api_key}"}

        # Normalize API URL (remove trailing slash)
        api_url = api_url.rstrip("/")

        # Try by ID first (assume bench_id is a CUID)
        resp = requests.get(
            f"{api_url}/v2/validation/benches/{bench_id}/profile",
            headers=headers,
            timeout=30,
        )

        if resp.status_code == 404:
            # Try looking up by station_id
            list_resp = requests.get(
                f"{api_url}/v2/validation/benches",
                headers=headers,
                params={"station_id": bench_id},
                timeout=30,
            )
            if list_resp.ok:
                benches = list_resp.json().get("data", [])
                if benches:
                    # Found bench by station_id, now get its profile
                    bench = benches[0]
                    resp = requests.get(
                        f"{api_url}/v2/validation/benches/{bench['id']}/profile",
                        headers=headers,
                        timeout=30,
                    )
            # If list_resp failed or returned empty, keep original 404 resp

        if not resp.ok:
            raise ValueError(
                f"Failed to load profile from API: {resp.status_code} {resp.text}"
            )

        response_data = resp.json()
        profile_data = response_data.get("data", response_data)

        return cls.from_dict(profile_data)

    @classmethod
    def from_dict(cls, data: dict) -> "FixtureProfile":
        """Create fixture profile from dictionary."""
        # Parse capabilities
        caps_raw = data.get("capabilities", [])
        capabilities = {Capability(c) for c in caps_raw}

        # Parse power config
        power_data = data.get("power", {})
        power = PowerConfig(
            battery_installed=power_data.get("battery_installed", False),
            dut_voltage=power_data.get("dut_voltage", 4.5),
            charger_voltage=power_data.get("charger_voltage", 5.0),
            boot_settle_s=power_data.get("boot_settle_s", 10.0),
        )

        # Parse DUT config
        dut_data = data.get("dut", {})
        dut = DutConfig(
            device_id=dut_data.get("device_id", ""),
            snr=dut_data.get("snr", ""),
            imei=dut_data.get("imei"),
            iccids=dut_data.get("iccids"),
        )

        # Parse optional hardware blocks
        button = None
        if "button" in data and data["button"]:
            b = data["button"]
            button = ButtonConfig(
                gpio_pin=b.get("gpio_pin", 2),
                active_low=b.get("active_low", True),
            )

        ppg_simulator = None
        if "ppg_simulator" in data and data["ppg_simulator"]:
            p = data["ppg_simulator"]
            ppg_simulator = PpgSimulatorConfig(
                servo_pwm_pin=p.get("servo_pwm_pin", 7),
                servo_blocked_duty_us=p.get("servo_blocked_duty_us", 1000),
                servo_exposed_duty_us=p.get("servo_exposed_duty_us", 2000),
                hr_led_gpio_pin=p.get("hr_led_gpio_pin", 3),
            )

        peltier = None
        if "peltier" in data and data["peltier"]:
            p = data["peltier"]
            peltier = PeltierConfig(
                gpio_pin=p.get("gpio_pin", 4),
                temp_adc_channel=p.get("temp_adc_channel", 7),
            )

        charger_relay = None
        if "charger_relay" in data and data["charger_relay"]:
            c = data["charger_relay"]
            charger_relay = ChargerRelayConfig(
                gpio_pin=c.get("gpio_pin", 5),
                active_high=c.get("active_high", True),
            )

        led_sensor = None
        if "led_sensor" in data and data["led_sensor"]:
            l = data["led_sensor"]
            led_sensor = LedSensorConfig(
                red_adc_channel=l.get("red_adc_channel", 4),
                green_adc_channel=l.get("green_adc_channel", 5),
                blue_adc_channel=l.get("blue_adc_channel", 6),
            )

        nfc_reader = None
        if "nfc_reader" in data and data["nfc_reader"]:
            n = data["nfc_reader"]
            nfc_reader = NfcReaderConfig(
                interface=n.get("interface", "i2c"),
                bus=n.get("bus", 1),
            )

        motion = None
        if "motion" in data and data["motion"]:
            m = data["motion"]
            motion = MotionConfig(enabled=m.get("enabled", False))

        return cls(
            station_id=data.get("station_id", "unknown"),
            product=data.get("product", "unknown"),
            board=data.get("board", "unknown"),
            mtib_revision=data.get("mtib_revision", "1.2"),
            capabilities=capabilities,
            power=power,
            dut=dut,
            button=button,
            ppg_simulator=ppg_simulator,
            peltier=peltier,
            charger_relay=charger_relay,
            led_sensor=led_sensor,
            nfc_reader=nfc_reader,
            motion=motion,
        )

    def to_dict(self) -> dict:
        """Serialize fixture profile to dictionary."""
        result = {
            "station_id": self.station_id,
            "product": self.product,
            "board": self.board,
            "mtib_revision": self.mtib_revision,
            "capabilities": [c.value for c in self.capabilities],
            "power": {
                "battery_installed": self.power.battery_installed,
                "dut_voltage": self.power.dut_voltage,
                "charger_voltage": self.power.charger_voltage,
                "boot_settle_s": self.power.boot_settle_s,
            },
            "dut": {
                "device_id": self.dut.device_id,
                "snr": self.dut.snr,
                "imei": self.dut.imei,
                "iccids": self.dut.iccids,
            },
        }

        if self.button:
            result["button"] = {
                "gpio_pin": self.button.gpio_pin,
                "active_low": self.button.active_low,
            }

        if self.ppg_simulator:
            result["ppg_simulator"] = {
                "servo_pwm_pin": self.ppg_simulator.servo_pwm_pin,
                "servo_blocked_duty_us": self.ppg_simulator.servo_blocked_duty_us,
                "servo_exposed_duty_us": self.ppg_simulator.servo_exposed_duty_us,
                "hr_led_gpio_pin": self.ppg_simulator.hr_led_gpio_pin,
            }

        if self.peltier:
            result["peltier"] = {
                "gpio_pin": self.peltier.gpio_pin,
                "temp_adc_channel": self.peltier.temp_adc_channel,
            }

        if self.charger_relay:
            result["charger_relay"] = {
                "gpio_pin": self.charger_relay.gpio_pin,
                "active_high": self.charger_relay.active_high,
            }

        if self.led_sensor:
            result["led_sensor"] = {
                "red_adc_channel": self.led_sensor.red_adc_channel,
                "green_adc_channel": self.led_sensor.green_adc_channel,
                "blue_adc_channel": self.led_sensor.blue_adc_channel,
            }

        if self.nfc_reader:
            result["nfc_reader"] = {
                "interface": self.nfc_reader.interface,
                "bus": self.nfc_reader.bus,
            }

        if self.motion:
            result["motion"] = {"enabled": self.motion.enabled}

        return result


# ═══════════════════════════════════════════════════════════════════════════════
# DeviceProfile — what features a DUT supports
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class DeviceProfile:
    """Device capability profile.

    Defines what features a specific product revision supports.
    Used to determine which tests are applicable to this DUT.
    """

    product: str
    revision: str
    features: Set[Feature]

    # Power requirements
    battery_required: bool = False
    boot_voltage_v: float = 4.5
    charger_voltage_v: Optional[float] = 5.0

    # UART targets
    uart_app_target: str = "nrf52840"
    uart_comms_target: str = "nrf9151"

    # Firmware metadata
    device_type: int = 2
    device_variant: int = 3
    app_ids: List[int] = field(default_factory=lambda: [108, 109])

    def has_feature(self, feature: Feature) -> bool:
        """Check if device supports a specific feature."""
        return feature in self.features

    @classmethod
    def from_dict(cls, data: dict) -> "DeviceProfile":
        """Create device profile from dictionary."""
        features_raw = data.get("features", [])
        features = {Feature(f) for f in features_raw}

        return cls(
            product=data.get("product", "unknown"),
            revision=data.get("revision", "unknown"),
            features=features,
            battery_required=data.get("battery_required", False),
            boot_voltage_v=data.get("boot_voltage_v", 4.5),
            charger_voltage_v=data.get("charger_voltage_v", 5.0),
            uart_app_target=data.get("uart_app_target", "nrf52840"),
            uart_comms_target=data.get("uart_comms_target", "nrf9151"),
            device_type=data.get("device_type", 2),
            device_variant=data.get("device_variant", 3),
            app_ids=data.get("app_ids", [108, 109]),
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Test Configuration — combines device + fixture for a test run
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ValidationConfig:
    """Combined configuration for a validation test run.

    Computes runnable features based on device capabilities and
    fixture hardware availability.
    """

    device: DeviceProfile
    fixture: FixtureProfile

    @property
    def runnable_features(self) -> Set[Feature]:
        """Features that can be tested with this device + fixture combo."""
        runnable = set()
        for feature in self.device.features:
            required_caps = FEATURE_REQUIREMENTS.get(feature, [])
            if self.fixture.has_all_capabilities(required_caps):
                runnable.add(feature)
        return runnable

    def can_test_feature(self, feature: Feature) -> bool:
        """Check if a specific feature can be tested."""
        if feature not in self.device.features:
            return False
        required_caps = FEATURE_REQUIREMENTS.get(feature, [])
        return self.fixture.has_all_capabilities(required_caps)

    def skip_reason(self, feature: Feature) -> Optional[str]:
        """Get skip reason for a feature, or None if testable."""
        if feature not in self.device.features:
            return f"Device {self.device.product}/{self.device.revision} does not support '{feature.value}'"

        required_caps = FEATURE_REQUIREMENTS.get(feature, [])
        missing = self.fixture.missing_capabilities(required_caps)
        if missing:
            missing_str = ", ".join(c.value for c in missing)
            return f"Fixture '{self.fixture.station_id}' lacks capabilities: {missing_str}"

        return None


# ═══════════════════════════════════════════════════════════════════════════════
# Built-in Device Profiles
# ═══════════════════════════════════════════════════════════════════════════════

DEVICE_PROFILES: Dict[str, DeviceProfile] = {
    "alpha_b0": DeviceProfile(
        product="alpha",
        revision="b0",
        features={
            Feature.POWER,
            Feature.BUTTON,
            Feature.LED,
            Feature.BIOMETRIC,
            Feature.ENVIRONMENTAL,
            Feature.MOTION,
            Feature.NFC,
            Feature.CELLULAR,
            Feature.GNSS,
            # Note: CHARGING and HAPTIC depend on battery being installed
        },
        battery_required=False,
        device_type=2,
        device_variant=3,
        app_ids=[108, 109],
    ),
    "alpha_a0": DeviceProfile(
        product="alpha",
        revision="a0",
        features={
            Feature.POWER,
            Feature.BUTTON,
            Feature.LED,
            Feature.ENVIRONMENTAL,
            Feature.CELLULAR,
        },
        battery_required=False,
        device_type=2,
        device_variant=2,
        app_ids=[102, 103],
    ),
}


def get_device_profile(product: str, revision: str) -> Optional[DeviceProfile]:
    """Get device profile by product and revision."""
    key = f"{product}_{revision}"
    return DEVICE_PROFILES.get(key)
