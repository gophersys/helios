# Standard includes
from typing import Dict, List, Optional


class PostTestSharedData:
    def __init__(self):
        self.imei: Optional[str] = None
        self.iccids: Optional[List[str]] = None


# Singleton global object for shared data
post_test_shared_data: Dict[str, PostTestSharedData] = {}
