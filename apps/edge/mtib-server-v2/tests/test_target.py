"""Tests for TargetHandler and ProbeManager."""

import subprocess
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest

from src.hardware.revision import HardwareRevision
from src.providers.handlers.target import (
    DPID_FAMILY_MAP,
    ProbeManager,
    TargetHandler,
)
from src.shared.types import DebugProbeType, Empty
from tests.mocks.hardware import MockHardwareContext


@pytest.fixture
def target_handler(logger, hardware):
    return TargetHandler(logger, hardware)


@pytest.fixture
def probe_manager(logger, hardware):
    return ProbeManager(logger, hardware)


@pytest.fixture
def probe_manager_rev12(logger, hardware_rev12):
    return ProbeManager(logger, hardware_rev12)


# ---- helpers for mocking nrfjprog ----

def _make_nrfjprog_mock(serials=None, probe_families=None):
    """Build a side_effect for subprocess.run that simulates nrfjprog.

    Args:
        serials: list of serial strings returned by --ids (default: [])
        probe_families: dict mapping serial -> (target_id, nrfjprog_family)
            e.g. {"821009543": ("nrf52840", "NRF52"), "821009541": ("nrf9151", "NRF91")}
    """
    serials = serials or []
    probe_families = probe_families or {}

    # Build a reverse lookup: serial -> set of families that succeed
    _good_families = {}
    for serial, (_, family) in probe_families.items():
        _good_families[serial] = family

    # DPID that nrfjprog reports for a mismatch
    _family_to_dpid = {"NRF52": 2, "NRF91": 6}

    def _side_effect(cmd, **kwargs):
        if "--ids" in cmd:
            stdout = "\n".join(serials) + "\n" if serials else ""
            return CompletedProcess(args=cmd, returncode=0, stdout=stdout, stderr="")

        if "--memrd" in cmd:
            serial = cmd[cmd.index("--snr") + 1]
            family = cmd[cmd.index("-f") + 1]

            good_family = _good_families.get(serial)
            if good_family and family == good_family:
                return CompletedProcess(args=cmd, returncode=0, stdout="0x00000000", stderr="")
            elif good_family:
                # Wrong family: report the actual DPID
                dpid = _family_to_dpid[good_family]
                return CompletedProcess(
                    args=cmd, returncode=1, stdout="",
                    stderr=f"unexpected debug port ID {dpid}",
                )
            else:
                return CompletedProcess(args=cmd, returncode=1, stdout="", stderr="error -102")

        return CompletedProcess(args=cmd, returncode=1, stdout="", stderr="unknown command")

    return _side_effect


# =========================================================================
# TargetHandler tests
# =========================================================================

class TestListTargets:
    def test_returns_four_targets(self, target_handler, context):
        """list_targets returns exactly 4 hardcoded targets."""
        response = target_handler.list_targets(Empty(), context)
        assert response.success is True
        assert len(response.targets) == 4

    def test_targets_have_correct_arch(self, target_handler, context):
        """Each target has a non-zero architecture."""
        response = target_handler.list_targets(Empty(), context)
        for target in response.targets:
            assert target.arch > 0

    def test_targets_have_capabilities(self, target_handler, context):
        """All targets should have debug and UART capabilities."""
        response = target_handler.list_targets(Empty(), context)
        for target in response.targets:
            assert target.has_debug is True
            assert target.has_uart is True


class TestListProbes:
    def test_with_probe_manager(self, target_handler, logger, hardware, context):
        """list_probes uses ProbeManager mappings when available."""
        pm = ProbeManager(logger, hardware)
        # Manually inject mappings
        from src.providers.handlers.target import ProbeMapping
        pm._mappings = {
            "821009543": ProbeMapping(serial="821009543", target_id="nrf52840", family="NRF52", slot="jlink1"),
            "821009541": ProbeMapping(serial="821009541", target_id="nrf9151", family="NRF91", slot="jlink2"),
        }
        target_handler.set_probe_manager(pm)

        response = target_handler.list_probes(Empty(), context)
        assert response.success is True
        assert len(response.probes) == 2
        serials = {p.serial for p in response.probes}
        assert "821009543" in serials
        assert "821009541" in serials
        for probe in response.probes:
            assert probe.type == DebugProbeType.PROBE_JLINK
            assert len(probe.supported_targets) == 1

    def test_fallback_nrfjprog(self, target_handler, context):
        """Without ProbeManager, list_probes falls back to nrfjprog --ids."""
        mock_run = _make_nrfjprog_mock(serials=["821009543", "821009541"])

        with patch("src.providers.handlers.target.subprocess.run", side_effect=mock_run), \
             patch("src.providers.handlers.target.glob.glob", return_value=[]):
            response = target_handler.list_probes(Empty(), context)

        assert response.success is True
        assert len(response.probes) == 2
        # Fallback probes get all supported targets
        for probe in response.probes:
            assert len(probe.supported_targets) == 4

    def test_nrfjprog_not_available(self, target_handler, context):
        """Returns empty list when nrfjprog is not installed."""
        with patch("src.providers.handlers.target.subprocess.run", side_effect=FileNotFoundError), \
             patch("src.providers.handlers.target.glob.glob", return_value=[]):
            response = target_handler.list_probes(Empty(), context)

        assert response.success is True
        assert len(response.probes) == 0


# =========================================================================
# ProbeManager tests
# =========================================================================

class TestProbeManager:
    def test_discover_dual_mode(self, probe_manager):
        """Two probes identified -> dual mode."""
        mock_run = _make_nrfjprog_mock(
            serials=["821009543", "821009541"],
            probe_families={
                "821009543": ("nrf52840", "NRF52"),
                "821009541": ("nrf9151", "NRF91"),
            },
        )
        with patch("src.providers.handlers.target.subprocess.run", side_effect=mock_run):
            err = probe_manager.discover()

        assert err is None
        assert probe_manager.mode == "dual"
        assert probe_manager.probe_count == 2

    def test_discover_single_mode(self, probe_manager):
        """One probe identified -> single mode."""
        mock_run = _make_nrfjprog_mock(
            serials=["821009543"],
            probe_families={"821009543": ("nrf52840", "NRF52")},
        )
        with patch("src.providers.handlers.target.subprocess.run", side_effect=mock_run):
            err = probe_manager.discover()

        assert err is None
        assert probe_manager.mode == "single"
        assert probe_manager.probe_count == 1

    def test_discover_none_mode(self, probe_manager):
        """No probes detected -> none mode."""
        mock_run = _make_nrfjprog_mock(serials=[])
        with patch("src.providers.handlers.target.subprocess.run", side_effect=mock_run):
            err = probe_manager.discover()

        assert err is None
        assert probe_manager.mode == "none"
        assert probe_manager.probe_count == 0

    def test_resolve_probe_for_target(self, probe_manager):
        """Resolves correct serial for a target after discovery."""
        mock_run = _make_nrfjprog_mock(
            serials=["821009543", "821009541"],
            probe_families={
                "821009543": ("nrf52840", "NRF52"),
                "821009541": ("nrf9151", "NRF91"),
            },
        )
        with patch("src.providers.handlers.target.subprocess.run", side_effect=mock_run):
            probe_manager.discover()

        serial, err = probe_manager.resolve_probe_for_target("nrf52840")
        assert err is None
        assert serial == "821009543"

        serial, err = probe_manager.resolve_probe_for_target("nrf9151")
        assert err is None
        assert serial == "821009541"

    def test_resolve_auto_discovers(self, probe_manager):
        """resolve_probe_for_target triggers discover() if not yet discovered."""
        mock_run = _make_nrfjprog_mock(
            serials=["821009543"],
            probe_families={"821009543": ("nrf52840", "NRF52")},
        )
        with patch("src.providers.handlers.target.subprocess.run", side_effect=mock_run):
            serial, err = probe_manager.resolve_probe_for_target("nrf52840")

        assert err is None
        assert serial == "821009543"
        assert probe_manager._discovered is True

    def test_resolve_single_mode_jlink1(self, probe_manager):
        """Single probe in jlink1 slot can resolve both targets."""
        mock_run = _make_nrfjprog_mock(
            serials=["821009543"],
            probe_families={"821009543": ("nrf52840", "NRF52")},
        )
        with patch("src.providers.handlers.target.subprocess.run", side_effect=mock_run):
            probe_manager.discover()

        # Direct target
        serial, err = probe_manager.resolve_probe_for_target("nrf52840")
        assert err is None
        assert serial == "821009543"

        # Other target reachable via MUX
        serial, err = probe_manager.resolve_probe_for_target("nrf9151")
        assert err is None
        assert serial == "821009543"

    def test_prepare_mux_dual_mode(self, probe_manager_rev12):
        """Dual mode: MUX always set to NORMAL (swap=False)."""
        mock_run = _make_nrfjprog_mock(
            serials=["821009543", "821009541"],
            probe_families={
                "821009543": ("nrf52840", "NRF52"),
                "821009541": ("nrf9151", "NRF91"),
            },
        )
        with patch("src.providers.handlers.target.subprocess.run", side_effect=mock_run), \
             patch("src.providers.handlers.target.time.sleep"):
            probe_manager_rev12.discover()

        with patch.object(probe_manager_rev12.hardware, "set_jlink_mux") as mock_mux, \
             patch("src.providers.handlers.target.time.sleep"):
            err = probe_manager_rev12.prepare_mux_for_target("nrf52840", "821009543")

        assert err is None
        mock_mux.assert_called_once_with(swap=False)

    def test_prepare_mux_single_mode_nrf91(self, probe_manager_rev12):
        """Single mode JLINK1: MUX swapped for NRF91 targets."""
        mock_run = _make_nrfjprog_mock(
            serials=["821009543"],
            probe_families={"821009543": ("nrf52840", "NRF52")},
        )
        with patch("src.providers.handlers.target.subprocess.run", side_effect=mock_run), \
             patch("src.providers.handlers.target.time.sleep"):
            probe_manager_rev12.discover()

        with patch.object(probe_manager_rev12.hardware, "set_jlink_mux") as mock_mux, \
             patch("src.providers.handlers.target.time.sleep"):
            err = probe_manager_rev12.prepare_mux_for_target("nrf9151", "821009543")

        assert err is None
        mock_mux.assert_called_once_with(True)

    def test_get_probe_lock(self, probe_manager):
        """get_probe_lock returns a per-probe threading.Lock."""
        lock1 = probe_manager.get_probe_lock("serial_a")
        lock2 = probe_manager.get_probe_lock("serial_a")
        lock3 = probe_manager.get_probe_lock("serial_b")

        assert lock1 is lock2  # Same serial -> same lock
        assert lock1 is not lock3  # Different serial -> different lock

    def test_dpid_identification(self):
        """DPID_FAMILY_MAP correctly maps ARM debug port IDs."""
        assert DPID_FAMILY_MAP[2] == ("nrf52840", "NRF52")
        assert DPID_FAMILY_MAP[6] == ("nrf9151", "NRF91")
