import pytest

from ..src.math_utils import haversine


def test_haversine_zero_distance():
    lat, lon = 0, 0
    distance = haversine(lat, lon, lat, lon)
    assert distance == 0.0


def test_haversine_known_distance():
    # Distance between New York (40.7128° N, 74.0060° W)
    # and London (51.5074° N, 0.1278° W) ~ 3458 miles
    ny_lat, ny_lon = 40.7128, -74.0060
    london_lat, london_lon = 51.5074, -0.1278
    distance_miles = haversine(ny_lat, ny_lon, london_lat, london_lon, in_miles=True)
    assert distance_miles == pytest.approx(3458, abs=5)  # Allow a 5-mile margin

    distance_km = haversine(ny_lat, ny_lon, london_lat, london_lon, in_miles=False)
    assert distance_km == pytest.approx(5567, abs=5)  # Allow a 5-km margin


def test_haversine_antipodal_points():
    # Antipodal points should be approximately 3959 miles (half Earth's circumference)
    lat1, lon1 = 33.448, -112.074  # Phoenix
    lat2, lon2 = -33.448, 67.926  # Antipodal to Phoenix

    distance_miles = haversine(lat1, lon1, lat2, lon2, in_miles=True)
    assert round(distance_miles) == 12437  # As measured using Google Earth

    distance_km = haversine(lat1, lon1, lat2, lon2, in_miles=False)
    assert round(distance_km) == 20015  # As measured using Google Earth


def test_haversine_invalid_inputs():
    with pytest.raises(TypeError):
        haversine("34.05", -118.25, 40.7128, -74.0060)  # Invalid type for lat1
    with pytest.raises(TypeError):
        haversine(34.05, -118.25, None, -74.0060)  # NoneType for lat2
