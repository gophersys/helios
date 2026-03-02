"""C8: NFC tag verification test.

Verifies that the NFC tag on the device contains the correct device ID.
Uses the MTIB's I2C NFC reader to scan the tag.

Tests:
    - NFC tag readable and contains device ID
"""

import os
import logging

import pytest

log = logging.getLogger(__name__)


class TestNfc:
    """NFC tag verification."""

    @pytest.mark.skip(reason="NFC I2C reader not yet wired (Stream B: B6)")
    def test_nfc_device_id(self, ctx, firmware_build):
        """NFC tag read returns correct device ID."""
        # NFC reader is on I2C bus 1 (per fixture profile)
        # TODO: Implement when NFC reader is wired and MTIB NFC RPC is available
        expected_device_id = os.environ["DEVICE_ID"]
        # tag_data = ctx.mtib.nfc_read(bus=1)
        # assert expected_device_id in tag_data.decode(), (
        #     f"Device ID {expected_device_id} not found in NFC tag"
        # )
        pytest.skip("NFC reader RPC not yet implemented")
