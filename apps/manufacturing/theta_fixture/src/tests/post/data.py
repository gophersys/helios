# Standard includes
from typing import Dict, List, Optional

# Corekinect libraries
from corekinect.mtib_client.v1.client.core import MtibV1Client


class PostTestSharedData:
    def __init__(self):
        self.client: Optional[MtibV1Client] = None
        self.imei: Optional[str] = None
        self.iccids: Optional[List[str]] = None


# Singleton global object for shared data
post_test_shared_data: Dict[str, PostTestSharedData] = {}
