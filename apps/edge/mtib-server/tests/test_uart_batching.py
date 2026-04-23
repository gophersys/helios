#!/usr/bin/env python3
"""Tests for UART handler with batching.

These tests verify that the UART handler correctly uses the streaming
infrastructure for batching and multi-subscriber support.

Run with:
    cd apps/edge/mtib-server
    PYTHONPATH=src:../../../libs/python:../../../libs/protocols:../../../libs \
        pytest tests/test_uart_batching.py -v
"""

import queue
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

# Add paths for imports
sys.path.insert(0, "src")
sys.path.insert(0, "../../../libs/python")
sys.path.insert(0, "../../../libs/protocols")
sys.path.insert(0, "../../../libs")

from corekinect.utils import Logger

from src.shared.streaming import (
    BatchConfig,
    BatchStrategy,
    StreamBroadcaster,
    UartBatchingMixin,
)


class MockLogger(Logger):
    """Mock logger for testing."""

    def __init__(self):
        super().__init__(log_name="test")

    def debug(self, msg, *args):
        pass

    def info(self, msg, *args):
        pass

    def warning(self, msg, *args):
        pass

    def error(self, msg, *args):
        pass


class TestUartBatchingMixin(unittest.TestCase):
    """Test UART-specific batching configuration."""

    def test_uart_config_values(self):
        """Verify UART batching constants."""
        self.assertEqual(UartBatchingMixin.UART_MAX_BATCH_BYTES, 256)
        self.assertEqual(UartBatchingMixin.UART_BATCH_TIMEOUT_MS, 50)
        self.assertEqual(UartBatchingMixin.UART_NEWLINE_CHARS, b"\n\r")

    def test_create_uart_batch_config(self):
        """Verify UART batch config creation."""
        config = UartBatchingMixin.create_uart_batch_config()

        self.assertEqual(config.strategy, BatchStrategy.NEWLINE_OR_BYTES)
        self.assertEqual(config.max_bytes, 256)
        self.assertEqual(config.timeout_ms, 50)
        self.assertEqual(config.newline_chars, b"\n\r")


class TestUartBatching(unittest.TestCase):
    """Test UART batching behavior with StreamBroadcaster."""

    def setUp(self):
        self.logger = MockLogger()
        self.config = UartBatchingMixin.create_uart_batch_config()
        self.broadcaster = StreamBroadcaster(
            name="test-uart",
            logger=self.logger,
            batch_config=self.config,
        )

    def tearDown(self):
        self.broadcaster.stop()

    def test_line_by_line_output(self):
        """Test that complete lines are delivered together."""
        sub = self.broadcaster.subscribe()

        # Simulate typical UART output: partial line, then completion
        self.broadcaster.feed(b"[00:00:00.000] Boot")
        self.broadcaster.feed(b"ing...\n")

        time.sleep(0.01)

        data = sub.get(timeout=0.1)
        self.assertEqual(data, b"[00:00:00.000] Booting...\n")

    def test_multiple_lines(self):
        """Test multiple lines are batched separately."""
        sub = self.broadcaster.subscribe()

        self.broadcaster.feed(b"line1\nline2\n")
        time.sleep(0.01)

        data1 = sub.get(timeout=0.1)
        data2 = sub.get(timeout=0.1)

        self.assertEqual(data1, b"line1\n")
        self.assertEqual(data2, b"line2\n")

    def test_long_line_split(self):
        """Test long lines (>256 bytes) are split."""
        config = BatchConfig(
            strategy=BatchStrategy.NEWLINE_OR_BYTES,
            max_bytes=64,
            timeout_ms=50,
        )
        broadcaster = StreamBroadcaster(
            name="test-long-line",
            logger=self.logger,
            batch_config=config,
        )
        sub = broadcaster.subscribe()

        # Send 200 bytes without newline
        long_line = b"x" * 200
        broadcaster.feed(long_line)
        time.sleep(0.01)

        # Should get chunks of 64 bytes
        chunks = []
        for _ in range(10):
            data = sub.get_nowait()
            if data:
                chunks.append(data)

        total_received = sum(len(c) for c in chunks)
        self.assertGreaterEqual(total_received, 128)  # At least 2 chunks

        broadcaster.stop()

    def test_mixed_newlines(self):
        """Test handling of \\r and \\n."""
        sub = self.broadcaster.subscribe()

        self.broadcaster.feed(b"line1\rline2\nline3\r\nline4\n")
        time.sleep(0.01)

        received = []
        for _ in range(10):
            data = sub.get_nowait()
            if data:
                received.append(data)

        # Should have separate chunks for each line ending
        self.assertGreater(len(received), 0)
        total = b"".join(received)
        self.assertEqual(total, b"line1\rline2\nline3\r\nline4\n")

    def test_shell_prompt_scenario(self):
        """Test realistic shell prompt scenario.

        Shell prompts don't have newlines, so they rely on timeout flush.
        We need to start the flush thread via start_with_source.
        """
        # Create broadcaster with flush thread
        config = UartBatchingMixin.create_uart_batch_config()
        broadcaster = StreamBroadcaster(
            name="test-prompt",
            logger=self.logger,
            batch_config=config,
        )

        stop_event = threading.Event()

        def dummy_source():
            if stop_event.is_set():
                return None
            time.sleep(0.1)
            return None

        broadcaster.start_with_source(dummy_source)
        sub = broadcaster.subscribe()

        # Simulate manufacturing shell output
        broadcaster.feed(b"mfg> ")  # No newline
        time.sleep(0.1)  # Wait for timeout flush (50ms config)

        data = sub.get(timeout=0.1)
        self.assertEqual(data, b"mfg> ")

        stop_event.set()
        broadcaster.stop()

    def test_rapid_fire_bytes(self):
        """Test rapid individual byte delivery."""
        sub = self.broadcaster.subscribe()

        # Simulate byte-by-byte UART (worst case)
        for byte in b"test\n":
            self.broadcaster.feed(bytes([byte]))

        time.sleep(0.01)

        data = sub.get(timeout=0.1)
        self.assertEqual(data, b"test\n")


class TestUartMultiSubscriber(unittest.TestCase):
    """Test UART multi-subscriber scenarios."""

    def setUp(self):
        self.logger = MockLogger()
        config = UartBatchingMixin.create_uart_batch_config()
        self.broadcaster = StreamBroadcaster(
            name="test-uart-multi",
            logger=self.logger,
            batch_config=config,
        )

    def tearDown(self):
        self.broadcaster.stop()

    def test_two_clients_same_data(self):
        """Test two clients receive identical data."""
        sub1 = self.broadcaster.subscribe()
        sub2 = self.broadcaster.subscribe()

        self.broadcaster.feed(b"shared output\n")
        time.sleep(0.01)

        data1 = sub1.get(timeout=0.1)
        data2 = sub2.get(timeout=0.1)

        self.assertEqual(data1, data2)
        self.assertEqual(data1, b"shared output\n")

    def test_late_joiner(self):
        """Test late-joining subscriber doesn't get old data."""
        sub1 = self.broadcaster.subscribe()

        # Send data before sub2
        self.broadcaster.feed(b"old line\n")
        time.sleep(0.01)

        sub2 = self.broadcaster.subscribe()

        # Sub1 should have it
        data1 = sub1.get(timeout=0.1)
        self.assertEqual(data1, b"old line\n")

        # Sub2 should not have old data
        data2 = sub2.get_nowait()
        self.assertIsNone(data2)

        # Both should get new data
        self.broadcaster.feed(b"new line\n")
        time.sleep(0.01)

        self.assertEqual(sub1.get(timeout=0.1), b"new line\n")
        self.assertEqual(sub2.get(timeout=0.1), b"new line\n")

    def test_subscriber_crash_recovery(self):
        """Test that subscriber disconnect doesn't affect others."""
        sub1 = self.broadcaster.subscribe()
        sub2 = self.broadcaster.subscribe()
        sub3 = self.broadcaster.subscribe()

        # Simulate disconnect by unsubscribing
        sub2.unsubscribe()

        # Remaining subscribers should still work
        self.broadcaster.feed(b"after disconnect\n")
        time.sleep(0.01)

        self.assertEqual(sub1.get(timeout=0.1), b"after disconnect\n")
        self.assertEqual(sub3.get(timeout=0.1), b"after disconnect\n")

        # Disconnected subscriber should return None
        self.assertIsNone(sub2.get_nowait())


class TestUartLatency(unittest.TestCase):
    """Test UART latency requirements."""

    def setUp(self):
        self.logger = MockLogger()
        config = UartBatchingMixin.create_uart_batch_config()
        self.broadcaster = StreamBroadcaster(
            name="test-uart-latency",
            logger=self.logger,
            batch_config=config,
        )

    def tearDown(self):
        self.broadcaster.stop()

    def test_complete_line_latency(self):
        """Test latency for complete line delivery."""
        sub = self.broadcaster.subscribe()

        latencies = []
        for _ in range(50):
            start = time.time()
            self.broadcaster.feed(b"test line\n")
            data = sub.get(timeout=1.0)
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            self.assertIsNotNone(data)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Complete lines should be delivered quickly
        self.assertLess(avg_latency, 20, f"Average latency {avg_latency}ms too high")
        self.assertLess(max_latency, 100, f"Max latency {max_latency}ms too high")
        print(f"Complete line latency: avg={avg_latency:.2f}ms, max={max_latency:.2f}ms")

    def test_partial_line_timeout_latency(self):
        """Test that partial lines flush within timeout."""
        config = BatchConfig(
            strategy=BatchStrategy.NEWLINE_OR_BYTES,
            max_bytes=256,
            timeout_ms=50,
        )
        broadcaster = StreamBroadcaster(
            name="test-timeout-latency",
            logger=self.logger,
            batch_config=config,
        )

        # Start flush thread
        stop_event = threading.Event()

        def dummy_source():
            if stop_event.is_set():
                return None
            time.sleep(0.1)
            return None

        broadcaster.start_with_source(dummy_source)
        sub = broadcaster.subscribe()

        start = time.time()
        broadcaster.feed(b"no newline")
        data = sub.get(timeout=0.2)
        latency = (time.time() - start) * 1000

        self.assertIsNotNone(data)
        self.assertLess(
            latency, 100,
            f"Partial line flush latency {latency}ms exceeds 100ms target"
        )
        print(f"Partial line flush latency: {latency:.2f}ms")

        stop_event.set()
        broadcaster.stop()


if __name__ == "__main__":
    unittest.main()
