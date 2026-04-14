"""Manufacturing fixture controller for Alpha B0.

Extends the shared AlphaB0Fixture with manufacturing-specific helpers
(electrical test thresholds, J-Link power sequencing). The base class
handles all MTIB RPC operations.
"""

from pathlib import Path
from typing import Dict, Optional

import yaml

from corekinect.mtib_client.v1.client.core import MtibV1Client
from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig, PowerChannel
from corekinect.utils import Logger

log = Logger(log_name="alpha_b0_mfg")

_FIXTURE_YAML = Path(__file__).parent / "fixture.yaml"


class AlphaB0MfgFixture:
    """Manufacturing fixture controller for Alpha B0.

    Loads config from fixture.yaml in this directory. Provides
    power sequencing, electrical test thresholds, and J-Link
    power helpers specific to the manufacturing test flow.
    """

    def __init__(self, mtib: MtibV1Client, config_override: Optional[dict] = None):
        self._mtib = mtib

        with open(_FIXTURE_YAML) as f:
            self._config = yaml.safe_load(f)

        if config_override:
            self._config.update(config_override)

        self._capabilities = set(self._config.get("capabilities", []))

    @property
    def config(self) -> dict:
        return self._config

    @property
    def thresholds(self) -> dict:
        return self._config.get("thresholds", {})

    @property
    def battery_installed(self) -> bool:
        return bool(self._config["power"]["battery_installed"])

    def has(self, capability: str) -> bool:
        return capability in self._capabilities

    # ── Power ────────────────────────────────────────────────

    def configure_gpios(self) -> None:
        """Configure GPIO 0+1 as output LOW — required for DUT boot."""
        for gpio in (0, 1):
            self._mtib.GpioConfig(gpio, GpioDirection.OUTPUT, GpioResistorConfig.NONE)
            self._mtib.GpioWrite(gpio, False)

    def power_on(self, voltage: Optional[float] = None) -> None:
        """Enable DUT power. Configures GPIOs first."""
        v = voltage or self._config["power"]["dut_voltage"]
        self.configure_gpios()
        err = self._mtib.PowerEnable(channel=PowerChannel.DUT, voltage_v=v)
        if err:
            raise RuntimeError(f"PowerEnable(DUT, {v}V) failed: {err}")
        log.info("DUT power on at %.1fV", v)

    def power_off(self) -> None:
        """Disable all power rails."""
        self._mtib.PowerDisable(channel=PowerChannel.DUT)
        if self.battery_installed:
            self._mtib.PowerDisable(channel=PowerChannel.CHARGER)
        log.info("DUT power off")

    def power_on_for_jlink(self) -> None:
        """Power on in J-Link mode — GPIO configured, 4.5V, no charger."""
        self.configure_gpios()
        err = self._mtib.PowerEnable(channel=PowerChannel.DUT, voltage_v=4.5)
        if err:
            raise RuntimeError(f"PowerEnable for J-Link failed: {err}")
        log.info("J-Link power on at 4.5V")

    # ── Power Read ───────────────────────────────────────────

    def read_dut_current(self) -> float:
        result, err = self._mtib.PowerRead(channel=PowerChannel.DUT)
        if err:
            raise RuntimeError(f"PowerRead(DUT) failed: {err}")
        return result.current_ma

    def read_dut_voltage(self) -> float:
        result, err = self._mtib.PowerRead(channel=PowerChannel.DUT)
        if err:
            raise RuntimeError(f"PowerRead(DUT) failed: {err}")
        return result.voltage_v

    def read_charger_current(self) -> float:
        result, err = self._mtib.PowerRead(channel=PowerChannel.CHARGER)
        if err:
            raise RuntimeError(f"PowerRead(CHARGER) failed: {err}")
        return result.current_ma

    def read_total_current(self) -> float:
        return self.read_dut_current() + self.read_charger_current()

    # ── ADC ──────────────────────────────────────────────────

    def read_adc(self, channel: int) -> float:
        value, err = self._mtib.AdcRead(channel)
        if err:
            raise RuntimeError(f"AdcRead(ch={channel}) failed: {err}")
        return value

    def read_power_rails(self) -> Dict[str, float]:
        """Read manufacturing ADC rail voltages."""
        return {
            "3v3": self.read_adc(0),
            "batt_sys": self.read_adc(1),
            "vbckp": self.read_adc(2),
            "sys": self.read_adc(3),
            "ref_3v3": self.read_adc(7),
        }
