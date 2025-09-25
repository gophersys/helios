import base64


def to_hex(data: bytes) -> str:
    """
    Converts a bytes object to its hexadecimal representation.
    """
    return data.hex()


def int_to_bin_str(value: int | str) -> str:
    """
    Converts an integer or a string representation of an integer to its binary representation.
    """
    if isinstance(value, str):
        value = int(value, 0)
    return bin(value)[2:]


def hex_to_base64(hex_string: str) -> str:
    """
    Converts a hexadecimal string to a base64 encoded string.
    """
    return base64.b64encode(bytes.fromhex(hex_string)).decode("utf-8")


def bytes_to_base64(data: bytes) -> str:
    """
    Convert the given bytes data to a base64 encoded string.
    """
    return base64.b64encode(data).decode("utf-8")
