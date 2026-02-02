# Standard includes
from typing import Dict, Optional

# Corekinect libraries
from corekinect.mtib_client.v1.client.core import MtibV1Client


class FwFlashTestSharedData:
    def __init__(self):
        self.client: Optional[MtibV1Client] = None


# Singleton global object for shared data
fw_flash_test_shared_data: Dict[str, FwFlashTestSharedData] = {}
