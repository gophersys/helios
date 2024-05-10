# Standard includes
import time

# Corekinect libraries
from src.tests.core import *

# Test includes
from .rpcs import *

# ----------------------------------------------------------------------------------
#                                                                      Configuration
# --------------------------------------------------------------------------------*/

# ----------------------------------------------------------------------------------
#                                                                      Configuration
# --------------------------------------------------------------------------------*/
def electrical_test_step_2_handler(runner:str) -> TestStepResult:
    # Declare the return object with default data
    result:TestStepResult = TestStepResult(
        execOk = False,
        success = False,
    )
    
    time.sleep(1)
    
    # Succeeded
    result.success = True
    
    return result

# ----------------------------------------------------------------------------------
#                                                                         Definition
# --------------------------------------------------------------------------------*/
electrical_test_step_2:TestStep = TestStep(
    info=StepInfo(
        sequence = 2,
        name = "Second step",
        description = "Delays for 1 second and succeeds"
    ),
    handler=electrical_test_step_2_handler
)
