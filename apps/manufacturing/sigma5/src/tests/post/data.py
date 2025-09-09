# Standard includes
from dataclasses import dataclass
from typing import Dict, List


@dataclass
class PostTestSharedData:
    snr: str = None
    device_id: str = None
    public_key: str = None
    imei: str = None
    iccids: List[str] = None
    ble_mac: str = None


# Singleton global object for shared data
post_test_shared_data: Dict[str, PostTestSharedData] = {}
