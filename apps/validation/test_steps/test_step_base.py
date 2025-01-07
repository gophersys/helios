import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime

from packaging.version import InvalidVersion, Version
from protos.cluster_test.cluster_test_pb2 import TestStepResult


@dataclass
class TestStepConfig:
    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @classmethod
    def unmarshall(cls, json_str: str):
        try:
            data = json.loads(json_str)
            return TestStepConfig(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


@dataclass
class GlobalTestConfig(TestStepConfig):
    """
    Data class to hold the configuration for a test step.
    This may end up being a huge class with many fields, but until we find a
    better way to share test configs between the test steps, this will have to do.
    """

    dut_id: int = None  # Device under test ID (i.e. 0x70B3D584C0200316)
    ss_api_version: str = None  # Socket server API version (e.g. 0.9, 1.0)
    platform: str = None  # Platform name (e.g. sigma3, sigma5, sigma7)
    board_revision: str = None  # Board revision (e.g. A3, B0, B1, C0)
    firmware_version: str = None  # Firmware version (e.g. 1.2.331)

    func__name: DisableGpsAiding.Config


# @dataclass
# class TestStepResult:
#     error: str = ""
#     success: bool = False
#     reason: str = ""
#     details: str = ""
#     node: str = ""
#     timeout: bool = False
#     # sequence: int = 0
#     startTime: str = ""
#     endTime: str = ""
#     noPassIsFatal: bool = False


class TestStep(ABC):
    name: str | None = None
    description: str | None = None
    noPassIsFatal: bool | None = None
    timeout: int | None = None
    supported_platforms: list[str] | None = None
    supported_board_revisions: list[str] | None = None
    supported_firmware_versions: list[str] | None = None
    supported_socket_server_versions: list[str] | None = None
    global_config: GlobalTestConfig

    @abstractmethod
    def _run_step(self) -> None:
        """
        Abstract method that must båe implemented by subclasses to define the logic of the test step.
        """
        raise NotImplementedError("Subclasses must implement the _run_step method!")

    def _validate_required_fields(self) -> None:
        required_fields = {
            "Name": self.name,
            "Description": self.description,
            "No pass is fatal": self.noPassIsFatal,
            "Timeout": self.timeout,
            "Supported platforms": self.supported_platforms,
            "Supported board revisions": self.supported_board_revisions,
            "Supported firmware versions": self.supported_firmware_versions,
            "Supported socket server versions": self.supported_socket_server_versions,
            "Node": self.node,
            "Test Config": self.config,
            "DUT ID": self.config.dut_id,
            "Socket server API version": self.config.ss_api_version,
            "Platform": self.config.platform,
            "Board revision": self.config.board_revision,
            "Firmware version": self.config.firmware_version,
        }
        for field_name, field_value in required_fields.items():
            if field_value is None:
                raise FailTest(
                    message=f"{field_name} not specified.",
                    function_name="TestStep._validate_required_fields",
                    details=f"The {field_name} parameter must be provided.",
                )

    def _validate_supported_configurations(self) -> None:
        if self.config.platform not in self.supported_platforms:
            raise FailTest(
                message="Platform not supported.",
                function_name="TestStep._validate_supported_configurations",
                details=f"The platform {self.config.platform} is not supported by this test step.",
            )
        if self.config.board_revision not in self.supported_board_revisions:
            raise FailTest(
                message="Board revision not supported.",
                function_name="TestStep._validate_supported_configurations",
                details=f"The board revision {self.config.board_revision} is not supported by this test step.",
            )

        if not is_version_supported(self.config.firmware_version, self.supported_firmware_versions):
            raise FailTest(
                message="Firmware version not supported.",
                function_name="TestStep._validate_supported_configurations",
                details=f"The firmware version {self.config.firmware_version} is not supported by this test step.",
            )

        if not is_version_supported(self.config.ss_api_version, self.supported_socket_server_versions):
            raise FailTest(
                message="Socket server API version not supported.",
                function_name="TestStep._validate_supported_configurations",
                details=f"The socket server API version {self.config.ss_api_version} is not supported by this test step.",
            )

    def _validate(self) -> None:
        """
        Validate the test step configuration before running the test step logic.
        """
        self._validate_required_fields()
        self._validate_supported_configurations()

    def _pre_test_step(self):
        # Placeholder if we need to add any logic before the test step
        pass

    def _post_test_step(self):
        # Placeholder if we need to add any logic after the test step
        pass

    def __call__(self, config: TestStepConfig, node: str, usr_data: None) -> TestStepResult:
        """
        Run this class like a function test step handler with the given configuration and user data.
        This is a template method that calls the abstract _run_step method implemented by subclasses.
        This is done so the result handling can be removed from the test step implementations, removing boilerplate.

        Example:
        test_step = EnableGpsAiding()
        result = test_step(config, node, usr_data)
        """
        try:
            self.config = config
            self.node = node
            self.usr_data = usr_data
            self.start_time = datetime.utcnow()

            # Validate the test step configuration
            self._validate()

            # Run any pre-test step logic
            self._pre_test_step()

            # Run the test step logic
            self._run_step()

        except FailTest as e:
            self.log.error(e)
            return TestStepResult(
                error=e.message,
                success=False,
                reason=f"Failed in step {self.name}.",
                details=f"function: {e.function_name}, details: {e.details}",
                node=self.node,
                timeout=self.timeout,
                startTime=self.start_time,
                endTime=datetime.utcnow(),
                noPassIsFatal=self.noPassIsFatal,
            )
        else:
            # The test step passed
            return TestStepResult(
                error="",
                success=True,
                reason="",
                details="",
                node=self.node,
                timeout=self.timeout,
                startTime=self.start_time,
                endTime=datetime.utcnow(),
                noPassIsFatal=self.noPassIsFatal,
            )
        finally:
            # Run any post-test step logic
            self._post_test_step()


def is_version_supported(full_version: str, supported_versions: list[str] | str) -> bool:
    """
    Check if a given full version is supported based on a list of supported versions or a single version string.

    Args:
        full_version (str): The full version to check (e.g., '1.2.331').
        supported_versions (list[str] or str): A list of supported versions or a single version (e.g., '1.x', ['1.x', '1.2']).

    Returns:
        bool: True if the version is supported, False otherwise.
    """
    try:
        # Parse the full version string
        parsed_full_version = Version(full_version)
        # print(f"Parsed full version: {parsed_full_version}")
    except InvalidVersion:
        raise ValueError(f"Invalid full version: {full_version}")

    # If supported_versions is a string, convert it to a list for uniform processing
    if isinstance(supported_versions, str):
        supported_versions = [supported_versions]

    # print(f"Supported versions: {supported_versions}")

    # Iterate over the supported versions and check if the full version matches
    for supported in supported_versions:
        # print(f"Checking supported version: {supported}")
        try:
            # Handle cases like '1.x' or '2.x'
            if supported.endswith(".x"):
                # Extract the major version for comparison
                major_version = int(supported.split(".")[0])
                # print(f"Major version to compare: {major_version}")
                if parsed_full_version.major == major_version:
                    # print(f"Matched major version: {parsed_full_version.major} == {major_version}")
                    return True
            else:
                # Parse the supported version as a partial or full version
                parsed_supported_version = Version(supported)
                # print(f"Parsed supported version: {parsed_supported_version}")

                # Match based on the specificity of the supported version
                if parsed_full_version.major == parsed_supported_version.major:
                    if (
                        parsed_supported_version.minor is not None
                        and parsed_full_version.minor != parsed_supported_version.minor
                    ):
                        # print(
                        #     f"Minor version mismatch: {parsed_full_version.minor} != {parsed_supported_version.minor}"
                        # )
                        continue

                    # Don't enforce patch version if the supported version doesn't specify it
                    if parsed_supported_version.micro is not None and parsed_supported_version.micro != 0:
                        if parsed_full_version.micro != parsed_supported_version.micro:
                            # print(
                            #     f"Patch version mismatch: {parsed_full_version.micro} != {parsed_supported_version.micro}"
                            # )
                            continue

                    # print("Version matched.")
                    return True
        except InvalidVersion:
            raise ValueError(f"Invalid supported version: {supported}")

    # If no match found, return False
    # print(f"No match found for version: {full_version}")
    return False
