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
