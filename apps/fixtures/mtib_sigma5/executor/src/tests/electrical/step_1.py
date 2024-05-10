# Standard includes
import time

# Corekinect libraries
from src.tests.core import *

# Test includes
from .rpcs import *

# -------------------------------------------------------------------------------------------------
#                                                                                    Configurations
# -----------------------------------------------------------------------------------------------*/

# Number of seconds to wait for VIN to settle
VIN_ITERATIONS=15

# Value for test 2.d
NEAR_ZERO_CURRENT_A=0.01

# -------------------------------------------------------------------------------------------------
#                                                                                           Handler
# -----------------------------------------------------------------------------------------------*/
def electrical_test_step_1_handler(runner:str) -> TestStepResult:
    # Declare the return object with default data
    result:TestStepResult = TestStepResult(
        execOk = False,
        success = False,
    )
    
    # # Apply +2.5V to the +BATT test point.
    # error:str = set_vbat(runner, 2.5)
    # if error:
    #     return TestStepResult(error=error)
    
    # # a. Ensure +VIN test point voltage is below 0.3V
    # iteration:int = 0
    # success:bool = False
    # while iteration < VIN_ITERATIONS:
    #     iteration = iteration + 1
    #     error, vin_value = read_vin(runner)
    #     if error:
    #         return TestStepResult(error=f"Step a failed: Error reading +VIN test point voltage: {error}")
    #     elif vin_value >= 0.3:
    #         time.sleep(1)
    #     else:
    #         success = True
    #         break
    
    # if not success: 
    #     return TestStepResult(execOk=True,
    #                           error=f"Step 2.a failed: Expected +VIN < 0.3V, Actual +VIN = {vin_value}V")

    # # 2.c. Ensure UVP_N test point voltage is digital low
    # error, uvp_n_value = read_uvp_n(runner)
    # if error:
    #     return TestStepResult(error=f"Step a failed: Error reading UVP_N test point voltage: {error}")
    # elif uvp_n_value is not False:  # Assuming digital low is < 0.3V
    #     return TestStepResult(execOk=True,
    #                           error=f"Step 2.c failed: Expected UVP_N digital low, Actual UVP_N = {uvp_n_value}")
        
    # # 2.d. Ensure near-zero current consumption
    # error, current_value = read_current(runner)
    # if error:
    #     return TestStepResult(error=f"Step 2.d failed: Error reading current consumption: {error}")
    # elif current_value > NEAR_ZERO_CURRENT_A:
    #     return TestStepResult(execOk=True,
    #                           error=f"Step 2.d failed: Expected near-zero current consumption, Actual current = {current_value}A")
    
    # Succeeded
    result.success = True
    
    return result

# -------------------------------------------------------------------------------------------------
#                                                                                        Definition
# -----------------------------------------------------------------------------------------------*/
electrical_test_step_1:TestStep = TestStep(
    info=StepInfo(
        sequence = 1,
        name = "First step",
        description = "Returns immediately"
    ),
    handler=electrical_test_step_1_handler
)
