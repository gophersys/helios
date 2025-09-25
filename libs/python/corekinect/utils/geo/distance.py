import math


def haversine(lat1, lon1, lat2, lon2, in_miles=False) -> float:
    """
    Calculate the great-circle distance between two points on the Earth's surface.

    Parameters:
    - lat1, lon1: Latitude and Longitude of the first point in degrees.
    - lat2, lon2: Latitude and Longitude of the second point in degrees.
    - in_miles: If True, return the distance in miles. Otherwise, return the distance in kilometers. Default is False.

    Returns:
    - Distance between the two points in miles.
    """
    # Earth's radius in kilometers
    EARTH_RADIUS_KM = 6371.01
    KM_TO_MILES = 0.621371

    # Convert degrees to radians
    lat1_rad = math.radians(lat1)
    lon1_rad = math.radians(lon1)
    lat2_rad = math.radians(lat2)
    lon2_rad = math.radians(lon2)

    # Differences in coordinates
    dlat = lat2_rad - lat1_rad
    dlon = lon2_rad - lon1_rad

    # Haversine formula
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    km_distance = EARTH_RADIUS_KM * c

    # Convert to miles
    if in_miles:
        return km_distance * KM_TO_MILES
    else:
        return km_distance
