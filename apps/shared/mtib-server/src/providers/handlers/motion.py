import grpc
from corekinect.utils import Logger
from src.shared.types import *

class MotionHandler:
    def __init__(self, logger: Logger):
        self.logger = logger

    def get_status(self, request: GetMotionStatusRequest, context: grpc.ServicerContext) -> GetMotionStatusResponse:
        """Get the current motion system status."""
        self.logger.info("GetMotionStatus request received")
        return GetMotionStatusResponse(
            success=False,
            message="Not implemented",
            status=MotionStatus.MOTION_STATUS_UNDEFINED
        )

    def home(self, request: Empty, context: grpc.ServicerContext) -> MotionHomeResponse:
        """Home all axes."""
        self.logger.info("MotionHome request received")
        return MotionHomeResponse(success=False, message="Not implemented")

    def stop(self, request: Empty, context: grpc.ServicerContext) -> MotionStopResponse:
        """Emergency stop all motion."""
        self.logger.info("MotionStop request received")
        return MotionStopResponse(success=False, message="Not implemented")

    def send_gcode(self, request: GcodeRequest, context: grpc.ServicerContext) -> GcodeResponse:
        """Send a G-code command."""
        self.logger.info(f"SendGcode request received: {request.command}")
        return GcodeResponse(success=False, message="Not implemented", response="") 