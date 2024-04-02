from flask import Blueprint, jsonify
from tests.base import tests_registry

tests_bp = Blueprint('tests', __name__)

@tests_bp.route('/v1/Tests', methods=['GET'])
def list_tests():
    tests_info = [
        {
            "name": test_instance.name,
            "id": test_instance.test_id,
            "description": test_instance.description,
            "steps": [
                {
                    "description": step["description"],
                    "expectedDurationMs": step["expectedDurationMs"]
                } for step in test_instance.steps
            ]
        } for test_instance in tests_registry.values()
    ]
    return jsonify({"tests": tests_info})
