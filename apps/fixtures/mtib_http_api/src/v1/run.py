from flask import Blueprint, jsonify, request
from tests.base import tests_registry
import asyncio
import grpc
from protos.mtib_cs_pi.mtib_cs_pi_pb2_grpc import MtibCsPiStub

run_bp = Blueprint('run', __name__)

slot_hostnames = {
    "single": "control-plane",
    "slot-1": "slot-1",
    "slot-2": "slot-2",
    "slot-3": "slot-3",
    "slot-4": "slot-4",
    "slot-5": "slot-5",
}
port = 12345

@run_bp.route('/v1/tests/<test_id>/run', methods=['POST'])
def run_test(test_id):
    test_instance = tests_registry.get(test_id)
    if not test_instance:
        return jsonify({"error": "Test not found"}), 404

    slots_info = request.json  # This should be the structure you mentioned
    results = run_test_on_slots(test_instance, slots_info)

    return jsonify({"testId": test_id, "results": results})

async def execute_step_on_slot(test_instance, step_index, slot_id, grpc_stub):
    # Since grpc_stub is already passed, no need to create it inside this function
    result = test_instance.run_step(step_index, grpc_stub)
    return {"slot": slot_id, "result": result}

def run_test_on_slots(test_instance, slots_info):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    results = {"panel": [[] for _ in range(6)]}  # Assuming up to 6 slots

    for step_index, step_info in enumerate(test_instance.steps):
        step_description = step_info["description"]
        step_tasks = []
        for slot_id, should_run in slots_info.items():
            if should_run and slot_id in slot_hostnames:  # Check if the test should run on this slot
                hostname = slot_hostnames[slot_id]
                channel = grpc.insecure_channel(f"{hostname}:{port}")
                grpc_stub = MtibCsPiStub(channel)
                task = loop.create_task(execute_step_on_slot(test_instance, step_index, slot_id, grpc_stub))
                task.set_name(f"{slot_id}-{step_index}")  # Include step index in task name
                step_tasks.append(task)
        
        loop.run_until_complete(asyncio.gather(*step_tasks))

        for task in step_tasks:
            task_name_parts = task.get_name().split('-')
            slot_id, step_idx = task_name_parts[0], int(task_name_parts[1])
            result = task.result()
            if result:  # If the task was executed and returned a result
                slot_index = int(slot_id.split('-')[1]) - 1
                enhanced_result = {
                    "stepIndex": step_idx,
                    "stepDescription": step_description,
                    **result["result"]  # Merge the original result dict with the step metadata
                }
                results["panel"][slot_index].append(enhanced_result)

    loop.close()
    return results
