import pytest

from ..src.temperature import celsius_to_fahrenheit, fahrenheit_to_celsius


def test_celsius_to_fahrenheit():
    assert celsius_to_fahrenheit(0) == 32
    assert celsius_to_fahrenheit(100) == 212
    assert celsius_to_fahrenheit(-40) == -40
    assert celsius_to_fahrenheit(37) == 98.6


def test_fahrenheit_to_celsius():
    assert fahrenheit_to_celsius(32) == 0
    assert fahrenheit_to_celsius(212) == 100
    assert fahrenheit_to_celsius(-40) == -40
    assert fahrenheit_to_celsius(98.6) == pytest.approx(37.0, 0.1)


def test_temperature_round_trip():
    temps_c = [0, 100, -40, 37.0, 25.5]
    for temp in temps_c:
        temp_f = celsius_to_fahrenheit(temp)
        converted_c = fahrenheit_to_celsius(temp_f)
        assert converted_c == pytest.approx(temp, 0.01)


def test_temperature_invalid_inputs():
    with pytest.raises(TypeError):
        celsius_to_fahrenheit("100")  # Invalid type
    with pytest.raises(TypeError):
        fahrenheit_to_celsius(None)  # Invalid type
