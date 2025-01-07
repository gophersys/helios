from dataclasses import dataclass
from typing import Dict, List, Optional

# Corekinect includes
from corekinect.utils.log import Logger
from corekinect.test import (
    TestConfig,
    ValidationTestConfig,
    CompatibleValidationTestConfig,
    TestStep,
    TestStepInfo,
    TestStepConfig,
    TestStepData,
    PassTestStep,
    FailTestStep,
    ErrorTestStep,
    ValidationTest,
)

from corekinect.mtib_runner.v1 import MtibRunnerV1Features
from corekinect.mtib_runner.v1.client import MtibRunnerV1Client, GpioConfig, AdcConfig, NetConfig


# ---------------------------------------------------------------------------------
#                                                              Test Step Definition
# -------------------------------------------------------------------------------*/
class SimpleTestStep(TestStep):
    # Step info
    info: TestStepInfo = TestStepInfo(
        name="Some test step",
        description="This is a long description of what this step would do",
        timeout_s=5,
    )

    # Compatible validation configuration
    compatible_config: CompatibleValidationTestConfig = CompatibleValidationTestConfig(
        platforms=["sigma5"],
        hw_versions=["B0", "C1"],
        fw_versions=["1.2.X"],
        hosts=[
            "nrf9160",
            "nrf52840",
        ],
        socket_server_versions=["0.9"],
        socket_server_messages=[],
    )

    # Runner dependencies
    runner_dependencies = MtibRunnerV1Features(
        motion=True,
        sensor_accel=False,
        sensor_alt=False,
        fw_flash=False,
    )

    @dataclass
    class Config(TestStepConfig):
        sleep_interval: int = 10

    class Data(TestStepData):
        some_var: int

    def handler(
        self,
        runner_client: MtibRunnerV1Client,
        test_config: ValidationTestConfig,
        step_config: Config,
    ):
        logger = Logger.get_test_case_logger()

        if test_config.platform == "B0":
            pass
        else:
            pass

        logger.info(f"Runner connected")
        logger.info(f"Global test case configuration {test_config.platform}")
        logger.info(f"Local test configuration: {step_config}")

        err = runner_client.motion_trigger(num_cycles=10, cycle_time_seconds=1)
        if err is not None:
            raise ErrorTestStep(message="Some simple error message", details="Some details")

        raise PassTestStep("Test passed succesfully")


class NotSoSimpleTestStep(TestStep):
    # Step info
    info: TestStepInfo = TestStepInfo(
        name="Some other test step",
        description="This is a long description of what this step would do if it wasnt simple",
        timeout_s=5,
    )

    # Compatible validation configuration
    compatible_config: CompatibleValidationTestConfig = CompatibleValidationTestConfig(
        platforms=["sigma5"],
        hw_versions=["B0", "C1"],
        fw_versions=["1.2.X"],
        hosts=[
            "nrf9160",
            "nrf52840",
        ],
        socket_server_versions=["0.9"],
        socket_server_messages=[],
    )

    @dataclass
    class Config(TestStepConfig):
        sleep_interval: int = 10

    class Data(TestStepData):
        some_var: int

    def handler(
        self,
        runner_client: MtibRunnerV1Client,
        test_config: ValidationTestConfig,
        step_config: Config,
    ):
        logger = Logger.get_test_case_logger()

        if test_config.platform == "B0":
            pass
        else:
            pass

        logger.info(f"Runner connected")
        logger.info(f"Global test case configuration {test_config.platform}")
        logger.info(f"Local test configuration: {step_config}")

        err = runner_client.motion_trigger(num_cycles=10, cycle_time_seconds=1)
        if err is not None:
            raise ErrorTestStep(message="Some simple error message", details="Some details")

        raise PassTestStep("Test passed succesfully")


# ---------------------------------------------------------------------------------
#                                                                              Main
# -------------------------------------------------------------------------------*/
if __name__ == "__main__":
    logger: Logger = Logger(
        config=Logger.Config(
            logger_name="main",
        ),
    )

    some_test_step: SimpleTestStep = SimpleTestStep()

    logger.warning(some_test_step.info.marshall())
    some_test_step_default_config = SimpleTestStep.Config()
    logger.warning(some_test_step_default_config.marshall())

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
        ),
        # Runner client configuration
        mtib_runner_client_config=MtibRunnerV1Client.Config(
            net=NetConfig(
                addr="127.0.0.1",
                port=50051,
            )
        ),
        # Test steps
        steps_info=[
            (
                SimpleTestStep(),
                SimpleTestStep.Config.unmarshall('{"sleep_interval": 15}'),
            )
        ],
    )

    err = test_case.run()
    if err is not None:
        logger.error(f"Could not run test, {err}")
