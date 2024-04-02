class BaseTest:
    def __init__(self, name, test_id, description):
        self.name = name
        self.test_id = test_id
        self.description = description
        self.steps = []  # Now a list of dictionaries

    def add_step(self, step_method, description, expected_duration_ms):
        self.steps.append({
            "method": step_method,
            "description": description,
            "expectedDurationMs": expected_duration_ms
        })

    def run_step(self, step_index, grpc_stub):
        step_info = self.steps[step_index]
        step_method = step_info["method"]
        return step_method(grpc_stub)

class TestStepResult:
    def __init__(self, success, duration_ms, error=""):
        self.success = success
        self.duration_ms = duration_ms
        self.error = error

    def to_dict(self):
        return {
            "success": self.success,
            "durationMs": self.duration_ms,
            "error": self.error
        }

tests_registry = {}

def register_test(cls):
    test_instance = cls()  # Initialize the test instance
    tests_registry[cls.test_id] = test_instance
    return cls