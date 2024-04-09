# Standard includes
import logging
import uuid
import time
from typing import Tuple, Optional 

# Test includes
from ..base import *

# Protocol includes
from protos.mtib_controller.mtib_controller_pb2 import (
    TestStepResult
)

# -------------------------------------------------------------------------------------------------
#                                                                                            Step 3
# -----------------------------------------------------------------------------------------------*/
def step_3_handler(runner:ClusterRunner) -> TestStepResult:
    logging.error("oh yea baby im being called 3")

    time.sleep(1)

    return TestStepResult(
        runnerId = runner.info.id, # This is clumsy i dont like it
        execOk = True,
        error = "",
        success = True,
    )
    
step_3:ClusterTestStep = ClusterTestStep(
            info=StepInfo(
                sequence = 3,
                name = "Third step",
                description = "The test description"
            ),
            handler=step_3_handler
        ) 

# -------------------------------------------------------------------------------------------------
#                                                                                            Step 2
# -----------------------------------------------------------------------------------------------*/
def step_2_handler(runner:ClusterRunner) -> TestStepResult:
    logging.error("oh yea baby im being called 2")

    time.sleep(1)

    return TestStepResult(
        runnerId = runner.info.id,
        execOk = True,
        error = "",
        success = True,
    )
    
step_2:ClusterTestStep = ClusterTestStep(
            info=StepInfo(
                sequence = 2,
                name = "Second step",
                description = "The test description"
            ),
            handler=step_2_handler
        ) 

# -------------------------------------------------------------------------------------------------
#                                                                                            Step 1
# -----------------------------------------------------------------------------------------------*/
def step_1_handler(runner:ClusterRunner) -> TestStepResult:
    logging.error("oh yea baby im being called 1")

    return TestStepResult(
        runnerId = runner.info.id,
        execOk = True,
        error = "",
        success = True,
    )
    
step_1:ClusterTestStep = ClusterTestStep(
            info=StepInfo(
                sequence = 1,
                name = "First step",
                description = "The test description"
            ),
            handler=step_1_handler
        ) 

# -------------------------------------------------------------------------------------------------
#                                                                                   Electrical Test
# -----------------------------------------------------------------------------------------------*/
electrical_test:ClusterTest = ClusterTest(
    info = TestInfo(
            id = "d23d0e5b-1123-4219-8ba7-0a6539bb613f",
            name = "Sample Test",
            description = "An example test to register"
    ),
    steps=[
        step_1,
        step_2,
        step_3
    ]
)
