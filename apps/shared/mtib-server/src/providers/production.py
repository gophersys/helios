# Standard imports
import logging
from typing import Optional, List
from dataclasses import dataclass

# Protocol imports
from protocols.mtib.mtib_pb2_grpc import MtibV1Servicer

# 3rd party imports
import grpc

# Corekinect imports
from corekinect.utils import Logger

# Private imports
from src.lib.gpio import Pin

# from lib.stepper.core import StepperMotor, FluidNC

# Protocol imports
from .types import *

# ----------------------------------------------------------------------------------
#                                                                              Entry
# --------------------------------------------------------------------------------*/


class MtibV1ServicerProvider(MtibV1Servicer):
    def __init__(
        self,
        config: MtibV1ServicerProviderConfig,
        logger: Logger = None,
    ):
        # Setup the logger for the server
        self.logger: Logger = logger
        if self.logger is None:
            self.logger = Logger(
                logger_name="mtib-server",
                log_directory="logs",
                overall_log_level=logging.DEBUG,
                console_log_level=logging.DEBUG,
                file_log_level=logging.DEBUG,
                enable_log_color=True,
            )

        # Setup the config
        self.config: MtibV1ServicerProviderConfig = config

        # Create a list to keep track of components
        self._components: List[Component] = []

        # # Servicer components
        # self._stepper_motor_a: StepperMotor = StepperMotor(
        #     fluidnc=FluidNC(
        #         serial_port=self.config.FLUIDNC_SERIAL_PORT,
        #         reset_pin=self.config.FLUIDNC_RESET_PIN,
        #         logger=self.logger,
        #         assets_dir=self.config.ASSETS_DIR + "/fluidNc",
        #     )
        # )

        # self._stepper_motor_b: StepperMotor = StepperMotor(
        #     fluidnc=FluidNC(
        #         serial_port=self.config.FLUIDNC_SERIAL_PORT,
        #         reset_pin=self.config.FLUIDNC_RESET_PIN,
        #         logger=self.logger,
        #         assets_dir=self.config.ASSETS_DIR + "/fluidNc",
        #     )
        # )

        self.logger.info("MtibServicerProvider initialized OK")

    def init(self) -> Optional[str]:
        """
        Initialize the servicer components.
        """
        # Initialize servicer objects
        if err := self._stepper_motor_a.init():
            return f"Failed to initialize stepper motor: {err}"

        if err := self._stepper_motor_b.init():
            return f"Failed to initialize stepper motor: {err}"

        self.logger.debug("Stepper motors initialized OK")

        return None

    # def GetServerInfo(self, request: Empty, context: grpc.ServicerContext):
    #     self.logger.info("GetServerInfo request received")
    #     return GetServerInfoResponse(
    #         server_info=GetServerInfoResponse.ServerInfo(
    #             name="mtib-server",
    #             version="0.0.2",
    #         )
    #     )

    # def GpioConfig(self, request: GpioConfigRequest, context: grpc.ServicerContext):
    #     self.logger.info(f"GpioConfig request received for GPIO {request.gpio}")
    #     # TODO: Implement GPIO configuration
    #     return Response(error="")

    # def GpioWrite(self, request: GpioWriteRequest, context: grpc.ServicerContext):
    #     self.logger.info(f"GpioWrite request received for GPIO {request.gpio}, state: {request.state}")
    #     # TODO: Implement GPIO write
    #     return Response(error="")

    # def GpioRead(self, request: GpioReadRequest, context: grpc.ServicerContext):
    #     self.logger.info(f"GpioRead request received for GPIO {request.gpio}")
    #     # TODO: Implement GPIO read
    #     return GpioReadResponse(error="", state=False)

    # -------------------------------------------------------------------------------
    #                                                                          Motion
    # -------------------------------------------------------------------------------
    # def GetMotionStatus(self, request: Empty, context: grpc.ServicerContext) -> GetMotionStatusResponse:
    #     self.logger.info("GetMotionStatus request received")
    #     return GetMotionStatusResponse(
    #         success=False, message="Not implemented", status=MotionStatus.MOTION_STATUS_UNDEFINED
    #     )

    # def MotionHome(self, request: Empty, context: grpc.ServicerContext) -> MotionHomeResponse:
    #     self.logger.info("MotionHome request received")
    #     return MotionHomeResponse(success=False, message="Not implemented")

    # def SendGcode(self, request: GcodeRequest, context: grpc.ServicerContext) -> GcodeResponse:
    #     self.logger.info(f"SendGcode request received: {request.command}")
    #     return GcodeResponse(success=False, message="Not implemented", response="")

    # def UploadMotionProfile(
    #     self, request: MotionProfileRequest, context: grpc.ServicerContext
    # ) -> MotionProfileResponse:
    #     self.logger.info(f"UploadMotionProfile request received: {request.profile.name}")
    #     return MotionProfileResponse(success=False, message="Not implemented")

    # def ListMotionProfiles(self, request: Empty, context: grpc.ServicerContext) -> ListMotionProfilesResponse:
    #     self.logger.info("ListMotionProfiles request received")
    #     return ListMotionProfilesResponse(profiles=[])

    # def ExecuteMotionProfile(
    #     self, request: ExecuteProfileRequest, context: grpc.ServicerContext
    # ) -> ExecuteProfileResponse:
    #     self.logger.info(f"ExecuteMotionProfile request received: {request.profile_name}")
    #     return ExecuteProfileResponse(success=False, message="Not implemented")

    # def GetFluidConfig(self, request: Empty, context: grpc.ServicerContext) -> FluidConfigResponse:
    #     self.logger.info("GetFluidConfig request received")
    #     return FluidConfigResponse(success=False, message="Not implemented", yaml_content="")

    # def UpdateFluidConfig(
    #     self, request: UpdateFluidConfigRequest, context: grpc.ServicerContext
    # ) -> UpdateFluidConfigResponse:
    #     self.logger.info("UpdateFluidConfig request received")
    #     return UpdateFluidConfigResponse(success=False, message="Not implemented")

    # def MotionStop(self, request: Empty, context: grpc.ServicerContext) -> MotionStopResponse:
    #     self.logger.info("MotionStop request received")
    #     return MotionStopResponse(success=False, message="Not implemented")
