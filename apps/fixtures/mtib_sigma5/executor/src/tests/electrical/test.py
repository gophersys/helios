# Standard includes
import uuid

# Corekinect libraries
from src.tests.core import *

# Test includes
from .step_1 import electrical_test_step_1

# -------------------------------------------------------------------------------------------------
#                                                                                   Electrical Test
# -----------------------------------------------------------------------------------------------*/
electrical_test:Test = Test(
    info=TestInfo(
        uuid="fce7ab74-b225-433d-b27d-629d346548d9",
        name="Electrical Test",
        description="This test is a test designed to test the electrical state of a newly manufactured panel",
    ),
    steps=[
        electrical_test_step_1
    ]
)   