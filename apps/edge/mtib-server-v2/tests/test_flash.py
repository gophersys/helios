"""Tests for FlashHandler."""

import subprocess
import threading
from pathlib import Path
from subprocess import CompletedProcess
from unittest.mock import MagicMock, patch

import pytest

from src.providers.handlers.flash import FlashHandler
from src.shared.types import (
    FlashEraseRequest,
    FlashInfoRequest,
    FlashProgramRequest,
    FlashWriteRequest,
)


@pytest.fixture
def flash_handler(logger, hardware, assets_dir):
    return FlashHandler(logger, hardware, assets_dir)


@pytest.fixture
def mock_debug_handler():
    handler = MagicMock()
    session = MagicMock()
    session.probe_id = "821009543"
    session.target_id = "nrf52840"
    handler._sessions = {"test-session": session}
    return handler


@pytest.fixture
def firmware_file(assets_dir):
    fw_path = Path(assets_dir) / "test_firmware.hex"
    fw_path.write_bytes(b":020000040000FA\n" * 100)
    return fw_path


class TestFlashInfo:
    def test_returns_flash_regions(self, flash_handler, context):
        response = flash_handler.info(FlashInfoRequest(), context)
        assert response.success is True
        assert len(response.regions) == 1
        region = response.regions[0]
        assert region.start == 0x00000000
        assert region.size == 0x100000
        assert region.sector_size == 4096
        assert region.writable is True


class TestFlashProgram:
    @patch("src.providers.handlers.flash.subprocess.run")
    @patch("src.providers.handlers.flash.time.sleep", return_value=None)
    def test_program_success(self, mock_sleep, mock_run, flash_handler, mock_debug_handler, firmware_file, context):
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        flash_handler.set_debug_handler(mock_debug_handler)

        request = FlashProgramRequest(
            session_id="test-session",
            filename="test_firmware.hex",
            erase_before=True,
            verify_after=True,
            reset_after=False,
        )
        response = flash_handler.program(request, context)

        assert response.success is True
        assert response.bytes_programmed == firmware_file.stat().st_size
        assert response.time_ms >= 0

    def test_missing_file_returns_error(self, flash_handler, mock_debug_handler, context):
        flash_handler.set_debug_handler(mock_debug_handler)

        request = FlashProgramRequest(
            session_id="test-session",
            filename="nonexistent.hex",
            erase_before=False,
            verify_after=False,
            reset_after=False,
        )
        response = flash_handler.program(request, context)

        assert response.success is False
        assert "not found" in response.message

    @patch("src.providers.handlers.flash.subprocess.run")
    @patch("src.providers.handlers.flash.time.sleep", return_value=None)
    def test_recover_retry_on_first_failure(self, mock_sleep, mock_run, flash_handler, mock_debug_handler, firmware_file, context):
        # First call (recover attempt 1) fails, second call (recover attempt 2) succeeds,
        # third call (program) succeeds
        mock_run.side_effect = [
            CompletedProcess(args=[], returncode=1, stdout="", stderr="recover failed"),
            CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
            CompletedProcess(args=[], returncode=0, stdout="", stderr=""),
        ]
        flash_handler.set_debug_handler(mock_debug_handler)

        request = FlashProgramRequest(
            session_id="test-session",
            filename="test_firmware.hex",
            erase_before=True,
            verify_after=False,
            reset_after=False,
        )
        response = flash_handler.program(request, context)

        assert response.success is True
        assert mock_run.call_count == 3  # 2 recover attempts + 1 program

    @patch("src.providers.handlers.flash.subprocess.run")
    def test_nrfjprog_not_found(self, mock_run, flash_handler, mock_debug_handler, firmware_file, context):
        mock_run.side_effect = FileNotFoundError("nrfjprog")
        flash_handler.set_debug_handler(mock_debug_handler)

        request = FlashProgramRequest(
            session_id="test-session",
            filename="test_firmware.hex",
            erase_before=False,
            verify_after=False,
            reset_after=False,
        )
        response = flash_handler.program(request, context)

        assert response.success is False
        assert "nrfjprog not found" in response.message

    @patch("src.providers.handlers.flash.subprocess.run")
    def test_timeout_returns_error(self, mock_run, flash_handler, mock_debug_handler, firmware_file, context):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="nrfjprog", timeout=60)
        flash_handler.set_debug_handler(mock_debug_handler)

        request = FlashProgramRequest(
            session_id="test-session",
            filename="test_firmware.hex",
            erase_before=False,
            verify_after=False,
            reset_after=False,
        )
        response = flash_handler.program(request, context)

        assert response.success is False
        assert "timed out" in response.message

    @patch("src.providers.handlers.flash.subprocess.run")
    @patch("src.providers.handlers.flash.time.sleep", return_value=None)
    def test_verify_flag(self, mock_sleep, mock_run, flash_handler, mock_debug_handler, firmware_file, context):
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        flash_handler.set_debug_handler(mock_debug_handler)

        request = FlashProgramRequest(
            session_id="test-session",
            filename="test_firmware.hex",
            erase_before=True,
            verify_after=True,
            reset_after=False,
        )
        flash_handler.program(request, context)

        # The program call is the last one (after recover calls).
        # Find the call that contains --program
        program_call = None
        for call in mock_run.call_args_list:
            cmd = call[0][0] if call[0] else call[1].get("args", [])
            if "--program" in cmd:
                program_call = cmd
                break

        assert program_call is not None
        assert "--verify" in program_call

    @patch("src.providers.handlers.flash.subprocess.run")
    @patch("src.providers.handlers.flash.time.sleep", return_value=None)
    def test_sector_erase_flag(self, mock_sleep, mock_run, flash_handler, mock_debug_handler, firmware_file, context):
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        flash_handler.set_debug_handler(mock_debug_handler)

        request = FlashProgramRequest(
            session_id="test-session",
            filename="test_firmware.hex",
            erase_before=True,
            verify_after=False,
            reset_after=False,
        )
        flash_handler.program(request, context)

        # Find the --program call and check for --sectorerase
        program_call = None
        for call in mock_run.call_args_list:
            cmd = call[0][0] if call[0] else call[1].get("args", [])
            if "--program" in cmd:
                program_call = cmd
                break

        assert program_call is not None
        assert "--sectorerase" in program_call


class TestFlashErase:
    @patch("src.providers.handlers.flash.subprocess.run")
    def test_chip_erase_success(self, mock_run, flash_handler, mock_debug_handler, context):
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        flash_handler.set_debug_handler(mock_debug_handler)

        request = FlashEraseRequest(session_id="test-session", address=0, size=0)
        response = flash_handler.erase(request, context)

        assert response.success is True
        assert "erased" in response.message.lower()

    @patch("src.providers.handlers.flash.subprocess.run")
    def test_erase_failure_returns_error(self, mock_run, flash_handler, mock_debug_handler, context):
        mock_run.return_value = CompletedProcess(args=[], returncode=1, stdout="", stderr="erase error")
        flash_handler.set_debug_handler(mock_debug_handler)

        request = FlashEraseRequest(session_id="test-session", address=0, size=0)
        response = flash_handler.erase(request, context)

        assert response.success is False
        assert "erase error" in response.message

    def test_sector_erase_not_implemented(self, flash_handler, mock_debug_handler, context):
        flash_handler.set_debug_handler(mock_debug_handler)

        request = FlashEraseRequest(session_id="test-session", address=0x1000, size=4096)
        response = flash_handler.erase(request, context)

        assert response.success is False
        assert "not yet implemented" in response.message.lower()


class TestFlashWrite:
    def test_write_not_implemented(self, flash_handler, context):
        request = FlashWriteRequest(session_id="test-session", address=0x0, data=b"\x00\x01")
        response = flash_handler.write(request, context)

        assert response.success is False
        assert response.bytes_written == 0


class TestFlashProbeIntegration:
    @patch("src.providers.handlers.flash.subprocess.run")
    def test_uses_probe_manager_lock(self, mock_run, flash_handler, mock_debug_handler, firmware_file, context):
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        flash_handler.set_debug_handler(mock_debug_handler)

        mock_pm = MagicMock()
        lock = threading.Lock()
        mock_pm.get_probe_lock.return_value = lock
        mock_pm.prepare_mux_for_target.return_value = None
        flash_handler.set_probe_manager(mock_pm)

        request = FlashProgramRequest(
            session_id="test-session",
            filename="test_firmware.hex",
            erase_before=False,
            verify_after=False,
            reset_after=False,
        )
        flash_handler.program(request, context)

        mock_pm.get_probe_lock.assert_called_with("821009543")

    @patch("src.providers.handlers.flash.subprocess.run")
    def test_mux_preparation_called(self, mock_run, flash_handler, mock_debug_handler, firmware_file, context):
        mock_run.return_value = CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        flash_handler.set_debug_handler(mock_debug_handler)

        mock_pm = MagicMock()
        mock_pm.get_probe_lock.return_value = threading.Lock()
        mock_pm.prepare_mux_for_target.return_value = None
        flash_handler.set_probe_manager(mock_pm)

        request = FlashProgramRequest(
            session_id="test-session",
            filename="test_firmware.hex",
            erase_before=False,
            verify_after=False,
            reset_after=False,
        )
        flash_handler.program(request, context)

        mock_pm.prepare_mux_for_target.assert_called_once_with("nrf52840", "821009543")
