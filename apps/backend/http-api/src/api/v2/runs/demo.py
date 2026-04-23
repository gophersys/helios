"""Demo endpoint that simulates a validation run via WebSocket events.

Emits realistic test-start / test-result / run-finish events on a timer,
so the frontend can be developed and tested without real hardware.
"""
import logging
import time
import random

from flask import jsonify, request

from src.lib.decorators import require_permissions
from src.lib.permissions import Permissions
from src.lib.errors import bad_request
from src.lib.types import ApiResponse

from .reporter import _emit

logger = logging.getLogger(__name__)

# Simulated test suite — matches real Stage 4 test names
DEMO_TESTS = [
    {"name": "test_dut_boots", "module": "test_power", "duration": 2.1, "pass_rate": 1.0},
    {"name": "test_idle_current", "module": "test_power", "duration": 10.5, "pass_rate": 0.95},
    {"name": "test_active_current", "module": "test_power", "duration": 15.2, "pass_rate": 0.9},
    {"name": "test_peak_current", "module": "test_power", "duration": 8.3, "pass_rate": 0.95},
    {"name": "test_power_rails", "module": "test_environmental", "duration": 3.0, "pass_rate": 0.98},
    {"name": "test_temperature_reading", "module": "test_environmental", "duration": 5.5, "pass_rate": 0.92},
    {"name": "test_button_short_press", "module": "test_button", "duration": 4.2, "pass_rate": 0.98},
    {"name": "test_button_long_press", "module": "test_button", "duration": 6.1, "pass_rate": 0.95},
    {"name": "test_led_color_on_status", "module": "test_button", "duration": 3.8, "pass_rate": 0.9},
    {"name": "test_cloud_boot_message", "module": "test_cloud", "duration": 12.0, "pass_rate": 0.85},
    {"name": "test_cloud_telemetry", "module": "test_cloud", "duration": 20.0, "pass_rate": 0.88},
    {"name": "test_cloud_biometric_upload", "module": "test_cloud", "duration": 25.0, "pass_rate": 0.82},
    {"name": "test_skin_detection", "module": "test_ppg", "duration": 8.0, "pass_rate": 0.9},
    {"name": "test_heartbeat_simulation", "module": "test_ppg", "duration": 15.0, "pass_rate": 0.85},
    {"name": "test_sleep_current", "module": "test_power", "duration": 30.0, "pass_rate": 0.92},
    {"name": "test_ota_firmware_update", "module": "test_fuota", "duration": 45.0, "pass_rate": 0.8},
]


@require_permissions(Permissions.VALIDATION_RUN)
def simulate_run(run_id: str):
    """POST /v2/runs/<id>/demo/simulate -- Start a simulated run.

    Emits WebSocket events mimicking a real validation run.
    Query params:
        speed: float -- multiplier for test duration (default 0.1 = 10x faster)
        scenario: str -- "happy" (all pass), "mixed" (realistic), "failing" (many failures)
    """
    speed = request.args.get("speed", 0.1, type=float)
    speed = max(0.01, min(speed, 1.0))

    scenario = request.args.get("scenario", "mixed")
    if scenario not in ("happy", "mixed", "failing"):
        return bad_request("scenario must be one of: happy, mixed, failing")

    # Emit run start
    _emit("run_start", {
        "runId": run_id,
        "status": "ACTIVE",
    }, run_id)

    passed_count = 0
    failed_count = 0
    total = len(DEMO_TESTS)

    def _run_simulation():
        """Emit simulated test events on a background timer."""
        nonlocal passed_count, failed_count

        for i, test in enumerate(DEMO_TESTS):
            # Emit test start
            _emit("execution_start", {
                "runId": run_id,
                "testName": test["name"],
                "module": test["module"],
                "executionId": f"demo-exec-{i}",
                "testIndex": i,
                "totalTests": total,
            }, run_id)

            # Simulate test duration
            sim_duration = test["duration"] * speed
            time.sleep(sim_duration)

            # Determine pass/fail based on scenario
            if scenario == "happy":
                test_passed = True
            elif scenario == "failing":
                test_passed = random.random() < 0.4
            else:  # mixed
                test_passed = random.random() < test["pass_rate"]

            if test_passed:
                passed_count += 1
            else:
                failed_count += 1

            error_msg = None
            measurements = None
            log_output = None

            if not test_passed:
                error_msg = f"AssertionError: {test['name']} measurement out of range"
                log_output = (
                    f"[INF] {test['module']}: Starting {test['name']}...\n"
                    f"[INF] power: DUT ch0=4.50V ch1=5.00V\n"
                    f"[INF] power: Current reading: {random.uniform(15, 90):.1f}mA\n"
                    f"[WRN] {test['module']}: Value outside threshold\n"
                    f"[ERR] {test['module']}: Expected <20.0mA, got {random.uniform(25, 90):.1f}mA\n"
                    f"FAILED {test['name']} - {test['duration']:.1f}s"
                )
            else:
                # Generate plausible measurements
                if "current" in test["name"] or "power" in test["name"]:
                    avg = round(random.uniform(2.0, 25.0), 2)
                    peak = round(random.uniform(30.0, 120.0), 2)
                    measurements = {
                        "avg_current_ma": avg,
                        "peak_current_ma": peak,
                    }
                    log_output = (
                        f"[INF] {test['module']}: Starting {test['name']}...\n"
                        f"[INF] power: PowerEnable ch0=4.5V\n"
                        f"[INF] power: Waiting 3s for boot...\n"
                        f"[INF] power: DUT ch0=4.50V, {avg:.1f}mA\n"
                        f"[INF] power: Peak current: {peak:.1f}mA\n"
                        f"[INF] power: Average current: {avg:.1f}mA (threshold: <30mA)\n"
                        f"PASSED {test['name']} - {test['duration']:.1f}s"
                    )
                elif "temperature" in test["name"]:
                    temp = round(random.uniform(22.0, 35.0), 1)
                    measurements = {"temperature_c": temp}
                    log_output = (
                        f"[INF] {test['module']}: Starting {test['name']}...\n"
                        f"[INF] env: Reading MLX90614 IR sensor\n"
                        f"[INF] env: Temperature: {temp}C (range: 15-45C)\n"
                        f"PASSED {test['name']} - {test['duration']:.1f}s"
                    )
                elif "button" in test["name"] or "led" in test["name"]:
                    log_output = (
                        f"[INF] {test['module']}: Starting {test['name']}...\n"
                        f"[INF] fixture: GPIO 2 -> LOW (button press)\n"
                        f"[INF] uart: [APP] BTN: press detected\n"
                        f"[INF] fixture: GPIO 2 -> HIGH (button release)\n"
                        f"[INF] uart: [APP] BTN: release after 150ms\n"
                        f"PASSED {test['name']} - {test['duration']:.1f}s"
                    )
                elif "cloud" in test["name"]:
                    log_output = (
                        f"[INF] {test['module']}: Starting {test['name']}...\n"
                        f"[INF] cloud: Querying device status...\n"
                        f"[INF] cloud: Device 70B3D584C01E1FCC - active\n"
                        f"[INF] cloud: Last message: boot_msg (2s ago)\n"
                        f"PASSED {test['name']} - {test['duration']:.1f}s"
                    )
                elif "skin" in test["name"] or "ppg" in test["name"] or "heart" in test["name"]:
                    log_output = (
                        f"[INF] {test['module']}: Starting {test['name']}...\n"
                        f"[INF] fixture: Servo -> exposed (PPG active)\n"
                        f"[INF] uart: [APP] PPG: SKIN_CONFIRMED\n"
                        f"[INF] uart: [APP] BIO: HR=72 SpO2=98\n"
                        f"PASSED {test['name']} - {test['duration']:.1f}s"
                    )
                else:
                    log_output = (
                        f"[INF] {test['module']}: Starting {test['name']}...\n"
                        f"[INF] {test['module']}: Test completed successfully\n"
                        f"PASSED {test['name']} - {test['duration']:.1f}s"
                    )

            _emit("execution_result", {
                "runId": run_id,
                "testName": test["name"],
                "passed": test_passed,
                "durationS": round(test["duration"], 2),
                "errorMessage": error_msg,
                "measurements": measurements,
                "logOutput": log_output,
            }, run_id)

        # Emit run finish
        _emit("run_finish", {
            "runId": run_id,
            "status": "COMPLETED",
            "total": total,
            "passed": passed_count,
            "failed": failed_count,
            "errors": 0,
            "durationS": round(sum(t["duration"] for t in DEMO_TESTS), 2),
        }, run_id)

    # Run in background thread via eventlet
    import eventlet
    eventlet.spawn(_run_simulation)

    return jsonify(ApiResponse.ok({
        "runId": run_id,
        "status": "SIMULATING",
        "totalTests": total,
        "speed": speed,
        "scenario": scenario,
    }).to_dict()), 200
