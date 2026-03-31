"""Physical stimulus controller for Stage 4 black-box tests.

Translates test-level actions (press button, shake, apply contact) into
MTIB V1 GPIO/ADC/power/motion RPCs using pin mappings from the fixture
profile JSON.

Uses the capability system from profiles.py to gate hardware methods.
Methods that require missing capabilities raise CapabilityNotAvailable.
"""

import time
from pathlib import Path
from typing import Dict, Optional

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig, PowerChannel
from corekinect.utils import Logger
from protocols.mtib.mtib_pb2 import HostType

from .errors import HardwareError
from .profiles import Capability, FixtureProfile
from .programmable_fixture import CapabilityNotAvailable

log = Logger(log_name="fixture_controller")


class FixtureController:
    """Physical stimulus controller for Stage 4 black-box tests.

    Translates test-level actions (press button, shake, apply contact)
    into MTIB V1 GPIO/ADC/power/motion RPCs using pin mappings from
    the fixture profile.

    Uses capability-based gating — methods that require unavailable
    hardware raise CapabilityNotAvailable. This enables:
    - Dynamic test scheduling to any bench with required capabilities
    - Automatic test skipping when hardware isn't wired
    - Unified interface between real hardware and test stubs

    Args:
        mtib: Connected MtibV1Client instance.
        profile: FixtureProfile with pin/channel mappings and capabilities.
    """

    def __init__(self, mtib: MtibV1Client, profile: FixtureProfile):
        self._mtib = mtib
        self._profile = profile
        self._gpios_configured = False

    @property
    def profile(self) -> FixtureProfile:
        return self._profile

    # ═══════════════════════════════════════════════════════════════════════
    # Capability checking
    # ═══════════════════════════════════════════════════════════════════════

    def has_capability(self, cap: Capability) -> bool:
        """Check if this fixture has a specific capability."""
        return self._profile.has_capability(cap)

    def require_capability(self, cap: Capability, method: str) -> None:
        """Raise if capability is missing."""
        if not self.has_capability(cap):
            raise CapabilityNotAvailable(cap, method, self._profile.station_id)

    @property
    def primary_power_channel(self) -> int:
        """Return the power channel that carries DUT current.

        Battery mode: ch1 (charger) after BQ25180 takeover.
        Batteryless: ch0 (DUT direct).
        """
        return 1 if self._profile.power.battery_installed else 0

    def _check_error(self, err: Optional[str], operation: str) -> None:
        if err:
            raise HardwareError(f"{operation} failed: {err}")

    def configure_stimulus_gpios(self) -> None:
        """Configure all stimulus GPIOs as OUTPUT with safe initial states.

        The MTIB server initializes all GPIOs as INPUT by default.
        Stimulus pins must be configured as OUTPUT before GpioWrite will
        succeed. Each pin is set to its "inactive" state immediately after
        configuration to prevent phantom stimulus.

        Critical: button (active_low) defaults to LOW which means "pressed"
        — firmware would see an 8s hold and power off the DUT.

        Called automatically on first use, or explicitly during setup.
        Only configures GPIOs for capabilities that are present.
        """
        if self._gpios_configured:
            return

        # Build list of stimulus pins based on available capabilities
        stimulus_pins = []

        # Button — requires BUTTON capability
        if self.has_capability(Capability.BUTTON) and self._profile.button:
            stimulus_pins.append((
                "button",
                self._profile.button.gpio_pin,
                self._profile.button.active_low,  # HIGH = released for active_low
            ))

        # PPG HR LED — requires PPG_LED capability
        if self.has_capability(Capability.PPG_LED) and self._profile.ppg_simulator:
            stimulus_pins.append((
                "ppg_hr_led",
                self._profile.ppg_simulator.hr_led_gpio_pin,
                False,  # OFF = no LED pulsing
            ))

        # Peltier — requires PELTIER capability
        if self.has_capability(Capability.PELTIER) and self._profile.peltier:
            stimulus_pins.append((
                "peltier",
                self._profile.peltier.gpio_pin,
                False,  # OFF = no heating
            ))

        # Charger relay — requires CHARGER_RELAY capability
        if self.has_capability(Capability.CHARGER_RELAY) and self._profile.charger_relay:
            stimulus_pins.append((
                "charger_relay",
                self._profile.charger_relay.gpio_pin,
                not self._profile.charger_relay.active_high,  # open
            ))

        failed_gpios = []
        for name, gpio, initial_state in stimulus_pins:
            err = self._mtib.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
            if err:
                log.warning("Failed to configure %s GPIO %d as OUTPUT: %s", name, gpio, err)
                failed_gpios.append(name)
                continue
            err = self._mtib.GpioWrite(gpio, initial_state)
            if err:
                log.warning("Failed to set %s GPIO %d initial state: %s", name, gpio, err)
                failed_gpios.append(name)

        if failed_gpios:
            self._gpios_configured = False
            log.warning("GPIO configuration incomplete — failed: %s", ", ".join(failed_gpios))
        else:
            self._gpios_configured = True
        log.info("Stimulus GPIOs configured: %s",
                 {name: gpio for name, gpio, _ in stimulus_pins})

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

    def power_on(self, voltage: Optional[float] = None, with_charger: Optional[bool] = None) -> None:
        """Enable DUT power at specified voltage (default from profile, typically 4.5V).

        Power behavior depends on the fixture's battery_installed setting:

        **Without battery (battery_installed=False):** Only ch0 (VBAT) is
        enabled. Ch1 (charger) must NEVER be enabled — the variable PSU
        would attempt to sink current and risk damaging the supply. All DUT
        current flows through ch0.

        **With battery (battery_installed=True):** Both ch0 (battery sim)
        and ch1 (charger) are enabled. After ~4s the BQ25180 charger takes
        over — ch0 drops to ~0mA, ch1 draws ~17-33mA.

        GPIO 0+1 are configured as output LOW before power-on — these
        control the SWD level shifter and must be LOW for DUT to boot.

        Args:
            voltage: Battery rail voltage (default from profile, typically 4.5V).
            with_charger: Enable charger rail. Defaults to profile.power.battery_installed.
                WARNING: Enabling charger without a battery causes the PSU to
                sink current — hardware risk.
        """
        if with_charger is None:
            with_charger = self._profile.power.battery_installed

        v = voltage if voltage is not None else self._profile.power.dut_voltage
        if v < 0 or v > 6.0:
            raise HardwareError(f"Voltage {v}V out of safe range [0, 6.0]V")
        self._configure_swd_gpios()
        self.configure_stimulus_gpios()
        err = self._mtib.PowerEnable(channel=PowerChannel.DUT, voltage_v=v)
        self._check_error(err, f"PowerEnable(DUT, v={v})")
        if with_charger:
            err = self._mtib.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=self._profile.power.charger_voltage)
            self._check_error(err, f"PowerEnable(CHARGER, v={self._profile.power.charger_voltage})")
            log.info("DUT power on at %.1fV + charger at %.1fV", v, self._profile.power.charger_voltage)
        else:
            log.info("DUT power on at %.1fV (no battery, charger disabled)", v)

    def power_off(self) -> None:
        """Disable all DUT power rails."""
        err = self._mtib.PowerDisable(channel=PowerChannel.DUT)
        self._check_error(err, "PowerDisable(DUT)")
        if self._profile.power.battery_installed:
            err = self._mtib.PowerDisable(channel=PowerChannel.CHARGER)
            self._check_error(err, "PowerDisable(CHARGER)")
        log.info("DUT power off")

    def power_cycle(self, off_duration_s: float = 2.0) -> None:
        """Power off, wait, power on. Blocks until boot settle time elapses."""
        self.power_off()
        time.sleep(off_duration_s)
        self.power_on()
        log.info("Waiting %.1fs for boot settle", self._profile.power.boot_settle_s)
        time.sleep(self._profile.power.boot_settle_s)

    def charger_power_on(self) -> None:
        """Enable charger/USB power rail (5V default).

        Requires CHARGER_RELAY capability.
        """
        self.require_capability(Capability.CHARGER_RELAY, "charger_power_on")
        err = self._mtib.PowerEnable(channel=PowerChannel.CHARGER, voltage_v=self._profile.power.charger_voltage)
        self._check_error(err, "PowerEnable(CHARGER)")
        log.info("Charger power on at %.1fV", self._profile.power.charger_voltage)

    def charger_power_off(self) -> None:
        """Disable charger/USB power rail.

        Requires CHARGER_RELAY capability.
        """
        self.require_capability(Capability.CHARGER_RELAY, "charger_power_off")
        err = self._mtib.PowerDisable(channel=PowerChannel.CHARGER)
        self._check_error(err, "PowerDisable(CHARGER)")
        log.info("Charger power off")

    # ------------------------------------------------------------------
    # Button (requires BUTTON capability)
    # ------------------------------------------------------------------

    def press_button(self, duration_s: float = 0.5) -> None:
        """Simulate button press via GPIO pulse.

        Requires BUTTON capability.
        Active-low: write LOW to press, HIGH to release.
        Active-high: write HIGH to press, LOW to release.
        """
        self.require_capability(Capability.BUTTON, "press_button")
        self.configure_stimulus_gpios()

        if not self._profile.button:
            raise RuntimeError("BUTTON capability present but button config missing")

        gpio = self._profile.button.gpio_pin
        press_state = not self._profile.button.active_low
        release_state = self._profile.button.active_low

        err = self._mtib.GpioWrite(gpio, press_state)
        self._check_error(err, f"GpioWrite({gpio}, {press_state})")
        time.sleep(duration_s)
        err = self._mtib.GpioWrite(gpio, release_state)
        self._check_error(err, f"GpioWrite({gpio}, {release_state})")
        log.info("Button press: %.1fs", duration_s)

    def long_press_button(self, duration_s: float = 5.0) -> None:
        """Simulate long button press (SOS, power off, etc.).

        Requires BUTTON capability.
        """
        self.press_button(duration_s)

    # ------------------------------------------------------------------
    # PPG Simulator (requires PPG_SERVO + PPG_LED capabilities)
    # ------------------------------------------------------------------

    def simulate_on_skin(self, on: bool = True) -> None:
        """Simulate skin contact by moving the PPG IR blocker servo.

        Requires PPG_SERVO and PPG_LED capabilities.

        The Alpha fixture has a 3D-printed black IR-absorbing piece
        between the DUT's PPG sensor (PAH8151) glass and a green LED
        array underneath. When the blocker is in position, it absorbs
        IR — the PPG sensor sees no reflectance (no touch). When the
        servo rotates the blocker 90 degrees out, the green LED PCB
        reflects IR back — the PPG sensor detects "touch" and
        transitions to SKIN_CONFIRMED.

        This also turns on the HR LED GPIO so the green LED array
        provides a baseline reflective surface (steady, no pulsing).

        Args:
            on: True = expose PPG sensor (skin contact).
                False = block PPG sensor (no contact).
        """
        self.require_capability(Capability.PPG_SERVO, "simulate_on_skin")
        self.require_capability(Capability.PPG_LED, "simulate_on_skin")
        self.configure_stimulus_gpios()

        if not self._profile.ppg_simulator:
            raise RuntimeError("PPG capabilities present but ppg_simulator config missing")

        ppg = self._profile.ppg_simulator

        if on:
            # Turn on green LED array first (provides reflective surface)
            err = self._mtib.GpioWrite(ppg.hr_led_gpio_pin, True)
            self._check_error(err, "GpioWrite(ppg_hr_led, ON)")
            # Move servo to exposed position
            # TODO: PWM RPC not yet in V1 proto — servo control requires
            # MTIB server PWM support. For now, log the intended action.
            log.warning(
                "PPG servo control not yet implemented (needs PWM RPC). "
                "Pin %d, target duty: %dus",
                ppg.servo_pwm_pin,
                ppg.servo_exposed_duty_us,
            )
        else:
            # Move servo to blocked position first
            log.warning(
                "PPG servo control not yet implemented (needs PWM RPC). "
                "Pin %d, target duty: %dus",
                ppg.servo_pwm_pin,
                ppg.servo_blocked_duty_us,
            )
            # Turn off green LED array
            err = self._mtib.GpioWrite(ppg.hr_led_gpio_pin, False)
            self._check_error(err, "GpioWrite(ppg_hr_led, OFF)")

        log.info("Skin contact simulation: %s", "ON" if on else "OFF")

    def simulate_heartbeat(self, bpm: int = 72) -> None:
        """Start pulsing the green LED array at a heart-rate frequency.

        Requires PPG_LED capability.

        The green LEDs sit under the PPG sensor and pulse at the
        specified BPM to simulate a PPG waveform. The PAH8151 reads
        this as a real heartbeat signal, and the PSP algorithm computes
        HR/SpO2 from it.

        The servo must be in the "exposed" position first (call
        simulate_on_skin(on=True) before this).

        Args:
            bpm: Heart rate in beats per minute. Typical range: 40-200.

        Note:
            Current implementation uses GPIO toggle which produces a
            square wave, not a realistic PPG waveform. The PAH8151 +
            PSP algorithm may or may not accept this as valid HR data.
            Actual HR simulation parameters (duty cycle, LED current,
            waveform shape) need to be characterized experimentally.
        """
        self.require_capability(Capability.PPG_LED, "simulate_heartbeat")
        self.configure_stimulus_gpios()

        if not self._profile.ppg_simulator:
            raise RuntimeError("PPG_LED capability present but ppg_simulator config missing")

        # TODO: Implement GPIO-based pulsing at target frequency.
        # At low BPM (40-200 = 0.67-3.33 Hz), a background thread
        # toggling the GPIO is sufficient. No PWM hardware needed.
        freq_hz = bpm / 60.0
        log.warning(
            "HR LED pulsing not yet implemented. "
            "GPIO %d at %.2f Hz (%d BPM)",
            self._profile.ppg_simulator.hr_led_gpio_pin, freq_hz, bpm,
        )

    def stop_heartbeat(self) -> None:
        """Stop pulsing the green LED array.

        Requires PPG_LED capability.
        """
        self.require_capability(Capability.PPG_LED, "stop_heartbeat")
        self.configure_stimulus_gpios()

        if not self._profile.ppg_simulator:
            raise RuntimeError("PPG_LED capability present but ppg_simulator config missing")

        err = self._mtib.GpioWrite(self._profile.ppg_simulator.hr_led_gpio_pin, False)
        self._check_error(err, "GpioWrite(ppg_hr_led, OFF)")
        log.info("HR LED pulsing stopped")

    # ------------------------------------------------------------------
    # Peltier (requires PELTIER capability)
    # ------------------------------------------------------------------

    def set_peltier(self, on: bool) -> None:
        """Drive peltier/heater element for skin temperature simulation.

        Requires PELTIER capability.

        The peltier heater sits near the MLX90614 IR temperature sensor
        on the DUT. When heated to ~33C, the MLX90614 reads a realistic
        skin temperature, allowing the VSM firmware to pass the
        skin_temp_min_threshold_f check.
        """
        self.require_capability(Capability.PELTIER, "set_peltier")
        self.configure_stimulus_gpios()

        if not self._profile.peltier:
            raise RuntimeError("PELTIER capability present but peltier config missing")

        gpio = self._profile.peltier.gpio_pin
        err = self._mtib.GpioWrite(gpio, on)
        self._check_error(err, f"GpioWrite(peltier={gpio}, {on})")
        log.info("Peltier: %s", "ON" if on else "OFF")

    # ------------------------------------------------------------------
    # Charger relay (requires CHARGER_RELAY capability)
    # ------------------------------------------------------------------

    def connect_charger(self) -> None:
        """Close charger relay (connect charger to DUT).

        Requires CHARGER_RELAY capability.
        """
        self.require_capability(Capability.CHARGER_RELAY, "connect_charger")
        self.configure_stimulus_gpios()

        if not self._profile.charger_relay:
            raise RuntimeError("CHARGER_RELAY capability present but charger_relay config missing")

        gpio = self._profile.charger_relay.gpio_pin
        state = self._profile.charger_relay.active_high
        err = self._mtib.GpioWrite(gpio, state)
        self._check_error(err, f"GpioWrite({gpio}, {state})")
        log.info("Charger relay closed")

    def disconnect_charger(self) -> None:
        """Open charger relay (disconnect charger from DUT).

        Requires CHARGER_RELAY capability.
        """
        self.require_capability(Capability.CHARGER_RELAY, "disconnect_charger")

        if not self._profile.charger_relay:
            raise RuntimeError("CHARGER_RELAY capability present but charger_relay config missing")

        gpio = self._profile.charger_relay.gpio_pin
        state = not self._profile.charger_relay.active_high
        err = self._mtib.GpioWrite(gpio, state)
        self._check_error(err, f"GpioWrite({gpio}, {state})")
        log.info("Charger relay open")

    # ------------------------------------------------------------------
    # Motion (requires MOTION_ACTUATOR capability)
    # ------------------------------------------------------------------

    def shake(self, duration_s: float = 5.0, speed_mm_s: float = 50.0) -> None:
        """Drive linear actuator for motion simulation.

        Requires MOTION_ACTUATOR capability.
        """
        self.require_capability(Capability.MOTION_ACTUATOR, "shake")
        result, err = self._mtib.MotionStart(
            duration_seconds=int(duration_s),
            dwell_seconds=0,
            speed_mm_s=int(speed_mm_s),
            distance_mm=0,
        )
        self._check_error(err, "MotionStart")
        time.sleep(duration_s)
        err = self._mtib.MotionStop()
        self._check_error(err, "MotionStop")
        log.info("Shake: %.1fs at %.0f mm/s", duration_s, speed_mm_s)

    def stop_motion(self) -> None:
        """Stop linear actuator.

        Requires MOTION_ACTUATOR capability.
        """
        self.require_capability(Capability.MOTION_ACTUATOR, "stop_motion")
        err = self._mtib.MotionStop()
        self._check_error(err, "MotionStop")
        log.info("Motion stopped")

    # ------------------------------------------------------------------
    # ADC (Sensors)
    # ------------------------------------------------------------------

    def read_led_color(self) -> Dict[str, float]:
        """Read RGB photodiode ADC channels.

        Requires LED_PHOTODIODE capability.
        Returns {'red': v, 'green': v, 'blue': v}.
        """
        self.require_capability(Capability.LED_PHOTODIODE, "read_led_color")

        if not self._profile.led_sensor:
            raise RuntimeError("LED_PHOTODIODE capability present but led_sensor config missing")

        led = self._profile.led_sensor
        result = {}
        for name, ch in [
            ("red", led.red_adc_channel),
            ("green", led.green_adc_channel),
            ("blue", led.blue_adc_channel),
        ]:
            value, err = self._mtib.AdcRead(ch)
            self._check_error(err, f"AdcRead(ch={ch})")
            if value is None:
                log.warning("AdcRead(ch=%d) returned None for %s, skipping", ch, name)
                continue
            result[name] = value
        return result

    def read_temperature(self) -> float:
        """Read thermistor ADC channel. Returns raw voltage (conversion TBD).

        Uses the peltier config's temp_adc_channel. This doesn't strictly
        require PELTIER capability — the ADC channel exists regardless.
        """
        if self._profile.peltier:
            ch = self._profile.peltier.temp_adc_channel
        else:
            # Default to ch7 if no peltier config (legacy behavior)
            ch = 7
        value, err = self._mtib.AdcRead(ch)
        self._check_error(err, f"AdcRead(ch={ch})")
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

    # Target string → HostType mapping
    _TARGET_MAP = {
        "nrf52840": HostType.HOST_TYPE_NRF52840,
        "nrf9151": HostType.HOST_TYPE_NRF9151,
        "nrf9160": HostType.HOST_TYPE_NRF9160,
        "nrf9151_modem": HostType.HOST_TYPE_NRF9151_MODEM,
        "nrf9160_modem": HostType.HOST_TYPE_NRF9160_MODEM,
    }

    def _resolve_target(self, target: str) -> "HostType":
        """Resolve a target string to a HostType enum value."""
        ht = self._TARGET_MAP.get(target.lower())
        if ht is None:
            raise ValueError(
                f"Unknown target '{target}'. "
                f"Valid targets: {', '.join(self._TARGET_MAP.keys())}"
            )
        return ht

    def flash_firmware(self, hex_path: str, target: str = "nrf52840") -> None:
        """Flash firmware via MTIB V1 flash operations.

        Always uses --recover then --program --chiperase --verify --reset
        at speed 4000. See mtib-hardware rules for details.

        For modem firmware (target='nrf9151_modem'), uses sector_erase=True
        since modem firmware is flashed to a separate partition.

        Args:
            hex_path: Path to .hex/.zip file on the MTIB filesystem.
            target: 'nrf52840', 'nrf9151', 'nrf9151_modem', 'nrf9160', or 'nrf9160_modem'.
        """
        host_type = self._resolve_target(target)
        is_modem = host_type in (HostType.HOST_TYPE_NRF9151_MODEM, HostType.HOST_TYPE_NRF9160_MODEM)

        from protocols.mtib.mtib_pb2 import FwFileInfo

        file_info = FwFileInfo(name=Path(hex_path).name, target=host_type)

        # Flash — modem uses sector_erase, app firmware uses recover
        flash_time, err = self._mtib.FlashFwFile(
            file_info=file_info,
            sector_erase=is_modem,
            recover=True,
        )
        self._check_error(err, f"FlashFwFile({hex_path})")
        log.info("Flashed %s to %s in %dms", hex_path, target, flash_time or 0)

    def upload_firmware(self, local_path: str, target: str = "nrf52840") -> None:
        """Upload firmware hex/zip file to MTIB server filesystem.

        Args:
            local_path: Local path to .hex/.zip file.
            target: 'nrf52840', 'nrf9151', 'nrf9151_modem', 'nrf9160', or 'nrf9160_modem'.
        """
        host_type = self._resolve_target(target)
        err = self._mtib.UploadFwFile(local_path, host_type)
        self._check_error(err, f"UploadFwFile({local_path})")
        log.info("Uploaded %s for %s", local_path, target)

    # ------------------------------------------------------------------
    # Power Read
    # ------------------------------------------------------------------

    def read_dut_current(self) -> float:
        """Read DUT battery rail (ch0) current in milliamps.

        Without battery: ch0 carries all DUT current — this is the primary
        power measurement.

        With battery: after BQ25180 charger takeover (~4s post-boot), ch0
        drops to ~0mA. Use read_total_current() instead.
        """
        result, err = self._mtib.PowerRead(channel=PowerChannel.DUT)
        self._check_error(err, "PowerRead(DUT)")
        return result.current_ma

    def read_charger_current(self) -> float:
        """Read charger rail (ch1) current in milliamps.

        Only meaningful when battery_installed=True and charger rail is
        enabled. In batteryless mode, ch1 is not powered.
        """
        result, err = self._mtib.PowerRead(channel=PowerChannel.CHARGER)
        self._check_error(err, "PowerRead(CHARGER)")
        return result.current_ma

    def read_total_current(self) -> float:
        """Read total DUT current (battery + charger rails).

        For battery-installed mode: after charger takeover, most current
        flows through ch1 (charger). Total current is the reliable measure.

        For batteryless mode: ch1 is not powered, so this returns the same
        as read_dut_current(). Use read_dut_current() directly instead.
        """
        dut = self.read_dut_current()
        chg = self.read_charger_current()
        return dut + chg

    # ------------------------------------------------------------------
    # UART Capture
    # ------------------------------------------------------------------

    def capture_uart(self, target: str = "app", duration_s: float = 3.0) -> bytes:
        """Capture UART output for a duration.

        Opens a blocking UART stream and collects all received bytes.

        Args:
            target: 'app' (nRF52840) or 'comms' (nRF9151).
            duration_s: How long to capture.

        Returns:
            Raw bytes received during the capture window.
        """
        from protocols.mtib.mtib_pb2 import UartStreamRequest

        if target.lower() == "app":
            host_type = HostType.HOST_TYPE_NRF52840
        elif target.lower() == "comms":
            host_type = HostType.HOST_TYPE_NRF9151
        else:
            host_type = HostType.HOST_TYPE_NRF52840

        collected = bytearray()
        start = time.time()

        def request_gen():
            while time.time() - start < duration_s:
                yield UartStreamRequest(target=host_type, data=b"")
                time.sleep(0.05)

        try:
            for resp in self._mtib.UartStream(host_type, request_gen()):
                if time.time() - start >= duration_s:
                    break
                if resp.data:
                    collected.extend(resp.data)
        except Exception as e:
            log.warning("UART capture error: %s", e)

        return bytes(collected)

    def verify_dut_powered(self, min_current_ma: float = 5.0, samples: int = 10) -> bool:
        """Verify DUT is drawing expected current.

        Takes multiple samples over ~2s and uses the peak reading. This
        handles devices that sleep between bursts (e.g., modem retry loops)
        where a single-point read may return 0mA despite the device running.

        When battery_installed=False: reads ch0 only (no charger rail).
        When battery_installed=True: reads total (ch0+ch1) since charger
        takeover shifts current to ch1.

        Returns True if peak current exceeds threshold.
        """
        peak = 0.0
        for _ in range(samples):
            if self._profile.power.battery_installed:
                current = self.read_total_current()
            else:
                current = self.read_dut_current()
            peak = max(peak, current)
            if peak >= min_current_ma:
                return True
            time.sleep(0.5)
        if peak < min_current_ma:
            log.warning(
                "DUT current %.1fmA below threshold %.1fmA — device may not be booting",
                peak, min_current_ma,
            )
        return peak >= min_current_ma
