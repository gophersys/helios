import struct
from typing import Tuple


def hex_lat_long_to_base_10(lat: int | str, lon: int | str, do_print=True) -> Tuple[float, float]:
    """
    Converts latitude and longitude values from hexadecimal format to decimal format.
    """
    # Get bytes from input
    if isinstance(lat, str):
        lat = bytes.fromhex(lat)
    if isinstance(lon, str):
        lon = bytes.fromhex(lon)
    if isinstance(lat, int):
        lat = lat.to_bytes(4, byteorder="big")
    if isinstance(lon, int):
        lon = lon.to_bytes(4, byteorder="big")

    # Big-endian (>)
    # signed int (i; 4 bytes)
    my_lat = struct.unpack(">i", lat)[0]
    my_lon = struct.unpack(">i", lon)[0]

    # Convert to decimal degrees
    my_lat = my_lat / 1e7
    my_lon = my_lon / 1e7

    if do_print:
        print(f"{my_lat}, {my_lon}")

    return my_lat, my_lon
