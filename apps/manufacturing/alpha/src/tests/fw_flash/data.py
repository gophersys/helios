# Standard includes
from typing import Dict


class FwFlashTestSharedData:
    def __init__(self):
        pass


# Singleton global object for shared data
fw_flash_test_shared_data: Dict[str, FwFlashTestSharedData] = {}
