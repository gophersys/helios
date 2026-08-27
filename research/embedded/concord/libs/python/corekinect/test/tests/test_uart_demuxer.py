"""Tests for UartDemuxer — dual-target UART capture with command sending."""

import os
import queue
import tempfile
import threading
import time
from types import SimpleNamespace
from typing import Dict, List
from unittest.mock import MagicMock

import pytest

from protocols.mtib.mtib_pb2 import HostType, UartStreamRequest

# Import after PYTHONPATH is set
from corekinect.test.uart_demuxer import UartDemuxer


# ── Test fixtures ────────────────────────────────────────


class MockMtib:
    """Mock MtibV1Client that simulates UART streams for testing.

    Feed data with feed() or feed_line(), then UartDemuxer's capture threads
    consume it on each pump cycle. Thread-safe.
    """

    def __init__(self):
        self._queues: Dict[int, queue.Queue] = {}
        self._sent: Dict[int, List[bytes]] = {}
        self._active: Dict[int, threading.Event] = {}

    def feed(self, target, data):
        """Queue raw bytes to be delivered on next pump cycle."""
        if target not in self._queues:
            self._queues[target] = queue.Queue()
        if isinstance(data, str):
            data = data.encode("utf-8")
        self._queues[target].put(data)

    def feed_line(self, target, line):
        """Queue a complete line (appends newline)."""
        text = line if line.endswith("\n") else line + "\n"
        self.feed(target, text)

    def get_sent(self, target) -> List[bytes]:
        """Return all data that was sent TO the given target."""
        return list(self._sent.get(target, []))

    def wait_active(self, target, timeout=5) -> bool:
        """Block until the stream for this target is active."""
        if target not in self._active:
            self._active[target] = threading.Event()
        return self._active[target].wait(timeout=timeout)

    def UartStream(self, target, request_iterator):
        """Mock bidirectional stream: consumes requests, yields responses."""
        if target not in self._queues:
            self._queues[target] = queue.Queue()
        if target not in self._sent:
            self._sent[target] = []
        if target not in self._active:
            self._active[target] = threading.Event()

        self._active[target].set()

        for req in request_iterator:
            if req.data:
                self._sent[target].append(req.data)

            try:
                data = self._queues[target].get_nowait()
            except queue.Empty:
                data = b""

            yield SimpleNamespace(data=data, success=True, target=target)


@pytest.fixture
def mock_mtib():
    """Mock mtib."""
    return MockMtib()


@pytest.fixture
def log_dir():
    """Log dir."""
    with tempfile.TemporaryDirectory() as d:
        yield d


# ── Tests ────────────────────────────────────────────────


class TestDualTargetCapture:
    """Core capture: both APP + COMMS simultaneously."""

    def test_default_targets_are_app_and_comms(self, mock_mtib):
        """Test default targets are app and comms."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        assert set(demuxer._targets) == {UartDemuxer.APP, UartDemuxer.COMMS}

    def test_captures_from_both_targets(self, mock_mtib):
        """Test captures from both targets."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        demuxer.start()
        try:
            # Wait for both streams to be active
            assert mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            assert mock_mtib.wait_active(UartDemuxer.COMMS, timeout=2)

            mock_mtib.feed_line(UartDemuxer.APP, "app boot complete")
            mock_mtib.feed_line(UartDemuxer.COMMS, "comms ready")
            time.sleep(0.1)

            app_logs = demuxer.get_logs(target="app")
            comms_logs = demuxer.get_logs(target="comms")

            assert "app boot complete" in app_logs
            assert "comms ready" in comms_logs
        finally:
            demuxer.stop()

    def test_single_target_mode(self, mock_mtib):
        """Backward compat: can run with just one target."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "hello")
            time.sleep(0.1)

            logs = demuxer.get_logs(target="app")
            assert "hello" in logs
        finally:
            demuxer.stop()

    def test_get_logs_all_targets_returns_tuples(self, mock_mtib):
        """get_logs() with no target returns (target_name, line) tuples."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "from app")
            mock_mtib.feed_line(UartDemuxer.COMMS, "from comms")
            time.sleep(0.1)

            logs = demuxer.get_logs()
            # Should be list of (name, line) tuples
            names = [name for name, _ in logs]
            lines = [line for _, line in logs]
            assert "app" in names
            assert "comms" in names
            assert "from app" in lines
            assert "from comms" in lines
        finally:
            demuxer.stop()


class TestByteAssembly:
    """Lines must assemble correctly from byte-by-byte or chunked data."""

    def test_byte_by_byte_assembly(self, mock_mtib):
        """Simulates MTIB byte-by-byte delivery (old server)."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=500,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)

            # Feed "hello\n" one byte at a time
            for ch in "hello\n":
                mock_mtib.feed(UartDemuxer.APP, ch)
            time.sleep(0.2)

            logs = demuxer.get_logs(target="app")
            assert "hello" in logs
        finally:
            demuxer.stop()

    def test_chunked_assembly(self, mock_mtib):
        """Simulates MTIB batched delivery (new server)."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)

            # Feed multi-line chunk at once
            mock_mtib.feed(UartDemuxer.APP, "line one\nline two\nline three\n")
            time.sleep(0.1)

            logs = demuxer.get_logs(target="app")
            assert logs == ["line one", "line two", "line three"]
        finally:
            demuxer.stop()

    def test_partial_line_carried_forward(self, mock_mtib):
        """Incomplete lines are buffered until newline arrives."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=500,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)

            mock_mtib.feed(UartDemuxer.APP, "partial ")
            time.sleep(0.05)
            # No complete line yet
            assert demuxer.get_logs(target="app") == []

            mock_mtib.feed(UartDemuxer.APP, "line\n")
            time.sleep(0.05)
            assert "partial line" in demuxer.get_logs(target="app")
        finally:
            demuxer.stop()

    def test_cr_lf_handling(self, mock_mtib):
        """Windows-style \\r\\n should not leave \\r in the line."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed(UartDemuxer.APP, "hello world\r\n")
            time.sleep(0.1)

            logs = demuxer.get_logs(target="app")
            assert logs == ["hello world"]
        finally:
            demuxer.stop()


class TestCommandSending:
    """Send commands via queue while capturing."""

    def test_send_command(self, mock_mtib):
        """Test send command."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            demuxer.send("app", "lock_shell")
            time.sleep(0.1)

            sent = mock_mtib.get_sent(UartDemuxer.APP)
            # Should contain \rlock_shell\r
            assert any(b"lock_shell" in s for s in sent)
        finally:
            demuxer.stop()

    def test_send_bytes(self, mock_mtib):
        """Test send bytes."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.COMMS],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.COMMS, timeout=2)
            demuxer.send_bytes("comms", b"\x01\x02\x03")
            time.sleep(0.1)

            sent = mock_mtib.get_sent(UartDemuxer.COMMS)
            assert b"\x01\x02\x03" in sent
        finally:
            demuxer.stop()

    def test_send_during_capture(self, mock_mtib):
        """Commands and capture work simultaneously."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.COMMS],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.COMMS, timeout=2)

            # Feed response data
            mock_mtib.feed_line(UartDemuxer.COMMS, "Mfg shell: mode ON")
            # Send command at the same time
            demuxer.send("comms", "lock_shell")
            time.sleep(0.1)

            # Both should work
            logs = demuxer.get_logs(target="comms")
            sent = mock_mtib.get_sent(UartDemuxer.COMMS)
            assert "Mfg shell: mode ON" in logs
            assert any(b"lock_shell" in s for s in sent)
        finally:
            demuxer.stop()


class TestWaitForLog:
    """Pattern matching with timeout."""

    def test_wait_success(self, mock_mtib):
        """Test wait success."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "boot complete v1.2.3")
            time.sleep(0.1)

            line = demuxer.wait_for_log(r"boot complete v\d+\.\d+", timeout_s=1)
            assert "boot complete v1.2.3" == line
        finally:
            demuxer.stop()

    def test_wait_timeout(self, mock_mtib):
        """Test wait timeout."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            with pytest.raises(TimeoutError):
                demuxer.wait_for_log("will never match", timeout_s=0.3)
        finally:
            demuxer.stop()

    def test_wait_target_filter(self, mock_mtib):
        """wait_for_log with target= only matches that target."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.wait_active(UartDemuxer.COMMS, timeout=2)

            # Put the pattern on COMMS, search on APP — should timeout
            mock_mtib.feed_line(UartDemuxer.COMMS, "mode ON")
            time.sleep(0.1)

            with pytest.raises(TimeoutError):
                demuxer.wait_for_log("mode ON", target="app", timeout_s=0.3)

            # Same pattern, correct target — should succeed
            line = demuxer.wait_for_log("mode ON", target="comms", timeout_s=1)
            assert "mode ON" in line
        finally:
            demuxer.stop()

    def test_wait_any_target(self, mock_mtib):
        """wait_for_log with no target matches across all targets."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.COMMS, timeout=2)
            mock_mtib.feed_line(UartDemuxer.COMMS, "found it here")
            time.sleep(0.1)

            # No target filter — should find it on COMMS
            line = demuxer.wait_for_log("found it", timeout_s=1)
            assert "found it here" == line
        finally:
            demuxer.stop()

    def test_wait_for_delayed_data(self, mock_mtib):
        """Data arrives after wait_for_log is already polling."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)

            # Start waiting in a thread, then feed data after a delay
            result = {}

            def wait_thread():
                """Wait thread."""
                result["line"] = demuxer.wait_for_log("delayed", timeout_s=2)

            t = threading.Thread(target=wait_thread)
            t.start()

            time.sleep(0.3)
            mock_mtib.feed_line(UartDemuxer.APP, "delayed response")

            t.join(timeout=3)
            assert result.get("line") == "delayed response"
        finally:
            demuxer.stop()


class TestLocalFileWriting:
    """Incremental file persistence for crash safety."""

    def test_writes_log_files(self, mock_mtib, log_dir):
        """Test writes log files."""
        demuxer = UartDemuxer(mtib=mock_mtib, log_dir=log_dir, pump_hz=200)
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "app line 1")
            mock_mtib.feed_line(UartDemuxer.COMMS, "comms line 1")
            time.sleep(0.2)
        finally:
            demuxer.stop()

        # Check files exist and have content
        app_path = os.path.join(log_dir, "uart_app.log")
        comms_path = os.path.join(log_dir, "uart_comms.log")

        assert os.path.exists(app_path)
        assert os.path.exists(comms_path)

        with open(app_path) as f:
            content = f.read()
            assert "app line 1" in content

        with open(comms_path) as f:
            content = f.read()
            assert "comms line 1" in content

    def test_file_has_posix_timestamps(self, mock_mtib, log_dir):
        """Test file has posix timestamps."""
        demuxer = UartDemuxer(mtib=mock_mtib, log_dir=log_dir, pump_hz=200)
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "timestamped")
            time.sleep(0.1)
        finally:
            demuxer.stop()

        with open(os.path.join(log_dir, "uart_app.log")) as f:
            line = f.readline()
            # Format: [posix_us] text
            assert line.startswith("[")
            # Extract timestamp and verify it's a valid POSIX microsecond timestamp
            ts_str = line.split("]")[0].strip("[")
            ts = int(ts_str)
            # Should be a recent POSIX timestamp in microseconds
            now_us = int(time.time() * 1_000_000)
            assert abs(ts - now_us) < 5_000_000  # within 5 seconds

    def test_crash_safety_file_written_before_stop(self, mock_mtib, log_dir):
        """Data is flushed to file immediately — survives crash."""
        demuxer = UartDemuxer(mtib=mock_mtib, log_dir=log_dir, pump_hz=200)
        demuxer.start()

        mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
        mock_mtib.feed_line(UartDemuxer.APP, "crash safe data")
        time.sleep(0.2)

        # Read file BEFORE calling stop() — simulates crash
        app_path = os.path.join(log_dir, "uart_app.log")
        assert os.path.exists(app_path)
        with open(app_path) as f:
            assert "crash safe data" in f.read()

        demuxer.stop()

    def test_no_log_dir_means_no_files(self, mock_mtib):
        """Without log_dir, no files are created."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "no file")
            time.sleep(0.1)

            # In-memory capture still works
            assert "no file" in demuxer.get_logs(target="app")
        finally:
            demuxer.stop()


class TestOnLineCallback:
    """Callback integration for ArtifactWriter pipeline."""

    def test_callback_fires_for_each_line(self, mock_mtib):
        """Test callback fires for each line."""
        received = []

        def on_line(target_name, posix_us, line):
            """On line."""
            received.append((target_name, posix_us, line))

        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        demuxer.on_line = on_line
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "callback test")
            time.sleep(0.1)

            assert len(received) >= 1
            name, ts, line = received[0]
            assert name == "app"
            assert isinstance(ts, int)
            assert ts > 0
            assert line == "callback test"
        finally:
            demuxer.stop()

    def test_callback_includes_target_name(self, mock_mtib):
        """Test callback includes target name."""
        received = []
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        demuxer.on_line = lambda name, ts, line: received.append(name)
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.wait_active(UartDemuxer.COMMS, timeout=2)

            mock_mtib.feed_line(UartDemuxer.APP, "from app")
            mock_mtib.feed_line(UartDemuxer.COMMS, "from comms")
            time.sleep(0.1)

            assert "app" in received
            assert "comms" in received
        finally:
            demuxer.stop()

    def test_callback_error_does_not_crash_capture(self, mock_mtib):
        """A broken callback must never crash the capture thread."""

        def bad_callback(name, ts, line):
            """Bad callback."""
            raise RuntimeError("callback exploded")

        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.on_line = bad_callback
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)

            mock_mtib.feed_line(UartDemuxer.APP, "line one")
            time.sleep(0.1)
            mock_mtib.feed_line(UartDemuxer.APP, "line two")
            time.sleep(0.1)

            # Capture should continue despite callback errors
            logs = demuxer.get_logs(target="app")
            assert "line one" in logs
            assert "line two" in logs
        finally:
            demuxer.stop()


class TestTimeline:
    """Merged timeline across targets."""

    def test_get_timeline_sorted(self, mock_mtib):
        """Test get timeline sorted."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.wait_active(UartDemuxer.COMMS, timeout=2)

            mock_mtib.feed_line(UartDemuxer.APP, "app first")
            time.sleep(0.05)
            mock_mtib.feed_line(UartDemuxer.COMMS, "comms second")
            time.sleep(0.1)

            timeline = demuxer.get_timeline()
            assert len(timeline) >= 2

            # Verify sorted by timestamp
            timestamps = [ts for ts, _, _ in timeline]
            assert timestamps == sorted(timestamps)

            # Verify both targets present
            targets = [name for _, name, _ in timeline]
            assert "app" in targets
            assert "comms" in targets
        finally:
            demuxer.stop()

    def test_get_timeline_since_filter(self, mock_mtib):
        """Test get timeline since filter."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)

            mock_mtib.feed_line(UartDemuxer.APP, "old line")
            time.sleep(0.1)
            marker = time.monotonic()
            time.sleep(0.05)
            mock_mtib.feed_line(UartDemuxer.APP, "new line")
            time.sleep(0.1)

            timeline = demuxer.get_timeline(since=marker)
            lines = [line for _, _, line in timeline]
            assert "new line" in lines
            assert "old line" not in lines
        finally:
            demuxer.stop()


class TestClearAndDump:
    """Buffer management."""

    def test_clear_resets_memory_buffer(self, mock_mtib):
        """Test clear resets memory buffer."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "before clear")
            time.sleep(0.1)

            assert len(demuxer.get_logs(target="app")) > 0
            demuxer.clear()
            assert len(demuxer.get_logs(target="app")) == 0
        finally:
            demuxer.stop()

    def test_clear_does_not_affect_files(self, mock_mtib, log_dir):
        """Test clear does not affect files."""
        demuxer = UartDemuxer(mtib=mock_mtib, log_dir=log_dir, pump_hz=200)
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "persistent")
            time.sleep(0.1)

            demuxer.clear()

            # Memory cleared
            assert len(demuxer.get_logs(target="app")) == 0
        finally:
            demuxer.stop()

        # File still has the data
        with open(os.path.join(log_dir, "uart_app.log")) as f:
            assert "persistent" in f.read()

    def test_dump_to_file_single_target(self, mock_mtib):
        """Test dump to file single target."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "dump test")
            time.sleep(0.1)
        finally:
            demuxer.stop()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            path = f.name

        try:
            demuxer.dump_to_file(path, target="app")
            with open(path) as f:
                content = f.read()
                assert "dump test" in content
        finally:
            os.unlink(path)

    def test_dump_to_file_merged(self, mock_mtib):
        """Test dump to file merged."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)
            mock_mtib.feed_line(UartDemuxer.APP, "app line")
            mock_mtib.feed_line(UartDemuxer.COMMS, "comms line")
            time.sleep(0.1)
        finally:
            demuxer.stop()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            path = f.name

        try:
            demuxer.dump_to_file(path)
            with open(path) as f:
                content = f.read()
                assert "[app]" in content
                assert "[comms]" in content
                assert "app line" in content
                assert "comms line" in content
        finally:
            os.unlink(path)


class TestPumpRate:
    """Dynamic pump rate control."""

    def test_set_pump_rate(self, mock_mtib):
        """Test set pump rate."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=20)
        assert demuxer._pump_interval == pytest.approx(0.05)

        demuxer.set_pump_rate(100)
        assert demuxer._pump_interval == pytest.approx(0.01)

    def test_high_pump_rate_still_captures(self, mock_mtib):
        """Even at very high pump rates, data is captured correctly."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=500,
        )
        demuxer.start()
        try:
            mock_mtib.wait_active(UartDemuxer.APP, timeout=2)

            for i in range(10):
                mock_mtib.feed_line(UartDemuxer.APP, f"line {i}")
            time.sleep(0.3)

            logs = demuxer.get_logs(target="app")
            assert len(logs) == 10
        finally:
            demuxer.stop()


class TestTargetResolution:
    """String shorthand for targets."""

    def test_resolve_app(self, mock_mtib):
        """Test resolve app."""
        demuxer = UartDemuxer(mtib=mock_mtib)
        assert demuxer._resolve_target("app") == UartDemuxer.APP
        assert demuxer._resolve_target("APP") == UartDemuxer.APP

    def test_resolve_comms(self, mock_mtib):
        """Test resolve comms."""
        demuxer = UartDemuxer(mtib=mock_mtib)
        assert demuxer._resolve_target("comms") == UartDemuxer.COMMS
        assert demuxer._resolve_target("COMMS") == UartDemuxer.COMMS

    def test_resolve_hosttype_passthrough(self, mock_mtib):
        """Test resolve hosttype passthrough."""
        demuxer = UartDemuxer(mtib=mock_mtib)
        assert demuxer._resolve_target(UartDemuxer.APP) == UartDemuxer.APP

    def test_resolve_unknown_raises(self, mock_mtib):
        """Test resolve unknown raises."""
        demuxer = UartDemuxer(mtib=mock_mtib)
        with pytest.raises(ValueError, match="Unknown target"):
            demuxer._resolve_target("bluetooth")


class TestLifecycle:
    """Start/stop behavior."""

    def test_double_start_is_noop(self, mock_mtib):
        """Test double start is noop."""
        demuxer = UartDemuxer(
            mtib=mock_mtib,
            targets=[UartDemuxer.APP],
            pump_hz=200,
        )
        demuxer.start()
        try:
            thread_count = len(demuxer._threads)
            demuxer.start()  # should not create more threads
            assert len(demuxer._threads) == thread_count
        finally:
            demuxer.stop()

    def test_stop_joins_threads(self, mock_mtib):
        """Test stop joins threads."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        demuxer.start()
        assert len(demuxer._threads) == 2
        demuxer.stop()
        assert len(demuxer._threads) == 0

    def test_is_running_property(self, mock_mtib):
        """Test is running property."""
        demuxer = UartDemuxer(mtib=mock_mtib, pump_hz=200)
        assert not demuxer.is_running
        demuxer.start()
        assert demuxer.is_running
        demuxer.stop()
        assert not demuxer.is_running
