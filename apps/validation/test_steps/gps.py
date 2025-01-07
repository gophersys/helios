from typing import Any, Dict, List

from corekinect.socket_server import get_jumptrack_gps_config, send_jumptrack_gps_config
from corekinect.socket_server.data_types import JumpTrackGpsConfig
from corekinect.test.config import ValidationTestConfig
from corekinect.test.dependencies import TestDependency
from corekinect.test.exceptions import FailTest
from corekinect.test.step import TestStep, TestStepConfig, TestStepInfo
from corekinect.utils.log import get_test_case_logger
from corekinect.validation.motion import move_dut


class EnableGpsAiding(TestStep):

    info = TestStepInfo(
        name="Enable GPS Aiding",
        description="""
1. Get the current GPS aiding configuration.
2. Check if GPS aiding is already enabled.
3. If GPS aiding is not enabled, enable GPS aiding.
4. Trigger motion on the DUT to apply the configuration.
5. Verify the GPS aiding configuration.
""",
        no_pass_is_fatal=True,
        timeout_s=300,
        dependencies=[],
        supported_platforms=["sigma3", "sigma5", "sigma7"],
        supported_hosts=[],
        supported_hw_versions=["A3", "B0", "B1", "C0"],
        supported_fw_versions=["1.x", "2.x"],
        supported_socket_server_versions=["0.9", "1.x"],
        supported_socket_server_messages=[],
    )

    class Config(TestStepConfig):
        number: int = None

    def handler(
        self,
        g_config: ValidationTestConfig,
        config: Config,
        node: str,
        update_callback: Any,
        dependencies: Dict[str, TestDependency],
        shared_data: Any,
    ):
        log = get_test_case_logger()
        log.info("Enabling GPS aiding on the DUT.")

        # Get the current GPS aiding configuration
        gps_config: JumpTrackGpsConfig = get_jumptrack_gps_config(self.config)

        # Check if GPS aiding is already enabled
        if gps_config.aiding_enabled:
            self.log.warning("GPS aiding is already enabled.")
            return None

        # Apply the GPS aiding configuration
        gps_config.aiding_enabled = True
        send_jumptrack_gps_config(test_config=self.config, gps_config=gps_config)

        # Trigger motion on the DUT to apply the configuration
        move_dut(num_cycles=1, do_wait_for_motion=True, do_wait_for_stop=True)

        # Verify the GPS aiding configuration
        log.debug("Verifying GPS aiding configuration.")
        gps_config = get_jumptrack_gps_config(self.config)
        if not gps_config.aiding_enabled:
            raise FailTest(
                message="Failed to enable GPS aiding.",
                function_name="EnableGpsAiding._run_step",
                details="GPS aiding is not enabled.",
            )

        # Fall through to Pass
        log.info("GPS aiding enabled successfully.")
        return None


class DisableGpsAiding(TestStep):
    name = "Disable GPS Aiding"
    description = """
1. Get the current GPS aiding configuration.
2. Check if GPS aiding is already disabled.
3. If GPS aiding is not disabled, disable GPS aiding.
3. Trigger motion on the DUT to apply the configuration.
4. Verify the GPS aiding configuration.
"""
    noPassIsFatal = True
    timeout = 300  # 5 minutes
    supported_platforms = ["sigma3", "sigma5", "sigma7"]
    supported_board_revisions = ["A3", "B0", "B1", "C0"]
    supported_firmware_versions = ["1.1", "1.2", "2.0"]
    supported_socket_server_versions = ["0.9", "1.0"]

    log = setup_logger(name=f"test: {name}")

    def _run_step(self) -> None:
        self.log.info("Disabling GPS aiding on the DUT.")

        # Get the current GPS aiding configuration
        gps_config = get_jumptrack_gps_config(self.config)

        # Check if GPS aiding is already disabled
        if not gps_config.aiding_enabled:
            self.log.warning("GPS aiding is already disabled.")
            return None

        # Apply the GPS aiding configuration
        gps_config.aiding_enabled = False
        send_jumptrack_gps_config(test_config=self.config, gps_config=gps_config)

        # Trigger motion on the DUT to apply the configuration
        move_dut(num_cycles=1, do_wait_for_motion=True, do_wait_for_stop=True)

        # Verify the GPS aiding configuration
        self.log.debug("Verifying GPS aiding configuration.")
        gps_config = get_jumptrack_gps_config(self.config)
        if gps_config.aiding_enabled:
            raise FailTest(
                message="Failed to disable GPS aiding.",
                function_name="DisableGpsAiding._run_step",
                details="GPS aiding is still enabled.",
            )

        self.log.info("GPS aiding disabled successfully.")
        return None
