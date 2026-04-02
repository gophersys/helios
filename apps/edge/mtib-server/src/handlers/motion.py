# Standard library
import threading
import time
from typing import Optional

# Third party
import grpc

# Corekinect
from corekinect.utils import Logger

# Proto types
from src.shared.types import (
    Empty,
    GetMotionStatusResponse,
    MotionStartRequest,
    MotionStartResponse,
    MotionStatus,
    MotionHomeResponse,
    MotionStopResponse,
)

# Drivers
from src.drivers.fluidnc import FluidNC
from src.drivers.gpio import Pin


class MotionHandler:
    def __init__(self, logger: Logger, assets_dir: str, serial_port: str, reset_pin: Pin):
        self.logger = logger
        self.assets_dir = assets_dir
        self.serial_port = serial_port
        self.reset_pin = reset_pin

        # REV 1.2 motor power switch (set via set_gpio_expander)
        self._gpio_expander = None

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

    def set_gpio_expander(self, gpio_expander) -> None:
        """Set the TCA9534A GPIO expander for REV 1.2 motor power control.

        The motor power MOSFET (VMM_EN) is controlled by TCA9534A P2.
        It must be enabled before any FluidNC commands.
        """
        self._gpio_expander = gpio_expander
        self.logger.info("Motor power switch support enabled via TCA9534A")

    def _set_motor_power(self, enable: bool) -> Optional[str]:
        """Enable/disable motor power via TCA9534A.

        Returns error string on failure, None on success.
        """
        if self._gpio_expander is None:
            return None  # No GPIO expander configured
        try:
            self._gpio_expander.set_motor_power(enable)
            self.logger.info(f"Motor power {'enabled' if enable else 'disabled'}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to set motor power: {e}")
            return f"Failed to set motor power: {e}"

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

        # Enable motor power on REV 1.2
        if err := self._set_motor_power(True):
            yield MotionStartResponse(success=False, message=err)
            return

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

        # Enable motor power on REV 1.2
        if err := self._set_motor_power(True):
            return MotionHomeResponse(success=False, message=err)

        err = self.fluidnc.home()
        if err:
            return MotionHomeResponse(success=False, message=err)

        # Disable motor power on REV 1.2 (power saving)
        if err := self._set_motor_power(False):
            self.logger.warning(f"Failed to disable motor power after home: {err}")

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

        # Disable motor power on REV 1.2 (power saving)
        if err := self._set_motor_power(False):
            self.logger.warning(f"Failed to disable motor power after stop: {err}")

        return MotionStopResponse(success=True, message="Motion stopped successfully")
