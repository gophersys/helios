from .constants import *


def meters_to_feet(meters: float) -> float:
    return meters * M_TO_FT


def feet_to_meters(feet: float) -> float:
    return feet * FT_TO_M


def kilometers_to_miles(km: float) -> float:
    return km * KM_TO_MILES


def miles_to_kilometers(mi: float) -> float:
    return mi * MILES_TO_KM


def nautical_miles_to_miles(nm: float) -> float:
    return nm * NM_TO_MILES


def miles_to_nautical_miles(mi: float) -> float:
    return mi * MILES_TO_NM


def nautical_miles_to_kilometers(nm: float) -> float:
    return nm * KNOTS_TO_KPH  # 1 nm = 1.852 km


def kilometers_to_nautical_miles(km: float) -> float:
    return km / KNOTS_TO_KPH
