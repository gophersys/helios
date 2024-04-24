# App includes
from src.tests.core import *

# Protocol includes
from protos.cluster_runner.cluster_runner_pb2 import (
    GpioWriteRequest, GpioWriteResponse,
    GpioReadRequest, GpioReadResponse,
    AdcReadRequest, AdcReadResponse,
    DutPowerEnableRequest, DutPowerEnableResponse,
    DutVoltageSetRequest, DutVoltageSetResponse,
    DutCurrentReadRequest, DutCurrentReadResponse,
    DutVoltageReadRequest, DutVoltageReadResponse
)

# Test includes
from .gpio import *

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