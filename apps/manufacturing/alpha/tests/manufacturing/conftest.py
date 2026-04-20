"""Manufacturing test fixtures — device lifecycle and stateless helpers.

Fixtures
--------

:func:`booted_device`
    Module-scoped: boots the DUT once per test module per slot, opens
    UART streams on both processors, locks the manufacturing shells,
    and disables debug output. Yields a :class:`BootedDevice` reused
    by every test in the module. Raises on any step failure —
    pytest's dependency graph converts that raise into an ERROR for
    every dependent test in the same slot, so the post-boot tests
    get native cascade-skip without a module global or a
    ``pytest_runtest_setup`` hook.

    The fixture retries the full boot up to ``BOOT_ATTEMPTS`` times
    if the manufacturing-shell window is missed (each attempt power-
    cycles and gives the lock ``LOCK_TIMEOUT_S`` to detect the shell
    prompt). This bounds the worst-case fixture time to roughly
    ``BOOT_ATTEMPTS × (LOCK_TIMEOUT_S × 2 + power-cycle overhead)``
    rather than the single 120 s wait we used to do.

:func:`device_identity`
    Module-scoped, depends on :func:`booted_device`. Reads IMEI +
    ICCIDs from the comms shell once per (module, slot) and yields a
    :class:`DeviceIdentity`. Downstream tests (personalization)
    consume this instead of stashing identifiers in ``slot.shared_data``.

Module scoping is essential: the previous function-scoped variant ran
the full power-cycle + dual shell-lock sequence before every test in
a module, adding 12-30 s of overhead per test (11 POST tests × 15 s ≈
2.5 min wasted per slot per panel). With ``slot_parallel`` propagating
per-slot ``nextitem`` to ``pytest_runtest_protocol``, pytest now
correctly preserves module-scoped fixtures across slot-parametrized
tests run on worker threads.

Power helpers
-------------

:func:`power_on_for_flashing`, :func:`power_off`, :func:`read_current_ma`
are stateless utilities used by the firmware flash stage where the
``booted_device`` fixture is deliberately not invoked (the DUT is
J-Link-accessible but has no firmware to boot into).
"""

import logging
import time
from dataclasses import dataclass
from typing import List, Optional

import pytest

from corekinect.mtib_client.v1.client.types import GpioDirection, GpioResistorConfig

log = logging.getLogger("manufacturing")

# Retry envelope for booting the DUT and locking both manufacturing shells.
# A healthy unit hits the shell window on attempt 1 in ~5-10 s; missed-window
# misfires retry by power-cycling. Worst-case wall time: 3 × (20 + 20 + ~3) ≈
# 130 s, comfortably under the 90 s test_01_boot timeout if the first attempt
# succeeds (typical), and short enough that even three failed attempts surface
# as a real ERROR instead of dragging the whole panel.
BOOT_ATTEMPTS = 3
LOCK_TIMEOUT_S = 20.0


# ── Device lifecycle dataclasses ─────────────────────────────────────────


@dataclass
class BootedDevice:
    """A powered, shell-locked device on one slot.

    Yielded by the :func:`booted_device` fixture. Tests that depend
    on this fixture reach the fixture's yield only if power-on,
    UART start, shell lock, and debug-off all succeeded.
    """

    slot: object
    app_shell: object
    comms_shell: object


@dataclass
class DeviceIdentity:
    """Per-device identifiers read from the modem.

    Yielded by the :func:`device_identity` fixture. ``ble_mac`` is
    optional because some product revisions populate it lazily from
    the app shell rather than the modem.
    """

    imei: str
    iccids: List[str]
    ble_mac: Optional[str] = None


# ── Fixtures ─────────────────────────────────────────────────────────────


def _boot_and_lock_once(slot, mtib):
    """Single boot attempt: power-cycle, open UARTs, lock both shells.

    Returns ``(app_shell, comms_shell)`` on success, raises
    :class:`AssertionError` if either shell-lock misses the window
    inside ``LOCK_TIMEOUT_S``. Always opens fresh shell objects so a
    retry never reuses streams that may be wedged from a missed window.
    """
    from corekinect.shells.alpha_app import AlphaAppShell
    from corekinect.shells.comms_coproc import CommsCoprocShell

    # Full power drain before boot — stale caps hold enough charge to
    # mask the "is the shell window open?" window.
    power_off(mtib)
    time.sleep(2)

    # Open UARTs BEFORE applying power so every byte of boot output
    # lands in the shell's buffer. See .claude/rules/mtib-hardware.md.
    app = AlphaAppShell(mtib)
    comms = CommsCoprocShell(mtib)
    comms.start()
    app.start()
    time.sleep(0.5)

    # GPIO 0/1 must be OUTPUT LOW for the DUT to boot. Without this
    # the rail reads 4.5V but the processor stays held in reset.
    for gpio in (0, 1):
        err = mtib.GpioConfig(
            gpio=gpio, direction=GpioDirection.OUTPUT,
            resistor=GpioResistorConfig.NONE,
        )
        assert err is None, f"GPIO {gpio} config failed: {err}"
        err = mtib.GpioWrite(gpio=gpio, state=False)
        assert err is None, f"GPIO {gpio} write failed: {err}"

    err = mtib.PowerEnable(channel=0, voltage_v=4.5)
    assert err is None, f"Failed to enable DUT power on {slot.slot_id}: {err}"

    time.sleep(0.5)

    if not comms.lock(timeout_s=LOCK_TIMEOUT_S):
        raise AssertionError(_lock_failure_message("comms", slot.slot_id))
    if not app.lock(timeout_s=LOCK_TIMEOUT_S):
        raise AssertionError(_lock_failure_message("app", slot.slot_id))
    return app, comms


def _lock_failure_message(shell_name: str, slot_id: str) -> str:
    """Build an actionable error for a missed manufacturing-shell window.

    Covers the three causes that account for ~all real failures so the
    operator doesn't have to grep the framework source to know what to
    check next.
    """
    return (
        f"Failed to lock {shell_name} manufacturing shell on {slot_id} "
        f"within {LOCK_TIMEOUT_S}s. Likely causes: "
        "(1) DUT did not boot — verify power rails and UVLO state; "
        "(2) manufacturing shell disabled in firmware — check that "
        "    the {shell_name} image was built with mfg shell enabled; "
        "(3) UART latency — bump LOCK_TIMEOUT_S or check the MTIB "
        "    server's UART buffering. "
        "See .claude/rules/mtib-hardware.md for the full diagnostic flow."
    )


@pytest.fixture(scope="module")
def booted_device(slot, config):
    """Boot the DUT on ``slot`` once per module and yield a :class:`BootedDevice`.

    Lifecycle (per ``(module, slot)`` instance):
      1. Try :func:`_boot_and_lock_once` up to ``BOOT_ATTEMPTS`` times.
         Each attempt power-cycles + opens fresh UART streams + locks
         both shells with a tight ``LOCK_TIMEOUT_S`` cap. A missed
         shell window on one attempt cleanly tears down the half-open
         streams before the next attempt.
      2. Disable shell debug output and reset stream buffers once both
         shells are locked.
      3. Yield the :class:`BootedDevice` for the entire module.
      4. On module teardown stop both UART streams so the next module
         can reopen them cleanly.

    Module scope means the 11 POST tests share one boot rather than
    re-running the ~10-30 s power-cycle + lock sequence per test.
    """
    mtib = slot.mtib
    app: Optional[object] = None
    comms: Optional[object] = None

    last_err: Optional[BaseException] = None
    for attempt in range(1, BOOT_ATTEMPTS + 1):
        try:
            app, comms = _boot_and_lock_once(slot, mtib)
            log.info(
                "DUT booted + shells locked on %s (attempt %d/%d)",
                slot.slot_id, attempt, BOOT_ATTEMPTS,
            )
            break
        except AssertionError as exc:
            last_err = exc
            log.warning(
                "Boot attempt %d/%d failed on %s: %s",
                attempt, BOOT_ATTEMPTS, slot.slot_id, exc,
            )
            # Drop any half-opened streams from this attempt before retrying;
            # a wedged UART stream can starve the next lock_shell write.
            for shell in (app, comms):
                if shell is None:
                    continue
                try:
                    shell.stop()
                except Exception:
                    pass
            app = comms = None
    else:
        # All retries exhausted — surface the last failure.
        raise AssertionError(
            f"Failed to boot {slot.slot_id} after {BOOT_ATTEMPTS} attempts: {last_err}"
        )

    comms.debug_off()
    app.debug_off()
    comms.reset_stream()
    app.reset_stream()
    log.info("Shells ready on %s — debug disabled, streams reset", slot.slot_id)

    yield BootedDevice(slot=slot, app_shell=app, comms_shell=comms)
    # Shell cleanup is handled by session-scoped fixture_ctx teardown
    # which runs after ALL slots finish. Do NOT stop shells here —
    # other slots may still be using their streams.


@pytest.fixture(scope="module")
def device_identity(booted_device) -> DeviceIdentity:
    """Read IMEI + ICCIDs from the modem and yield a :class:`DeviceIdentity`.

    Module-scoped: identifiers don't change for a given (module, slot)
    combination, so reading them once per module is correct and saves
    one comms-shell round-trip per test.

    Depends on :func:`booted_device`; inherits its cascade on failure.
    ``ble_mac`` is left ``None`` here — tests that need it should
    consume :func:`booted_device.app_shell` directly and capture
    ``get_chip_ids().ble_mac`` instead.
    """
    sim, err = booted_device.comms_shell.get_sim_info(timeout_s=30)
    assert err is None, f"Failed to get SIM info: {err}"
    assert sim.imei, "Modem returned empty IMEI"
    assert sim.iccids, "Modem returned no ICCIDs"
    return DeviceIdentity(imei=sim.imei, iccids=list(sim.iccids))


# ── Power helpers (stateless, used by fw_flash stage) ────────────────────

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
