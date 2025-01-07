# Standard includes
import logging
from typing import List, Any, Dict


# class ValidationTestConfig(ABC):
#     platform=
#     hosts=
#     fw_version
#     hw_verion


class SimpleTestStep(TestStep):

    # Step information
    info = TestStepInfo(
        name="Simple Test",
        description="Prints hello world to the terminal",
        no_pass_is_fatal=True,
        timeout_s=10,
        dependencies=["9160_uart", "52840_uart"],
        supported_platforms=["sigma3", "sigma5", "sigma7"],
    )

    class Config(TestStepConfig):
        number: int = None

    def handler(
        self,
        g_config: ManufacturingTestConfig,
        config: Config,
        node: str,
        update_callback: Any,
        dependencies: Dict[str, TestDependency],
        shared_data: Any,
    ):
        # runner_config: RunnerDependency.Config = RunnerDependency.Config(host="hostname")
        # runner: RunnerDependency = RunnerDependency(config=runner_config)

        runner: RunnerDependency = dependencies["runner"]

        runner.open()

        pass
        # Grab any needed dependencies
        # 9160_uart = dependencies.9160_uart:9160Uart

    #     pass

    # Gloabl config


if __name__ == "__main__":

    config = ManufacturingTestConfig(some_field=42)

    json_str = config.marshall()

    print("Serialized JSON:", json_str)

    # Unmarshall back to a ManufacturingTestConfig object
    new_config = ManufacturingTestConfig.unmarshall(json_str)
    print("Unmarshalled object:", new_config)

    # new_simple_step: SimpleTestStep = SimpleTestStep()

    # new_simple_step.run()
