# Standard includes
import uuid

# Corekinect libraries
from src.tests.core import *

# Test includes
from .config import ElectricalTestConfig, electrical_test_init, electrical_test_deinit
from .step_1 import electrical_test_step_1
from .step_2 import electrical_test_step_2
from .step_3 import electrical_test_step_3
from .step_4 import electrical_test_step_4

# -------------------------------------------------------------------------------------------------
#                                                                                   Electrical Test
# -----------------------------------------------------------------------------------------------*/
electrical_test:Test = Test(
    # Test metadata
    info=TestInfo(
        uuid="fce7ab74-b225-433d-b27d-629d346548d9",
        name="Electrical Test",
        description="This test is a test designed to test the electrical state of a newly manufactured panel",
    ),
    
    # Configuration type (if applicable)
    config_type=ElectricalTestConfig,
    
    # Init/Deinit function (if applicable)
    init_func=electrical_test_init,
    deinit_func=electrical_test_deinit,
    
    # Steps
    steps=[
        electrical_test_step_1,
        electrical_test_step_2,
        electrical_test_step_3,
        electrical_test_step_4
    ]
)   