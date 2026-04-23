"""Device identifier constants.

Carrier prefixes, IMEI/ICCID length constraints, and other
hardware identity constants shared across manufacturing and
validation test suites.
"""

IMEI_LENGTH = 15

ICCID_MIN_LENGTH = 19
ICCID_MAX_LENGTH = 20

# ICCID carrier prefix → carrier name.
# Matches the mapping in device_personalizer.py — keep in sync.
CARRIER_PREFIXES = {
    "891480": "Verizon",
    "8942310": "Soracom",
    "894573": "Onomondo",
    "890103": "Att",
}
