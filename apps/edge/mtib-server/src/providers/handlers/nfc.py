"""NFC reader handler for MTIB server.

Supports I2C-connected NFC readers (e.g., PN532, ST25DV) on the Verdin SoM.
Auto-detects reader presence at init; RPCs return graceful errors when
no reader is connected.
"""

import time
from typing import Optional

import grpc
from corekinect.utils import Logger
from src.shared.types import (
    NfcPollRequest,
    NfcPollResponse,
    NfcReadNdefRequest,
    NfcReadNdefResponse,
    NdefRecord,
)


class NfcHandler:
    """Handles NFC reader operations via I2C.

    Probes common NFC reader I2C addresses at init. If no reader is found,
    all RPCs return success=False with a descriptive message.
    """

    # Common NFC reader I2C addresses
    _NFC_I2C_ADDRESSES = [
        (0x24, "PN532"),      # PN532 default I2C address
        (0x2A, "PN532-alt"),  # PN532 alternate address
        (0x53, "ST25DV"),     # ST25DV dynamic NFC tag
        (0x57, "ST25DV-sys"), # ST25DV system area
    ]

    # I2C bus numbers to try on Verdin (bus 1 and 3 are common)
    _I2C_BUSES = [1, 3]

    def __init__(self, logger: Logger):
        self.logger = logger
        self._available = False
        self._reader_name: Optional[str] = None
        self._i2c_bus: Optional[int] = None
        self._i2c_addr: Optional[int] = None
        self._detect_reader()

    def _detect_reader(self):
        """Probe I2C buses for a connected NFC reader."""
        init_start = time.time()

        for bus in self._I2C_BUSES:
            for addr, name in self._NFC_I2C_ADDRESSES:
                if self._probe_i2c(bus, addr):
                    self._available = True
                    self._reader_name = name
                    self._i2c_bus = bus
                    self._i2c_addr = addr
                    elapsed = time.time() - init_start
                    self.logger.info(
                        f"NFC reader detected: {name} at I2C bus={bus} addr=0x{addr:02x} "
                        f"(took {elapsed:.3f}s)"
                    )
                    return

        elapsed = time.time() - init_start
        self.logger.info(f"No NFC reader detected on I2C buses {self._I2C_BUSES} (took {elapsed:.3f}s)")

    @staticmethod
    def _probe_i2c(bus: int, addr: int) -> bool:
        """Try to read a byte from an I2C address. Returns True if ACK received."""
        try:
            import smbus2
            with smbus2.SMBus(bus) as i2c:
                i2c.read_byte(addr)
                return True
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        """True if an NFC reader was detected at init."""
        return self._available

    def poll(self, request: NfcPollRequest, context: grpc.ServicerContext) -> NfcPollResponse:
        """Check if an NFC tag is present on the reader."""
        self.logger.info("NfcPoll request received")

        if not self._available:
            return NfcPollResponse(
                success=False,
                message="No NFC reader connected",
                tag_present=False,
            )

        timeout_ms = request.timeout_ms or 1000

        try:
            tag_present, uid = self._poll_tag(timeout_ms)
            return NfcPollResponse(
                success=True,
                message=f"Tag {'found' if tag_present else 'not found'}",
                tag_present=tag_present,
                uid=bytes(uid) if uid else b"",
            )
        except Exception as e:
            self.logger.error(f"NfcPoll error: {e}")
            return NfcPollResponse(
                success=False,
                message=f"NFC poll error: {e}",
                tag_present=False,
            )

    def read_ndef(self, request: NfcReadNdefRequest, context: grpc.ServicerContext) -> NfcReadNdefResponse:
        """Read NDEF records from an NFC tag."""
        self.logger.info("NfcReadNdef request received")

        if not self._available:
            return NfcReadNdefResponse(
                success=False,
                message="No NFC reader connected",
            )

        timeout_ms = request.timeout_ms or 1000

        try:
            records = self._read_ndef_records(timeout_ms)
            if records is None:
                return NfcReadNdefResponse(
                    success=False,
                    message="No NFC tag found or tag has no NDEF data",
                )

            proto_records = [
                NdefRecord(tnf=r["tnf"], type=r["type"], payload=r["payload"])
                for r in records
            ]
            return NfcReadNdefResponse(
                success=True,
                message=f"Read {len(proto_records)} NDEF record(s)",
                records=proto_records,
            )
        except Exception as e:
            self.logger.error(f"NfcReadNdef error: {e}")
            return NfcReadNdefResponse(
                success=False,
                message=f"NFC read error: {e}",
            )

    # ── Hardware-specific methods (PN532 I2C) ────────────────────────

    def _poll_tag(self, timeout_ms: int):
        """Poll for NFC tag presence. Returns (tag_present, uid_bytes)."""
        # TODO: Implement PN532 InListPassiveTarget command via I2C
        # For now, return not-found until hardware is wired and driver is tested
        self.logger.warning("NFC poll not yet implemented — hardware driver pending")
        return False, None

    def _read_ndef_records(self, timeout_ms: int):
        """Read NDEF records from a detected tag. Returns list of dicts or None."""
        # TODO: Implement NDEF read via PN532 I2C
        # 1. InListPassiveTarget to detect tag
        # 2. InDataExchange to read NDEF sectors
        # 3. Parse TLV to find NDEF message
        # 4. Parse NDEF records
        self.logger.warning("NFC NDEF read not yet implemented — hardware driver pending")
        return None
