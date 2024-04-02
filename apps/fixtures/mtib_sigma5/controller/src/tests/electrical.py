from .base import BaseTest, TestStepResult, register_test
from flask import jsonify

@register_test
class ElectricalTest(BaseTest):
    name = "Electrical Test"
    test_id = "ElectricalTest"
    description = "Tests that the electrons are doing the thing."
    
    def __init__(self):
        super().__init__(self.name, self.test_id, self.description)
        self.add_step(self.ping_step, "Ping an external resource", 100)
        self.add_step(self.verify_response_step, "Verify the ping response", 10)

    def ping_step(self, grpc_stub):
        # Directly return the dictionary representation of the result
        return TestStepResult(success=True, duration_ms=100, error="").to_dict()
    
    def verify_response_step(self, grpc_stub):
        # Similarly, return the dictionary representation of the result
        return TestStepResult(success=False, duration_ms=0, error="").to_dict()


