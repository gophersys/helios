"""ESP32-S3-WROOM-1 reference design (Stage F3).

See :mod:`examples.esp32_s3_reference.design` for the circuit itself, the
sheet/net conventions and the provenance table.

``build()`` returns the whole :class:`~src.pipeline.composer.GeneratedProject`
— the one example contract, documented in ``examples/README.md``. ``sheets()``
returns the per-sheet :class:`~src.ecad.Design` objects the circuit is
authored as, which is what the per-sheet gates and the rule engine work on.
"""

from .design import PROVENANCE, SHEETS, blocks, build, sheets

__all__ = ["PROVENANCE", "SHEETS", "blocks", "build", "sheets"]
