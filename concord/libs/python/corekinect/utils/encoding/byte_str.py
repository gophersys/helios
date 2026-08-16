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


def base64_to_str(data: str, *, encoding: str = "utf-8") -> str:
    """
    Convert Base64-encoded string to a decoded text string.
    Raises ValueError if the data is not valid Base64 or invalid encoding.
    """
    try:
        decoded_bytes = base64.b64decode(data.strip(), validate=True)
        utf_16 = decoded_bytes.decode("utf-16", errors="ignore")
        latin_1 = decoded_bytes.decode("latin-1")
        return decoded_bytes.decode(encoding, errors="ignore")
    except Exception as e:
        raise ValueError(f"Invalid Base64 or encoding error: {e}")
