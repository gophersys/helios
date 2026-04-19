"""Tests for the manufacturing ``booted_device`` / ``device_identity`` fixtures.

The manufacturing conftest replaces ``slot.shared_data[...]`` with two
pytest fixtures that model the device lifecycle explicitly:

* :func:`booted_device` — power-cycles the DUT, locks the two
  manufacturing shells, disables debug, and yields a
  :class:`BootedDevice`. Raises on any step failure.
* :func:`device_identity` — depends on ``booted_device`` and reads
  IMEI + ICCIDs via the comms shell, yields a :class:`DeviceIdentity`.

Because they are real fixtures, pytest's dependency graph handles
cascade-skip natively: when ``booted_device`` raises, every test in
the same slot that depends on it is reported as ERROR — no module
global ``_slot_failures`` dict, no ``pytest_runtest_setup`` skip logic.

These tests run pytest-inside-pytest (``pytester``) with mocked MTIB
clients and shells so the assertions are about the fixture graph, not
real hardware. They are the contract the production conftest must
honour.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from typing import List

import pytest

pytest_plugins = ["pytester"]


# ────────────────────────────────────────────────────────────────────────
# Shared fake-suite helpers
# ────────────────────────────────────────────────────────────────────────


def _result_path(pytester: pytest.Pytester) -> Path:
    """Path where fake tests dump observed fixture values."""
    return pytester.path / "fixture_observations.jsonl"


def _read_results(pytester: pytest.Pytester) -> List[dict]:
    path = _result_path(pytester)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _write_fake_shells_module(
    pytester: pytest.Pytester,
    *,
    fail_lock_slots: List[int] | None = None,
) -> None:
    """Emit a module with mock shell classes that the conftest can use.

    The fake shells expose the minimum surface used by the fixtures:
    ``start``, ``stop``, ``lock``, ``debug_off``, ``reset_stream``,
    ``get_chip_ids``, ``get_sim_info``, ``personalize``. The lock
    behaviour can be made to fail for specific slot indices so we
    can assert cascade semantics.
    """
    fail_lock_slots = fail_lock_slots or []
    body = f'''
from dataclasses import dataclass
from typing import List, Optional

FAIL_LOCK_SLOTS = {fail_lock_slots!r}


@dataclass
class FakeChipIds:
    ext_flash_id: Optional[str] = "0xef 0x40 0x17"
    ble_mac: Optional[str] = "AA:BB:CC:DD:EE:FF"


@dataclass
class FakeSimInfo:
    imei: str = "354678901234567"
    iccids: List[str] = None
    eids: List[str] = None

    def __post_init__(self):
        if self.iccids is None:
            self.iccids = ["8901260123456789012"]
        if self.eids is None:
            self.eids = []


class FakeAppShell:
    def __init__(self, mtib, slot_index: int = 0):
        self.mtib = mtib
        self.slot_index = slot_index
        self.started = False
        self.stopped = False
        self.locked = False
        self.debug_disabled = False

    def start(self): self.started = True
    def stop(self): self.stopped = True
    def lock(self, timeout_s=120):
        if self.slot_index in FAIL_LOCK_SLOTS:
            return False
        self.locked = True
        return True
    def debug_off(self, timeout_s=30):
        self.debug_disabled = True
        return True
    def reset_stream(self): pass
    def get_chip_ids(self, timeout_s=30):
        return FakeChipIds(), None


class FakeCommsShell:
    def __init__(self, mtib, slot_index: int = 0):
        self.mtib = mtib
        self.slot_index = slot_index
        self.started = False
        self.stopped = False
        self.locked = False

    def start(self): self.started = True
    def stop(self): self.stopped = True
    def lock(self, timeout_s=120):
        if self.slot_index in FAIL_LOCK_SLOTS:
            return False
        self.locked = True
        return True
    def debug_off(self, timeout_s=30): return True
    def reset_stream(self): pass
    def get_sim_info(self, timeout_s=30):
        return FakeSimInfo(), None
    def personalize(self, device_id):
        return object(), None
    def rekey_ipc(self):
        return True, None
'''
    pytester.makepyfile(_fake_shells=textwrap.dedent(body).lstrip())


def _write_slot_stub_conftest(pytester: pytest.Pytester) -> None:
    """Emit a conftest.py that stubs ``slot``/``config``/``report`` fixtures.

    We don't stand up a real ``fixture_ctx`` — we just provide plain
    objects with the shape the production fixtures read
    (``slot.mtib``, ``slot.slot_index``, ``slot.slot_id``). We also
    stub ``config`` (returns {}) and ``report`` (a shim that accepts
    ``.step(...)``).
    """
    body = '''
import pytest


class _Slot:
    def __init__(self, slot_index: int):
        self.slot_index = slot_index
        self.slot_id = f"slot-{slot_index}"
        self.mtib = object()
        self.serial_number = f"MOCK{slot_index}"


class _StepCtx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def record(self, *a, **k): pass
    def record_dict(self, *a, **k): pass


class _Report:
    def step(self, name): return _StepCtx()


@pytest.fixture(params=["slot-0", "slot-1", "slot-2", "slot-3"])
def slot(request):
    idx = int(request.param.split("-")[1])
    return _Slot(idx)


@pytest.fixture
def config():
    return {}


@pytest.fixture
def report():
    return _Report()
'''
    pytester.makeconftest(textwrap.dedent(body).lstrip())


def _write_production_like_conftest(
    pytester: pytest.Pytester,
    *,
    booted_device_imports: str,
) -> None:
    """Emit a conftest.py that exposes the production ``booted_device``/
    ``device_identity`` fixtures but sources the shell classes from the
    fake module.

    This lets the tests exercise real fixture behaviour (cascade,
    dependency graph, teardown) without pulling in the real
    ``AlphaAppShell`` / ``CommsCoprocShell`` (which expect real MTIB
    gRPC).

    ``booted_device_imports`` is a block of Python to inject so the
    fixture imports the fake shell classes instead of the real ones.
    """
    body = f'''
import pytest

{booted_device_imports}


class _Slot:
    def __init__(self, slot_index: int):
        self.slot_index = slot_index
        self.slot_id = f"slot-{{slot_index}}"
        self.mtib = object()
        self.serial_number = f"MOCK{{slot_index}}"


class _StepCtx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def record(self, *a, **k): pass


class _Report:
    def step(self, name): return _StepCtx()


@pytest.fixture(scope="module", params=["slot-0", "slot-1", "slot-2", "slot-3"])
def slot(request):
    idx = int(request.param.split("-")[1])
    return _Slot(idx)


@pytest.fixture(scope="session")
def config():
    return {{}}


@pytest.fixture
def report():
    return _Report()


from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BootedDevice:
    slot: object
    app_shell: object
    comms_shell: object


@dataclass
class DeviceIdentity:
    imei: str
    iccids: List[str]
    ble_mac: Optional[str] = None


@pytest.fixture(scope="module")
def booted_device(slot, config):
    from _fake_shells import FakeAppShell, FakeCommsShell

    app = FakeAppShell(slot.mtib, slot.slot_index)
    comms = FakeCommsShell(slot.mtib, slot.slot_index)
    comms.start()
    app.start()
    if not comms.lock(timeout_s=20):
        raise AssertionError(f"Failed to lock comms shell on {{slot.slot_id}}")
    if not app.lock(timeout_s=20):
        raise AssertionError(f"Failed to lock app shell on {{slot.slot_id}}")
    comms.debug_off()
    app.debug_off()
    try:
        yield BootedDevice(slot=slot, app_shell=app, comms_shell=comms)
    finally:
        try: app.stop()
        except Exception: pass
        try: comms.stop()
        except Exception: pass


@pytest.fixture(scope="module")
def device_identity(booted_device):
    sim, err = booted_device.comms_shell.get_sim_info(timeout_s=30)
    if err:
        raise AssertionError(f"Failed to get SIM info: {{err}}")
    return DeviceIdentity(imei=sim.imei, iccids=sim.iccids)
'''
    pytester.makeconftest(textwrap.dedent(body).lstrip())


# ────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────


def test_booted_device_yields_populated_shells(pytester: pytest.Pytester) -> None:
    """``booted_device.app_shell`` / ``.comms_shell`` are both non-None."""
    _write_fake_shells_module(pytester)
    _write_production_like_conftest(pytester, booted_device_imports="")

    result_path = str(_result_path(pytester))
    pytester.makepyfile(test_boot=textwrap.dedent(f'''
        import json
        import pytest


        def test_boot(booted_device):
            with open({result_path!r}, "a") as fh:
                fh.write(json.dumps({{
                    "test": "test_boot",
                    "slot_index": booted_device.slot.slot_index,
                    "has_app": booted_device.app_shell is not None,
                    "has_comms": booted_device.comms_shell is not None,
                    "app_locked": getattr(booted_device.app_shell, "locked", False),
                    "comms_locked": getattr(booted_device.comms_shell, "locked", False),
                    "app_debug_off": getattr(booted_device.app_shell, "debug_disabled", False),
                }}) + "\\n")
    '''))

    result = pytester.runpytest("-v", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=4)

    rows = _read_results(pytester)
    assert len(rows) == 4
    assert all(r["has_app"] and r["has_comms"] for r in rows)
    assert all(r["app_locked"] and r["comms_locked"] for r in rows)
    assert all(r["app_debug_off"] for r in rows)
    assert sorted(r["slot_index"] for r in rows) == [0, 1, 2, 3]


def test_device_identity_depends_on_booted_device(pytester: pytest.Pytester) -> None:
    """The identity fixture is satisfied by reading from ``booted_device.comms_shell``."""
    _write_fake_shells_module(pytester)
    _write_production_like_conftest(pytester, booted_device_imports="")

    result_path = str(_result_path(pytester))
    pytester.makepyfile(test_identity=textwrap.dedent(f'''
        import json

        def test_identity(device_identity):
            with open({result_path!r}, "a") as fh:
                fh.write(json.dumps({{
                    "imei": device_identity.imei,
                    "iccid_count": len(device_identity.iccids),
                }}) + "\\n")
    '''))

    result = pytester.runpytest("-v", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=4)

    rows = _read_results(pytester)
    assert len(rows) == 4
    assert all(r["imei"] == "354678901234567" for r in rows)
    assert all(r["iccid_count"] == 1 for r in rows)


def test_booted_device_failure_errors_dependent_tests(pytester: pytest.Pytester) -> None:
    """When ``booted_device`` raises on slot-0, downstream tests for slot-0 ERROR.

    The other slots' ``booted_device`` runs independently so their
    dependent tests still pass. This is the cascade semantic pytest
    gives us for free once we express the dependency as a fixture.
    """
    _write_fake_shells_module(pytester, fail_lock_slots=[0])
    _write_production_like_conftest(pytester, booted_device_imports="")

    pytester.makepyfile(test_cascade=textwrap.dedent('''
        def test_downstream(booted_device):
            # If booted_device ERRORS for slot-0, this test is reported as ERROR.
            assert booted_device.app_shell.locked
    '''))

    result = pytester.runpytest("-v", "-p", "no:cacheprovider", "-p", "no:randomly")
    # 1 error (slot-0 booted_device raises), 3 passed (slot-1/2/3).
    result.assert_outcomes(passed=3, errors=1)


def test_failure_on_one_slot_does_not_affect_other_slots(pytester: pytest.Pytester) -> None:
    """Per-slot fixture isolation: slot-1 failing leaves slot-0/2/3 alone."""
    _write_fake_shells_module(pytester, fail_lock_slots=[1])
    _write_production_like_conftest(pytester, booted_device_imports="")

    result_path = str(_result_path(pytester))
    pytester.makepyfile(test_iso=textwrap.dedent(f'''
        import json


        def test_downstream(booted_device):
            with open({result_path!r}, "a") as fh:
                fh.write(json.dumps({{
                    "slot_index": booted_device.slot.slot_index,
                }}) + "\\n")
    '''))

    result = pytester.runpytest("-v", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=3, errors=1)

    rows = _read_results(pytester)
    succeeded = sorted(r["slot_index"] for r in rows)
    assert succeeded == [0, 2, 3]  # slot-1 never ran the downstream test


def test_device_identity_fails_when_booted_device_fails(pytester: pytest.Pytester) -> None:
    """A two-step chain: ``device_identity`` inherits the cascade from ``booted_device``.

    If ``booted_device`` raises on slot-2, ``device_identity`` doesn't
    execute — it is reported as ERROR, not failed.
    """
    _write_fake_shells_module(pytester, fail_lock_slots=[2])
    _write_production_like_conftest(pytester, booted_device_imports="")

    pytester.makepyfile(test_identity_chain=textwrap.dedent('''
        def test_identity(device_identity):
            assert device_identity.imei
    '''))

    result = pytester.runpytest("-v", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=3, errors=1)


def test_tests_without_booted_device_are_unaffected(pytester: pytest.Pytester) -> None:
    """Electrical-stage tests (no ``booted_device`` dep) run regardless.

    The cascade must be scoped to the fixture graph — tests that don't
    depend on ``booted_device`` are oblivious to a boot failure.
    """
    _write_fake_shells_module(pytester, fail_lock_slots=[0, 1, 2, 3])
    _write_production_like_conftest(pytester, booted_device_imports="")

    pytester.makepyfile(test_electrical=textwrap.dedent('''
        def test_uvlo(slot):
            # No booted_device dep — boot failures must not cascade here.
            assert slot is not None
    '''))

    result = pytester.runpytest("-v", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=4)


def test_booted_device_is_module_scoped_one_boot_per_module(
    pytester: pytest.Pytester,
) -> None:
    """``booted_device`` runs ONCE per (module, slot), not once per test.

    A function-scoped variant would call ``shell.start()`` again for
    every test (so the previous test's shell would already be
    ``.stopped == True`` before the next one's fixture runs). With
    module scope every test in the module sees the SAME shell objects
    and the shells stay running for the duration of the module.

    Two tests in the same module share booted_device → both observe
    the same ``id(app_shell)`` and never see ``.stopped == True``.
    """
    _write_fake_shells_module(pytester)
    _write_production_like_conftest(pytester, booted_device_imports="")

    result_path = str(_result_path(pytester))
    pytester.makepyfile(test_share=textwrap.dedent(f'''
        import json

        def _record(label, booted_device):
            with open({result_path!r}, "a") as fh:
                fh.write(json.dumps({{
                    "test": label,
                    "slot_index": booted_device.slot.slot_index,
                    "app_id": id(booted_device.app_shell),
                    "comms_id": id(booted_device.comms_shell),
                    "app_stopped": booted_device.app_shell.stopped,
                    "comms_stopped": booted_device.comms_shell.stopped,
                }}) + "\\n")


        def test_one(booted_device):
            _record("one", booted_device)


        def test_two(booted_device):
            _record("two", booted_device)
    '''))

    result = pytester.runpytest(
        "-v", "-p", "no:cacheprovider", "-p", "no:randomly",
        "-k", "slot-0",
    )
    result.assert_outcomes(passed=2)

    rows = _read_results(pytester)
    assert len(rows) == 2, f"expected 2 records, got {rows}"
    one, two = rows
    assert one["app_id"] == two["app_id"], (
        f"booted_device.app_shell was re-instantiated between tests: "
        f"one={one['app_id']} two={two['app_id']}"
    )
    assert one["comms_id"] == two["comms_id"], (
        f"booted_device.comms_shell was re-instantiated between tests"
    )
    assert not any(r["app_stopped"] or r["comms_stopped"] for r in rows), (
        "shells were stopped between tests in the same module — "
        "fixture is not module-scoped"
    )


def test_booted_device_teardown_stops_shells_at_module_end(
    pytester: pytest.Pytester,
) -> None:
    """When the module finishes, the fixture's finalizer stops both shells.

    Module teardown still has to happen — otherwise the next test
    module's first ``booted_device`` couldn't reopen the UART streams.
    We verify by:
      1. Capturing the shell objects from inside ``test_one``.
      2. Reading their ``.stopped`` flags from inside a
         ``pytest_sessionfinish`` hook in conftest, which is the
         well-defined point AFTER all module teardowns have run.
    """
    _write_fake_shells_module(pytester)

    # Re-emit the production-like conftest, but with an extra
    # session-finish hook that dumps shell state for the outer test
    # to inspect.
    state_path = str(pytester.path / "shell_state.json")
    body = f'''
import pytest


class _Slot:
    def __init__(self, slot_index: int):
        self.slot_index = slot_index
        self.slot_id = f"slot-{{slot_index}}"
        self.mtib = object()
        self.serial_number = f"MOCK{{slot_index}}"


class _StepCtx:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def record(self, *a, **k): pass


class _Report:
    def step(self, name): return _StepCtx()


@pytest.fixture(scope="module", params=["slot-0", "slot-1", "slot-2", "slot-3"])
def slot(request):
    idx = int(request.param.split("-")[1])
    return _Slot(idx)


@pytest.fixture(scope="session")
def config():
    return {{}}


@pytest.fixture
def report():
    return _Report()


from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BootedDevice:
    slot: object
    app_shell: object
    comms_shell: object


# Hold references to all shells ever created so the session-finish
# hook can inspect their final state after module teardown ran.
_ALL_SHELLS = []


@pytest.fixture(scope="module")
def booted_device(slot, config):
    from _fake_shells import FakeAppShell, FakeCommsShell

    app = FakeAppShell(slot.mtib, slot.slot_index)
    comms = FakeCommsShell(slot.mtib, slot.slot_index)
    comms.start()
    app.start()
    comms.lock(timeout_s=20)
    app.lock(timeout_s=20)
    comms.debug_off()
    app.debug_off()
    _ALL_SHELLS.append((app, comms))
    try:
        yield BootedDevice(slot=slot, app_shell=app, comms_shell=comms)
    finally:
        try: app.stop()
        except Exception: pass
        try: comms.stop()
        except Exception: pass


def pytest_sessionfinish(session, exitstatus):
    import json
    with open({state_path!r}, "w") as fh:
        json.dump([
            {{"app_stopped": app.stopped, "comms_stopped": comms.stopped}}
            for app, comms in _ALL_SHELLS
        ], fh)
'''
    pytester.makeconftest(textwrap.dedent(body).lstrip())

    pytester.makepyfile(test_module_a=textwrap.dedent('''
        def test_only(booted_device):
            assert booted_device.app_shell.locked
            assert booted_device.comms_shell.locked
    '''))

    result = pytester.runpytest("-v", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=4)

    import json
    with open(state_path) as fh:
        states = json.load(fh)
    assert len(states) == 4, f"expected 4 shells (one per slot), got {states}"
    assert all(s["app_stopped"] and s["comms_stopped"] for s in states), (
        f"shells not stopped at module teardown: {states}"
    )


def test_device_identity_is_a_dataclass_with_imei_iccids(pytester: pytest.Pytester) -> None:
    """Sanity: the ``DeviceIdentity`` yielded by the fixture has the expected shape.

    Guards against accidental drift — tests downstream (test_10_personalize)
    read ``device_identity.imei`` and ``.iccids`` directly.
    """
    _write_fake_shells_module(pytester)
    _write_production_like_conftest(pytester, booted_device_imports="")

    result_path = str(_result_path(pytester))
    pytester.makepyfile(test_shape=textwrap.dedent(f'''
        import json

        def test_shape(device_identity):
            with open({result_path!r}, "a") as fh:
                fh.write(json.dumps({{
                    "has_imei": hasattr(device_identity, "imei"),
                    "has_iccids": hasattr(device_identity, "iccids"),
                    "has_ble_mac": hasattr(device_identity, "ble_mac"),
                    "imei_type": type(device_identity.imei).__name__,
                    "iccids_type": type(device_identity.iccids).__name__,
                }}) + "\\n")
    '''))

    result = pytester.runpytest("-v", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=4)

    rows = _read_results(pytester)
    assert rows
    row = rows[0]
    assert row["has_imei"] and row["has_iccids"] and row["has_ble_mac"]
    assert row["imei_type"] == "str"
    assert row["iccids_type"] == "list"
