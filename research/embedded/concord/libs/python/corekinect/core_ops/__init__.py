"""CoreOps client library for device personalization.

Provides authenticated access to CoreOps server endpoints:
- Device ID assignment (SNR → Device ID)
- Public key upload
- ICCID registration

Usage:
    from corekinect.core_ops import CoreOpsClient

    with CoreOpsClient() as client:
        device_id = client.assign_device_id("0964")
        client.upload_public_key(device_id, pub_key_base64)
        client.save_iccid(iccid, carrier, snr, imei)
"""

from .client import CoreOpsClient, CoreOpsConfig

__all__ = ["CoreOpsClient", "CoreOpsConfig"]
