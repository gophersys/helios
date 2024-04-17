# Standard includes
import uuid

# App includes
from src.tests.core import *

# Protocol includes

# -------------------------------------------------------------------------------------------------
#                                                                                            Step 1
# -----------------------------------------------------------------------------------------------*/

# Handler definition
def electrical_test_step_1_handler(runner:TestRunner) -> TestStepResult:
    result:TestStepResult = TestStepResult(
        execOk = True,
        error = "",
        success = True,
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