# Standard includes
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator, Optional

# 3rd party includes
import grpc

# Corekinect includes
from corekinect.utils import Logger

# Protocol includes
from protos.mtib_runner.mtib_runner_pb2_grpc import MtibRunnerV1Servicer

# App includes
from src.config.env import ServerEnvConfig

# Private includes
from .types import *  # All types are declared externally for readability of this file


class MockServerProvider(MtibRunnerV1Servicer):
    def __init__(self, env_config: ServerEnvConfig, logger: Logger = None):

        # Instantiate the class logger
        self.log: Logger = None
        if logger == None:
            self.log = Logger(config=Logger.Config(logger_name="mock", console_log_level=logging.DEBUG))
        else:
            self.log = logger

        # Assign class's global environment config
        self.env_config: ServerEnvConfig = env_config

        # Executors for UART streams
        self.executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=10)

        self.log.info("Starting runner mock servicer")

    def stop(self) -> Optional[str]:
        return None

    # -----------------------------------------------------------------------------
    #                                                                   HealthCheck
    # ---------------------------------------------------------------------------*/
    def HealthCheck(self, request: pbEmpty, context: grpc.ServicerContext):
        return HealthCheckResponse(ok=True)

    # -----------------------------------------------------------------------------
    #                                                                 GetRunnerInfo
    # ---------------------------------------------------------------------------*/
    def GetRunnerInfo(self, request: pbEmpty, context: grpc.ServicerContext) -> GetRunnerInfoResponse:
        self.log.debug(f"GetRunnerInfo called with request: {request}")

        # Populate the response
        response = GetRunnerInfoResponse(
            platform=self.env_config.PLATFORM,
            hw_version=self.env_config.HW_VERSION,
            features=RunnerFeatures(
                dut_power=self.env_config.FEATURE_DUT_POWER_ENABLED,
                motion=self.env_config.FEATURE_MOTION_ENABLED,
                sensor_accel=self.env_config.FEATURE_SENSOR_ACCEL_ENABLED,
                sensor_alt=self.env_config.FEATURE_SENSOR_ALT_ENABLED,
                fw_flash=self.env_config.FEATURE_FW_FLASH_ENABLED,
                joulescope=self.env_config.FEATURE_JOULESCOPE
            ),
        )

        return response

    # -----------------------------------------------------------------------------
    #                                                                          Gpio
    # ---------------------------------------------------------------------------*/
    def GpioConfig(self, request: GpioConfigRequest, context: grpc.ServicerContext) -> GpioConfigResponse:
        self.log.debug(f"GpioConfig called with request: {request}")

        response: GpioConfigResponse = GpioConfigResponse(success=True)

        return response

    def GpioWrite(self, request: GpioWriteRequest, context: grpc.ServicerContext) -> GpioWriteResponse:
        self.log.debug(f"GpioWrite called with request: {request}")

        response: GpioWriteResponse = GpioWriteResponse(success=True)

        return response

    def GpioRead(self, request: GpioReadRequest, context: grpc.ServicerContext) -> GpioReadResponse:
        self.log.debug(f"GpioRead called with request: {request}")

        response: GpioReadResponse = GpioReadResponse(success=True, state=0)

        return response

    # -----------------------------------------------------------------------------
    #                                                                           Adc
    # ---------------------------------------------------------------------------*/
    def AdcRead(self, request: AdcReadRequest, context: grpc.ServicerContext) -> AdcReadResponse:
        self.log.debug(f"AdcRead called with request: {request}")

        response: AdcReadResponse = AdcReadResponse(success=True, voltage_v=0)

        return response

    def AdcReadAll(self, request: AdcReadAllRequest, context: grpc.ServicerContext) -> AdcReadAllRequest:
        self.log.debug(f"AdcReadAll called with request: {request}")

        response: AdcReadAllRequest = AdcReadAllRequest(
            success=True,
            voltages_v=[
                0,
                0,
                0,
                0,
                0,
            ],
        )

        return response

    # -----------------------------------------------------------------------------
    #                                                                         Power
    # ---------------------------------------------------------------------------*/
    def DutPowerEnable(self, request: DutPowerRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        self.log.debug(f"DutPowerEnable called with request: {request}")

        response: DutPowerResponse = DutPowerResponse(success=True)

        return response

    def DutPowerDisable(self, request: pbEmpty, context: grpc.ServicerContext) -> DutPowerResponse:
        self.log.debug(f"DutPowerDisable called with request: {request}")

        response: DutPowerResponse = DutPowerResponse(success=True)

        return response

    def DutChargePowerEnable(self, request: DutPowerRequest, context: grpc.ServicerContext) -> DutPowerResponse:
        self.log.debug(f"DutChargePowerEnable called with request: {request}")

        response: DutPowerResponse = DutPowerResponse(success=True)

        return response

    def DutChargePowerDisable(self, request: pbEmpty, context: grpc.ServicerContext) -> DutPowerResponse:
        self.log.debug(f"DutChargePowerDisable called with request: {request}")

        response: DutPowerResponse = DutPowerResponse(success=True)

        return response

    # -----------------------------------------------------------------------------
    #                                                             Power Consumption
    # ---------------------------------------------------------------------------*/
    def DutPowerRead(self, request: pbEmpty, context: grpc.ServicerContext) -> DutPowerReadResponse:
        self.log.debug(f"DutPowerRead called with request: {request}")

        response: DutPowerReadResponse = DutPowerReadResponse(
            success=True,
            current_a=0,
            voltage_v=0,
            power_w=0,
        )

        return response

    # -----------------------------------------------------------------------------
    #                                                                       Sensors
    # ---------------------------------------------------------------------------*/
    def AltimeterRead(self, request: pbEmpty, context: grpc.ServicerContext) -> AltimeterReadResponse:
        self.log.debug(f"AltimeterRead called with request: {request}")

        response: AltimeterReadResponse = AltimeterReadResponse(
            success=True,
            temperature_f=0,
            pressure_hg=0,
            altitude_ft=0,
        )

        return response

    def AccelRead(self, request: pbEmpty, context: grpc.ServicerContext) -> AccelReadResponse:
        self.log.debug(f"AccelRead called with request: {request}")

        response: AccelReadResponse = AccelReadResponse(
            success=True,
            x_g=0,
            y_g=0,
            z_g=0,
        )

        return response

    # -----------------------------------------------------------------------------
    #                                                                        Motion
    # ---------------------------------------------------------------------------*/
    def GetMotionStatus(self, request: pbEmpty, context: grpc.ServicerContext) -> GetMotionStatusResponse:
        self.log.debug(f"GetMotionStatus called with request: {request}")

        response: GetMotionStatusResponse = GetMotionStatusResponse(
            success=True,
            status=MotionStatus.MOTION_STATUS_IDLE,
        )

        return response

    def MotionHome(self, request: pbEmpty, context: grpc.ServicerContext) -> MotionHomeResponse:
        self.log.debug(f"MotionHome called with request: {request}")

        response: MotionHomeResponse = MotionHomeResponse(success=True)

        return response

    def MotionTrigger(self, request: MotionTriggerRequest, context: grpc.ServicerContext) -> MotionTriggerResponse:
        self.log.debug(f"MotionTrigger called with request: {request}")

        response: MotionTriggerResponse = MotionTriggerResponse(success=True)

        return response

    def MotionContinuous(
        self, request: MotionContinuousRequest, context: grpc.ServicerContext
    ) -> MotionContinuousResponse:
        self.log.debug(f"MotionContinuous called with request: {request}")

        response: MotionContinuousResponse = MotionContinuousResponse(success=True)

        return response

    def MotionStop(self, request: pbEmpty, context: grpc.ServicerContext) -> MotionStopResponse:
        self.log.debug(f"MotionStop called with request: {request}")

        response: MotionStopResponse = MotionStopResponse(success=True)

        return response

    # -----------------------------------------------------------------------------
    #                                                                      Firmware
    # ---------------------------------------------------------------------------*/
    def ListFwFiles(self, request: pbEmpty, context: grpc.ServicerContext) -> ListFwFilesResponse:
        self.log.debug(f"ListFwFiles called with request: {request}")

        response: ListFwFilesResponse = ListFwFilesResponse(files=[])

        return response

    def UploadFwFile(
        self, request_iterator: Iterator[UploadFwFileRequest], context: grpc.ServicerContext
    ) -> UploadFwFileResponse:
        filename = None
        content = bytearray()

        # Assemble the file from the stream
        for chunk in request_iterator:
            if filename is None:
                filename = chunk.name
            content.extend(chunk.content)

        if not filename:
            self.log.warning("UploadFwFile failed due to missing filename.")
            return UploadFwFileResponse(success=False, error="Filename is missing")

        self.log.debug(f"UploadFwFile called for file: {filename}")
        return UploadFwFileResponse(success=True, sha256_digest=0)

    def DeleteFwFile(self, request: DeleteFwFileRequest, context: grpc.ServicerContext) -> DeleteFwFileResponse:
        self.log.debug(f"DeleteFwFile called with request: {request}")

        response: DeleteFwFileResponse = DeleteFwFileResponse(success=True)

        return response

    def FlashFwFile(self, request: FlashFwFileRequest, context: grpc.ServicerContext) -> FlashFwFileResponse:
        self.log.debug(f"FlashFwFile called with request: {request}")

        response: FlashFwFileResponse = FlashFwFileResponse(success=True)

        return response

    # -----------------------------------------------------------------------------
    #                                                                   UART Stream
    # ---------------------------------------------------------------------------*/
    def UartStream(
        self, request_iterator: Iterator[UartStreamRequest], context: grpc.ServicerContext
    ) -> Iterator[UartStreamResponse]:
        pass
