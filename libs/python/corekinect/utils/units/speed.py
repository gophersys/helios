from .constants import *


def kph_to_mph(kph: float) -> float:
    return kph * KPH_TO_MPH


def mph_to_kph(mph: float) -> float:
    return mph * MPH_TO_KPH


def mps_to_fps(mps: float) -> float:
    return mps * MPS_TO_FPS


def fps_to_mps(fps: float) -> float:
    return fps * FPS_TO_MPS


def knots_to_mph(knots: float) -> float:
    return knots * KNOTS_TO_MPH


def mph_to_knots(mph: float) -> float:
    return mph * MPH_TO_KNOTS


def knots_to_kph(knots: float) -> float:
    return knots * KNOTS_TO_KPH


def kph_to_knots(kph: float) -> float:
    return kph * KPH_TO_KNOTS
