"""C8: NFC tag verification tests.

Verifies that the NFC tag on the device contains the correct device ID.
Uses the MTIB's I2C NFC reader to scan the tag via NfcPoll/NfcReadNdef RPCs.

PRD Requirements:
    - Device NFC tag must contain the assigned device ID
    - Tag must be readable by external NFC reader

Tests:
    - NFC tag detected (NfcPoll returns tag_present=True)
    - NFC NDEF text record contains correct device ID
"""

import os
import logging

import pytest

from corekinect.test.validation import Capability, requires_capability

log = logging.getLogger(__name__)


@pytest.mark.nfc
class TestNfc:
    """NFC tag verification."""

    @requires_capability(Capability.NFC_READER)
    def test_nfc_tag_detected(self, ctx, firmware_build):
        """PRDTST-337: NFC tag is detected by the reader."""
        tag_present, uid, err = ctx.mtib.NfcPoll(timeout_ms=3000)
        assert err is None, f"NfcPoll RPC failed: {err}"
        assert tag_present, "No NFC tag detected — check tag proximity to reader"
        assert len(uid) >= 4, f"Tag UID too short ({len(uid)} bytes)"
        log.info("NFC tag detected: UID=%s", uid.hex())

    @requires_capability(Capability.NFC_READER)
    def test_nfc_device_id(self, ctx, firmware_build):
        """PRDTST-337: NFC NDEF text record contains correct device ID."""
        expected_device_id = os.environ["DEVICE_ID"]

        records, err = ctx.mtib.NfcReadNdef(timeout_ms=3000)
        assert err is None, f"NfcReadNdef RPC failed: {err}"
        assert records, "No NDEF records found on tag"

        # Extract text records (TNF=0x01, type=b"T")
        texts = []
        for rec in records:
            if rec.tnf == 1 and rec.type == b"T":
                # NDEF Text: [status_byte][lang_code...][text...]
                status = rec.payload[0]
                lang_len = status & 0x3F
                text = rec.payload[1 + lang_len:].decode("utf-8", errors="replace")
                texts.append(text)

        log.info("NFC NDEF texts: %s", texts)
        found = any(expected_device_id in t for t in texts)
        assert found, (
            f"Device ID {expected_device_id} not found in NFC NDEF text records: {texts}"
        )
