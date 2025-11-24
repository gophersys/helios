import sys
import threading
import time

import grpc
from corekinect.utils import Logger
from src.services.fluidnc import FluidNC
from src.shared.types import *

from .gpio import Pin


class MotionHandler:
    def __init__(self, logger: Logger, assets_dir: str, serial_port: str, reset_pin: Pin):
        self.logger = logger
        self.assets_dir = assets_dir
        self.serial_port = serial_port
        self.reset_pin = reset_pin

        # Instantiate the FluidNC object
        self.fluidnc = FluidNC(
            logger=self.logger,
            assets_dir=self.assets_dir,
            serial_port=self.serial_port,
            reset_pin=self.reset_pin,
        )

        # Initialize the FluidNC object
        err = self.fluidnc.init()
        if err:
            raise Exception(f"Failed to initialize FluidNC: {err}")

        # Initialize the internal state
        self.state: MotionStatus = MotionStatus.MOTION_STATUS_IDLE
        self.current_motion_data = None  # Store current motion progress data

    # -------------------------------------------------
    #                                            Motion
    # -------------------------------------------------
    def get_status(self, request: Empty, context: grpc.ServicerContext) -> GetMotionStatusResponse:
        """Get the current motion system status."""
        self.logger.info("GetMotionStatus request received")

        # First check internal state
        if self.state == MotionStatus.MOTION_STATUS_MOVING:
            # Return internal state with progress data
            if self.current_motion_data:
                return GetMotionStatusResponse(
                    success=True, message="Success", status=self.state, **self.current_motion_data
                )

        # If not moving, check actual status
        success, state = self.fluidnc.get_status()
        if not success:
            return GetMotionStatusResponse(success=False, message=state)

        # Map FluidNC state to protobuf MotionStatus
        self.logger.debug(f"FluidNC state: {state}")
        if state == "IDLE":
            motion_status = MotionStatus.MOTION_STATUS_IDLE
        elif state == "RUN":
            motion_status = MotionStatus.MOTION_STATUS_MOVING
        elif state in ["ALARM", "ERROR", "HOLD"]:
            motion_status = MotionStatus.MOTION_STATUS_ERRORED
        else:
            motion_status = MotionStatus.MOTION_STATUS_UNDEFINED

        # Update internal state
        self.state = motion_status

        return GetMotionStatusResponse(
            success=True,
            message="Success",
            status=motion_status,
        )

    def start(self, request: MotionStartRequest, context: grpc.ServicerContext):
        """Start motion with streaming progress updates."""
        self.logger.debug(f"MotionStart request received: {request}")

        # Set initial state
        self.state = MotionStatus.MOTION_STATUS_MOVING

        # Store progress updates in a queue
        progress_queue = []

        def progress_callback(progress_data):
            """Callback that stores progress data."""
            # Check if client is still connected before adding to queue
            if context.is_active():
                progress_queue.append(progress_data)

        try:
            # Call fluidnc.start with callback (this will run in a thread)
            def run_motion():
                err = self.fluidnc.start(
                    request.duration_seconds,
                    request.dwell_seconds,
                    request.speed_mm_s,
                    request.distance_mm,
                    request.accel_mm_s2,
                    progress_callback=progress_callback,
                )
                if context.is_active():
                    if err:
                        progress_queue.append({"error": err})
                    else:
                        progress_queue.append({"complete": True})

            # Start motion in background thread
            motion_thread = threading.Thread(target=run_motion)
            motion_thread.daemon = True
            motion_thread.start()

            # Yield initial response
            yield MotionStartResponse(
                success=True,
                message="Motion started",
                status=self.state,
            )

            # Stream progress updates
            while context.is_active():
                # Check if motion completed
                if progress_queue:
                    data = progress_queue.pop(0)
                    if "error" in data:
                        self.state = MotionStatus.MOTION_STATUS_ERRORED
                        self.current_motion_data = None
                        yield MotionStartResponse(success=False, message=data["error"])
                        break
                    elif "complete" in data:
                        self.state = MotionStatus.MOTION_STATUS_IDLE
                        self.current_motion_data = None
                        yield MotionStartResponse(success=True, message="Motion completed successfully")
                        break
                    else:
                        # Progress update
                        self.current_motion_data = data
                        yield MotionStartResponse(success=True, message="In progress", status=self.state, **data)

                # Small delay to avoid busy-waiting
                time.sleep(0.1)

            # Client disconnected
            if not context.is_active():
                self.logger.info("Client disconnected from motion stream")

        except Exception as e:
            self.state = MotionStatus.MOTION_STATUS_ERRORED
            self.current_motion_data = None
            self.logger.error(f"Error in motion start: {e}")
            yield MotionStartResponse(success=False, message=f"Unexpected error: {str(e)}")

    def home(self, request: Empty, context: grpc.ServicerContext) -> MotionHomeResponse:
        """Home all axes."""
        self.logger.info("MotionHome request received")
        err = self.fluidnc.home()
        if err:
            return MotionHomeResponse(success=False, message=err)

        return MotionHomeResponse(success=True, message="Success")

    def stop(self, request: Empty, context: grpc.ServicerContext) -> MotionStopResponse:
        """Emergency stop all motion."""
        self.logger.info("MotionStop request received")

        # Update internal state
        self.state = MotionStatus.MOTION_STATUS_IDLE
        self.current_motion_data = None

        # Call FluidNC stop method
        err = self.fluidnc.stop()
        if err:
            self.state = MotionStatus.MOTION_STATUS_ERRORED
            return MotionStopResponse(success=False, message=err)

        return MotionStopResponse(success=True, message="Motion stopped successfully")
