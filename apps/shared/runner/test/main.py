# # Standard includes
# import sys
# import json
# from typing import List

# # Corekinect includes
# from corekinect.utils.log import Logger
# from corekinect.utils.env import EnvConfig
# from corekinect.mtib_runner_client.v1.client import Module, ConfigField, Capture


# class RunnerEnvConfig(EnvConfig):
#     CONFIG_FILE_PATH: str


# def load_config_file(file_path: str) -> dict:
#     """
#     Reads and loads the JSON configuration file.
#     """
#     with open(file_path, "r") as f:
#         return json.load(f)


# def load_config_file(file_path: str) -> dict:
#     """
#     Reads and loads the JSON configuration file.
#     """
#     with open(file_path, "r") as f:
#         return json.load(f)


# if __name__ == "__main__":
#     logger: Logger = Logger(Logger.Config(logger_name="mtib_runner"))

#     # Load environment configuration
#     env_config: RunnerEnvConfig = RunnerEnvConfig()

#     # Read in config JSON file
#     try:
#         config_json = load_config_file(env_config.CONFIG_FILE_PATH)
#     except FileNotFoundError as e:
#         logger.error(f"Configuration file not found: {str(e)}")
#         sys.exit(1)
#     except json.JSONDecodeError as e:
#         logger.error(f"Failed to decode JSON from config file: {str(e)}")
#         sys.exit(1)

#     # Parse required modules
#     if "modules" in config_json:
#         required_modules = [Module.from_json(json.dumps(module)) for module in config_json["modules"]]
#         logger.info(f"Parsed {len(required_modules)} modules from the config file")
#     else:
#         logger.error("No 'modules' found in the config file")
#         sys.exit(1)

#     # Parse required captures
#     if "captures" in config_json:
#         required_captures = [Capture.from_json(json.dumps(capture)) for capture in config_json["captures"]]
#         logger.info(f"Parsed {len(required_captures)} captures from the config file")
#     else:
#         logger.error("No 'captures' found in the config file")
#         sys.exit(1)

#     # Convert back to JSON to check the serialization works
#     for module in required_modules:
#         logger.info(f"Module JSON: {module}")

#     for capture in required_captures:
#         logger.info(f"Capture JSON: {capture}")

#     logger.info("Configuration successfully loaded and parsed.")


# # Standard includes
# import sys

# # Corekinect includes
# from corekinect.utils.log import Logger
# from corekinect.manufacturing.sigma5.mtib_runner_client import Sigma5MtibRunnerClient, MtibRunnerV1Client

# ADDR = "127.0.0.1"
# PORT = 50051

# if __name__ == "__main__":
#     # Instantiate a logger
#     logger: Logger = Logger(
#         config=Logger.Config(
#             logger_name="sigma5_client",
#         )
#     )

#     # Instantiate a client
#     client = Sigma5MtibRunnerClient(
#         config=MtibRunnerV1Client.Config(
#             addr=ADDR,
#             port=PORT,
#         )
#     )

#     # Connect
#     error = client.connect()
#     if error is not None:
#         logger.error(f"Could not connect to Sigma5 runner at {ADDR}:{PORT}")
#         sys.exit(1)

#     logger.info(f"Sigma5 client succesfully connected to {ADDR}:{PORT}")


from dataclasses import dataclass
from typing import Dict

# Corekinect includes
from corekinect.utils.log import Logger
from corekinect.test.config import ValidationTestConfig, ManufacturingTestConfig, TestConfig
from corekinect.test.runtime import ValidationTest
from corekinect.test.step import TestStep
from corekinect.mtib_runner.modules import StmGpio
from corekinect.mtib_runner.types import CaptureInfo, CaptureType
from corekinect.mtib_runner.v1.client import MtibRunnerV1Client


# Child class
class SomeTestStep(TestStep):
    @dataclass  # Run time must not only check for the existence of the config class but also that its a @dataclass
    class Config(TestConfig):
        sleep_interval: int = 10

    def handler(
        self,
        runner: MtibRunnerV1Client,
        test_config: ValidationTestConfig,
        step_config: Config,
    ):
        logger = Logger.get_test_case_logger()

        logger.info(f"Runner connected at {runner.config.addr}:{runner.config.port}")
        logger.info(f"Global test case configuration {test_config.captures}")
        logger.info(f"Local test configuration: {step_config}")


if __name__ == "__main__":
    logger: Logger = Logger(
        config=Logger.Config(
            logger_name="validation",
        ),
    )

    some_test_step: SomeTestStep = SomeTestStep()

    gpio_module = StmGpio()

    # This is the client, it will talk to the runner
    test_case: ValidationTest = ValidationTest(
        # Global test configuration
        config=ValidationTestConfig(
            platform="sigma5",
            hw_version="B0",
            fw_version="1.2.3",
            hosts=[
                "nrf9160",
                "nrf52840",
            ],
            socket_server_version="0.9",
            socket_server_messages=[
                "0x10",
                "0x30",
                "0x4B",
            ],
            captures_info=CaptureInfo(
                id="joulescope",
                version=1,
                name="Current measurement",
                type=CaptureType.CAPTURE_JOULESCOPE,
                config_fields=[],
            ),
        ),
        # Test runner configuration
        mtib_runner_client_config=MtibRunnerV1Client.NetConfig(
            addr="127.0.0.1",
            port=50051,
        ),
        steps_info=[
            (
                SomeTestStep(),
                SomeTestStep.Config.unmarshall('{"sleep_interval": 15}'),
            )
        ],
    )

    test_case.run()
