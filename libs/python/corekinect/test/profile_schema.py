"""Fixture profile validation.

Validates fixture profile JSON against a schema at load time, catching
typos, missing fields, and type mismatches before tests run.

Usage:
    from corekinect.test.profile_schema import validate_fixture_profile

    errors = validate_fixture_profile(data)
    if errors:
        raise ConfigError(f"Fixture profile invalid: {errors}")

    # Or use the validated loader:
    from corekinect.test.profile_schema import load_validated_profile

    profile = load_validated_profile("fixtures/alpha_b0.json")
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from corekinect.test.errors import ConfigError


# =============================================================================
# Schema definition
# =============================================================================

# Valid capability names (must match Capability enum values)
VALID_CAPABILITIES = {
    "power", "button", "peltier", "charger_relay", "ppg_servo",
    "ppg_led", "led_photodiode", "nfc_reader", "motion_actuator",
    "haptic_sensor", "jlink",
}

# Required top-level fields and their types
_REQUIRED_FIELDS = {
    "station_id": str,
    "product": str,
    "board": str,
}

_OPTIONAL_FIELDS = {
    "mtib_revision": str,
    "capabilities": list,
    "dut": dict,
    "power": dict,
    "button": (dict, type(None)),
    "ppg_simulator": (dict, type(None)),
    "peltier": (dict, type(None)),
    "charger_relay": (dict, type(None)),
    "led_sensor": (dict, type(None)),
    "nfc_reader": (dict, type(None)),
    "motion": (dict, type(None)),
}

# Sub-schemas for nested objects
_POWER_SCHEMA = {
    "battery_installed": {"type": bool, "required": True},
    "dut_voltage": {"type": (int, float), "required": True},
    "charger_voltage": {"type": (int, float), "required": False},
    "boot_settle_s": {"type": (int, float), "required": False},
}

_DUT_SCHEMA = {
    "device_id": {"type": str, "required": False},
    "snr": {"type": str, "required": False},
    "imei": {"type": str, "required": False},
    "iccids": {"type": list, "required": False},
}

_BUTTON_SCHEMA = {
    "gpio_pin": {"type": int, "required": True},
    "active_low": {"type": bool, "required": False},
}

_PPG_SCHEMA = {
    "servo_pwm_pin": {"type": int, "required": True},
    "servo_blocked_duty_us": {"type": int, "required": False},
    "servo_exposed_duty_us": {"type": int, "required": False},
    "hr_led_gpio_pin": {"type": int, "required": True},
}

_PELTIER_SCHEMA = {
    "gpio_pin": {"type": int, "required": True},
    "temp_adc_channel": {"type": int, "required": True},
}

_CHARGER_RELAY_SCHEMA = {
    "gpio_pin": {"type": int, "required": True},
    "active_high": {"type": bool, "required": False},
}

_LED_SENSOR_SCHEMA = {
    "red_adc_channel": {"type": int, "required": True},
    "green_adc_channel": {"type": int, "required": True},
    "blue_adc_channel": {"type": int, "required": True},
}

_NFC_READER_SCHEMA = {
    "interface": {"type": str, "required": True},
    "bus": {"type": int, "required": True},
}

_MOTION_SCHEMA = {
    "enabled": {"type": bool, "required": False},
}

# Map hardware block name → schema
_HARDWARE_SCHEMAS = {
    "button": _BUTTON_SCHEMA,
    "ppg_simulator": _PPG_SCHEMA,
    "peltier": _PELTIER_SCHEMA,
    "charger_relay": _CHARGER_RELAY_SCHEMA,
    "led_sensor": _LED_SENSOR_SCHEMA,
    "nfc_reader": _NFC_READER_SCHEMA,
    "motion": _MOTION_SCHEMA,
}


# =============================================================================
# Validation
# =============================================================================


def _validate_sub_object(
    data: dict,
    schema: Dict[str, dict],
    path: str,
) -> List[str]:
    """Validate a nested object against its schema.

    Returns list of error messages.
    """
    errors = []
    known_keys = set(schema.keys())

    for field_name, field_def in schema.items():
        expected_type = field_def["type"]
        required = field_def.get("required", False)

        if field_name not in data:
            if required:
                errors.append(f"{path}.{field_name}: required field missing")
            continue

        value = data[field_name]
        if not isinstance(value, expected_type):
            type_name = (
                expected_type.__name__
                if isinstance(expected_type, type)
                else str(expected_type)
            )
            errors.append(
                f"{path}.{field_name}: expected {type_name}, "
                f"got {type(value).__name__}"
            )

    # Warn about unknown keys (excluding _doc and _* private fields)
    for key in data:
        if key.startswith("_"):
            continue
        if key not in known_keys:
            errors.append(f"{path}.{key}: unknown field")

    return errors


def validate_fixture_profile(data: Dict[str, Any]) -> List[str]:
    """Validate a fixture profile dict against the schema.

    Args:
        data: Parsed fixture profile JSON.

    Returns:
        List of error messages. Empty if valid.
    """
    errors = []

    if not isinstance(data, dict):
        return [f"Profile must be a dict, got {type(data).__name__}"]

    # Required top-level fields
    for field_name, expected_type in _REQUIRED_FIELDS.items():
        if field_name not in data:
            errors.append(f"{field_name}: required field missing")
        elif not isinstance(data[field_name], expected_type):
            errors.append(
                f"{field_name}: expected {expected_type.__name__}, "
                f"got {type(data[field_name]).__name__}"
            )

    # Optional top-level fields — check type if present
    for field_name, expected_type in _OPTIONAL_FIELDS.items():
        if field_name in data and data[field_name] is not None:
            if not isinstance(data[field_name], expected_type):
                type_name = (
                    expected_type.__name__
                    if isinstance(expected_type, type)
                    else str(expected_type)
                )
                errors.append(
                    f"{field_name}: expected {type_name}, "
                    f"got {type(data[field_name]).__name__}"
                )

    # Validate capabilities list
    if "capabilities" in data and isinstance(data["capabilities"], list):
        for i, cap in enumerate(data["capabilities"]):
            if not isinstance(cap, str):
                errors.append(
                    f"capabilities[{i}]: expected string, got {type(cap).__name__}"
                )
            elif cap not in VALID_CAPABILITIES:
                errors.append(
                    f"capabilities[{i}]: unknown capability '{cap}'. "
                    f"Valid: {sorted(VALID_CAPABILITIES)}"
                )

    # Validate power config
    if "power" in data and isinstance(data["power"], dict):
        errors.extend(_validate_sub_object(data["power"], _POWER_SCHEMA, "power"))

    # Validate DUT config
    if "dut" in data and isinstance(data["dut"], dict):
        errors.extend(_validate_sub_object(data["dut"], _DUT_SCHEMA, "dut"))

    # Validate hardware blocks
    for block_name, block_schema in _HARDWARE_SCHEMAS.items():
        if block_name in data and data[block_name] is not None:
            if isinstance(data[block_name], dict):
                errors.extend(
                    _validate_sub_object(
                        data[block_name], block_schema, block_name,
                    )
                )

    # Warn about completely unknown top-level keys
    known_top_level = (
        set(_REQUIRED_FIELDS.keys())
        | set(_OPTIONAL_FIELDS.keys())
        | {"_hardware_notes", "_doc"}
    )
    for key in data:
        if key.startswith("_"):
            continue
        if key not in known_top_level:
            errors.append(f"{key}: unknown top-level field")

    return errors


def load_validated_profile(
    path: Union[str, Path],
    strict: bool = True,
) -> Dict[str, Any]:
    """Load and validate a fixture profile JSON file.

    Args:
        path: Path to the JSON file.
        strict: If True, raise ConfigError on validation errors.
            If False, log warnings and return the data anyway.

    Returns:
        Parsed and validated profile dict.

    Raises:
        ConfigError: If strict=True and validation errors found.
        FileNotFoundError: If the file doesn't exist.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Fixture profile not found: {path}")

    with open(path) as f:
        data = json.load(f)

    errors = validate_fixture_profile(data)
    if errors and strict:
        error_list = "\n  - ".join(errors)
        raise ConfigError(
            f"Fixture profile '{path.name}' has {len(errors)} error(s):\n"
            f"  - {error_list}"
        )

    return data
