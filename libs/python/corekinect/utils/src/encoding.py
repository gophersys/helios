import base64
import struct
from typing import Tuple


def to_hex(data: bytes) -> str:
    """
    Converts a bytes object to its hexadecimal representation.
    """
    return data.hex()


def hex_to_base10(hex_string: str) -> int:
    """
    Converts a hexadecimal string to its base10 representation.
    """
    if isinstance(hex_string, int):
        return hex_string
    elif isinstance(hex_string, str):
        return int(hex_string, 16)
    else:
        raise ValueError("Invalid input type")


def int_to_padded_hex(n: int, num_bytes: int = 4, do_print: bool = False) -> str:
    """
    Converts an integer to a padded hexadecimal string.
    """
    hex_str = f"{n:0{num_bytes*2}x}"
    if do_print:
        print(hex_str)
    return hex_str


def int_to_padded_bin(n: int, num_bytes: int = 4, do_print: bool = False) -> str:
    """
    Converts an integer to a padded binary string.
    """
    bin_str = f"{n:0{num_bytes*8}b}"
    if do_print:
        print(bin_str)
    return bin_str


def hex_to_base64(hex_string: str) -> str:
    """
    Converts a hexadecimal string to a base64 encoded string.
    """
    return base64.b64encode(bytes.fromhex(hex_string)).decode("utf-8")


def to_base64(data: bytes) -> str:
    """
    Convert the given bytes data to a base64 encoded string.
    """
    return base64.b64encode(data).decode("utf-8")


def to_bin(value: int | str) -> str:
    """
    Converts an integer or a string representation of an integer to its binary representation.
    """
    if isinstance(value, str):
        value = int(value, 0)
    return bin(value)[2:]


def print_binary(value: int | str) -> None:
    """
    Prints the binary representation of the given value.
    """
    if isinstance(value, str):
        value = int(value, 0)
    binary_string = bin(value)[2:]
    print(binary_string)


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
