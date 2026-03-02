import builtins
from typing import Optional, Tuple, Union


def set_bits(num: int, start: int, end: int, value: int) -> int | None:
    if not all(isinstance(i, int) for i in [num, start, end, value]):
        return None
    if start > end:
        start, end = end, start
    if start < 0 or end < 0:
        return None
    width = end - start + 1
    mask = ((1 << width) - 1) << start
    # truncate value to the field width so out of range bits don’t leak
    return (num & ~mask) | (((value & ((1 << width) - 1)) << start) & mask)


def get_bits(num: int, start: int, end: int) -> int | None:
    if not all(isinstance(i, int) for i in [num, start, end]):
        return None
    if start > end:
        start, end = end, start
    if start < 0 or end < 0:
        return None
    return (num >> start) & ((1 << (end - start + 1)) - 1)


def _to_int(value, *, default: int = 0) -> int:
    if value is None:
        return default
    # check bool BEFORE int (bool is apparently a subclass of int)
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, (bytes, bytearray, memoryview)):
        b = bytes(value)
        return int.from_bytes(b, "big", signed=False) if b else default
    if isinstance(value, str):
        return default
    try:
        return int(value)  # numpy scalars because fuck me
    except Exception:
        return default


def get_bits_safe(num: Union[int, bool, bytes, bytearray], start: int, end: int) -> int:
    if start > end:
        start, end = end, start
    if start < 0 or end < 0:
        raise ValueError("bit positions must be non-negative")
    n = _to_int(num, default=0)
    width = end - start + 1
    return (n >> start) & ((1 << width) - 1)


def extract_bits(
    flags: int | bool | bytes | bytearray,
    bit_range: Tuple[int, int],
    *,
    cast: type[int] | type[bool] | type[float] = int,
    default: int | bool = None,  # if flags is None
    scale: float = 1.0,
) -> int | bool | None:
    if not (
        isinstance(bit_range, tuple)
        and len(bit_range) == 2
        and isinstance(bit_range[0], int)
        and isinstance(bit_range[1], int)
    ):
        raise ValueError("bit_range must be a tuple[int, int]")

    if flags is None:
        return default

    raw = get_bits_safe(flags, *bit_range)

    if cast is bool:
        return builtins.bool(raw)  # type: ignore[return-value]
    if scale != 1.0 or cast is float:
        return builtins.float(raw) * scale  # type: ignore[return-value]
    return builtins.int(raw)  # type: ignore[return-value]


def has_bit(v: Union[int, bool, bytes, bytearray], bit: int) -> Optional[bool]:
    if v is None:
        return None
    if bit < 0:
        raise ValueError("bit must be >= 0")
    return bool(get_bits_safe(v, bit, bit))
