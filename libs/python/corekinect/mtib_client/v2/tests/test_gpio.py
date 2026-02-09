"""Tests for GPIO control operations."""

from corekinect.mtib_client.v2.types.gpio import GpioState


class TestGpioConfig:
    def test_gpio_config_input(self, client):
        err = client.gpio_config(pin=5, direction=0, pull=1)
        assert err is None

    def test_gpio_config_output(self, client):
        err = client.gpio_config(pin=13, direction=1)
        assert err is None


class TestGpioWrite:
    def test_gpio_write_high(self, client):
        err = client.gpio_write(pin=13, value=True)
        assert err is None

    def test_gpio_write_low(self, client):
        err = client.gpio_write(pin=13, value=False)
        assert err is None


class TestGpioRead:
    def test_gpio_read_returns_state(self, client):
        err, state = client.gpio_read(pin=5)
        assert err is None
        assert isinstance(state, GpioState)
        assert state.pin == 5
        assert state.value is True
