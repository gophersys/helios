from dataclasses import dataclass

from corekinect.test.config import TestConfig


@dataclass
class CompatibleManufacturingTestConfig(TestConfig):
    some_field: int = 0


@dataclass
class ManufacturingTestConfig(TestConfig):
    some_field: int = 0
