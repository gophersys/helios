"""Physical stimulus controller for Stage 4 black-box tests.

Translates test-level actions (press button, shake, apply contact) into
MTIB V1 GPIO/ADC/power/motion RPCs using pin mappings from the fixture
profile JSON.
"""

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig
from protocols.mtib.mtib_pb2 import HostType

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class FixtureProfile:
    """Pin and channel mappings for a specific product fixture.

    Loaded from JSON file. See fixtures/alpha_b0.json for the schema.
    """
    product: str
    board: str

    # Button simulation
    button_gpio: int
    button_active_low: bool

    # On-skin electrode
    on_skin_gpio: int
    on_skin_active_high: bool

    # Charger relay
    charger_relay_gpio: int
    charger_relay_active_high: bool

    # Peltier / temperature
    peltier_gpio: int
    temp_adc_channel: int

    # LED photodiode ADC channels
    led_red_adc: int
    led_green_adc: int
    led_blue_adc: int

    # Power defaults
    dut_voltage: float
    charger_voltage: float
    boot_settle_s: float

    @classmethod
    def from_json(cls, path: str) -> "FixtureProfile":
        with open(path) as f:
            data = json.load(f)

        button = data.get("button", {})
        on_skin = data.get("on_skin", {})
        charger = data.get("charger_relay", {})
        peltier = data.get("peltier", {})
        led = data.get("led_sensor", {})
        power = data.get("power", {})

        return cls(
            product=data.get("product", "unknown"),
            board=data.get("board", "unknown"),
            button_gpio=button.get("gpio_pin", 0),
            button_active_low=button.get("active_low", True),
            on_skin_gpio=on_skin.get("gpio_pin", 1),
            on_skin_active_high=on_skin.get("active_high", True),
            charger_relay_gpio=charger.get("gpio_pin", 5),
            charger_relay_active_high=charger.get("active_high", True),
            peltier_gpio=peltier.get("gpio_pin", 3),
            temp_adc_channel=peltier.get("sensor_adc_channel", 2),
            led_red_adc=led.get("red_adc_channel", 0),
            led_green_adc=led.get("green_adc_channel", 1),
            led_blue_adc=led.get("blue_adc_channel", 3),
            dut_voltage=power.get("dut_voltage", 4.5),
            charger_voltage=power.get("charger_voltage", 5.0),
            boot_settle_s=power.get("boot_settle_s", 3.0),
        )


class FixtureController:
    """Physical stimulus controller for Stage 4 black-box tests.

    Translates test-level actions (press button, shake, apply contact)
    into MTIB V1 GPIO/ADC/power/motion RPCs using pin mappings from
    the fixture profile.

    Args:
        mtib: Connected MtibV1Client instance.
        profile: FixtureProfile with pin/channel mappings.
    """

    def __init__(self, mtib: MtibV1Client, profile: FixtureProfile):
        self._mtib = mtib
        self._profile = profile

    @property
    def profile(self) -> FixtureProfile:
        return self._profile

    def _check_error(self, err: Optional[str], operation: str) -> None:
        if err:
            raise RuntimeError(f"{operation} failed: {err}")

    # ------------------------------------------------------------------
    # Power
    # ------------------------------------------------------------------

    def _configure_swd_gpios(self) -> None:
        """Configure GPIO 0+1 as output LOW — required for DUT to boot.

        These GPIOs control the SWD level shifter enable lines on Alpha B0.
        Without them driven LOW, the INA219 reads 4.5V but 0mA — the DUT
        does not boot despite correct voltage.
        See mtib-hardware rules for details.
        """
        for gpio in (0, 1):
            err = self._mtib.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
            self._check_error(err, f"GpioConfig({gpio}, OUTPUT, NONE)")
            err = self._mtib.GpioWrite(gpio, False)
            self._check_error(err, f"GpioWrite({gpio}, LOW)")

    def power_on(self, voltage: Optional[float] = None) -> None:
        """Enable DUT power at specified voltage (default from profile, typically 4.5V).

        The BQ25180 charger on Alpha B0 requires 4.5V on the battery sim
        rail to clear its UVLO threshold. Using lower voltage (e.g. 4.0V)
        results in 0mA current draw — the DUT will not boot.

        GPIO 0+1 are configured as output LOW before power-on — these
        control the SWD level shifter and must be LOW for DUT to boot.
        """
        v = voltage if voltage is not None else self._profile.dut_voltage
        self._configure_swd_gpios()
        err = self._mtib.PowerEnable(channel=0, voltage_v=v)
        self._check_error(err, f"PowerEnable(ch=0, v={v})")
        log.info("DUT power on at %.1fV", v)

    def power_off(self) -> None:
        """Disable DUT power."""
        err = self._mtib.PowerDisable(channel=0)
        self._check_error(err, "PowerDisable(ch=0)")
        log.info("DUT power off")

    def power_cycle(self, off_duration_s: float = 2.0) -> None:
        """Power off, wait, power on. Blocks until boot settle time elapses."""
        self.power_off()
        time.sleep(off_duration_s)
        self.power_on()
        log.info("Waiting %.1fs for boot settle", self._profile.boot_settle_s)
        time.sleep(self._profile.boot_settle_s)

    def charger_power_on(self) -> None:
        """Enable charger/USB power rail (5V default)."""
        err = self._mtib.PowerEnable(channel=1, voltage_v=self._profile.charger_voltage)
        self._check_error(err, "PowerEnable(ch=1)")
        log.info("Charger power on at %.1fV", self._profile.charger_voltage)

    def charger_power_off(self) -> None:
        """Disable charger/USB power rail."""
        err = self._mtib.PowerDisable(channel=1)
        self._check_error(err, "PowerDisable(ch=1)")
        log.info("Charger power off")

    # ------------------------------------------------------------------
    # Button
    # ------------------------------------------------------------------

    def press_button(self, duration_s: float = 0.5) -> None:
        """Simulate button press via GPIO pulse.

        Active-low: write LOW to press, HIGH to release.
        Active-high: write HIGH to press, LOW to release.
        """
        gpio = self._profile.button_gpio
        press_state = not self._profile.button_active_low
        release_state = self._profile.button_active_low

        err = self._mtib.GpioWrite(gpio, press_state)
        self._check_error(err, f"GpioWrite({gpio}, {press_state})")
        time.sleep(duration_s)
        err = self._mtib.GpioWrite(gpio, release_state)
        self._check_error(err, f"GpioWrite({gpio}, {release_state})")
        log.info("Button press: %.1fs", duration_s)

    def long_press_button(self, duration_s: float = 5.0) -> None:
        """Simulate long button press (SOS, power off, etc.)."""
        self.press_button(duration_s)

    # ------------------------------------------------------------------
    # Sensors
    # ------------------------------------------------------------------

    def simulate_on_skin(self, on: bool = True) -> None:
        """Drive on-skin electrode GPIO (HIGH = skin contact for active-high)."""
        gpio = self._profile.on_skin_gpio
        state = on if self._profile.on_skin_active_high else not on
        err = self._mtib.GpioWrite(gpio, state)
        self._check_error(err, f"GpioWrite({gpio}, {state})")
        log.info("On-skin electrode: %s", "ON" if on else "OFF")

    def connect_charger(self) -> None:
        """Close charger relay (connect charger to DUT)."""
        gpio = self._profile.charger_relay_gpio
        state = self._profile.charger_relay_active_high
        err = self._mtib.GpioWrite(gpio, state)
        self._check_error(err, f"GpioWrite({gpio}, {state})")
        log.info("Charger relay closed")

    def disconnect_charger(self) -> None:
        """Open charger relay (disconnect charger from DUT)."""
        gpio = self._profile.charger_relay_gpio
        state = not self._profile.charger_relay_active_high
        err = self._mtib.GpioWrite(gpio, state)
        self._check_error(err, f"GpioWrite({gpio}, {state})")
        log.info("Charger relay open")

    # ------------------------------------------------------------------
    # Motion
    # ------------------------------------------------------------------

    def shake(self, duration_s: float = 5.0, speed_mm_s: float = 50.0) -> None:
        """Drive linear actuator for motion simulation."""
        result, err = self._mtib.MotionStart(
            direction=1, speed_mm_s=speed_mm_s, distance_mm=0
        )
        self._check_error(err, "MotionStart")
        time.sleep(duration_s)
        err = self._mtib.MotionStop()
        self._check_error(err, "MotionStop")
        log.info("Shake: %.1fs at %.0f mm/s", duration_s, speed_mm_s)

    def stop_motion(self) -> None:
        """Stop linear actuator."""
        err = self._mtib.MotionStop()
        self._check_error(err, "MotionStop")
        log.info("Motion stopped")

    # ------------------------------------------------------------------
    # ADC (Sensors)
    # ------------------------------------------------------------------

    def read_led_color(self) -> Dict[str, float]:
        """Read RGB photodiode ADC channels. Returns {'red': v, 'green': v, 'blue': v}."""
        p = self._profile
        result = {}
        for name, ch in [("red", p.led_red_adc), ("green", p.led_green_adc), ("blue", p.led_blue_adc)]:
            value, err = self._mtib.AdcRead(ch)
            self._check_error(err, f"AdcRead(ch={ch})")
            result[name] = value
        return result

    def read_temperature(self) -> float:
        """Read thermistor ADC channel. Returns raw voltage (conversion TBD)."""
        value, err = self._mtib.AdcRead(self._profile.temp_adc_channel)
        self._check_error(err, f"AdcRead(ch={self._profile.temp_adc_channel})")
        return value

    def read_power_rails(self) -> Dict[str, float]:
        """Read manufacturing ADC rail voltages (ch 0-3).

        Returns dict with keys: '3v3', 'batt_sys', 'vbckp', 'sys'.
        Channel mapping from manufacturing test patterns.
        """
        channel_map = {
            "3v3": 0,      # TP301: +3.3V
            "batt_sys": 1,  # TP201: +BATT_SYS
            "vbckp": 2,     # TP607: +VBCKP
            "sys": 3,       # TP202: +SYS
        }
        result = {}
        for name, ch in channel_map.items():
            value, err = self._mtib.AdcRead(ch)
            self._check_error(err, f"AdcRead(ch={ch})")
            result[name] = value
        return result

    # ------------------------------------------------------------------
    # Firmware Flash
    # ------------------------------------------------------------------

    def flash_firmware(self, hex_path: str, target: str = "nrf52840") -> None:
        """Flash firmware via MTIB V1 flash operations.

        Always uses --recover then --program --chiperase --verify --reset
        at speed 4000. See mtib-hardware rules for details.

        Args:
            hex_path: Path to .hex file on the MTIB filesystem.
            target: 'nrf52840' or 'nrf9151'.
        """
        host_type = (
            HostType.HOST_TYPE_NRF52840 if target == "nrf52840"
            else HostType.HOST_TYPE_NRF9151
        )

        from protocols.mtib.mtib_pb2 import FwFileInfo

        file_info = FwFileInfo(name=Path(hex_path).name, target=host_type)

        # Erase (recover) first
        err = self._mtib.EraseFlash(target=host_type, recover=True)
        self._check_error(err, f"EraseFlash({target}, recover=True)")

        # Flash with chip erase + verify
        flash_time, err = self._mtib.FlashFwFile(
            file_info=file_info, sector_erase=False, recover=False
        )
        self._check_error(err, f"FlashFwFile({hex_path})")
        log.info("Flashed %s to %s in %dms", hex_path, target, flash_time or 0)

    def upload_firmware(self, local_path: str, target: str = "nrf52840") -> None:
        """Upload firmware hex file to MTIB server filesystem.

        Args:
            local_path: Local path to .hex file.
            target: 'nrf52840' or 'nrf9151'.
        """
        host_type = (
            HostType.HOST_TYPE_NRF52840 if target == "nrf52840"
            else HostType.HOST_TYPE_NRF9151
        )
        err = self._mtib.UploadFwFile(local_path, host_type)
        self._check_error(err, f"UploadFwFile({local_path})")
        log.info("Uploaded %s for %s", local_path, target)

    # ------------------------------------------------------------------
    # Power Read
    # ------------------------------------------------------------------

    def read_dut_current(self) -> float:
        """Read DUT current in milliamps. Returns current_ma."""
        result, err = self._mtib.PowerRead(channel=0)
        self._check_error(err, "PowerRead(ch=0)")
        return result.current_ma

    def verify_dut_powered(self, min_current_ma: float = 20.0) -> bool:
        """Verify DUT is drawing expected current (>20mA = booted).

        Alpha B0 draws ~33-34mA in active mode. Threshold at 20mA
        to account for variance while still detecting 0mA (not booted).
        Returns True if current exceeds threshold.
        """
        current = self.read_dut_current()
        powered = current >= min_current_ma
        if not powered:
            log.warning(
                "DUT current %.1fmA below threshold %.1fmA — device may not be booting",
                current, min_current_ma,
            )
        return powered
