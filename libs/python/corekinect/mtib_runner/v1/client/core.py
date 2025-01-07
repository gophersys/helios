from typing import Optional, Tuple, List, Any
from contextlib import contextmanager
import inspect

# 3rd Party includes
import grpc
from grpc import insecure_channel, RpcError

# Protocol includes
from protos.mtib_runner.mtib_runner_pb2 import (
    Empty as pbEmpty,
    HealthCheckResponse,
    RunnerFeatures,
    GetRunnerInfoResponse,
    GpioDirection,
    GpioResistorConfig,
    GpioConfigRequest,
    GpioConfigResponse,
    GpioWriteRequest,
    GpioWriteResponse,
    GpioReadRequest,
    GpioReadResponse,
    AdcReadRequest,
    AdcReadResponse,
    AdcReadAllRequest,
    AdcReadAllResponse,
    DutPowerRequest,
    DutPowerResponse,
    DutPowerReadResponse,
    AltimeterReadResponse,
    AccelReadResponse,
    MotionHomeResponse,
    MotionStatus,
    GetMotionStatusResponse,
    MotionTriggerRequest,
    MotionTriggerResponse,
    MotionContinuousRequest,
    MotionContinuousResponse,
    MotionStopResponse,
    HostType,
    FwFileInfo,
    ListFwFilesResponse,
    UploadFwFileRequest,
    UploadFwFileResponse,
    DeleteFwFileRequest,
    DeleteFwFileResponse,
    FlashFwFileRequest,
    FlashFwFileResponse,
    UartStreamRequest,
    UartStreamResponse,
)

from protos.mtib_runner.mtib_runner_pb2_grpc import MtibRunnerV1Stub

# Corekinect includes
from corekinect.utils import Logger

from ..config.config import MtibRunnerV1Features, MtibRunnerV1Info


class GpioConfig:
    def __init__(
        self,
        pin_hard_reset: int = 0,
        pin_chrg_detect: int = 1,
        pin_uvp_n: int = 2,
        pin_3v3_psm: int = 3,
    ):
        self.pin_hard_reset: int = pin_hard_reset
        self.pin_chrg_detect: int = pin_chrg_detect
        self.pin_uvp_n: int = pin_uvp_n
        self.pin_3v3_psm: int = pin_3v3_psm


class AdcConfig:
    def __init__(
        self,
        read_delay_ms: int = 100,
        ch_3v3: int = 0,
        ch_vin: int = 1,
        ch_vbckp: int = 2,
        ch_vbat: int = 3,
        ch_3v3_gps: int = 4,
    ):
        self.read_delay_ms: int = read_delay_ms
        self.ch_3v3: int = ch_3v3
        self.ch_vin: int = ch_vin
        self.ch_vbckp: int = ch_vbckp
        self.ch_vbat: int = ch_vbat
        self.ch_3v3_gps: int = ch_3v3_gps


class NetConfig:
    def __init__(
        self,
        addr: str = "127.0.0.1",
        port: int = 50051,
    ):
        self.addr: str = addr
        self.port: int = port


class MtibRunnerV1Client:
    # -----------------------------------------------------------------------------
    #                                                                        Config
    # ---------------------------------------------------------------------------*/
    class Config:
        def __init__(
            self,
            gpio: GpioConfig = GpioConfig(),
            adc: AdcConfig = AdcConfig(),
            net: NetConfig = NetConfig(),
        ):
            self.gpio: GpioConfig = gpio
            self.adc: AdcConfig = adc
            self.net: NetConfig = net

    # -----------------------------------------------------------------------------
    #                                                                          Init
    # ---------------------------------------------------------------------------*/
    def __init__(self, config: Config, logger: Logger = None):
        self.config: self.Config = config

        if logger is None:
            self.logger: Logger = Logger(
                config=Logger.Config(
                    logger_name="runner_client_v1",
                )
            )
        else:
            self.logger: Logger = logger

        # Internal objects used by the channel
        self.channel: grpc.Channel = None
        self.client: MtibRunnerV1Stub = None

    # -----------------------------------------------------------------------------
    #                                                               Private Helpers
    # ---------------------------------------------------------------------------*/
    def _get_func_name(self) -> str:
        return inspect.currentframe().f_back.f_code.co_name

    # -----------------------------------------------------------------------------
    #                                                                       Connect
    # ---------------------------------------------------------------------------*/
    def connect(self) -> Optional[str]:
        # First we connect to the desired server
        err = self._connect_to_server()
        if err is not None:
            return f"An error ocurred connecting to server: {err}"

        # Configure any GPIOs or services needed
        err = self._configure_server()
        if err is not None:
            return f"An error ocurred configuring server: {err}"

    def _connect_to_server(self) -> Optional[str]:
        try:
            # Create a gRPC channel
            self.channel = insecure_channel(f"{self.config.net.addr}:{self.config.net.port}")

            # Create a stub using the newly created channel
            self.client = MtibRunnerV1Stub(self.channel)

            # Do an initial health check with a timeout
            response = self.client.HealthCheck(pbEmpty(), timeout=1)
            if response.ok:
                self.logger.info(f"Runner at {self.config.net.addr}:{self.config.net.port} connected successfully")
                return None
            else:
                return "Health check failed"
        except RpcError as e:
            return f"Failed to connect to runner. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error when connecting to runner. Error: {str(e)}"

    def _configure_server(self) -> Optional[str]:
        # Setup any neede GPIOs by this client
        err = self.gpio_config(
            self.config.gpio.pin_hard_reset,
            GpioDirection.GPIO_DIRECTION_OUTPUT,
            GpioResistorConfig.GPIO_RESISTOR_PULL_UP,
        )
        if err is not None:
            return err

        err = self.gpio_config(
            self.config.gpio.pin_chrg_detect,
            GpioDirection.GPIO_DIRECTION_INPUT,
            GpioResistorConfig.GPIO_RESISTOR_PULL_DOWN,
        )
        if err is not None:
            return err

        err = self.gpio_config(
            self.config.gpio.pin_uvp_n,
            GpioDirection.GPIO_DIRECTION_INPUT,
            GpioResistorConfig.GPIO_RESISTOR_PULL_UP,
        )
        if err is not None:
            return err

        err = self.gpio_config(
            self.config.gpio.pin_3v3_psm,
            GpioDirection.GPIO_DIRECTION_INPUT,
            GpioResistorConfig.GPIO_RESISTOR_PULL_DOWN,
        )
        if err is not None:
            return err

        self.logger.debug("Server was configured succesfully")

        return None

    # -----------------------------------------------------------------------------
    #                                                                    Disconnect
    # ---------------------------------------------------------------------------*/
    def disconnect(self) -> Optional[str]:
        """
        Cleanly disconnect from the gRPC client and close any resources.
        """
        try:
            if self.channel:
                # Close the gRPC channel if it's open
                self.channel.close()
                self.logger.info(f"Disconnected from runner at {self.config.net.addr}:{self.config.net.port}")
                return None
            else:
                self.logger.warning(f"No active connection to close for {self.config.net.addr}:{self.config.net.port}")
                return None
        except Exception as e:
            return f"Unexpected error when disconnecting from runner. Error: {str(e)}"

    # -----------------------------------------------------------------------------
    #                                                                          Info
    # ---------------------------------------------------------------------------*/
    def get_runner_info(self) -> Tuple[Optional[MtibRunnerV1Info], Optional[str]]:
        try:
            response = self.client.GetRunnerInfo(pbEmpty())

            info: MtibRunnerV1Info = MtibRunnerV1Info(
                platform=response.platform,
                hw_version=response.hw_version,
                features=MtibRunnerV1Features(
                    response.features.dut_power,
                    response.features.motion,
                    response.features.sensor_accel,
                    response.features.sensor_alt,
                    response.features.fw_flash,
                ),
            )
            return info, None
        except grpc.RpcError as e:
            return None, f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------------------------------------
    #                                                                          GPIO
    # ---------------------------------------------------------------------------*/
    def gpio_config(self, gpio: int, direction: GpioDirection, resistor: GpioResistorConfig) -> Optional[str]:
        try:
            response = self.client.GpioConfig(GpioConfigRequest(gpio=gpio, direction=direction, resistor=resistor))
            if not response.success:
                return f"{self._get_func_name()} error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    def gpio_write(self, gpio: int, state: bool) -> Optional[str]:
        try:
            response = self.client.GpioWrite(GpioConfigRequest(gpio=gpio, state=state))
            if not response.success:
                return f"{self._get_func_name()} error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    def gpio_read(self, gpio: int, state: bool) -> Tuple[Optional[bool], Optional[str]]:
        try:
            response = self.client.GpioWrite(GpioConfigRequest(gpio=gpio, state=state))
            if not response.success:
                return None, f"{self._get_func_name()} error: {response.message}"
            return response.state, None
        except grpc.RpcError as e:
            return (
                None,
                f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}",
            )
        except Exception as e:
            return None, f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # # -----------------------------------------------------------------------------
    # #                                                                           ADC
    # # ---------------------------------------------------------------------------*/
    # def adc_read(self, channel: int) -> Tuple[Optional[float], Optional[str]]:
    #     try:
    #         response = self.client.AdcRead(AdcReadRequest(channel=channel, delay_ms=self.config.adc.read_delay_ms))
    #         if not response.success:
    #             return None, f"{self._get_func_name()} error: {response.message}"
    #         return response.voltage, None
    #     except grpc.RpcError as e:
    #         return (
    #             None,
    #             f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}",
    #         )
    #     except Exception as e:
    #         return None, f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # def adc_read_all(self) -> Tuple[Optional[List[float]], Optional[str]]:
    #     try:
    #         response = self.client.AdcReadAll(AdcReadAllRequest(delay_ms=self.config.adc.read_delay_ms))
    #         if not response.success:
    #             return None, f"{self._get_func_name()} error: {response.message}"
    #         return response.voltages, None
    #     except grpc.RpcError as e:
    #         return (
    #             None,
    #             f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}",
    #         )
    #     except Exception as e:
    #         return None, f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # # -----------------------------------------------------------------------------
    # #                                                                     DUT Power
    # # ---------------------------------------------------------------------------*/
    # def dut_power_enable(self, vbat_voltage: float) -> Optional[str]:
    #     try:
    #         # Set the battery voltage first
    #         err = self._dut_set_vbat(voltage=vbat_voltage)
    #         if err is not None:
    #             return f"could not set power voltage to {vbat_voltage}, {err}"

    #         # Switch power on
    #         response: DutPowerEnableResponse = self.client.DutPowerEnable(DutPowerEnableRequest(enable=True))
    #         if not response.success:
    #             return f"{self._get_func_name()} error: {response.message}"
    #         return None
    #     except grpc.RpcError as e:
    #         return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
    #     except Exception as e:
    #         return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # def dut_power_disable(self) -> Optional[str]:
    #     try:
    #         response: DutPowerEnableResponse = self.client.DutPowerEnable(DutPowerEnableRequest(enable=False))
    #         if not response.success:
    #             return f"{self._get_func_name()} error: {response.message}"
    #         return None
    #     except grpc.RpcError as e:
    #         return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
    #     except Exception as e:
    #         return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # def dut_charge_power_enable(self) -> Optional[str]:
    #     try:
    #         response: DutPowerEnableResponse = self.client.DutChargePowerEnable(DutPowerEnableRequest(enable=True))
    #         if not response.success:
    #             return f"{self._get_func_name()} error: {response.message}"
    #         return None
    #     except grpc.RpcError as e:
    #         return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
    #     except Exception as e:
    #         return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # def dut_charge_power_disable(self) -> Optional[str]:
    #     try:
    #         response: DutPowerEnableResponse = self.client.DutChargePowerEnable(DutPowerEnableRequest(enable=False))
    #         if not response.success:
    #             return f"{self._get_func_name()} error: {response.message}"
    #         return None
    #     except grpc.RpcError as e:
    #         return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
    #     except Exception as e:
    #         return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # def _dut_set_vbat(self, voltage: float) -> Optional[str]:
    #     try:
    #         response: DutVoltageSetResponse = self.client.DutVoltageSet(DutVoltageSetRequest(voltage=voltage))
    #         if not response.success:
    #             return f"{self._get_func_name()} error: {response.message}"
    #         return None
    #     except grpc.RpcError as e:
    #         return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
    #     except Exception as e:
    #         return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # # -----------------------------------------------------------------------------
    # #                                                                       Sensors
    # # ---------------------------------------------------------------------------*/

    # -----------------------------------------------------------------------------
    #                                                                        Motion
    # ---------------------------------------------------------------------------*/
    def _get_motion_status(self) -> Tuple[Optional[Any], Optional[str]]:
        try:
            response = self.client.GetMotionStatus(pbEmpty())
            if not response.success:
                return None, f"{self._get_func_name()} error: {response.message}"
            return response.status, None
        except grpc.RpcError as e:
            return (
                None,
                f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}",
            )
        except Exception as e:
            return None, f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    def motion_home(self) -> Optional[str]:
        try:
            status, err = self._get_motion_status()
            if err != None:
                return f"An error ocurred getting the motion status {err}"

            if status != MotionStatus.MOTION_STATUS_IDLE:
                return f"Cannot home device while in {status} state"

            response = self.client.MotionHome(pbEmpty())
            if not response.success:
                return None, f"{self._get_func_name()} error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    def motion_trigger(self, num_cycles: int, cycle_time_seconds: int) -> Optional[str]:
        try:
            status, err = self._get_motion_status()
            if err != None:
                return f"An error ocurred getting the motion status {err}"

            if status != MotionStatus.MOTION_STATUS_IDLE:
                return f"Cannot home device while in {status} state"

            response = self.client.MotionTrigger(
                MotionTriggerRequest(
                    num_cycles=num_cycles,
                    cycle_time_seconds=cycle_time_seconds,
                )
            )
            if not response.success:
                return None, f"{self._get_func_name()} error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    def motion_continuous(
        self, duration_seconds: Optional[int] = None, duration_hours: Optional[int] = None
    ) -> Optional[str]:
        # Ensure that only one of the two arguments is set
        if (duration_seconds is not None and duration_hours is not None) or (
            duration_seconds is None and duration_hours is None
        ):
            return f"{self._get_func_name()} error: You must specify either 'duration_hours' or 'duration_seconds', but not both."

        try:
            status, err = self._get_motion_status()
            if err != None:
                return f"An error ocurred getting the motion status {err}"

            if status != MotionStatus.MOTION_STATUS_IDLE:
                return f"Cannot home device while in {status} state"

            # Set the appropriate field based on the user input
            if duration_seconds is not None:
                request = MotionContinuousRequest(duration_seconds=duration_seconds)
            else:
                request = MotionContinuousRequest(duration_hours=duration_hours)

            response: MotionContinuousResponse = self.client.MotionContinuous(request)

            if not response.success:
                return f"{self._get_func_name()} error: {response.message}"

            return None

        except grpc.RpcError as e:
            return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    def motion_stop(self) -> Optional[str]:
        try:
            status, err = self._get_motion_status()
            if err != None:
                return f"An error ocurred getting the motion status {err}"

            # Check if we're already stopped
            if status == MotionStatus.MOTION_STATUS_IDLE:
                return None

            response = self.client.MotionStop(pbEmpty())
            if not response.success:
                return None, f"{self._get_func_name()} error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # # -----------------------------------------------------------------------------
    # #                                                                      Fw Files
    # # ---------------------------------------------------------------------------*/

    # # -----------------------------------------------------------------------------
    # #                                                                       J-Links
    # # ---------------------------------------------------------------------------*/

    # # -----------------------------------------------------------------------------
    # #                                                                  UART Streams
    # # ---------------------------------------------------------------------------*/
