"""Manufacturing test fixtures — shared state, shell lifecycle, power helpers.

Provides:
  - Shell lifecycle management via slot.shared_data
  - Power helper functions (power_on, power_off, read_current)
  - Automatic shell cleanup on session teardown
  - Skip logic for tests that depend on prior state

Shell lifecycle:
  POST tests open UART streams during boot (test_03_post/test_01_boot).
  Shells are stored in slot.shared_data["comms_shell"] and ["app_shell"].
  The _shell_cleanup fixture guarantees cleanup even on crash.
"""

import logging
import time

import pytest

from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig

log = logging.getLogger("manufacturing")


# ── Shell cleanup (session-scoped, guaranteed) ───────────────────────────

@pytest.fixture(autouse=True, scope="session")
def _shell_cleanup(fixture_ctx):
    """Stop any open UART shells when the session ends."""
    yield
    for slot_id, slot in fixture_ctx.slots.items():
        for key in ("app_shell", "comms_shell"):
            shell = slot.shared_data.get(key)
            if shell:
                try:
                    shell.stop()
                except Exception:
                    pass


# ── Power helpers ────────────────────────────────────────────────────────

def power_on_for_flashing(mtib, battery_installed: bool = False):
    """Configure GPIOs and power rails for J-Link access.

    GPIO 0+1 must be OUTPUT LOW for the DUT processor to be accessible
    via SWD. Power at 4.5V on ch0 (VBAT). Ch1 (charger) only if battery
    is installed. See .claude/rules/mtib-hardware.md for details.
    """
    for gpio in (0, 1):
        mtib.GpioConfig(gpio=gpio, direction=GpioDirection.OUTPUT, resistor=GpioResistorConfig.NONE)
        mtib.GpioWrite(gpio=gpio, state=False)
    log.info("GPIO 0+1 configured as OUTPUT LOW")

    err = mtib.PowerEnable(channel=0, voltage_v=4.5)
    assert err is None, f"PowerEnable ch0 failed: {err}"

    if battery_installed:
        err = mtib.PowerEnable(channel=1, voltage_v=5.0)
        assert err is None, f"PowerEnable ch1 failed: {err}"

    time.sleep(3)
    log.info("DUT powered at 4.5V — ready for J-Link")


def power_off(mtib):
    """Disable both power channels."""
    mtib.PowerDisable(channel=0)
    mtib.PowerDisable(channel=1)


def read_current_ma(mtib, channel: int = 0) -> float:
    """Read current in mA from a power channel."""
    result, err = mtib.PowerRead(channel=channel)
    if err or not result:
        return 0.0
    return result.current_ma


# ── Shared state helpers ─────────────────────────────────────────────────

def require_prior(slot, key: str, message: str):
    """Skip this test if a required prior state is missing."""
    if key not in slot.shared_data or slot.shared_data[key] is None:
        pytest.skip(f"Prerequisite not met: {message}")


def get_shells(slot):
    """Get (app_shell, comms_shell) from shared_data, or skip if not booted."""
    app = slot.shared_data.get("app_shell")
    comms = slot.shared_data.get("comms_shell")
    if not app or not comms:
        pytest.skip("Shells not available — test_01_boot must pass first")
    return app, comms
