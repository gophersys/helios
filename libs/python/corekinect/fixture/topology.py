"""Fixed MTIB hardware topology — derived from the schematic.

The MTIB exposes a finite set of physical resources to a DUT. This
module enumerates the limits so the fixture validators (and the
declarative wrappers in :mod:`corekinect.fixture.types`) can reject
out-of-range channels/pins at fixture-load time, before any test runs.

Source of truth: ``apps/edge/mtib-server/docs/schematics/MTIB-Expansion_2026-04-23.pdf``
(REV 1.2). Update both this file AND the schematic together when the
hardware changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


# ── Main DUT connector (CN2, 48 signal pins) ─────────────────────

# ADC channels. The MTIB has two ADS1115s (0x48, 0x49) wired through
# op-amp signal conditioning. The wire protocol indexes channels 0..7;
# the schematic labels the corresponding DUT pins ``EXT_DUT_ADC1..ADC7``
# (so protocol channel 0 = ADC1 on the connector). Channel 7 measures
# an internal reference rail with no external pin.
ADC_CHANNELS: Tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6, 7)

# GPIO. ``EXT_DUT_GPIO0..GPIO6`` reach the DUT through level shifters.
GPIO_PINS: Tuple[int, ...] = (0, 1, 2, 3, 4, 5, 6)

# UART. Two ports: UART1 and UART2.
UART_PORTS: Tuple[int, ...] = (1, 2)

# J-Link. Two physical J-Link headers (JLINK1, JLINK2) routed through a
# multiplexer so the test code refers to them by chip family.
JLINK_PORTS: Tuple[int, ...] = (1, 2)

# I2C: a single bus exposed as ``EXT_DUT_I2C_{SDA,SCL}``.
I2C_PORTS: Tuple[int, ...] = (1,)

# SPI: a single bus exposed as ``EXT_DUT_SPI_{CLK,MISO,MOSI}``. No CS
# is exposed externally — the DUT manages chip-select internally.
SPI_PORTS: Tuple[int, ...] = (1,)


# ── DUT power rails the MTIB drives ─────────────────────────────

# ``+EXT_DUT_PWR`` (battery sim, ch 0 of the INA219 power monitor)
# and ``+EXT_DUT_CHG`` (charger sim, ch 1). Both are voltage-set at
# runtime via ``MtibV1Client.PowerEnable(channel, voltage_v)``.
POWER_RAILS: Tuple[str, ...] = ("DUT_PWR", "DUT_CHG")
POWER_RAIL_CHANNEL = {
    "DUT_PWR": 0,
    "DUT_CHG": 1,
}


# ── Aux connector (CN1, 30 pins, REV 1.2 only) ──────────────────

# Three aux ADCs.
AUX_ADC_CHANNELS: Tuple[int, ...] = (0, 1, 2)
# Two aux GPIOs.
AUX_GPIO_PINS: Tuple[int, ...] = (0, 1)
# Two stepper drivers, four output phases each.
STEPPER_PORTS: Tuple[int, ...] = (1, 2)


# ── Chip families the J-Link multiplexer can target ─────────────
#
# These are the symbolic family names the fixture passes to the MTIB
# server, which resolves the actual probe SNR at runtime via the
# server-side ``_find_programmer`` map. The server's nrfjprog
# ``-f`` flag is derived from the family (NRF52, NRF53, NRF91).
#
# The mapping family → MTIB ``HostType`` enum lives in
# :mod:`corekinect.fixture.types` (``BoundJLink._resolve_host``).
# Both must stay in sync — adding a family here without a matching
# host map entry will fail at runtime with a clear error.
KNOWN_JLINK_FAMILIES: Tuple[str, ...] = ("NRF52", "NRF53", "NRF91")


@dataclass(frozen=True)
class MtibLimits:
    """Snapshot of a single MTIB revision's resource limits.

    Used by validators to bound-check fixture declarations. The
    ``revision`` field tracks the schematic revision the limits are
    derived from so a future hardware change invalidates fixtures
    that were authored against the prior revision.
    """

    revision: str
    adc_channels: Tuple[int, ...]
    gpio_pins: Tuple[int, ...]
    uart_ports: Tuple[int, ...]
    jlink_ports: Tuple[int, ...]
    i2c_ports: Tuple[int, ...]
    spi_ports: Tuple[int, ...]
    power_rails: Tuple[str, ...]
    aux_adc_channels: Tuple[int, ...]
    aux_gpio_pins: Tuple[int, ...]
    stepper_ports: Tuple[int, ...]
    has_aux_connector: bool


CURRENT = MtibLimits(
    revision="1.2",
    adc_channels=ADC_CHANNELS,
    gpio_pins=GPIO_PINS,
    uart_ports=UART_PORTS,
    jlink_ports=JLINK_PORTS,
    i2c_ports=I2C_PORTS,
    spi_ports=SPI_PORTS,
    power_rails=POWER_RAILS,
    aux_adc_channels=AUX_ADC_CHANNELS,
    aux_gpio_pins=AUX_GPIO_PINS,
    stepper_ports=STEPPER_PORTS,
    has_aux_connector=True,
)
