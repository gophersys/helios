import sys

import grpc
from corekinect.utils import Logger
from src.types.protocols import *


class MotionHandler:
    def __init__(self, logger: Logger):
        self.logger = logger

    # -------------------------------------------------
    #                                    FluicNC Config
    # -------------------------------------------------
    def get_config(self, request: Empty, context: grpc.ServicerContext) -> FluidNcConfigResponse:
        """Get the current FluidNC configuration."""
        self.logger.info("GetFluidNcConfig request received")
        return FluidNcConfigResponse(
            success=False,
            message="Not implemented",
            config_yaml="",
        )

    def update_config(
        self, request: UpdateFluidNcConfigRequest, context: grpc.ServicerContext
    ) -> UpdateFluidNcConfigResponse:
        """Update the FluidNC configuration."""
        self.logger.info("UpdateFluidNcConfig request received")
        return UpdateFluidNcConfigResponse(success=False, message="Not implemented")

    # -------------------------------------------------
    #                                             Gcode
    # -------------------------------------------------
    def send_gcode(self, request: GcodeRequest, context: grpc.ServicerContext) -> GcodeResponse:
        """Send a G-code command."""
        self.logger.info(f"SendGcode request received: {request.command}")
        return GcodeResponse(success=False, message="Not implemented", response="")

    # -------------------------------------------------
    #                                   Motion Profiles
    # -------------------------------------------------
    def upload_profile(self, request: MotionProfileRequest, context: grpc.ServicerContext) -> MotionProfileResponse:
        """Upload a motion profile."""
        self.logger.info("UploadMotionProfile request received")
        return MotionProfileResponse(success=False, message="Not implemented")

    def list_profiles(self, request: Empty, context: grpc.ServicerContext) -> ListMotionProfilesResponse:
        """List all motion profiles."""
        self.logger.info("ListMotionProfiles request received")
        return ListMotionProfilesResponse(success=False, message="Not implemented")

    def execute_profile(self, request: ExecuteProfileRequest, context: grpc.ServicerContext) -> ExecuteProfileResponse:
        """Execute a motion profile."""
        self.logger.info("ExecuteMotionProfile request received")
        return ExecuteProfileResponse(success=False, message="Not implemented")

    def delete_profile(self, request: DeleteProfileRequest, context: grpc.ServicerContext) -> DeleteProfileResponse:
        """Delete a motion profile."""
        self.logger.info("DeleteMotionProfile request received")
        return DeleteProfileResponse(success=False, message="Not implemented")

    def set_default_profile(
        self, request: SetDefaultProfileRequest, context: grpc.ServicerContext
    ) -> SetDefaultProfileResponse:
        """Set the default motion profile."""
        self.logger.info("SetDefaultMotionProfile request received")
        return SetDefaultProfileResponse(success=False, message="Not implemented")

    # -------------------------------------------------
    #                                            Motion
    # -------------------------------------------------
    def get_status(self, request: Empty, context: grpc.ServicerContext) -> GetMotionStatusResponse:
        """Get the current motion system status."""
        self.logger.info("GetMotionStatus request received")
        return GetMotionStatusResponse(
            success=False,
            message="Not implemented",
            status=MotionStatus.MOTION_STATUS_UNDEFINED,
            position=MotionPosition.MOTION_POSITION_UNDEFINED,
        )

    def start(self, request: Empty, context: grpc.ServicerContext) -> MotionStartResponse:
        """Start the motion system."""
        self.logger.info("MotionStart request received")
        return MotionStartResponse(success=False, message="Not implemented")

    def home(self, request: Empty, context: grpc.ServicerContext) -> MotionHomeResponse:
        """Home all axes."""
        self.logger.info("MotionHome request received")
        return MotionHomeResponse(success=False, message="Not implemented")

    def stop(self, request: Empty, context: grpc.ServicerContext) -> MotionStopResponse:
        """Emergency stop all motion."""
        self.logger.info("MotionStop request received")
        return MotionStopResponse(success=False, message="Not implemented")
