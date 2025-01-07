# Standard includes
import json
from dataclasses import asdict, dataclass

# Corekinect libraries
from tests.lib import *

# Shared includes
from ..shared.config import Sigma5ManufacturingConfig
from ..shared.rpcs import runnners_controller

# Test includes
from .data import ElectricalTestSharedData


# ---------------------------------------------------------------------------------
#                                                                      Step Details
# -------------------------------------------------------------------------------*/
@dataclass
class Step4Readings:
    vin_voltage: float = None
    vbatt_voltage: float = None
    _3v3_voltage: float = None
    vbckp_voltage: float = None
    uvp_n_value: bool = None
    current_a: float = None

    def marshall(self) -> str:
        try:
            return json.dumps(asdict(self))
        except TypeError as e:
            raise ValueError(f"Error marshalling data: {e}")

    @staticmethod
    def unmarshall(json_str: str):
        try:
            data = json.loads(json_str)
            return Step4Readings(**data)
        except KeyError as e:
            raise ValueError(f"Missing required configuration value: {e}")
        except TypeError as e:
            raise ValueError(f"Invalid configuration value type: {e}")


# ---------------------------------------------------------------------------------
#                                                                           Handler
# -------------------------------------------------------------------------------*/
def electrical_test_step_4_handler(config: Sigma5ManufacturingConfig, node: str, usr_data: Dict[str, ElectricalTestSharedData]) -> None:
    result: TestStepResult = TestStepResult(success=False)

    readings = Step4Readings()

    # 4.a: Ensure +VIN test point is the same as +BATT
    result.error, readings.vin_voltage = runnners_controller.read_vin(node)
    if result.error:
        raise PassTest(
            details = readings.marshall()
        )

    result.error, readings.vbatt_voltage = runnners_controller.read_vbat(node)
    if result.error:
        raise FailTest(
            details = readings.marshall()
        )
    
    return result

electrical_test_step_4: TestStep = TestStep(
    info=StepInfo(
        sequence=4,
        name="Ensure device electrical state.",
        description="Checks VIN, 3.3V, VBCKUP, UVP_N and current consumption against thresholds.",
        noPassIsFatal=False,
        supported_platforms = ["sigma3", "sigma5", "sigma7"]
        supported_board_revisions = ["A3", "B0", "B1", "C0"]
        supported_firmware_versions = ["1.x", "2.x"]
        supported_socket_server_versions = ["0.9", "1.x"]
    ),
    timeout_ms=1000,
    handler=electrical_test_step_4_handler,
)


# ----------------------------------------------------------------------------------
#                                                                               Step
# --------------------------------------------------------------------------------*/

class StepGpsSomething(TestStep):
    metadata: StepInfo(
            name="Ensure device electrical state.",
            description="Checks VIN, 3.3V, VBCKUP, UVP_N and current consumption against thresholds.",
            noPassIsFatal=False,
            supported_platforms = ["sigma3", "sigma5", "sigma7"]
            supported_board_revisions = ["A3", "B0", "B1", "C0"]
            supported_firmware_versions = ["1.x", "2.x"]
            supported_socket_server_versions = ["0.9", "1.x"]
        ),
    
    class Config:
        field_1: int = 0
        
    class Data:
        field_1: int = 0

    # TODO: How do we pass global config
    # TODO: How do we use the 'usr_data' -> 'shared_data'
    # TODO: Modify handler to pass 1 more arguement, called global_config (Manufacturing or Validation)
    # TODO: Unmarshall configs (local and global) in the lib.py
    # TODO: Progress indicator object (prefereably a callback)
    # TODO: Add ons
    
    def _handler(config: Config, node: str, usr_data:Any, add_ons:Any ):
        data:Data = Data()
        
        # 4.a: Ensure +VIN test point is the same as +BATT
        error, data.vin_voltage = runnners_controller.read_vin(node)
        if error:
            raise FailTest(
                ""
            )

        result.error, readings.vbatt_voltage = runnners_controller.read_vbat(node)
        if result.error:
            
        raise PassTest(
            data=data.marshall()
        )

    