from .constants import *


def kph_to_mph(kph: float) -> float:
    """Convert kilometers per hour to miles per hour."""
    return kph * KPH_TO_MPH


def mph_to_kph(mph: float) -> float:
    """Convert miles per hour to kilometers per hour."""
    return mph * MPH_TO_KPH


def mps_to_fps(mps: float) -> float:
    """Convert meters per second to feet per second."""
    return mps * MPS_TO_FPS


def fps_to_mps(fps: float) -> float:
    """Convert feet per second to meters per second."""
    return fps * FPS_TO_MPS


def knots_to_mph(knots: float) -> float:
    """Convert knots to miles per hour."""
    return knots * KNOTS_TO_MPH


def mph_to_knots(mph: float) -> float:
    """Convert miles per hour to knots."""
    return mph * MPH_TO_KNOTS


def knots_to_kph(knots: float) -> float:
    """Convert knots to kilometers per hour."""
    return knots * KNOTS_TO_KPH


def kph_to_knots(kph: float) -> float:
    """Convert kilometers per hour to knots."""
    return kph * KPH_TO_KNOTS
