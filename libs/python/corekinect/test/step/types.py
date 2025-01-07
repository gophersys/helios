from dataclasses import asdict, dataclass
from typing import Type
import json


@dataclass
class TestStepInfo:
    name: str
    description: str
    timeout_s: int

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling test step info: {e}")

    @classmethod
    def unmarshall(cls: Type["TestStepInfo"], json_str: str) -> "TestStepInfo":
        try:
            data = json.loads(json_str)
            return cls(**data)  # Use cls to create an instance of the correct class
        except KeyError as e:
            raise ValueError(f"Missing required test step info value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid test step info value type: {e}")


@dataclass
class TestStepConfig:
    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling configuration: {e}")

    @classmethod
    def unmarshall(cls: Type["TestStepConfig"], json_str: str) -> "TestStepConfig":
        try:
            data = json.loads(json_str)
            return cls(**data)  # Use cls to create an instance of the correct class
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


@dataclass
class TestStepData:
    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @classmethod
    def unmarshall(cls: Type["TestStepData"], json_str: str):
        try:
            data = json.loads(json_str)
            return TestStepConfig(**data)
        except KeyError as e:
            raise ValueError(f"Missing required data value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid data value type: {e}")
