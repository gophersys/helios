import json
from dataclasses import asdict, dataclass
from typing import Any, Type


@dataclass
class TestConfig:
    def marshall(self) -> str:
        try:
            # Convert the dataclass to a dict and serialize it as JSON
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling configuration: {e}")

    @classmethod
    def unmarshall(cls: Type["TestConfig"], json_str: str) -> "TestConfig":
        try:
            # Load the JSON string into a dictionary
            data = json.loads(json_str)

            # Create an instance of the dataclass using the data
            return cls(**data)
        except KeyError as e:
            raise ValueError(f"Missing required test configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid test configuration value type: {e}")
