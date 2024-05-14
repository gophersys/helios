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
def electrical_test_step_4_handler(runner:str) -> TestStepResult:
    # Declare the return object with default data
    result:TestStepResult = TestStepResult(
        execOk = False,
        success = False,
    )
    
    time.sleep(0.5)
    
    # Succeeded
    result.success = True
    
    return result

# ----------------------------------------------------------------------------------
#                                                                         Definition
# --------------------------------------------------------------------------------*/
electrical_test_step_4:TestStep = TestStep(
    info=StepInfo(
        sequence = 4,
        name = "Fourth step",
        description = "Delays for half a second and succeeds"
    ),
    timeout_ms=2000,
    handler=electrical_test_step_4_handler
)
