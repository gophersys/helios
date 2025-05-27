from .config import ProviderConfig
from .helpers import grpc_method

# Standard imports
import logging
import time
from typing import Optional, List, Dict
from dataclasses import dataclass

# Protocol imports
from protocols.mtib.mtib_pb2_grpc import MtibV1Servicer

# 3rd party imports
import grpc
import gpiod

# Corekinect imports
from corekinect.utils import Logger

# Private imports
from src.shared.types import *
from src.lib.gpio import Gpio, Pin

# Function handlers makes it easier to write service handlers
from .handlers.gpio import GpioHandler
from .handlers.adc import AdcHandler
from .handlers.motion import MotionHandler
from .handlers.power import PowerHandler
from .handlers.sensors import SensorsHandler
from .handlers.firmware import FirmwareHandler

LOG_MODULE = "provider"

# -------------------------------------------------
#                              Toradex SoM GPIO Map
# -------------------------------------------------
GPIO_PIN_MAP = {
    0: Pin.SODIMM_206,  # GPIO_0 - available on gpiochip2, line 4
    1: Pin.SODIMM_208,  # GPIO_1 - available on gpiochip4, line 5
    2: Pin.SODIMM_210,  # GPIO_2 - available on gpiochip4, line 26
    3: Pin.SODIMM_212,  # GPIO_3 - available on gpiochip4, line 27
    4: Pin.SODIMM_34,  # I2S1_D_OUT - available on gpiochip3, line 26
    5: Pin.SODIMM_30,  # I2S1_BCLK - available on gpiochip3, line 25
    6: Pin.SODIMM_32,  # I2S1_SYNC - available on gpiochip3, line 24
    10: Pin.SODIMM_196,  # SPI_1_CLK - available on gpiochip4, line 10
    11: Pin.SODIMM_198,  # SPI_1_MISO - available on gpiochip4, line 12
    12: Pin.SODIMM_200,  # SPI_1_MOSI - available on gpiochip4, line 11
}


class MtibV1Provider(MtibV1Servicer):
    # -------------------------------------------------
    #                                              Init
    # -------------------------------------------------
    def __init__(
        self,
        config: ProviderConfig,
        logger: Logger = None,
    ):
        # Measure the time it takes to initialize the provider
        start_time = time.time()

        # Setup the config
        self.config: ProviderConfig = config

        # Setup the logger for the server
        self.logger: Logger = logger
        if self.logger is None:
            self.logger = Logger(
                Logger.Config(
                    logger_name=LOG_MODULE,
                    log_directory="logs",
                    overall_log_level=logging.DEBUG,
                    console_log_level=logging.DEBUG,
                    file_log_level=logging.DEBUG,
                    enable_log_color=True,
                )
            )
        else:
            # Create a child logger from the parent
            self.logger = logger.from_parent(LOG_MODULE)

        # Global error list for all components
        self.errors: List[str] = []

        # Objects we manage
        self._gpios: Dict[int, Gpio] = {}

        # Initialize all the objects
        if err := self._init_components():
            self.logger.error(f"Failed to initialize the components: {err}")
            raise Exception(err)

        if err := self._init_handlers():
            self.logger.error(f"Failed to initialize the handlers: {err}")
            raise Exception(err)

        self.logger.info("MtibV1Provider initialized OK in %s ms", (time.time() - start_time) * 1000)

    def _init_components(self) -> Optional[str]:
        """
        Initialize the servicer components.
        """
        # Initialize all GPIOs as OUTPUT by default
        for logical_num, pin in GPIO_PIN_MAP.items():
            # Initialize as OUTPUT with initial value INACTIVE (0)
            gpio = Gpio(consumer=f"mtib-gpio-{logical_num}", pin=pin, direction=gpiod.line.Direction.OUTPUT)
            if err := gpio.init():
                return f"Failed to initialize GPIO {logical_num} ({pin}): {err}"
            # Set initial value to 0
            if err := gpio.write(0):
                return f"Failed to set initial value for GPIO {logical_num} ({pin}): {err}"
            self._gpios[logical_num] = gpio

        self.logger.debug("All components initialized successfully")
        return None

    def _init_handlers(self) -> Optional[str]:
        """
        Initialize the servicer function handlers.
        """
        self._gpio_handlers = GpioHandler(self._gpios, self.logger)
        self._adc_handlers = AdcHandler(self.logger)
        self._motion_handlers = MotionHandler(self.logger)
        self._power_handlers = PowerHandler(self.logger)
        self._sensors_handlers = SensorsHandler(self.logger)
        self._firmware_handlers = FirmwareHandler(self.logger)

        return None

    # -------------------------------------------------
    #                                              GPIO
    # -------------------------------------------------
    @grpc_method
    def GpioConfig(self, request: GpioConfigRequest, context: grpc.ServicerContext) -> GpioConfigResponse:
        return self._gpio_handlers.config(request, context)

    @grpc_method
    def GpioWrite(self, request: GpioWriteRequest, context: grpc.ServicerContext) -> GpioWriteResponse:
        return self._gpio_handlers.write(request, context)

    @grpc_method
    def GpioRead(self, request: GpioReadRequest, context: grpc.ServicerContext) -> GpioReadResponse:
        return self._gpio_handlers.read(request, context)

    # -------------------------------------------------
    #                                               ADC
    # -------------------------------------------------
    @grpc_method
    def AdcRead(self, request: AdcReadRequest, context: grpc.ServicerContext) -> AdcReadResponse:
        return self._adc_handlers.read(request, context)

    @grpc_method
    def AdcReadAll(self, request: Empty, context: grpc.ServicerContext) -> AdcReadAllResponse:
        return self._adc_handlers.read_all(request, context)

    # -------------------------------------------------------------------------------
    #                                                                          Motion
    # -------------------------------------------------------------------------------
    @grpc_method
    def GetMotionStatus(
        self, request: GetMotionStatusRequest, context: grpc.ServicerContext
    ) -> GetMotionStatusResponse:
        return self._motion_handlers.get_status(request, context)

    @grpc_method
    def MotionHome(self, request: Empty, context: grpc.ServicerContext) -> MotionHomeResponse:
        return self._motion_handlers.home(request, context)

    @grpc_method
    def MotionStop(self, request: Empty, context: grpc.ServicerContext) -> MotionStopResponse:
        return self._motion_handlers.stop(request, context)

    @grpc_method
    def SendGcode(self, request: GcodeRequest, context: grpc.ServicerContext) -> GcodeResponse:
        return self._motion_handlers.send_gcode(request, context)

    # -------------------------------------------------
    #                                             Power
    # -------------------------------------------------
    @grpc_method
    def DutPowerEnable(self, request: DutPowerRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        return self._power_handlers.dut_power_enable(request, context)

    @grpc_method
    def DutPowerDisable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        return self._power_handlers.dut_power_disable(request, context)

    @grpc_method
    def DutChargePowerEnable(self, request: DutPowerRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        return self._power_handlers.dut_charge_power_enable(request, context)

    @grpc_method
    def DutChargePowerDisable(self, request: Empty, context: grpc.ServicerContext) -> DutPowerResponse:
        return self._power_handlers.dut_charge_power_disable(request, context)

    @grpc_method
    def DutPowerRead(self, request: Empty, context: grpc.ServicerContext) -> DutPowerReadResponse:
        return self._power_handlers.dut_power_read(request, context)

    # -------------------------------------------------
    #                                          Sensors
    # -------------------------------------------------
    @grpc_method
    def AltimeterRead(self, request: Empty, context: grpc.ServicerContext) -> AltimeterReadResponse:
        return self._sensors_handlers.read_altimeter(request, context)

    @grpc_method
    def AccelRead(self, request: Empty, context: grpc.ServicerContext) -> AccelReadResponse:
        return self._sensors_handlers.read_accel(request, context)

    # -------------------------------------------------
    #                                         Firmware
    # -------------------------------------------------
    @grpc_method
    def ListProgrammers(self, request: Empty, context: grpc.ServicerContext) -> ListProgrammersResponse:
        return self._firmware_handlers.list_programmers(request, context)

    @grpc_method
    def ListFwFiles(self, request: Empty, context: grpc.ServicerContext) -> ListFwFilesResponse:
        return self._firmware_handlers.list_fw_files(request, context)

    @grpc_method
    def UploadFwFile(self, request: UploadFwFileRequest, context: grpc.ServicerContext) -> UploadFwFileResponse:
        return self._firmware_handlers.upload_fw_file(request, context)

    @grpc_method
    def DeleteFwFile(self, request: DeleteFwFileRequest, context: grpc.ServicerContext) -> DeleteFwFileResponse:
        return self._firmware_handlers.delete_fw_file(request, context)

    @grpc_method
    def FlashFwFile(self, request: FlashFwFileRequest, context: grpc.ServicerContext) -> FlashFwFileResponse:
        return self._firmware_handlers.flash_fw_file(request, context)

    # -------------------------------------------------
    #                                    Motion Profile
    # -------------------------------------------------
    @grpc_method
    def UploadMotionProfile(
        self, request: MotionProfileRequest, context: grpc.ServicerContext
    ) -> MotionProfileResponse:
        return self._motion_handlers.upload_profile(request, context)

    @grpc_method
    def ListMotionProfiles(self, request: Empty, context: grpc.ServicerContext) -> ListMotionProfilesResponse:
        return self._motion_handlers.list_profiles(request, context)

    @grpc_method
    def ExecuteMotionProfile(
        self, request: ExecuteProfileRequest, context: grpc.ServicerContext
    ) -> ExecuteProfileResponse:
        return self._motion_handlers.execute_profile(request, context)

    # -------------------------------------------------
    #                                     Health Check
    # -------------------------------------------------
    @grpc_method
    def HealthCheck(self, request: Empty, context: grpc.ServicerContext) -> HealthCheckResponse:
        self.logger.info("HealthCheck request received")
        return HealthCheckResponse(ready=True, errors=self.errors)
