# Standard includes
import logging
import os
import inspect
import sys
import time
import uuid
from concurrent import futures
from concurrent.futures import ThreadPoolExecutor
from queue import Empty, Queue
from threading import Thread
from typing import Dict, Iterator, List

# 3rd Party includes
import grpc
import wiringpi

# Corekinect includes
from corekinect.utils import EnvConfig, Logger
from corekinect.cipher.cipher import *
from protos.mtib_runner.mtib_runner_pb2_grpc import MtibRunnerV1Servicer

# Protocol includes
from protos.mtib_runner_zephyr.mtib_runner_zephyr_pb2_cipher import mtibrunnerzephyr_service_info, MtibRunnerZephyr

# App includes
from src.config.env import ServerEnvConfig
from src.providers.zephyr import ZephyrServerProvider

# from services.fw_files import *
# from services.jlink import *

# from .shared import uart_shared_state
from .types import *  # All types are declared externally for readability of this file


class ServerProvider(MtibRunnerV1Servicer):
    def __init__(self, env_config: ServerEnvConfig, logger: Logger = None):

        # Instantiate the class logger
        self.log: Logger = None
        if logger == None:
            self.log = Logger(config=Logger.Config(logger_name="provider", console_log_level=logging.DEBUG))
        else:
            self.log = logger

        # Assign class's global environment config
        self.env_config: ServerEnvConfig = env_config

        # Application daemon instance
        err = self._init_cipher_daemon()
        if err != None:
            raise RuntimeError("An error ocurred initializing the server's Cipher daemon")

        # App objects
        # self.fw_file_manager = FwFileManager(config.conf.FW_FILE_STORAGE_DIR)
        # self.jlink_manager = Jlink()

        # Executors for UART streams
        self.executor: ThreadPoolExecutor = ThreadPoolExecutor(max_workers=10)

        self.log.info("Starting runner servicer")

    def _init_cipher_daemon(self) -> Optional[str]:
        # Daemon configuration
        client_config = CipherConfig(
            server_ifaces=[],
            client_ifaces=[
                Iface(
                    type=IfaceType.UART,
                    link=IfaceLinkType.CLIENT,
                    uart_port=self.env_config.CIPHER_SERIAL_PORT,
                    baudrate=self.env_config.CIPHER_SERIAL_BAUD,
                )
            ],
        )

        # Reset the server before we attempt to connect to it
        self._reset_zephyr_server()

        # Cipher uses the standard log package
        logging.basicConfig(level=logging.DEBUG)

        # Instantiate & start the daemon
        self.daemon: Cipher = Cipher()
        if not self.daemon.init(client_config):
            return "Could not initialize cipher application daemon"

        # Register service provider
        mtib_service_provider = ZephyrServerProvider(self.daemon)
        if not self.daemon.register_service_provider(mtib_service_provider, mtibrunnerzephyr_service_info):
            return "Could not register the MTIB zephyr service provider"

        # Create a client to consume the service on the remote host
        self.stm32_client = MtibRunnerZephyr(self.daemon)

        self.log.info("Cipher daemon initialized OK")

        # General RPC info
        self.cipher_rpc_info: CipherUnaryRpcUserInfo = CipherUnaryRpcUserInfo(
            destination_id=CIPHER_DESTINATION_ID_ANY, timeout_ms=5000
        )

        return None

    def _reset_zephyr_server(self):
        self.log.debug("Resetting zephyr server...")

        wiringpi.wiringPiSetup()
        wiringpi.pinMode(self.env_config.CIPHER_SERVER_RESET_GPIO, wiringpi.GPIO.OUTPUT)

        # Drive the pin low
        wiringpi.digitalWrite(self.env_config.CIPHER_SERVER_RESET_GPIO, wiringpi.GPIO.LOW)

        # Drive the pin high
        wiringpi.digitalWrite(self.env_config.CIPHER_SERVER_RESET_GPIO, wiringpi.GPIO.HIGH)

        time.sleep(2)

        self.log.debug("Zephyr server has been reset")

    def stop(self) -> Optional[str]:
        self.daemon.stop()
        self.log.info("Runner service provider stopped succesfully")
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
                joulescope=self.env_config.FEATURE_JOULESCOPE,
            ),
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

    # -------------------------------------------------------------------------------------------------
    #                                                                                              Gpio
    # -----------------------------------------------------------------------------------------------*/
    def GpioConfig(self, request: GpioConfigRequest, context: grpc.ServicerContext):
        self.log.debug(f"GpioConfig called with request: {request}")

        rpc_response: GpioConfigResponse = GpioConfigResponse()

        rpc_response.success = True

        # # Create a request for the zephyr app
        # stm_request: GpioConfigurePinRequest = GpioConfigurePinRequest()
        # stm_request.pin_number = request.gpio
        # stm_request.direction = request.direction
        # stm_request.resistor = request.resistor

        # # Execute the request
        # start_time = time.time()
        # stm_response, err = self.stm32.GpioConfigurePinRpc(self.rpc_info, stm_request)
        # duration_ms = (time.time() - start_time) * 1000

        # # Parse the response
        # if err is not CipherRpcErr.OK:
        #     rpc_response.success = False
        #     rpc_response.message = str(err)
        # else:
        #     rpc_response.success = True

        #     if stm_response.success is not True:
        #         rpc_response.success = False
        #         rpc_response.message = stm_response.error

        #     logging.info(
        #         f"RPC GpioConfig executed successfully in {duration_ms:.3f} ms with pin {request.gpio}, direction {request.direction}, resistor {request.resistor}"
        #     )

        return rpc_response

    # def GpioWrite(self, request: GpioWriteRequest, context: grpc.ServicerContext):
    #     rpc_response: GpioWriteResponse = GpioWriteResponse()

    #     # Create a request for the zephyr app
    #     stm_request: GpioSetPinRequest = GpioSetPinRequest()
    #     stm_request.pin_number = request.gpio
    #     stm_request.value = request.state

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.GpioSetPinRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error

    #         logging.info(
    #             f"RPC GpioWrite executed successfully in {duration_ms:.3f} ms with pin {request.gpio}, value {request.state}"
    #         )

    #     return rpc_response

    # def GpioRead(self, request: GpioReadRequest, context: grpc.ServicerContext):
    #     rpc_response: GpioReadResponse = GpioReadResponse()

    #     # Create a request for the zephyr app
    #     stm_request: GpioReadPinRequest = GpioReadPinRequest()
    #     stm_request.pin_number = request.gpio

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.GpioReadPinRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error
    #         else:
    #             rpc_response.state = stm_response.value

    #         logging.info(
    #             f"RPC GpioRead executed successfully in {duration_ms:.3f} ms with pin {request.gpio}, state {rpc_response.state}"
    #         )

    #     return rpc_response

    # # -------------------------------------------------------------------------------------------------
    # #                                                                                               Adc
    # # -----------------------------------------------------------------------------------------------*/
    # def AdcRead(self, request, context: grpc.ServicerContext):
    #     rpc_response: AdcReadResponse = AdcReadResponse()

    #     # Create a request for the zephyr app
    #     stm_request: AdcReadChannelRequest = AdcReadChannelRequest()
    #     stm_request.channel_number = request.channel
    #     stm_request.delay_ms = request.delay_ms

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.AdcReadChannelRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error
    #         else:
    #             rpc_response.voltage = stm_response.voltage

    #         logging.info(
    #             f"RPC AdcRead executed successfully in {duration_ms:.3f} ms with channel {request.channel}, delay_ms {request.delay_ms}, voltage {rpc_response.voltage}"
    #         )

    #     return rpc_response

    # def AdcReadAll(self, request, context: grpc.ServicerContext):
    #     # Prepare the request for the STM32 device
    #     stm_request = AdcReadAllChannelsRequest()
    #     stm_request.delay_ms = request.delay_ms

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.AdcReadAllChannelsRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Prepare the gRPC response
    #     rpc_response = AdcReadAllResponse()

    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         if stm_response.success:
    #             rpc_response.success = True
    #             # Explicitly copy the voltage values
    #             for voltage in stm_response.voltage:
    #                 rpc_response.voltages.append(voltage)
    #             logging.info(
    #                 f"RPC AdcReadAll executed successfully in {duration_ms:.3f} ms with delay_ms {request.delay_ms}, voltages {rpc_response.voltages}"
    #             )
    #         else:
    #             logging.error("STM32 response indicated failure: %s", stm_response.error)
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error

    #     return rpc_response

    # # -------------------------------------------------------------------------------------------------
    # #                                                                                    Firmware Files
    # # -----------------------------------------------------------------------------------------------*/
    # def ListFwFiles(self, request, context: grpc.ServicerContext):
    #     # Fetch the list of FileInfo objects
    #     filesInfo: List[FileInfo] = self.fw_file_manager.list_files()

    #     # Prepare the ListFwFilesResponse message
    #     response = ListFwFilesResponse()
    #     for fileInfo in filesInfo:
    #         file = FwFileInfo(
    #             name=fileInfo.name,
    #             sizeKb=fileInfo.size_kb,
    #             sha256Digest=fileInfo.sha256_digest,
    #         )
    #         response.files.append(file)  # Append the FwFileInfo object to the response list

    #     logging.info(f"ListFwFiles executed successfully with {len(filesInfo)} files.")
    #     return response

    # def UploadFwFile(self, stream, context: grpc.ServicerContext):
    #     filename = None
    #     content = bytearray()

    #     # Assemble the file from the stream
    #     for chunk in stream:
    #         if filename is None:
    #             filename = chunk.filename
    #         content.extend(chunk.content)

    #     if not filename:
    #         # Instead of raising an exception, set the gRPC context to reflect the error
    #         context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
    #         context.set_details("Filename is missing")
    #         logging.warning("UploadFwFile failed due to missing filename.")
    #         return UploadFwFileResponse(success=False, error="Filename is missing")

    #     try:
    #         # Attempt to save the file
    #         success, error, sha256_digest = self.fw_file_manager.save_file(filename, content)

    #         if success:
    #             logging.info(f"UploadFwFile executed successfully with filename {filename}.")
    #             return UploadFwFileResponse(success=True, sha256Digest=sha256_digest)
    #         else:
    #             context.set_code(grpc.StatusCode.ALREADY_EXISTS)
    #             context.set_details(error)
    #             logging.warning(f"UploadFwFile failed with filename {filename} - {error}.")
    #             return UploadFwFileResponse(success=False, error=error)

    #     except Exception as e:
    #         context.set_code(grpc.StatusCode.INTERNAL)
    #         context.set_details(str(e))
    #         logging.warning(f"UploadFwFile failed with exception: {str(e)}.")
    #         return UploadFwFileResponse(success=False, error=str(e))

    # def DeleteFwFile(self, request, context: grpc.ServicerContext):
    #     status, error = self.fw_file_manager.delete_file(request.filename)
    #     if status:
    #         logging.info(f"DeleteFwFile executed successfully for filename {request.filename}.")
    #     else:
    #         logging.warning(f"DeleteFwFile failed for filename {request.filename} - {error}.")
    #     return DeleteFwFileResponse(success=status, error=error)

    # # -------------------------------------------------------------------------------------------------
    # #                                                                                             JLink
    # # -----------------------------------------------------------------------------------------------*/
    # def FlashHexFile(self, request, context: grpc.ServicerContext):
    #     jlink = self.jlink_manager
    #     try:
    #         success = False
    #         if request.isModemFw:
    #             success, error = jlink.program_modem(request.device, request.fileName)
    #         else:
    #             success, error = jlink.program_app(request.device, request.fileName)

    #         return FlashHexFileResponse(success=success, error=error, timeMs=0)
    #     except Exception as e:
    #         return FlashHexFileResponse(success=False, error=str(e), timeMs=0)

    # # -------------------------------------------------------------------------------------------------
    # #                                                                                         DUT Power
    # # -----------------------------------------------------------------------------------------------*/
    # def DutPowerEnable(self, request: DutPowerEnableRequest, context: grpc.ServicerContext):
    #     rpc_response: DutPowerEnableResponse = DutPowerEnableResponse()

    #     # Create a request
    #     stm_request: DutEnablePowerRequest = DutEnablePowerRequest()
    #     stm_request.enable = request.enable

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.DutEnablePowerRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error

    #         logging.info(
    #             f"RPC DutPowerEnable executed successfully in {duration_ms:.3f} ms with state: {request.enable}"
    #         )

    #     return rpc_response

    # def DutChargePowerEnable(self, request: DutPowerEnableRequest, context: grpc.ServicerContext):
    #     rpc_response: DutPowerEnableResponse = DutPowerEnableResponse()

    #     # Create a request
    #     stm_request: DutEnableChargerRequest = DutEnableChargerRequest()
    #     stm_request.enable = request.enable

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.DutEnableChargerRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error

    #         logging.info(
    #             f"RPC DutChargePowerEnable executed successfully in {duration_ms:.3f} ms with state: {request.enable}"
    #         )

    #     return rpc_response

    # def DutVoltageSet(self, request: DutVoltageSetRequest, context: grpc.ServicerContext):
    #     rpc_response: DutVoltageSetResponse = DutVoltageSetResponse()

    #     # Create a request
    #     stm_request: DutSetOutputVoltageRequest = DutSetOutputVoltageRequest()
    #     stm_request.voltage_mv = int(round(request.voltage * 1000))  # Convert from V to mV

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.DutSetOutputVoltageRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error

    #         logging.info(
    #             f"RPC DutVoltageSet executed successfully in {duration_ms:.3f} ms with voltage {request.voltage} V."
    #         )

    #     return rpc_response

    # def DutCurrentRead(self, request: DutCurrentReadRequest, context: grpc.ServicerContext):
    #     rpc_response: DutCurrentReadResponse = DutCurrentReadResponse()

    #     # Create a request
    #     stm_request: Ina219ReadCurrentRequest = Ina219ReadCurrentRequest()

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.Ina219ReadCurrentRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error
    #         else:
    #             rpc_response.current_ma = stm_response.current_value_ma

    #         logging.info(
    #             f"RPC DutCurrentRead executed successfully in {duration_ms:.3f} ms with current {stm_response.current_value_ma} mA."
    #         )

    #     return rpc_response

    # def DutVoltageRead(self, request: DutVoltageReadRequest, context: grpc.ServicerContext):
    #     rpc_response: DutVoltageReadResponse = DutVoltageReadResponse()

    #     # Create a request
    #     stm_request: Ina219ReadVoltageRequest = Ina219ReadVoltageRequest()

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.Ina219ReadVoltageRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error
    #         else:
    #             rpc_response.voltage_mv = stm_response.voltage_value_mv

    #         logging.info(
    #             f"RPC DutVoltageRead executed successfully in {duration_ms:.3f} ms with voltage {stm_response.voltage_value_mv} mV."
    #         )

    #     return rpc_response

    # def DutPowerRead(self, request: DutPowerReadRequest, context: grpc.ServicerContext):
    #     rpc_response: DutPowerReadResponse = DutPowerReadResponse()

    #     # Create a request
    #     stm_request: Ina219ReadPowerRequest = Ina219ReadPowerRequest()

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.Ina219ReadPowerRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error
    #         else:
    #             rpc_response.power_mw = stm_response.power_value_mw

    #         logging.info(
    #             f"RPC DutPowerRead executed successfully in {duration_ms:.3f} ms with power {stm_response.power_value_mw} mW."
    #         )

    #     return rpc_response

    # # -------------------------------------------------------------------------------------------------
    # #                                                                                           Sensors
    # # -----------------------------------------------------------------------------------------------*/
    # def AltimeterRead(self, request: AltimeterReadRequest, context: grpc.ServicerContext):
    #     rpc_response: AltimeterReadResponse = AltimeterReadResponse()

    #     # Create a request
    #     stm_request: Bmp390ReadValuesRequest = Bmp390ReadValuesRequest()

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.Bmp390ReadValuesRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error
    #         else:
    #             rpc_response.temperature_f = stm_response.temperature_f
    #             rpc_response.pressure_hg = stm_response.pressure_hg
    #             rpc_response.altitude_ft = stm_response.altitude_ft

    #         logging.info(
    #             f"RPC AltimeterRead executed successfully in {duration_ms:.3f} ms with temperature {stm_response.temperature_f} F, pressure {stm_response.pressure_hg} Hg, altitude {stm_response.altitude_ft} ft."
    #         )

    #     return rpc_response

    # def AccelRead(self, request: AccelReadRequest, context: grpc.ServicerContext):
    #     rpc_response: AccelReadResponse = AccelReadResponse()

    #     # Create a request
    #     stm_request: Lis2de12ReadValuesRequest = Lis2de12ReadValuesRequest()

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.Lis2de12ReadValuesRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error
    #         else:
    #             rpc_response.x = stm_response.x_value
    #             rpc_response.y = stm_response.y_value
    #             rpc_response.z = stm_response.z_value

    #         logging.info(
    #             f"RPC AccelRead executed successfully in {duration_ms:.3f} ms with x: {stm_response.x_value}, y: {stm_response.y_value}, z: {stm_response.z_value}."
    #         )

    #     return rpc_response

    # def AccelReadMaxForce(self, request: AccelReadMaxRequest, context: grpc.ServicerContext):
    #     rpc_response: AccelReadMaxResponse = AccelReadMaxResponse()

    #     # Create a request
    #     stm_request: Lis2de12ReadMaxForceRequest = Lis2de12ReadMaxForceRequest()

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.Lis2de12ReadMaxForceRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error
    #         else:
    #             rpc_response.max = stm_response.max_force

    #         logging.info(
    #             f"RPC AccelReadMaxForce executed successfully in {duration_ms:.3f} ms with max force {stm_response.max_force}."
    #         )

    #     return rpc_response

    # def EepromRead(self, request: EepromReadRequest, context: grpc.ServicerContext):
    #     rpc_response: EepromReadResponse = EepromReadResponse()

    #     # Create a request
    #     stm_request: EepromReadFromMemRequest = EepromReadFromMemRequest()
    #     stm_request.address = request.address
    #     stm_request.len = request.len

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.EepromReadFromMemRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error
    #         else:
    #             rpc_response.data = stm_response.data

    #         logging.info(
    #             f"RPC EepromRead executed successfully in {duration_ms:.3f} ms with address {request.address}, length {request.len}."
    #         )

    #     return rpc_response

    # def EepromWrite(self, request: EepromWriteRequest, context: grpc.ServicerContext):
    #     rpc_response: EepromWriteResponse = EepromWriteResponse()

    #     # Create a request
    #     stm_request: EepromWriteToMemRequest = EepromWriteToMemRequest()
    #     stm_request.address = request.address
    #     stm_request.data = request.buffer
    #     # stm_request.len = request.len

    #     # Execute the request
    #     start_time = time.time()
    #     stm_response, err = self.stm32.EepromWriteToMemRpc(self.rpc_info, stm_request)
    #     duration_ms = (time.time() - start_time) * 1000

    #     # Parse the response
    #     if err is not CipherRpcErr.OK:
    #         rpc_response.success = False
    #         rpc_response.message = str(err)
    #     else:
    #         rpc_response.success = True

    #         if stm_response.success is not True:
    #             rpc_response.success = False
    #             rpc_response.message = stm_response.error

    #         logging.info(
    #             f"RPC EepromWrite executed successfully in {duration_ms:.3f} ms with address {request.address}, data length {len(request.buffer)}."
    #         )

    #     return rpc_response

    # # -------------------------------------------------------------------------------------------------
    # #                                                                                            Motion
    # # -----------------------------------------------------------------------------------------------*/
    # def GetMotionStatus(self, request: pbEmpty, context) -> GetMotionStatusResponse:
    #     status: MotionStatus = MotionStatus.MOTION_STATUS_ERRORED

    #     # TODO: Call motion table call here to assign the right status

    #     response: GetMotionStatusResponse = GetMotionStatusResponse(
    #         status=status,
    #     )

    #     return response

    # def MotionHome(self, request: pbEmpty, context) -> MotionHomeResponse:

    #     # TODO: Call motion table call here to move bed to home position

    #     response: MotionHomeResponse = MotionHomeResponse(
    #         success=True,
    #         message="Some error message",
    #     )

    #     return response

    # def MotionTrigger(self, request: MotionTriggerRequest, context) -> MotionTriggerResponse:
    #     # Variables from request can be used like so:
    #     logging.debug(
    #         f"MotionTrigger: num_cycles:{request.num_cycles}, cycle_time_second:{request.cycle_time_seconds}"
    #     )

    #     # TODO: Call motion table call here to trigger motion

    #     response: MotionTriggerResponse = MotionTriggerResponse(
    #         success=True,
    #         message="Some error message",
    #     )

    #     return response

    # def MotionContinuous(self, request: MotionContinuousRequest, context) -> MotionContinuousResponse:
    #     # Determine which oneof field is set
    #     active_field = request.WhichOneof("value")

    #     if active_field == "duration_seconds":
    #         logging.debug(f"MotionContinuous: duration_seconds:{request.duration_seconds}")
    #     elif active_field == "duration_hours":
    #         logging.debug(f"MotionContinuous: duration_hours:{request.duration_hours}")
    #     else:
    #         logging.debug(f"MotionContinuous: No valid duration field set")

    #     # TODO: Call motion table call here to trigger continuous motion

    #     response: MotionContinuousResponse = MotionContinuousResponse(
    #         success=True,
    #         message="Some error message",
    #     )

    #     return response

    # def MotionStop(self, request: pbEmpty, context) -> MotionStopResponse:
    #     # TODO: Call motion table call here to stop motion

    #     response: MotionStopResponse = MotionStopResponse(
    #         success=True,
    #         message="Some error message",
    #     )

    #     return response

    # -------------------------------------------------------------------------------------------------
    #                                                                                      Uart Streams
    # -----------------------------------------------------------------------------------------------*/
    def nrf9160UartStream(
        self, request_iterator: Iterator[UartStreamRequest], context: ServicerContext
    ) -> Iterator[UartStreamResponse]:
        device_id = UartDeviceType.NRF9160
        if device_id not in uart_shared_state.rx_queues:
            uart_shared_state.rx_queues[device_id] = Queue()

        # Enable UART port at the start of the stream
        enable_request = UartPortStateChangeRequest(device=device_id, enable=True)
        enable_response, err = self.stm32.UartPortEnableRpc(self.rpc_info, enable_request)
        if err != CipherRpcErr.OK:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Communication error while trying to enable UART port {str(err)}")
            return

        if enable_response.error:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to enable UART port {enable_response.error}")
            return

        logging.info(f"UART port enabled for nrf9160")

        def handle_tx():
            for request in request_iterator:
                if not context.is_active():
                    break
                pi_to_sigma_request = UartMessageRequest(device=device_id, data=request.data)
                response, err = self.stm32.PiToSigmaMessageRpc(self.rpc_info, pi_to_sigma_request)
                if err != CipherRpcErr.OK:
                    context.set_code(grpc.StatusCode.INTERNAL)
                    context.set_details(f"Communication error while sending data to port {str(err)}")
                    return

                if response.error:
                    context.set_code(grpc.StatusCode.INTERNAL)
                    context.set_details(f"Failed to send data {response.error}")
                    return

        def handle_rx():
            while context.is_active():
                try:
                    data = uart_shared_state.rx_queues[device_id].get(timeout=1)
                    yield UartStreamResponse(data=data)
                except Empty:
                    continue

        try:
            # Start the TX handler in a separate thread
            self.executor.submit(handle_tx)

            # Handle RX in the main thread
            yield from handle_rx()
        finally:
            # Ensure the UART port is disabled when the stream ends
            disable_request = UartPortStateChangeRequest(device=device_id, enable=False)
            self.stm32.UartPortDisableRpc(self.rpc_info, disable_request)
            logging.info(f"UART port disabled for nrf9160")

    def nrf52840UartStream(
        self, request_iterator: Iterator[UartStreamRequest], context: ServicerContext
    ) -> Iterator[UartStreamResponse]:
        device_id = UartDeviceType.NRF82840
        if device_id not in uart_shared_state.rx_queues:
            uart_shared_state.rx_queues[device_id] = Queue()

        # Enable UART port at the start of the stream
        enable_request = UartPortStateChangeRequest(device=device_id, enable=True)
        enable_response, err = self.stm32.UartPortEnableRpc(self.rpc_info, enable_request)
        if err != CipherRpcErr.OK:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Communication error while trying to enable UART port {str(err)}")
            return

        if enable_response.error:
            context.set_code(grpc.StatusCode.INTERNAL)
            context.set_details(f"Failed to enable UART port {enable_response.error}")
            return

        logging.info(f"UART port enabled for nrf52840")

        def handle_tx():
            for request in request_iterator:
                if not context.is_active():
                    break
                pi_to_sigma_request = UartMessageRequest(device=device_id, data=request.data)
                response, err = self.stm32.PiToSigmaMessageRpc(self.rpc_info, pi_to_sigma_request)
                if err != CipherRpcErr.OK:
                    context.set_code(grpc.StatusCode.INTERNAL)
                    context.set_details(f"Communication error while sending data to port {str(err)}")
                    return

                if response.error:
                    context.set_code(grpc.StatusCode.INTERNAL)
                    context.set_details(f"Failed to send data {response.error}")
                    return

        def handle_rx():
            while context.is_active():
                try:
                    data = uart_shared_state.rx_queues[device_id].get(timeout=1)
                    response = UartStreamResponse(data=data)
                    yield response
                except Empty:
                    continue

        try:
            # Start the TX handler in a separate thread
            self.executor.submit(handle_tx)

            # Handle RX in the main thread
            yield from handle_rx()
        finally:
            # Ensure the UART port is disabled when the stream ends
            disable_request = UartPortStateChangeRequest(device=device_id, enable=False)
            self.stm32.UartPortDisableRpc(self.rpc_info, disable_request)
            logging.info(f"UART port disabled for nrf52840")
