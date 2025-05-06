# Standard includes
import inspect
from typing import Optional, Tuple, List

# 3rd Party includes
import grpc
from grpc import insecure_channel, RpcError

# Protocol includes
from protocols.mtib.mtib_pb2_grpc import MtibV1Stub as MtibClientV1

# Corekinect includes
from corekinect.utils import Logger

# Private includes
from .types import *
from .config import *


class MtibV1Client:
    # -----------------------------------------------------------------------------
    #                                                                        Config
    # ---------------------------------------------------------------------------*/
    class Config:
        def __init__(
            self,
            net: NetConfig = NetConfig(),
            gpio: GpioConfig = GpioConfig(),
            adc: AdcConfig = AdcConfig(),
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
        self.client: MtibClientV1 = None

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

        # # Configure any GPIOs or services needed
        # err = self._configure_server()
        # if err is not None:
        #     return f"An error ocurred configuring server: {err}"

    def _connect_to_server(self) -> Optional[str]:
        try:
            # Create a gRPC channel
            self.channel = insecure_channel(f"{self.config.net.addr}:{self.config.net.port}")

            # Create a stub using the newly created channel
            self.client = MtibClientV1(self.channel)

        except RpcError as e:
            return f"Failed to connect to runner. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error when connecting to runner. Error: {str(e)}"

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
                return None
            else:
                self.logger.warning(f"No active connection to close for {self.config.net.addr}:{self.config.net.port}")
                return None
        except Exception as e:
            return f"Unexpected error when disconnecting from runner. Error: {str(e)}"

    # -----------------------------------------------------------------------------
    #                                                                        Health
    # ---------------------------------------------------------------------------*/
    def health_check(self) -> Tuple[Optional[bool], Optional[List[str]]]:
        try:
            response = self.client.HealthCheck(Empty())
            return response.ready, response.errors
        except grpc.RpcError as e:
            return False, [f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"]
        except Exception as e:
            return False, [f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"]

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
            response = self.client.GpioWrite(GpioWriteRequest(gpio=gpio, state=state))
            if not response.success:
                return f"{self._get_func_name()} error: {response.message}"
            return None
        except grpc.RpcError as e:
            return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    def gpio_read(self, gpio: int) -> Tuple[Optional[bool], Optional[str]]:
        try:
            response = self.client.GpioRead(GpioReadRequest(gpio=gpio))
            if not response.success:
                return None, f"{self._get_func_name()} error: {response.message}"
            return response.state, None
        except grpc.RpcError as e:
            return None, f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
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

    # # -----------------------------------------------------------------------------
    # #                                                                        Motion
    # # ---------------------------------------------------------------------------*/
    # def _get_motion_status(self) -> Tuple[Optional[Any], Optional[str]]:
    #     try:
    #         response = self.client.GetMotionStatus(pbEmpty())
    #         if not response.success:
    #             return None, f"{self._get_func_name()} error: {response.message}"
    #         return response.status, None
    #     except grpc.RpcError as e:
    #         return (
    #             None,
    #             f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}",
    #         )
    #     except Exception as e:
    #         return None, f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # def motion_home(self) -> Optional[str]:
    #     try:
    #         status, err = self._get_motion_status()
    #         if err != None:
    #             return f"An error ocurred getting the motion status {err}"

    #         if status != MotionStatus.MOTION_STATUS_IDLE:
    #             return f"Cannot home device while in {status} state"

    #         response = self.client.MotionHome(pbEmpty())
    #         if not response.success:
    #             return None, f"{self._get_func_name()} error: {response.message}"
    #         return None
    #     except grpc.RpcError as e:
    #         return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
    #     except Exception as e:
    #         return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # def motion_trigger(self, num_cycles: int, cycle_time_seconds: int) -> Optional[str]:
    #     try:
    #         status, err = self._get_motion_status()
    #         if err != None:
    #             return f"An error ocurred getting the motion status {err}"

    #         if status != MotionStatus.MOTION_STATUS_IDLE:
    #             return f"Cannot home device while in {status} state"

    #         response = self.client.MotionTrigger(
    #             MotionTriggerRequest(
    #                 num_cycles=num_cycles,
    #                 cycle_time_seconds=cycle_time_seconds,
    #             )
    #         )
    #         if not response.success:
    #             return None, f"{self._get_func_name()} error: {response.message}"
    #         return None
    #     except grpc.RpcError as e:
    #         return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
    #     except Exception as e:
    #         return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # def motion_continuous(
    #     self, duration_seconds: Optional[int] = None, duration_hours: Optional[int] = None
    # ) -> Optional[str]:
    #     # Ensure that only one of the two arguments is set
    #     if (duration_seconds is not None and duration_hours is not None) or (
    #         duration_seconds is None and duration_hours is None
    #     ):
    #         return f"{self._get_func_name()} error: You must specify either 'duration_hours' or 'duration_seconds', but not both."

    #     try:
    #         status, err = self._get_motion_status()
    #         if err != None:
    #             return f"An error ocurred getting the motion status {err}"

    #         if status != MotionStatus.MOTION_STATUS_IDLE:
    #             return f"Cannot home device while in {status} state"

    #         # Set the appropriate field based on the user input
    #         if duration_seconds is not None:
    #             request = MotionContinuousRequest(duration_seconds=duration_seconds)
    #         else:
    #             request = MotionContinuousRequest(duration_hours=duration_hours)

    #         response: MotionContinuousResponse = self.client.MotionContinuous(request)

    #         if not response.success:
    #             return f"{self._get_func_name()} error: {response.message}"

    #         return None

    #     except grpc.RpcError as e:
    #         return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
    #     except Exception as e:
    #         return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # def motion_stop(self) -> Optional[str]:
    #     try:
    #         status, err = self._get_motion_status()
    #         if err != None:
    #             return f"An error ocurred getting the motion status {err}"

    #         # Check if we're already stopped
    #         if status == MotionStatus.MOTION_STATUS_IDLE:
    #             return None

    #         response = self.client.MotionStop(pbEmpty())
    #         if not response.success:
    #             return None, f"{self._get_func_name()} error: {response.message}"
    #         return None
    #     except grpc.RpcError as e:
    #         return f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
    #     except Exception as e:
    #         return f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # -----------------------------------------------------------------------------
    #                                                                        Motion
    # ---------------------------------------------------------------------------*/
    def get_motion_status(self) -> Tuple[Optional[MotionStatus], Optional[str]]:
        try:
            response = self.client.GetMotionStatus(Empty())
            if not response.success:
                return None, f"{self._get_func_name()} error: {response.message}"
            return response.status, None
        except grpc.RpcError as e:
            return None, f"gRPC error for {self._get_func_name()} at {self.config.net.addr}. Error: {str(e.details())}"
        except Exception as e:
            return None, f"Unexpected error in {self._get_func_name()} at {self.config.net.addr}: {str(e)}"

    # # # -----------------------------------------------------------------------------
    # # #                                                                       J-Links
    # # # ---------------------------------------------------------------------------*/

    # # # -----------------------------------------------------------------------------
    # # #                                                                  UART Streams
    # # # ---------------------------------------------------------------------------*/
