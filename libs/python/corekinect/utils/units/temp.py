from .constants import *


def celsius_to_fahrenheit(celsius: float) -> float:
    return celsius * C_TO_F_SCALE + C_TO_F_OFFSET


def fahrenheit_to_celsius(fahrenheit: float) -> float:
    return (fahrenheit - C_TO_F_OFFSET) * F_TO_C_SCALE


def celsius_to_kelvin(celsius: float) -> float:
    return celsius + KELVIN_OFFSET


def kelvin_to_celsius(kelvin: float) -> float:
    return kelvin - KELVIN_OFFSET


def kelvin_to_fahrenheit(kelvin: float) -> float:
    return (kelvin - KELVIN_OFFSET) * C_TO_F_SCALE + C_TO_F_OFFSET


def fahrenheit_to_kelvin(fahrenheit: float) -> float:
    return (fahrenheit - C_TO_F_OFFSET) * F_TO_C_SCALE + KELVIN_OFFSET


def kelvin_to_rankine(kelvin: float) -> float:
    return kelvin * K_TO_R_SCALE


def rankine_to_kelvin(rankine: float) -> float:
    return rankine / K_TO_R_SCALE


def fahrenheit_to_rankine(fahrenheit: float) -> float:
    return fahrenheit + F_TO_R_OFFSET


def rankine_to_fahrenheit(rankine: float) -> float:
    return rankine - F_TO_R_OFFSET
