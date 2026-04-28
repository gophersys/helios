"""Tests for the AST-only fixture extractor.

Covers the contract the backend depends on: feed it the source of a
fixture module, get back a metadata dict (or a clear validation
error). The extractor must NEVER execute the source.
"""

from __future__ import annotations

import textwrap

import pytest

from corekinect.fixture.extractor import FixtureExtractionError, extract_fixture


# ── Fixture for "well-formed" source samples ────────────────────


VALID_SOURCE = textwrap.dedent(
    """
    from corekinect.fixture import Fixture, ADC, GPIO, UART, JLink, Power


    class AlphaB0Fixture(Fixture):
        name = "alpha_b0-fixture"
        revision = "1.0"
        battery_installed = False
        boot_settle_s = 3

        adcs = {
            "battery": ADC(channel=1, signal="VBAT", divider=2.0),
            "reg_3v3": ADC(channel=7, signal="REG_3V3"),
        }
        gpios = {
            "boot_app":   GPIO(pin=0, role="LOW = nRF52 boots"),
            "boot_comms": GPIO(pin=1, role="LOW = nRF91 boots"),
        }
        uarts = {
            "app":   UART(port=1, target="nrf52840"),
            "comms": UART(port=2, target="nrf9151", baud=921600),
        }
        jlinks = {
            "app":   JLink(family="NRF52"),
            "comms": JLink(family="NRF91"),
        }
        power = {
            "dut":     Power(rail="DUT_PWR"),
            "charger": Power(rail="DUT_CHG"),
        }
    """
)


class TestValidExtraction:
    def test_returns_name_and_revision(self):
        result = extract_fixture(VALID_SOURCE)
        assert result["name"] == "alpha_b0-fixture"
        assert result["revision"] == "1.0"
        assert result["class_name"] == "AlphaB0Fixture"

    def test_adcs_extracted_with_divider(self):
        result = extract_fixture(VALID_SOURCE)
        assert result["adcs"]["battery"]["channel"] == 1
        assert result["adcs"]["battery"]["divider"] == 2.0
        assert result["adcs"]["battery"]["signal"] == "VBAT"
        # Default divider when not specified.
        assert result["adcs"]["reg_3v3"]["divider"] == 1.0

    def test_gpios_extracted(self):
        result = extract_fixture(VALID_SOURCE)
        assert result["gpios"]["boot_app"]["pin"] == 0
        assert result["gpios"]["boot_comms"]["pin"] == 1
        assert result["gpios"]["boot_app"]["role"] == "LOW = nRF52 boots"

    def test_uarts_extracted_with_baud(self):
        result = extract_fixture(VALID_SOURCE)
        assert result["uarts"]["app"]["port"] == 1
        assert result["uarts"]["app"]["baud"] == 115200  # default
        assert result["uarts"]["comms"]["baud"] == 921600
        assert result["uarts"]["comms"]["target"] == "nrf9151"

    def test_jlinks_normalised_to_upper(self):
        source = VALID_SOURCE.replace('JLink(family="NRF52")', 'JLink(family="nrf52")')
        result = extract_fixture(source)
        assert result["jlinks"]["app"]["family"] == "NRF52"

    def test_power_rails_normalised(self):
        source = VALID_SOURCE.replace('Power(rail="DUT_PWR")', 'Power(rail="dut_pwr")')
        result = extract_fixture(source)
        assert result["power"]["dut"]["rail"] == "DUT_PWR"


class TestMinimalFixture:
    def test_only_name_and_revision_required(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture
            class TinyFix(Fixture):
                name = "tiny"
                revision = "1.0"
            """
        )
        result = extract_fixture(source)
        assert result["name"] == "tiny"
        assert result["adcs"] == {}
        assert result["gpios"] == {}


# ── Failure modes ───────────────────────────────────────────────


class TestRejections:
    def test_no_fixture_subclass(self):
        source = "class NotAFixture: pass\n"
        with pytest.raises(FixtureExtractionError, match="no class subclassing Fixture"):
            extract_fixture(source)

    def test_two_fixture_subclasses(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture
            class A(Fixture):
                name = "a"
                revision = "1.0"
            class B(Fixture):
                name = "b"
                revision = "1.0"
            """
        )
        with pytest.raises(FixtureExtractionError, match="exactly one"):
            extract_fixture(source)

    def test_missing_name(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture
            class X(Fixture):
                revision = "1.0"
            """
        )
        with pytest.raises(FixtureExtractionError, match="``name``"):
            extract_fixture(source)

    def test_missing_revision(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture
            class X(Fixture):
                name = "x"
            """
        )
        with pytest.raises(FixtureExtractionError, match="``revision``"):
            extract_fixture(source)

    def test_name_must_be_string_literal(self):
        # Variable reference — the AST extractor cannot resolve.
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture
            FIX_NAME = "computed-name"
            class X(Fixture):
                name = FIX_NAME
                revision = "1.0"
            """
        )
        with pytest.raises(FixtureExtractionError, match="must be a string literal"):
            extract_fixture(source)

    def test_adc_out_of_range(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture, ADC
            class X(Fixture):
                name = "x"
                revision = "1.0"
                adcs = {"bad": ADC(channel=99)}
            """
        )
        with pytest.raises(FixtureExtractionError, match="ADC channel 99"):
            extract_fixture(source)

    def test_gpio_out_of_range(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture, GPIO
            class X(Fixture):
                name = "x"
                revision = "1.0"
                gpios = {"bad": GPIO(pin=42)}
            """
        )
        with pytest.raises(FixtureExtractionError, match="GPIO pin 42"):
            extract_fixture(source)

    def test_uart_bad_port(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture, UART
            class X(Fixture):
                name = "x"
                revision = "1.0"
                uarts = {"bad": UART(port=5)}
            """
        )
        with pytest.raises(FixtureExtractionError, match="UART port 5"):
            extract_fixture(source)

    def test_jlink_unknown_family(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture, JLink
            class X(Fixture):
                name = "x"
                revision = "1.0"
                jlinks = {"app": JLink(family="STM32")}
            """
        )
        with pytest.raises(FixtureExtractionError, match="J-Link family"):
            extract_fixture(source)

    def test_power_unknown_rail(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture, Power
            class X(Fixture):
                name = "x"
                revision = "1.0"
                power = {"alt": Power(rail="VBAT_SIM")}
            """
        )
        with pytest.raises(FixtureExtractionError, match="power rail"):
            extract_fixture(source)

    def test_resource_value_must_be_call(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture, ADC
            BATTERY = ADC(channel=1)
            class X(Fixture):
                name = "x"
                revision = "1.0"
                adcs = {"battery": BATTERY}
            """
        )
        with pytest.raises(FixtureExtractionError, match="must be a call"):
            extract_fixture(source)

    def test_wrong_resource_type(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture, GPIO
            class X(Fixture):
                name = "x"
                revision = "1.0"
                adcs = {"battery": GPIO(pin=0)}
            """
        )
        with pytest.raises(FixtureExtractionError, match="expected ADC"):
            extract_fixture(source)

    def test_dict_key_must_be_string(self):
        source = textwrap.dedent(
            """
            from corekinect.fixture import Fixture, ADC
            class X(Fixture):
                name = "x"
                revision = "1.0"
                adcs = {1: ADC(channel=1)}
            """
        )
        with pytest.raises(FixtureExtractionError, match="keys must be string"):
            extract_fixture(source)

    def test_syntax_error_reported_with_path(self):
        with pytest.raises(FixtureExtractionError, match="syntax error"):
            extract_fixture("class X(Fixture\n", source_path="fixtures/x.py")


class TestNoCodeExecution:
    """The extractor must not import or execute anything in the source."""

    def test_module_with_side_effect_does_not_run(self):
        # If the extractor imported the module, the marker would
        # exist on the corekinect.fixture namespace. It mustn't.
        source = textwrap.dedent(
            """
            import sys
            sys.modules["corekinect.fixture"].__SIDE_EFFECT__ = "FIRED"

            from corekinect.fixture import Fixture
            class X(Fixture):
                name = "side-effect-test"
                revision = "1.0"
            """
        )
        result = extract_fixture(source)
        assert result["name"] == "side-effect-test"

        import corekinect.fixture
        assert not hasattr(corekinect.fixture, "__SIDE_EFFECT__")

    def test_corekinect_fixture_namespace_qualified_base_works(self):
        source = textwrap.dedent(
            """
            import corekinect.fixture as cf
            class X(cf.Fixture):
                name = "namespaced"
                revision = "1.0"
            """
        )
        result = extract_fixture(source)
        assert result["name"] == "namespaced"
