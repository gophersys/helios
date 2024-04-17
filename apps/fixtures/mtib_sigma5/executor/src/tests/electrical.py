# Standard includes
import uuid
import time

# App includes
from src.tests.core import *

# Protocol includes
from protos.cluster_runner.cluster_runner_pb2_grpc import ClusterRunnerStub
from protos.cluster_runner.cluster_runner_pb2 import (
    Gpio, GpioType, GpioResistorConfig,
    GpioWriteRequest, GpioWriteResponse,
    GpioConfigRequest, GpioConfigResponse,
    GpioReadRequest, GpioReadResponse,
    AdcChannel, AdcReadRequest, AdcReadResponse,
    AdcReadAllRequest, AdcReadAllResponse, 
    AltimeterReadRequest, AltimeterReadResponse,
    FlashHexFileRequest, FlashHexFileResponse, DeviceType,
    ListFwFilesRequest, ListFwFilesResponse, FwFileInfo,
    UploadFwFileRequest, UploadFwFileResponse,
    DeleteFwFileRequest, DeleteFwFileResponse,
    DutPowerEnableRequest, DutPowerEnableResponse,
    DutVoltageSetRequest, DutVoltageSetResponse,
    DutCurrentReadRequest, DutCurrentReadResponse,
    DutVoltageReadRequest, DutVoltageReadResponse, 
    DutPowerReadRequest, DutPowerReadResponse,
    AccelReadRequest, AccelReadResponse,
    AccelReadMaxRequest, AccelReadMaxResponse,
    EepromReadRequest, EepromReadResponse,
    EepromWriteRequest, EepromWriteResponse
)

# -------------------------------------------------------------------------------------------------
#                                                                               Test Points Mapping
# -----------------------------------------------------------------------------------------------*/
# Power
# TODO: These may be flipped in the fixture
TP8_BATT=0
TP47_5V_IN=0

# Adc
TP11_3V3=AdcChannel.ADC_CHANNEL_0
TP52_VIN=AdcChannel.ADC_CHANNEL_1
TP30_VBCKP=AdcChannel.ADC_CHANNEL_2
TP7_VBAT_MEAS=AdcChannel.ADC_CHANNEL_3
TP24_3V3_GPS=AdcChannel.ADC_CHANNEL_4

ADC_READ_DELAY_MS=100

# Gpio
TP50_HARD_RESET=Gpio.GPIO_0
TP49_CHRG_DET=Gpio.GPIO_1
TP12_UVP_N=Gpio.GPIO_2
TP1_3V3_PSM=Gpio.GPIO_3

# Number of seconds to wait for VIN to settle
VIN_ITERATIONS=15

# Value for test 2.d
NEAR_ZERO_CURRENT_A=0.01

# Values for test 4.f.
EXPECTED_CURRENT_MIN_MA=10
EXPECTED_CURRENT_MAX_MA=100

# -------------------------------------------------------------------------------------------------
#                                                                                       RPC Helpers
# -----------------------------------------------------------------------------------------------*/
def enable_power(runner:TestRunner) -> str:
    response:DutPowerEnableResponse = runner.stub.DutPowerEnable(DutPowerEnableRequest(enable=True))
    if not response.success:
        return f"DutChargePowerEnable Error: {response.error}"
    
    return ""

def disable_power(runner:TestRunner) -> str:
    response:DutPowerEnableResponse = runner.stub.DutPowerEnable(DutPowerEnableRequest(enable=False))
    if not response.success:
        return f"DutPowerEnable Error: {response.error}"
    
    return ""

def set_vbat(runner:TestRunner, voltage: float) -> str:
    disable_power(runner)

    response:DutVoltageSetResponse = runner.stub.DutVoltageSet(DutVoltageSetRequest(voltage=voltage))
    if not response.success:
        return f"DutVoltageSet Error: {response.error}"
    
    enable_power(runner)  
    return ""

def set_5vin(runner:TestRunner, state: bool) -> str:
    response:DutPowerEnableResponse = runner.stub.DutChargePowerEnable(DutPowerEnableRequest(enable=state))
    if not response.success:
        return f"DutChargePowerEnable failed for state {state} Error: {response.error}"
    
    return ""

def set_hard_reset(runner:TestRunner, state: bool) -> bool:
    response:GpioWriteResponse = runner.stub.GpioWrite(GpioWriteRequest(gpio=TP50_HARD_RESET, state=state))
    if not response.success:
        return f"GpioWrite for {TP50_HARD_RESET} Error: {response.error}"

    return ""

def read_vin(runner:TestRunner) -> Tuple[str, Optional[float]]:
    response = runner.stub.AdcRead(AdcReadRequest(channel=TP52_VIN, delayMs=ADC_READ_DELAY_MS))
    if not response.success:
        return f"AdcRead Channel {TP52_VIN} Error: {response.error}", None
    
    return "", response.voltage

def read_3v3(runner:TestRunner) -> Tuple[str, Optional[float]]:
    response:AdcReadResponse = runner.stub.AdcRead(AdcReadRequest(channel=TP11_3V3, delayMs=ADC_READ_DELAY_MS))
    if not response.success:
        return f"AdcRead Channel {TP11_3V3} Error: {response.error}"
    
    return "", response.voltage

def read_voltage(runner:TestRunner) -> Tuple[str, Optional[float]]:
    response:DutVoltageReadResponse = runner.stub.DutVoltageRead(DutVoltageReadRequest())
    if not response.success:
        return f"DutCurrentRead Error: {response.error}", None
    
    return "", float(response.voltage_mv * 1000)

def read_current(runner:TestRunner) -> Tuple[str, Optional[float]]:
    response:DutCurrentReadResponse = runner.stub.DutCurrentRead(DutCurrentReadRequest())
    if not response.success:
        return f"DutCurrentRead Error: {response.error}", None
    
    return "", float(response.current_ma / 1000)

def read_vbat(runner:TestRunner) -> Tuple[str, Optional[float]]:
    response:DutVoltageReadResponse = runner.stub.DutVoltageRead(DutVoltageReadRequest())
    if not response.success:
        return f"DutVoltageRead Error: {response.error}", None
    
    return "", float(response.voltage_mv / 1000)

def read_vbckp(runner:TestRunner) -> Tuple[str, Optional[float]]:
    response:AdcReadResponse = runner.stub.AdcRead(AdcReadRequest(channel=TP30_VBCKP, delayMs=ADC_READ_DELAY_MS))
    if not response.success:
        return f"AdcRead Channel {TP30_VBCKP} Error: {response.error}", None
    
    return "", response.voltage

def read_uvp_n(runner:TestRunner) -> Tuple[str, Optional[bool]]:
    response:GpioReadResponse = runner.stub.GpioRead(GpioReadRequest(gpio=TP12_UVP_N))
    if not response.success:
        return f"GpioRead for {TP12_UVP_N} Error: {response.error}", None
    
    return "", response.state

def read_chrg_det(runner:TestRunner) -> Tuple[str, Optional[bool]]:
    response:GpioReadResponse = runner.stub.GpioRead(GpioReadRequest(gpio=TP49_CHRG_DET))
    if not response.success:
        return f"GpioRead for {TP49_CHRG_DET} Error: {response.error}", None
    
    return "", response.state
# -------------------------------------------------------------------------------------------------
#                                                                                            Step 1
# -----------------------------------------------------------------------------------------------*/

# Handler definition
def electrical_test_step_1_handler(runner:TestRunner) -> TestStepResult:
    # Declare the return object with default data
    result:TestStepResult = TestStepResult(
        execOk = True,
        error = "",
        success = True,
    )
    
    # Apply +2.5V to the +BATT test point.
    error:str = set_vbat(runner, 2.5)
    if error:
        return TestStepResult(
            execOk = False,
            error = error
        )
    
    error, voltage = read_voltage(runner)
    if error:
        return TestStepResult(
            execOk = False,
            error = error
        )
    
    # a. Ensure +VIN test point voltage is below 0.3V
    iteration:int = 0
    success:bool = False
    while iteration < VIN_ITERATIONS:
        iteration = iteration + 1
        error, vin_value = read_vin(runner)
        if error:
            return TestStepResult(
                execOk=False,
                error=f"Step a failed: Error reading +VIN test point voltage: {error}"
            )
        elif vin_value >= 0.3:
            time.sleep(1)
        else:
            success = True
            break
    
    if not success: 
        return TestStepResult(
            execOk=True,
            error=f"Step 2.a failed: Expected +VIN < 0.3V, Actual +VIN = {vin_value}V",
            success=False,
        )

    # 2.c. Ensure UVP_N test point voltage is digital low
    error, uvp_n_value = read_uvp_n(runner)
    if error:
        return TestStepResult(
            execOk=False,
            error=f"Step a failed: Error reading UVP_N test point voltage: {error}"
        )
    elif uvp_n_value is not False:  # Assuming digital low is < 0.3V
        return TestStepResult(
            execOk=True,
            error=f"Step 2.c failed: Expected UVP_N digital low, Actual UVP_N = {uvp_n_value}",
            success=False,
        )
        
    # 2.d. Ensure near-zero current consumption
    error, current_value = read_current(runner)
    if error:
        return TestStepResult(
            execOk=False,
            error=f"Step 2.d failed: Error reading current consumption: {error}"
        )
    elif current_value > NEAR_ZERO_CURRENT_A:
        return TestStepResult(
            execOk=True,
            error=f"Step 2.d failed: Expected near-zero current consumption, Actual current = {current_value}A",
            success=False,
        )
    
    return result

# Step definition
electrical_test_step_1:TestStep = TestStep(
    info=StepInfo(
        sequence = 1,
        name = "First step",
        description = "The test description"
    ),
    handler=electrical_test_step_1_handler
)

# -------------------------------------------------------------------------------------------------
#                                                                                   Electrical Test
# -----------------------------------------------------------------------------------------------*/
electrical_test:Test = Test(
    info=TestInfo(
        id=str(uuid.uuid4()),
        name="Electrical Test",
        description="This test is a test designed to test the electrical state of a newly manufactured panel",
    ),
    steps=[
        electrical_test_step_1
    ]
)   