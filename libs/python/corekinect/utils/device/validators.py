"""Device identifier validators.

IMEI, ICCID, and Luhn checksum validation used by manufacturing
POST tests and validation test suites.

    from corekinect.utils.device import validate_imei, validate_iccid

    err = validate_imei("359881090000013")
    assert not err, err

    err = validate_iccid("89148000000000000001")
    assert not err, err
"""

from .identifiers import (
    CARRIER_PREFIXES,
    ICCID_MAX_LENGTH,
    ICCID_MIN_LENGTH,
    IMEI_LENGTH,
)


def luhn_check(number: str) -> bool:
    """Validate a number string using the Luhn algorithm.

    Works for both IMEI (15 digits) and ICCID (19-20 digits).
    """
    digits = [int(d) for d in number]
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    checksum = sum(odd_digits)
    for d in even_digits:
        checksum += sum(int(x) for x in str(d * 2))
    return checksum % 10 == 0


def validate_imei(imei: str) -> str:
    """Validate an IMEI string. Returns empty string on success, error message on failure."""
    if len(imei) != IMEI_LENGTH or not imei.isdigit():
        return f"IMEI ({imei}) invalid: expected {IMEI_LENGTH} digits, got {len(imei)}"
    if not luhn_check(imei):
        return f"IMEI ({imei}) failed Luhn checksum"
    return ""


def validate_iccid(iccid: str) -> str:
    """Validate an ICCID string. Returns empty string on success, error message on failure."""
    cleaned = iccid.rstrip("F")
    if len(cleaned) not in (ICCID_MIN_LENGTH, ICCID_MAX_LENGTH):
        return f"ICCID ({cleaned}) invalid length: {len(cleaned)}"
    if not luhn_check(cleaned):
        return f"ICCID ({cleaned}) failed Luhn checksum"
    if not any(cleaned.startswith(prefix) for prefix in CARRIER_PREFIXES):
        return f"ICCID ({cleaned}) is not from a recognized carrier"
    return ""
