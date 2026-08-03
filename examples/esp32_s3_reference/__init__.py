"""ESP32-S3-WROOM-1 reference design (Stage F3).

See :mod:`examples.esp32_s3_reference.design` for the circuit itself, the
sheet/net conventions and the provenance table.
"""

from .design import PROVENANCE, SHEETS, build

__all__ = ["PROVENANCE", "SHEETS", "build"]
