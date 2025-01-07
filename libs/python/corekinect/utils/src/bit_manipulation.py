def get_bits(num: int, start: int, end: int) -> int:
    """
    Retrieves the bits from a given number within the specified range.
    """
    return (num >> start) & ((1 << (end - start + 1)) - 1)


def set_bits(num: int, start: int, end: int, value: int) -> int:
    """
    Sets the bits of a given number within the specified range.
    """
    mask = ((1 << (end - start + 1)) - 1) << start
    return (num & ~mask) | ((value << start) & mask)
