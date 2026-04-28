"""Tests for the typed fixture-definition library.

Two surfaces under test:

* Declarative validators on the resource types — out-of-range
  channels/pins, malformed declarations, family typos. These fire
  at import time so the test app fails fast.
* The :class:`Fixture` base — class-level validation in
  ``__init_subclass__`` and runtime binding to a stub MTIB client.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from corekinect.fixture import (
    ADC,
    Fixture,
    FixtureIOError,
    FixtureValidationError,
    GPIO,
    I2C,
    JLink,
    Power,
    SPI,
    UART,
)
from corekinect.fixture import topology


# ── Declarative type validators ───────────────────────────────────


class TestADCDecl:
    def test_valid_channel(self):
        a = ADC(channel=0, signal="VBAT")
        assert a.channel == 0
        assert a.signal == "VBAT"
        assert a.divider == 1.0

    def test_channel_out_of_range_low(self):
        with pytest.raises(FixtureValidationError, match="ADC channel -1"):
            ADC(channel=-1, signal="VBAT")

    def test_channel_out_of_range_high(self):
        with pytest.raises(FixtureValidationError, match="ADC channel 8"):
            ADC(channel=8, signal="VBAT")

    def test_negative_divider_rejected(self):
        with pytest.raises(FixtureValidationError, match="divider"):
            ADC(channel=0, divider=-1.0)


class TestGPIODecl:
    def test_valid_pin(self):
        g = GPIO(pin=0, role="boot")
        assert g.pin == 0
        assert g.role == "boot"

    @pytest.mark.parametrize("pin", [-1, 7, 99])
    def test_pin_out_of_range(self, pin):
        with pytest.raises(FixtureValidationError, match=f"GPIO pin {pin}"):
            GPIO(pin=pin)


class TestUARTDecl:
    def test_valid_port(self):
        u = UART(port=1, target="nrf52840", baud=115200)
        assert u.port == 1
        assert u.target == "nrf52840"

    def test_port_out_of_range(self):
        with pytest.raises(FixtureValidationError, match="UART port 5"):
            UART(port=5)

    def test_zero_baud_rejected(self):
        with pytest.raises(FixtureValidationError, match="baud"):
            UART(port=1, baud=0)


class TestJLinkDecl:
    def test_known_family(self):
        j = JLink(family="NRF52")
        assert j.family == "NRF52"

    def test_family_normalised_to_upper(self):
        j = JLink(family="nrf52")
        assert j.family == "NRF52"

    def test_unknown_family_rejected(self):
        with pytest.raises(FixtureValidationError, match="J-Link family"):
            JLink(family="STM32")


class TestPowerDecl:
    def test_known_rail(self):
        p = Power(rail="DUT_PWR")
        assert p.rail == "DUT_PWR"

    def test_rail_normalised(self):
        p = Power(rail="dut_chg")
        assert p.rail == "DUT_CHG"

    def test_unknown_rail_rejected(self):
        with pytest.raises(FixtureValidationError, match="power rail"):
            Power(rail="VBAT_SIM")


class TestI2CSPIDecl:
    def test_i2c_default_port(self):
        I2C()
        I2C(port=1)

    def test_i2c_bad_port(self):
        with pytest.raises(FixtureValidationError):
            I2C(port=2)

    def test_spi_default(self):
        SPI()


# ── Fixture subclass validation ──────────────────────────────────


class TestFixtureSubclassValidation:
    """``__init_subclass__`` catches bad fixture declarations at import."""

    def test_missing_name_rejected(self):
        with pytest.raises(FixtureValidationError, match="``name``"):

            class BadFix(Fixture):
                revision = "1.0"

    def test_missing_revision_rejected(self):
        with pytest.raises(FixtureValidationError, match="``revision``"):

            class BadFix(Fixture):
                name = "x"

    def test_resource_must_be_dict(self):
        with pytest.raises(FixtureValidationError, match="adcs must be a dict"):

            class BadFix(Fixture):
                name = "x"
                revision = "1.0"
                adcs = [ADC(channel=1)]  # type: ignore[assignment]

    def test_resource_value_must_be_correct_type(self):
        with pytest.raises(FixtureValidationError, match="expected ADC"):

            class BadFix(Fixture):
                name = "x"
                revision = "1.0"
                adcs = {"battery": GPIO(pin=0)}  # type: ignore[dict-item]

    def test_resource_key_must_be_string(self):
        with pytest.raises(FixtureValidationError, match="non-empty"):

            class BadFix(Fixture):
                name = "x"
                revision = "1.0"
                adcs = {"": ADC(channel=1)}

    def test_minimal_valid_subclass(self):
        class GoodFix(Fixture):
            name = "alpha_b0-fixture"
            revision = "1.0"

        f = GoodFix()
        assert f.adcs.keys() == set().union()  # empty
        assert len(f.gpios) == 0


# ── Runtime binding ──────────────────────────────────────────────


@pytest.fixture
def alpha_fixture_class():
    """A representative fixture: 2 ADCs, 2 GPIOs, 2 UARTs, 2 JLinks, 1 Power."""

    class AlphaB0(Fixture):
        name = "alpha_b0-fixture"
        revision = "1.0"
        battery_installed = False

        adcs = {
            "battery": ADC(channel=1, signal="VBAT", divider=2.0),
            "reg_3v3": ADC(channel=7, signal="REG_3V3"),
        }
        gpios = {
            "boot_app": GPIO(pin=0, role="LOW = nRF52 boot"),
            "boot_comms": GPIO(pin=1, role="LOW = nRF91 boot"),
        }
        uarts = {
            "app": UART(port=1, target="nrf52840"),
            "comms": UART(port=2, target="nrf9151"),
        }
        jlinks = {
            "app": JLink(family="NRF52"),
            "comms": JLink(family="NRF91"),
        }
        power = {
            "dut": Power(rail="DUT_PWR"),
            "charger": Power(rail="DUT_CHG"),
        }

    return AlphaB0


class TestFixtureBinding:
    def test_construct_without_mtib(self, alpha_fixture_class):
        """``mtib=None`` is supported for tooling — declarations still iterable."""
        f = alpha_fixture_class(mtib=None)
        assert "battery" in f.adcs
        assert sorted(f.gpios.keys()) == ["boot_app", "boot_comms"]

    def test_missing_resource_lookup_lists_available(self, alpha_fixture_class):
        f = alpha_fixture_class(mtib=None)
        with pytest.raises(KeyError, match="Available:"):
            _ = f.adcs["nope"]

    def test_class_constants_preserved(self, alpha_fixture_class):
        f = alpha_fixture_class(mtib=None)
        assert f.battery_installed is False


class TestADCRuntime:
    def test_read_v_applies_divider(self, alpha_fixture_class):
        mtib = MagicMock()
        mtib.AdcRead.return_value = (1.5, None)
        f = alpha_fixture_class(mtib=mtib)
        # battery has divider=2.0 → MTIB returns 1.5 → rail is 3.0V
        assert f.adcs["battery"].read_v() == pytest.approx(3.0)
        mtib.AdcRead.assert_called_once_with(1)

    def test_read_v_propagates_mtib_error(self, alpha_fixture_class):
        mtib = MagicMock()
        mtib.AdcRead.return_value = (None, "I2C bus stuck")
        f = alpha_fixture_class(mtib=mtib)
        with pytest.raises(FixtureIOError, match="I2C bus stuck"):
            f.adcs["battery"].read_v()


class TestGPIORuntime:
    def test_set_high(self, alpha_fixture_class):
        mtib = MagicMock()
        mtib.GpioWrite.return_value = None
        f = alpha_fixture_class(mtib=mtib)
        f.gpios["boot_app"].set_high()
        mtib.GpioWrite.assert_called_once_with(gpio=0, state=True)

    def test_set_low(self, alpha_fixture_class):
        mtib = MagicMock()
        mtib.GpioWrite.return_value = None
        f = alpha_fixture_class(mtib=mtib)
        f.gpios["boot_app"].set_low()
        mtib.GpioWrite.assert_called_once_with(gpio=0, state=False)

    def test_config_chains(self, alpha_fixture_class):
        mtib = MagicMock()
        mtib.GpioConfig.return_value = None
        mtib.GpioWrite.return_value = None
        f = alpha_fixture_class(mtib=mtib)
        f.gpios["boot_app"].config(direction="output", pull="none").set_low()
        mtib.GpioConfig.assert_called_once()
        mtib.GpioWrite.assert_called_once_with(gpio=0, state=False)

    def test_config_rejects_unknown_direction(self, alpha_fixture_class):
        f = alpha_fixture_class(mtib=MagicMock())
        with pytest.raises(FixtureValidationError, match="direction"):
            f.gpios["boot_app"].config(direction="bidirectional")


class TestPowerRuntime:
    def test_enable_uses_correct_channel(self, alpha_fixture_class):
        mtib = MagicMock()
        mtib.PowerEnable.return_value = None
        f = alpha_fixture_class(mtib=mtib)
        f.power["dut"].enable(voltage_v=4.5)
        mtib.PowerEnable.assert_called_once_with(channel=0, voltage_v=4.5)

    def test_charger_uses_channel_1(self, alpha_fixture_class):
        mtib = MagicMock()
        mtib.PowerEnable.return_value = None
        f = alpha_fixture_class(mtib=mtib)
        f.power["charger"].enable(voltage_v=5.0)
        mtib.PowerEnable.assert_called_once_with(channel=1, voltage_v=5.0)

    def test_negative_voltage_rejected(self, alpha_fixture_class):
        f = alpha_fixture_class(mtib=MagicMock())
        with pytest.raises(FixtureValidationError, match="voltage_v"):
            f.power["dut"].enable(voltage_v=-1)


class TestJLinkRuntime:
    def _stub_uploaded_file(self, name: str, host) -> MagicMock:
        info = MagicMock()
        info.name = name
        info.target = host
        return info

    def test_flash_uploads_lists_then_flashes(self, alpha_fixture_class):
        from corekinect.mtib_client.v1.client.types import HostType

        mtib = MagicMock()
        mtib.UploadFwFile.return_value = None
        # ListFwFiles returns the file we just uploaded.
        info = self._stub_uploaded_file("app.hex", HostType.HOST_TYPE_NRF52840)
        mtib.ListFwFiles.return_value = ([info], None)
        mtib.FlashFwFile.return_value = (1234, None)

        f = alpha_fixture_class(mtib=mtib)
        assert f.jlinks["app"].flash("/firmware/app.hex") == 1234
        mtib.UploadFwFile.assert_called_once_with(
            file_path="/firmware/app.hex",
            target=HostType.HOST_TYPE_NRF52840,
        )
        mtib.FlashFwFile.assert_called_once()
        # recover=True is forwarded by default.
        assert mtib.FlashFwFile.call_args.kwargs["recover"] is True

    def test_flash_recover_false_passes_through(self, alpha_fixture_class):
        from corekinect.mtib_client.v1.client.types import HostType

        mtib = MagicMock()
        mtib.UploadFwFile.return_value = None
        info = self._stub_uploaded_file("app.hex", HostType.HOST_TYPE_NRF52840)
        mtib.ListFwFiles.return_value = ([info], None)
        mtib.FlashFwFile.return_value = (200, None)
        f = alpha_fixture_class(mtib=mtib)
        f.jlinks["app"].flash("/firmware/app.hex", recover=False)
        assert mtib.FlashFwFile.call_args.kwargs["recover"] is False

    def test_flash_routes_nrf91_to_nrf9151_host(self, alpha_fixture_class):
        from corekinect.mtib_client.v1.client.types import HostType

        mtib = MagicMock()
        mtib.UploadFwFile.return_value = None
        info = self._stub_uploaded_file("modem.hex", HostType.HOST_TYPE_NRF9151)
        mtib.ListFwFiles.return_value = ([info], None)
        mtib.FlashFwFile.return_value = (500, None)
        f = alpha_fixture_class(mtib=mtib)
        f.jlinks["comms"].flash("/firmware/modem.hex")
        assert mtib.UploadFwFile.call_args.kwargs["target"] == HostType.HOST_TYPE_NRF9151

    def test_flash_raises_when_upload_lost(self, alpha_fixture_class):
        mtib = MagicMock()
        mtib.UploadFwFile.return_value = None
        # Server forgot the file we just uploaded.
        mtib.ListFwFiles.return_value = ([], None)
        f = alpha_fixture_class(mtib=mtib)
        with pytest.raises(FixtureIOError, match="not.*visible|server lost"):
            f.jlinks["app"].flash("/firmware/app.hex")

    def test_erase_calls_recover(self, alpha_fixture_class):
        from corekinect.mtib_client.v1.client.types import HostType

        mtib = MagicMock()
        mtib.EraseFlash.return_value = None
        f = alpha_fixture_class(mtib=mtib)
        f.jlinks["app"].erase()
        mtib.EraseFlash.assert_called_once_with(
            target=HostType.HOST_TYPE_NRF52840, recover=True,
        )


class TestSummary:
    def test_summary_shape(self, alpha_fixture_class):
        f = alpha_fixture_class(mtib=None)
        summary = f.summary()
        assert summary["name"] == "alpha_b0-fixture"
        assert summary["revision"] == "1.0"
        assert summary["adcs"]["battery"]["channel"] == 1
        assert summary["adcs"]["battery"]["divider"] == 2.0
        assert summary["gpios"]["boot_app"]["pin"] == 0
        assert summary["uarts"]["comms"]["target"] == "nrf9151"
        assert summary["jlinks"]["app"]["family"] == "NRF52"
        assert summary["power"]["charger"]["rail"] == "DUT_CHG"


# ── Topology constants sanity ────────────────────────────────────


class TestTopology:
    def test_current_revision_matches_schematic(self):
        assert topology.CURRENT.revision == "1.2"

    def test_adc_channels_zero_indexed(self):
        # Wire-protocol-aligned: ADS1115 channels are 0-7.
        assert topology.ADC_CHANNELS == (0, 1, 2, 3, 4, 5, 6, 7)
