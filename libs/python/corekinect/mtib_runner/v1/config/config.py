import json
from dataclasses import dataclass, asdict
from typing import List, Type


@dataclass
class MtibRunnerV1Features:
    def __init__(
        self,
        dut_power: bool = False,
        motion: bool = False,
        sensor_alt: bool = False,
        sensor_accel: bool = False,
        fw_flash: bool = False,
        joulescope: bool = False,
    ):
        self.dut_power: bool = dut_power
        self.motion: bool = motion
        self.sensor_accel: bool = sensor_accel
        self.sensor_alt: bool = sensor_alt
        self.fw_flash: bool = fw_flash
        self.joulescope: bool = joulescope

    def marshall(self) -> str:
        try:
            # Convert the dataclass to a dict and serialize it as JSON
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling configuration: {e}")

    @classmethod
    def unmarshall(cls: Type["MtibRunnerV1Features"], json_str: str) -> "MtibRunnerV1Features":
        try:
            # Load the JSON string into a dictionary
            data = json.loads(json_str)

            # Create an instance of the dataclass using the data
            return cls(**data)
        except KeyError as e:
            raise ValueError(f"Missing required runner configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid runner configuration value type: {e}")


@dataclass
class MtibRunnerV1Info:
    def __init__(
        self,
        platform: str = False,
        hw_version: str = False,
        features: MtibRunnerV1Features = None,
    ):
        self.platform: str = platform
        self.hw_version: str = hw_version
        self.features: MtibRunnerV1Features = features
