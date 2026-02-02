# Standard includes
from typing import Dict


class ElectricalTestSharedData:
    def __init__(self, step_count: int = 0):
        self.step_count: int = step_count


# Singleton global object for shared data
electrical_test_shared_data: Dict[str, ElectricalTestSharedData] = {}
