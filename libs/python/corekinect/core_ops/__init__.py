"""CoreOps client library for device personalization.

Provides authenticated access to CoreOps server endpoints:
- Device ID assignment (SNR → Device ID)
- Public key upload
- ICCID registration

Usage (direct - requires COREOPS_* env vars):
    from corekinect.core_ops import CoreOpsClient

    with CoreOpsClient() as client:
        device_id = client.assign_device_id("0964")
        client.upload_public_key(device_id, pub_key_base64)
        client.save_iccid(iccid, carrier, snr, imei)

Usage (via proxy - simpler, for validation tests):
    from corekinect.core_ops import CoreOpsProxyClient

    client = CoreOpsProxyClient()
    device_id = client.assign_device_id("09J5")
"""

from .client import CoreOpsClient, CoreOpsConfig
from .proxy_client import CoreOpsProxyClient

__all__ = ["CoreOpsClient", "CoreOpsConfig", "CoreOpsProxyClient"]
