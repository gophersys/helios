from .constants import *


def celsius_to_fahrenheit(celsius: float) -> float:
    """Convert Celsius to Fahrenheit."""
    return celsius * C_TO_F_SCALE + C_TO_F_OFFSET


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    """Convert Fahrenheit to Celsius."""
    return (fahrenheit - C_TO_F_OFFSET) * F_TO_C_SCALE


def celsius_to_kelvin(celsius: float) -> float:
    """Convert Celsius to Kelvin."""
    return celsius + KELVIN_OFFSET


def kelvin_to_celsius(kelvin: float) -> float:
    """Convert Kelvin to Celsius."""
    return kelvin - KELVIN_OFFSET


def kelvin_to_fahrenheit(kelvin: float) -> float:
    """Convert Kelvin to Fahrenheit."""
    return (kelvin - KELVIN_OFFSET) * C_TO_F_SCALE + C_TO_F_OFFSET


def fahrenheit_to_kelvin(fahrenheit: float) -> float:
    """Convert Fahrenheit to Kelvin."""
    return (fahrenheit - C_TO_F_OFFSET) * F_TO_C_SCALE + KELVIN_OFFSET


def kelvin_to_rankine(kelvin: float) -> float:
    """Convert Kelvin to Rankine."""
    return kelvin * K_TO_R_SCALE


def rankine_to_kelvin(rankine: float) -> float:
    """Convert Rankine to Kelvin."""
    return rankine / K_TO_R_SCALE


def fahrenheit_to_rankine(fahrenheit: float) -> float:
    """Convert Fahrenheit to Rankine."""
    return fahrenheit + F_TO_R_OFFSET


def rankine_to_fahrenheit(rankine: float) -> float:
    """Convert Rankine to Fahrenheit."""
    return rankine - F_TO_R_OFFSET
