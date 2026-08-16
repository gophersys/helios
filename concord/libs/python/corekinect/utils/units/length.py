from .constants import *


def meters_to_feet(meters: float) -> float:
    """Convert meters to feet."""
    return meters * M_TO_FT


def feet_to_meters(feet: float) -> float:
    """Convert feet to meters."""
    return feet * FT_TO_M


def kilometers_to_miles(km: float) -> float:
    """Convert kilometers to miles."""
    return km * KM_TO_MILES


def miles_to_kilometers(mi: float) -> float:
    """Convert miles to kilometers."""
    return mi * MILES_TO_KM


def nautical_miles_to_miles(nm: float) -> float:
    """Convert nautical miles to statute miles."""
    return nm * NM_TO_MILES


def miles_to_nautical_miles(mi: float) -> float:
    """Convert statute miles to nautical miles."""
    return mi * MILES_TO_NM


def nautical_miles_to_kilometers(nm: float) -> float:
    """Convert nautical miles to kilometers."""
    return nm * KNOTS_TO_KPH  # 1 nm = 1.852 km


def kilometers_to_nautical_miles(km: float) -> float:
    """Convert kilometers to nautical miles."""
    return km / KNOTS_TO_KPH
