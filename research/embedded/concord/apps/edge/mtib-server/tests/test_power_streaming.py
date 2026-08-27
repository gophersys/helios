#!/usr/bin/env python3
"""Tests for power stream multi-subscriber support.

These tests verify that the power handler correctly uses the streaming
infrastructure for multi-subscriber broadcast.

Run with:
    cd apps/edge/mtib-server
    PYTHONPATH=src:../../../libs/python:../../../libs/protocols:../../../libs \
        pytest tests/test_power_streaming.py -v
"""

import struct
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
    PowerStreamMixin,
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


class TestPowerStreamMixin(unittest.TestCase):
    """Test power stream configuration."""

    def test_power_config_values(self):
        """Verify power stream batching constants."""
        self.assertEqual(PowerStreamMixin.POWER_BATCH_TIMEOUT_MS, 10)

    def test_create_power_batch_config(self):
        """Verify power batch config creation."""
        config = PowerStreamMixin.create_power_batch_config()

        self.assertEqual(config.strategy, BatchStrategy.TIMEOUT_OR_BYTES)
        self.assertEqual(config.timeout_ms, 10)
        self.assertEqual(config.max_bytes, 4096)


class TestPowerSampleFormat(unittest.TestCase):
    """Test power sample binary format."""

    def test_sample_packing(self):
        """Test power sample binary format."""
        # Format: <iff = little-endian int, float, float
        timestamp_ms = 12345
        voltage_mv = 4500.0
        current_ma = 125.5

        packed = struct.pack("<iff", timestamp_ms, voltage_mv, current_ma)
        self.assertEqual(len(packed), 12)  # 4 + 4 + 4

        # Unpack and verify
        ts, v, i = struct.unpack("<iff", packed)
        self.assertEqual(ts, timestamp_ms)
        self.assertAlmostEqual(v, voltage_mv, places=1)
        self.assertAlmostEqual(i, current_ma, places=1)

    def test_multiple_samples(self):
        """Test multiple samples in one chunk."""
        samples = [
            (100, 4500.0, 120.0),
            (110, 4501.0, 121.5),
            (120, 4499.0, 119.0),
        ]

        # Pack all samples
        data = b""
        for ts, v, i in samples:
            data += struct.pack("<iff", ts, v, i)

        self.assertEqual(len(data), 36)  # 3 * 12

        # Unpack
        offset = 0
        unpacked = []
        while offset < len(data):
            ts, v, i = struct.unpack("<iff", data[offset : offset + 12])
            unpacked.append((ts, v, i))
            offset += 12

        self.assertEqual(len(unpacked), 3)
        for orig, unp in zip(samples, unpacked):
            self.assertEqual(orig[0], unp[0])
            self.assertAlmostEqual(orig[1], unp[1], places=1)
            self.assertAlmostEqual(orig[2], unp[2], places=1)


class TestPowerBroadcaster(unittest.TestCase):
    """Test power broadcaster behavior."""

    def setUp(self):
        self.logger = MockLogger()
        self.config = PowerStreamMixin.create_power_batch_config()
        self.broadcaster = StreamBroadcaster(
            name="test-power",
            logger=self.logger,
            batch_config=self.config,
        )

    def tearDown(self):
        self.broadcaster.stop()

    def test_multiple_power_subscribers(self):
        """Test multiple subscribers receive same power data."""
        subs = [self.broadcaster.subscribe() for _ in range(3)]

        # Simulate power sample
        sample = struct.pack("<iff", 1000, 4500.0, 125.0)
        self.broadcaster.feed(sample)
        self.broadcaster.flush_now()  # Force immediate delivery

        for idx, sub in enumerate(subs):
            data = sub.get(timeout=0.1)
            self.assertIsNotNone(data, f"Subscriber {idx} got None")
            ts, v, i_ma = struct.unpack("<iff", data)
            self.assertEqual(ts, 1000)
            self.assertAlmostEqual(v, 4500.0, places=1)

    def test_sample_batching(self):
        """Test that samples are batched by timeout."""
        stop_event = threading.Event()

        def dummy_source():
            if stop_event.is_set():
                return None
            time.sleep(0.1)
            return None

        self.broadcaster.start_with_source(dummy_source)
        sub = self.broadcaster.subscribe()

        # Feed multiple samples rapidly
        for i in range(5):
            sample = struct.pack("<iff", i * 10, 4500.0, 120.0)
            self.broadcaster.feed(sample)

        # Wait for batch timeout
        time.sleep(0.05)

        # Should get all samples in one or few chunks
        data = sub.get(timeout=0.1)
        self.assertIsNotNone(data)

        # Verify we got multiple samples
        num_samples = len(data) // 12
        self.assertGreater(num_samples, 1)

        stop_event.set()
        self.broadcaster.stop()


class TestPowerStreamLatency(unittest.TestCase):
    """Test power stream latency characteristics."""

    def setUp(self):
        self.logger = MockLogger()

    def test_sample_delivery_latency(self):
        """Test latency for power sample delivery."""
        config = BatchConfig(
            strategy=BatchStrategy.TIMEOUT_OR_BYTES,
            max_bytes=4096,
            timeout_ms=10,
        )
        broadcaster = StreamBroadcaster(
            name="test-power-latency",
            logger=self.logger,
            batch_config=config,
        )
        sub = broadcaster.subscribe()

        latencies = []
        for i in range(50):
            sample = struct.pack("<iff", i * 10, 4500.0, 120.0)
            start = time.time()
            broadcaster.feed(sample)
            broadcaster.flush_now()  # Force immediate delivery
            data = sub.get(timeout=1.0)
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            self.assertIsNotNone(data)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        self.assertLess(avg_latency, 10, f"Average latency {avg_latency}ms too high")
        self.assertLess(max_latency, 50, f"Max latency {max_latency}ms too high")
        print(f"Power sample latency: avg={avg_latency:.2f}ms, max={max_latency:.2f}ms")

        broadcaster.stop()


if __name__ == "__main__":
    unittest.main()
