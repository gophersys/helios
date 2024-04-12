# Standard libraryes
import hashlib
import os
import time
import logging
import subprocess
import threading

# 3rd party libraries
import grpc
import typer
from typing import Optional, Tuple, Literal
from rich import print as rprint
from rich.progress import Progress

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

# Assuming SERVER_ADDRESSES is a list of your server addresses
# SERVER_ADDRESSES = ['control-plane:12345', 'slot-2:12345', 'slot-3:12345', 'slot-4:12345', 'slot-5:12345']

SERVER_ADDRESSES = ['slot-5:12345']


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

# -------------------------------------------------------------------------------------------------
#                                                                             Fixture Configuration
# -----------------------------------------------------------------------------------------------*/

def config_gpio(server: ClusterRunnerStub, gpio:Gpio, type:GpioType, resistor:GpioResistorConfig) -> bool:
    # Execute RPC with provided channel and delay
    response = server.GpioConfig(GpioConfigRequest(gpio=gpio, type=type, resistor=resistor))
    
    if response.success:
        logging.debug(f"GPIO configuration successful for GPIO {gpio}, type: {type}")
    else:
        logging.error(f"Error: {response.error}, for GPIO {gpio}, type: {type}")
        return False
    
    return True

def config_fixture(server: ClusterRunnerStub) -> bool:
    # Configure all our GPIOs needed
    if not config_gpio(server, TP50_HARD_RESET, GpioType.GPIO_OUTPUT, GpioResistorConfig.GPIO_RESISTOR_PULL_UP):
        return False
 
    if not config_gpio(server, TP49_CHRG_DET, GpioType.GPIO_INPUT, GpioResistorConfig.GPIO_RESISTOR_PULL_DOWN):
        return False
    
    if not config_gpio(server, TP12_UVP_N, GpioType.GPIO_INPUT, GpioResistorConfig.GPIO_RESISTOR_PULL_UP):
        return False
    
    if not config_gpio(server, TP1_3V3_PSM, GpioType.GPIO_INPUT, GpioResistorConfig.GPIO_RESISTOR_PULL_DOWN):
        return False

    return True

# -------------------------------------------------------------------------------------------------
#                                                                                       RPC Helpers
# -----------------------------------------------------------------------------------------------*/
def enable_power(server: ClusterRunnerStub) -> bool:
    response:DutPowerEnableResponse = server.DutPowerEnable(DutPowerEnableRequest(enable=True))
    if not response.success:
        logging.error(f"DutChargePowerEnable Error: {response.error}")
        return False    
    
    return True

def disable_power(server: ClusterRunnerStub) -> bool:
    response:DutPowerEnableResponse = server.DutPowerEnable(DutPowerEnableRequest(enable=False))
    if not response.success:
        logging.error(f"DutChargePowerEnable Error: {response.error}")
        return False    
    
    return True
    
def set_vbat(server: ClusterRunnerStub, voltage: float) -> bool:
    disable_power(server)

    # Set the power
    response:DutVoltageSetResponse = server.DutVoltageSet(DutVoltageSetRequest(voltage=voltage))
    if not response.success:
        logging.error(f"DutVoltageSet Error: {response.error}")
        return False
    
    enable_power(server)  

    return True

def set_5vin(server: ClusterRunnerStub, state: bool) -> bool:
    response:DutPowerEnableResponse = server.DutChargePowerEnable(DutPowerEnableRequest(enable=state))
    if not response.success:
        logging.error(f"DutPowerEnable Error: {response.error}")
        return False
    
    return True

def set_hard_reset(server: ClusterRunnerStub, state: bool) -> bool:
    response:GpioWriteResponse = server.GpioWrite(GpioWriteRequest(gpio=TP50_HARD_RESET, state=state))
    if not response.success:
        logging.error(f"GpioWrite for {TP50_HARD_RESET} Error: {response.error}")
        return False

    return True

def read_vin(server: ClusterRunnerStub) -> Tuple[bool, float]:
    response = server.AdcRead(AdcReadRequest(channel=TP52_VIN, delayMs=ADC_READ_DELAY_MS))
    if not response.success:
        logging.error(f"AdcRead Channel {TP52_VIN} Error: {response.error}")
        return False, 0.0  # Return a tuple with False and a default voltage value, e.g., 0.0
    
    return True, response.voltage

def read_3v3(server:ClusterRunnerStub) -> Tuple[bool, float]:
    response:AdcReadResponse = server.AdcRead(AdcReadRequest(channel=TP11_3V3, delayMs=ADC_READ_DELAY_MS))
    if not response.success:
        logging.error(f"AdcRead Channel {TP11_3V3} Error: {response.error}")
        return False
    
    return True, response.voltage

def read_voltage(server:ClusterRunnerStub) -> Tuple[bool, float]:
    response:DutVoltageReadResponse = server.DutVoltageRead(DutVoltageReadRequest())
    if not response.success:
        logging.error(f"DutCurrentRead Error: {response.error}")
        return False
    
    return True, float(response.voltage_mv * 1000)

def read_vbat(server:ClusterRunnerStub) -> Tuple[bool, float]:
    response:DutVoltageReadResponse = server.DutVoltageRead(DutVoltageReadRequest())
    if not response.success:
        logging.error(f"DutVoltageRead Error: {response.error}")
        return False
    
    return True, float(response.voltage_mv / 1000)

def read_vbckp(server:ClusterRunnerStub) -> Tuple[bool, float]:
    response:AdcReadResponse = server.AdcRead(AdcReadRequest(channel=TP30_VBCKP, delayMs=ADC_READ_DELAY_MS))
    if not response.success:
        logging.error(f"AdcRead Channel {TP30_VBCKP} Error: {response.error}")
        return False
    
    return True, response.voltage

def read_uvp_n(server:ClusterRunnerStub) -> Tuple[bool, bool]:
    response:GpioReadResponse = server.GpioRead(GpioReadRequest(gpio=TP12_UVP_N))
    if not response.success:
        logging.error(f"GpioRead for {TP12_UVP_N} Error: {response.error}")
        return False, False
    
    return True, response.state

def read_current(server:ClusterRunnerStub) -> Tuple[bool, float]:
    response:DutCurrentReadResponse = server.DutCurrentRead(DutCurrentReadRequest())
    if not response.success:
        logging.error(f"DutCurrentRead Error: {response.error}")
        return False
    
    return True, float(response.current_ma / 1000)

def read_chrg_det(server: ClusterRunnerStub) -> Tuple[bool, float]:
    response:GpioReadResponse = server.GpioRead(GpioReadRequest(gpio=TP49_CHRG_DET))
    if not response.success:
        logging.error(f"GpioRead for {TP49_CHRG_DET} Error: {response.error}")
        return False
    
    return True, response.state

def read_all(server: ClusterRunnerStub) -> bool:
    response:AdcReadAllResponse = server.AdcReadAll(AdcReadAllRequest(delayMs=ADC_READ_DELAY_MS))
    if not response.success:
        logging.error(f"AdcReadAll Error: {response.error}")
        return False

    print(f"TP11_3V3: {response.voltage[0]}")
    print(f"TP52_VIN: {response.voltage[1]}")
    print(f"TP30_VBCKP: {response.voltage[2]}")
    print(f"TP7_VBAT_MEAS: {response.voltage[3] * 17.5}")
    read_voltage(server)
    print(f"TP24_3V3_GPS: {response.voltage[4]}")

    return True, response.voltage

# -------------------------------------------------------------------------------------------------
#                                                                                            Checks
# -----------------------------------------------------------------------------------------------*/
# Value for test 2.d
NEAR_ZERO_CURRENT_A=0.01

# Values for test 4.f.
EXPECTED_CURRENT_MIN_MA=10
EXPECTED_CURRENT_MAX_MA=100

# Number of seconds to wait for VIN to settle
VIN_ITERATIONS=15

def check_step_2(server: ClusterRunnerStub) -> bool:
     # 2.d. Ensure near-zero current consumption
    voltage_success, voltage_value = read_voltage(server)
    if not voltage_success:
        logging.error("Step 2.d failed: Error reading voltage consumption")

    # 2.a. Ensure +VIN test point voltage is below 0.3V
    iteration = 0
    success = False
    while iteration < VIN_ITERATIONS:
        iteration = iteration + 1
        vin_success, vin_value = read_vin(server)
        if not vin_success:
            logging.error("Step 2.a failed: Error reading +VIN test point voltage")
            return False
        elif vin_value >= 0.3:
            logging.debug(f"Step 2.a: Iteration {iteration} = {vin_value}V")
            time.sleep(1)
        else:
            logging.debug(f"Step 2.a success: Expected +VIN < 0.3V, Actual +VIN = {vin_value}V")
            success = True
            break
    
    if not success: 
        logging.error(f"Step 2.a failed: Expected +VIN < 0.3V, Actual +VIN = {vin_value}V")
        return False
    
    #TODO: Update documentation to remove this test
    # 2.b. Ensure +VBCKP test point voltage is below 0.3V
    # vbckp_success, vbckp_value = read_vbckp(server)
    # if not vbckp_success:
    #     logging.error("Step 2.b failed: Error reading +VBCKP test point voltage")
    #     return False
    # elif vbckp_value >= 0.3:
    #     logging.error(f"Step 2.b failed: Expected +VBCKP < 0.3V, Actual +VBCKP = {vbckp_value}V")
    #     return False
    # else:
    #     logging.debug(f"Step 2.b success: Expected +VBCKP < 0.3V, Actual +VBCKP = {vbckp_value}V")

    # 2.c. Ensure UVP_N test point voltage is digital low
    uvp_n_success, uvp_n_value = read_uvp_n(server)
    if not uvp_n_success:
        logging.error("Step 2.c failed: Error reading UVP_N test point voltage")
        return False
    elif uvp_n_value is not False:  # Assuming digital low is < 0.3V
        logging.error(f"Step 2.c failed: Expected UVP_N digital low, Actual UVP_N = {uvp_n_value}")
        return False
    else:
        logging.debug(f"Step 2.c success: Expected UVP_N digital low, Actual UVP_N = {uvp_n_value}")

    # 2.d. Ensure near-zero current consumption
    current_success, current_value = read_current(server)
    if not current_success:
        logging.error("Step 2.d failed: Error reading current consumption")
        return False
    elif current_value > NEAR_ZERO_CURRENT_A:
        logging.error(f"Step 2.d failed: Expected near-zero current consumption, Actual current = {current_value}A")
        return False
    else:
        logging.debug(f"Step 2.d success: Expected near-zero current, Actual current = {current_value}A")

    return True

def check_step_4(server: ClusterRunnerStub) -> bool:
    # Assuming VBAT_MEAS should match the last set VBAT value, for this example, let's say it was 3.2V.
    expected_vbat_value = 3.2

    # 4.a. Ensure +VIN test point voltage is the same as +BATT
    vin_success, vin_value = read_vin(server)
    vbat_success, vbat_value = read_vbat(server)
    if not vin_success or not vbat_success:
        logging.error("Step 4.a failed: Error reading +VIN or +VBAT test point voltage")
        return False
    elif abs(vin_value - vbat_value) > 0.1:
        logging.error(f"Step 4.a failed: Expected +VIN = +VBAT, Actual +VIN = {vin_value}V, +VBAT = {vbat_value}mV")
        return False
    else:
        logging.debug(f"Step 4.a success: Expected +VIN = +VBAT, Actual +VIN = {vin_value}V, +VBAT = {vbat_value}V")

    # 4.b. Ensure regulated +3.3V test point voltage is within 3.2V - 3.4V
    _3v3_success, _3v3_value = read_3v3(server)
    if not _3v3_success:
        logging.error("Step 4.b failed: Error reading +3.3V test point voltage")
        return False
    elif not 3.2 <= _3v3_value <= 3.4:
        logging.error(f"Step 4.b failed: Expected +3.3V within 3.2V - 3.4V, Actual +3.3V = {_3v3_value}V")
        return False
    else:
        logging.debug(f"Step 4.b success: Expected +3.3V within 3.2V - 3.4V, Actual +3.3V = {_3v3_value}V")

    # 4.c. Ensure +VBCKP test point voltage is within +2.4V - 2.6V
    vbckp_success, vbckp_value = read_vbckp(server)
    if not vbckp_success:
        logging.error("Step 4.c failed: Error reading +VBCKP test point voltage")
        return False
    elif not 2.4 <= vbckp_value <= 2.6:
        logging.error(f"Step 4.c failed: Expected +VBCKP within 2.4V - 2.6V, Actual +VBCKP = {vbckp_value}V")
        return False
    else:
        logging.debug(f"Step 4.c success: Expected +VBCKP within 2.4V - 2.6V, Actual +VBCKP = {vbckp_value}V")

    #TODO: Update documentation to remove this test
    # 4.d. Ensure VBAT_MEAS is correct voltage
    # vbat_success, vbat_value = read_vbat(server)
    # if not vbat_success:
    #     logging.error("Step 4.d failed: Error reading VBAT_MEAS")
    #     return False
    # elif vbat_value != expected_vbat_value:
    #     logging.error(f"Step 4.d failed: Expected VBAT_MEAS = {expected_vbat_value}V, Actual VBAT_MEAS = {vbat_value}V")
    #     return False
    # else:
    #     logging.debug(f"Step 4.d success: Expected VBAT_MEAS = {expected_vbat_value}V, Actual VBAT_MEAS = {vbat_value}V")

    # print(f"set the breakpoint")
    # time.sleep(5)

    # 4.e. Ensure UVP_N test point voltage is digital high
    uvp_n_success, uvp_n_value = read_uvp_n(server)
    if not uvp_n_success:
        logging.error("Step 4.e failed: Error reading UVP_N test point voltage")
        return False
    elif uvp_n_value < 0.8:  # Assuming digital high is >= 0.8V
        logging.error(f"Step 4.e failed: Expected UVP_N digital high, Actual UVP_N = {uvp_n_value}")
        return False
    else:
        logging.debug(f"Step 4.e success: Expected UVP_N digital high, Actual UVP_N = {uvp_n_value}")

    # 4.f. Ensure proper current consumption (no short circuits)
    current_success, current_value = read_current(server)
    current_value = current_value * 1000 # we comapre in mA
    if not current_success:
        logging.error("Step 4.f failed: Error reading current consumption")
        return False
    if not EXPECTED_CURRENT_MIN_MA <= current_value <= EXPECTED_CURRENT_MAX_MA:
        logging.error(f"Step 4.f failed: Expected current consumption within normal range, Actual current = {current_value}A")
        return False
    else:
        logging.debug(f"Step 4.f success: Expected current within normal range, Actual current = {current_value}mA")

    return True

def check_step_6(server: ClusterRunnerStub) -> bool:
    # 6.a. Ensure +VIN test point voltage is the same as +BATT
    vin_success, vin_value = read_vin(server)
    vbat_success, vbat_value = read_vbat(server)
    if not vin_success or not vbat_success:
        logging.error("Step 6.a failed: Error reading +VIN or +VBAT test point voltage")
        return False
    elif abs(vin_value - vbat_value) > 0.1:
        logging.error(f"Step 6.a failed: Expected +VIN = +VBAT, Actual +VIN = {vin_value}V, +VBAT = {vbat_value}V")
        return False
    else:
        logging.debug(f"Step 6.a success: +VIN = +VBAT as expected, Actual +VIN = {vin_value}V, +VBAT = {vbat_value}V")
    return True

def check_step_8(server: ClusterRunnerStub) -> bool:
    # 8.a. Ensure +VIN test point voltage is below 0.3V
    iteration = 0
    success = False
    while iteration < VIN_ITERATIONS:
        iteration = iteration + 1
        vin_success, vin_value = read_vin(server)
        if not vin_success:
            logging.error("Step 8.a failed: Error reading +VIN test point voltage")
            return False
        elif vin_value >= 0.3:
            logging.debug(f"Step 8.a: Iteration {iteration} = {vin_value}V")
            time.sleep(1)
        else:
            logging.debug(f"Step 8.a success: +VIN < 0.3V as expected, Actual +VIN = {vin_value}V")
            success = True
            break
    
    if not success: 
        logging.error(f"Step 8.a failed: Expected +VIN < 0.3V, Actual +VIN = {vin_value}V")
        return False

    uvp_n_success, uvp_n_value = read_uvp_n(server)
    if not uvp_n_success:
        logging.error("Error reading UVP_N test point voltage")
        return False
    elif uvp_n_value >= 0.3:  # Assuming digital low is < 0.3V
        logging.error(f"Step 8.b failed: Expected UVP_N digital low, Actual UVP_N = {uvp_n_value}V")
        return False
    else:
        logging.debug(f"Step 8.b success: UVP_N is digital low as expected, Actual UVP_N = {uvp_n_value}V")
    return True

def check_step_10(server: ClusterRunnerStub) -> bool:
    # 10.a. Ensure +VIN test point voltage is 5V.
    iteration = 0
    success = False
    while iteration < VIN_ITERATIONS:
        iteration = iteration + 1
        vin_success, vin_value = read_vin(server)
        if not vin_success:
            logging.error("Step 10.a failed: Error reading +VIN test point voltage")
            return False
        elif vin_value < 4.5:
            logging.debug(f"Step 10.a: Iteration {iteration} = {vin_value}V")
            time.sleep(1)
        else:
            logging.debug(f"Step 10.a success: +VIN ~ 5V as expected, Actual +VIN = {vin_value}V")
            success = True
            break
    
    if not success: 
        logging.error(f"Step 10.a failed: Expected +VIN ~ 5V, Actual +VIN = {vin_value}V")
        return False

    # 10.b. Ensure regulated +3.3V test point voltage is within 3.2V – 3.4V.
    _3v3_success, _3v3_value = read_3v3(server)
    if not _3v3_success:
        logging.error("Step 10.b Error reading +3.3V test point voltage")
        return False
    elif not 3.2 <= _3v3_value <= 3.4:
        logging.error(f"Step 10.b failed: Expected +3.3V within 3.2V – 3.4V, Actual +3.3V = {_3v3_value}V")
        return False
    else:
        logging.debug(f"Step 10.b success: +3.3V within 3.2V – 3.4V as expected, Actual +3.3V = {_3v3_value}V")

    # 10.c. Ensure +VBCKP test point voltage is within +2.4V – 2.6V.
    vbckp_success, vbckp_value = read_vbckp(server)
    if not vbckp_success:
        logging.error("Step 10.c failed: Error reading +VBCKP test point voltage")
        return False
    elif not 2.4 <= vbckp_value <= 2.6:
        logging.error(f"Step 10.c failed: Expected +VBCKP within 2.4V – 2.6V, Actual +VBCKP = {vbckp_value}V")
        return False
    else:
        logging.debug(f"Step 10.c success: +VBCKP within 2.4V – 2.6V as expected, Actual +VBCKP = {vbckp_value}V")

    # 10.d. Ensure UVP_N test point voltage is digital high.
    uvp_n_success, uvp_n_value = read_uvp_n(server)
    if not uvp_n_success:
        logging.error("Step 10.d failed: Error reading UVP_N test point voltage")
        return False
    elif uvp_n_value is True:
        logging.error(f"Step 10.d failed: Expected UVP_N digital high, Actual UVP_N = {uvp_n_value}V")
        return False
    else:
        logging.debug(f"Step 10.d success: UVP_N is digital high as expected, Actual UVP_N = {uvp_n_value}V")

    # 10.e. Ensure CHRG_DET test point is digital low.
    chrg_det_success, chrg_det_value = read_chrg_det(server)
    if not chrg_det_success:
        logging.error("Step 10.e failed: Error reading CHRG_DET test point")
        return False
    elif chrg_det_value >= 0.8:  # Assuming digital low is < 0.8V
        logging.error(f"Step 10.e failed: Expected CHRG_DET digital low, Actual CHRG_DET = {chrg_det_value}V")
        return False
    else:
        logging.debug(f"Step 10.e success: CHRG_DET is digital low as expected, Actual CHRG_DET = {chrg_det_value}V")

    return True

# -------------------------------------------------------------------------------------------------
#                                                                             Electrical Power Test
# -----------------------------------------------------------------------------------------------*/
STEP_SETTLE_DELAY_S=2

def electrical_power_test(server: ClusterRunnerStub) -> bool:
    # 1. Apply +2.5V to +BATT test point
    if not set_vbat(server, 2.5):
        logging.error("Step 1: Apply +2.5V to +BATT test point, failed")
        return False
    
    time.sleep(STEP_SETTLE_DELAY_S)

    # 2. Ensure device electrical state
    if not check_step_2(server):
        logging.error("Step 2: Ensure device electrical state, failed")
        return False

    # 3. Apply +3.2 to +BATT test point
    if not set_vbat(server, 3.2):
        logging.error("Step 3: Apply +3.2 to +BATT test point, failed")
        return False

    time.sleep(STEP_SETTLE_DELAY_S)

    # 4. Ensure device electrical state
    if not check_step_4(server):
        logging.error("Step 4: Ensure device electrical state, failed")
        return False
    
    # 5. Apply +3.6V to +BATT test point
    if not set_vbat(server, 3.6):
        logging.error("Step 5: Apply +3.6V to +BATT test point, failed")
        return False

    time.sleep(STEP_SETTLE_DELAY_S)

    # 6. Ensure device eletrical state
    if not check_step_6(server):
        logging.error("Step 6: Ensure device eletrical state, failed")
        return False

    # 7. Assert HARD_RESET test point to digital high
    if not set_hard_reset(server, True):
        logging.error("Step 7: Assert HARD_RESET test point to digital high, failed")
        return False

    time.sleep(STEP_SETTLE_DELAY_S)

    # 8. Ensure device electrical state
    if not check_step_8(server):
        logging.error("Step 8: Ensure device electrical state, failed")
        return False

    # 9. Apply +5V to +5V_IN test point
    if not set_5vin(server, True):
        logging.error("Step 9: Apply +5V to +5V_IN test point, failed")
        return False

    time.sleep(STEP_SETTLE_DELAY_S)

    # 10. Ensure device electrical state.
    if not check_step_10(server):
        logging.error("Step 10: Ensure device electrical state, failed")
        return False

    # 11.Set HARD_RESET test point to digital low.
    if not set_hard_reset(server, False):
        logging.error("Step 11: Set HARD_RESET test point to digital low, failed")
        return False

    # 12.Remove +5V.
    if not set_5vin(server, False):
        logging.error("Step 12: Remove +5V, failed")
        return False

    return True

# -------------------------------------------------------------------------------------------------
#                                                                                        Deployment
# -----------------------------------------------------------------------------------------------*/

# Path to the Kubernetes deployment file
DEPLOYMENT_FILE = '/workspaces/concord/apps/fixtures/mtib_runner/deploy/deployment.yaml'

# Name of the deployment
DEPLOYMENT_NAME = 'mtib-pos0x'

# Namespace where the deployment is applied, adjust if using a specific namespace
NAMESPACE = 'default'

def run_command(command):
    """Run a shell command."""
    try:
        output = subprocess.check_output(command, stderr=subprocess.STDOUT, shell=True, universal_newlines=True)
        return True, output
    except subprocess.CalledProcessError as e:
        return False, e.output

def apply_deployment():
    """Apply the Kubernetes deployment."""
    cmd = f'kubectl apply -f {DEPLOYMENT_FILE}'
    success, output = run_command(cmd)
    print(output)
    return success

def delete_deployment():
    """Delete the Kubernetes deployment if it exists."""
    # Check if the deployment exists
    check_cmd = f'kubectl get deployment {DEPLOYMENT_NAME} --namespace={NAMESPACE}'
    check_success, check_output = run_command(check_cmd)
    
    if check_success:
        # Deployment exists, proceed to delete
        delete_cmd = f'kubectl delete deployment {DEPLOYMENT_NAME} --namespace={NAMESPACE}'
        delete_success, delete_output = run_command(delete_cmd)
        print(delete_output)
        return delete_success
    else:
        # Deployment does not exist, no need to delete
        print("Deployment does not exist, skipping delete.")
        return True  # Considered a success because there's nothing to delete

def wait_for_deployment_ready(timeout=10):
    """Wait for the deployment to be ready, with a timeout."""
    start_time = time.time()
    print("Waiting for deployment to be ready...")
    while True:
        # Adjusted command for better compatibility
        cmd = f"kubectl get deployment {DEPLOYMENT_NAME} --namespace={NAMESPACE} -o jsonpath='{{.status.conditions[?(@.type==\"Available\")].status}}'"
        success, output = run_command(cmd)
        if output.strip() == "True":
            print("Deployment is ready.")
            break
        elif time.time() - start_time > timeout:
            print("Timeout waiting for deployment to become ready.")
            break
        else:
            time.sleep(2)  # Check every 2 seconds

# -------------------------------------------------------------------------------------------------
#                                                                                 Firmware flashing
# -----------------------------------------------------------------------------------------------*/

NRF9160_MODEM_FIRMWARE_FILE = "mfw_nrf9160_1.3.5.zip"
NRF9160_FIRMWARE_FILE = "Sigma5_9160_Eng_SSv0p9_1_Mfg.hex"
NRF82840_FIRMWARE_FILE = "Sigma5_52840_Eng_1.hex"
NRF9160_BUS_NUMBER = 2
NRF82840_BUS_NUMBER = 3

def flash_device(server, server_address: str,  firmware_file: str, device: DeviceType, is_modem_fw: Optional[bool]) -> bool:
    """Utility function to flash a firmware file to a specific device."""
    try:
        logging.info(f"Flashing {firmware_file} on {server_address}")

        # Prepare the device information and flash request
        request = FlashHexFileRequest(fileName=firmware_file, device=device, isModemFw=is_modem_fw)

        # Measure the flashing process time
        start_time = time.time()
        response = server.FlashHexFile(request)
        duration_seconds = time.time() - start_time

        if response.success:
            logging.info(f"Flash successful for {firmware_file}. Time taken: {duration_seconds:.2f} seconds")
            return True
        else:
            logging.error(f"Flash failed for {device}: {response.error}")
            return False
    except Exception as e:
        logging.error(f"Exception while flashing {device}: {e}")
        return False

def firmware_flashing(server: ClusterRunnerStub, server_address: str) -> bool:
    """Flashes firmware to specified devices."""
    try:
        # Flash nRF9160 modem firmware
        if not flash_device(server, server_address, NRF9160_MODEM_FIRMWARE_FILE, DeviceType.DEVICE_NRF9160, True):
            logging.error("Failed to flash nRF9160 modem firmware.")
            return False
        
         # Flash nRF9160 firmware
        if not flash_device(server, server_address, NRF9160_FIRMWARE_FILE, DeviceType.DEVICE_NRF9160, False):
            logging.error("Failed to flash nRF9160 firmware.")
            return False

        # Flash nRF82840 firmware
        if not flash_device(server, server_address, NRF82840_FIRMWARE_FILE, DeviceType.DEVICE_NRF82840, False):
            logging.error("Failed to flash nRF82840 firmware.")
            return False

        logging.info("Firmware flashing successful for both devices.")
        return True
    except Exception as e:
        logging.error(f"Unexpected error during firmware flashing: {e}")
        return False

# -------------------------------------------------------------------------------------------------
#                                                                                             Tests
# -----------------------------------------------------------------------------------------------*/

def run_tests(server_address):
    """Function to test each server."""
    channel = grpc.insecure_channel(server_address)
    server = ClusterRunnerStub(channel)

    if not config_fixture(server):
        logging.error(f"Could not configure test fixture for {server_address}")
        return

    disable_power(server)
    set_5vin(server, False)
    time.sleep(1)

    logging.info(f"Starting test for {server_address}")

    if not electrical_power_test(server):
        time.sleep(5)
        logging.error(f"Electrical Power Test failed for {server_address}")
        disable_power(server)
        set_5vin(server, False)
        if not set_hard_reset(server, False):
            logging.error(f"Assert HARD_RESET test point to digital low, failed for {server_address}")
    else:
        logging.info(f"Test passed for {server_address}!, Flashing firmware")
        
        # Run the flashing process
        if not firmware_flashing(server, server_address):
            logging.error(f"Error flashing firmware to {server_address}")
            return 0

        logging.info(f"All tests passed and firmware flashed to boards for {server_address}")

# -------------------------------------------------------------------------------------------------
#                                                                                              Main
# -----------------------------------------------------------------------------------------------*/
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)

    # # Delete any current deployments running
    # if not delete_deployment():
    #     print("Failed to apply deployment.")
    #     exit(1)

    # # Apply the deployment
    # if not apply_deployment():
    #     print("Failed to apply deployment.")
    #     exit(1)
    
    threads = []
    for address in SERVER_ADDRESSES:
        thread = threading.Thread(target=run_tests, args=(address,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    logging.info("All tests completed.")
    

