#!/usr/bin/env python3
"""Tests for the streaming infrastructure.

Tests cover:
1. Batching strategies (newline, byte count, timeout)
2. Multi-subscriber fan-out
3. Subscriber lifecycle (connect, receive, disconnect)
4. Latency characteristics
5. Error handling and recovery

Run with:
    cd apps/edge/mtib-server
    PYTHONPATH=src:../../../libs/python:../../../libs/protocols:../../../libs \
        pytest tests/test_streaming.py -v
"""

import queue
import struct
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock

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
    Subscription,
    UartBatchingMixin,
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


class TestBatchConfig(unittest.TestCase):
    """Test BatchConfig creation and defaults."""

    def test_default_config(self):
        config = BatchConfig()
        self.assertEqual(config.strategy, BatchStrategy.NEWLINE_OR_BYTES)
        self.assertEqual(config.max_bytes, 256)
        self.assertEqual(config.timeout_ms, 50)

    def test_uart_batch_config(self):
        config = UartBatchingMixin.create_uart_batch_config()
        self.assertEqual(config.strategy, BatchStrategy.NEWLINE_OR_BYTES)
        self.assertEqual(config.max_bytes, 256)
        self.assertEqual(config.timeout_ms, 50)

    def test_power_batch_config(self):
        config = PowerStreamMixin.create_power_batch_config()
        self.assertEqual(config.strategy, BatchStrategy.TIMEOUT_OR_BYTES)
        self.assertEqual(config.timeout_ms, 10)


class TestStreamBroadcaster(unittest.TestCase):
    """Test StreamBroadcaster core functionality."""

    def setUp(self):
        self.logger = MockLogger()

    def tearDown(self):
        pass

    def test_create_broadcaster(self):
        broadcaster = StreamBroadcaster(
            name="test",
            logger=self.logger,
        )
        self.assertEqual(broadcaster.name, "test")
        self.assertFalse(broadcaster.running)

    def test_subscribe_unsubscribe(self):
        broadcaster = StreamBroadcaster(
            name="test",
            logger=self.logger,
        )

        # Subscribe
        sub = broadcaster.subscribe()
        self.assertIsInstance(sub, Subscription)
        self.assertTrue(sub.active)
        self.assertEqual(broadcaster.stats.subscriber_count, 1)

        # Unsubscribe
        sub.unsubscribe()
        self.assertFalse(sub.active)
        self.assertEqual(broadcaster.stats.subscriber_count, 0)

    def test_multiple_subscribers(self):
        # Use no-batching config for immediate delivery
        config = BatchConfig(strategy=BatchStrategy.NONE)
        broadcaster = StreamBroadcaster(
            name="test",
            logger=self.logger,
            batch_config=config,
        )

        subs = [broadcaster.subscribe() for _ in range(5)]
        self.assertEqual(broadcaster.stats.subscriber_count, 5)

        # All should receive data
        broadcaster.feed(b"hello")
        time.sleep(0.05)

        for i, sub in enumerate(subs):
            data = sub.get(timeout=0.5)
            self.assertIsNotNone(data, f"Subscriber {i} got None")
            self.assertIn(b"hello", data)

        # Unsubscribe some
        subs[0].unsubscribe()
        subs[2].unsubscribe()
        self.assertEqual(broadcaster.stats.subscriber_count, 3)

        broadcaster.stop()


class TestNewlineBatching(unittest.TestCase):
    """Test newline-based batching strategy."""

    def setUp(self):
        self.logger = MockLogger()
        config = BatchConfig(
            strategy=BatchStrategy.NEWLINE_OR_BYTES,
            max_bytes=256,
            timeout_ms=50,
        )
        self.broadcaster = StreamBroadcaster(
            name="test-newline",
            logger=self.logger,
            batch_config=config,
        )

    def tearDown(self):
        self.broadcaster.stop()

    def test_newline_triggers_flush(self):
        sub = self.broadcaster.subscribe()

        # Feed partial line
        self.broadcaster.feed(b"hello")
        data = sub.get(timeout=0.01)
        self.assertIsNone(data)  # Should not flush yet

        # Feed newline
        self.broadcaster.feed(b"\n")
        time.sleep(0.01)
        data = sub.get(timeout=0.1)
        self.assertEqual(data, b"hello\n")

    def test_carriage_return_triggers_flush(self):
        sub = self.broadcaster.subscribe()

        self.broadcaster.feed(b"line1\rline2\n")
        time.sleep(0.01)

        # Should get two chunks
        data1 = sub.get(timeout=0.1)
        data2 = sub.get(timeout=0.1)

        self.assertEqual(data1, b"line1\r")
        self.assertEqual(data2, b"line2\n")

    def test_max_bytes_triggers_flush(self):
        config = BatchConfig(
            strategy=BatchStrategy.NEWLINE_OR_BYTES,
            max_bytes=10,
            timeout_ms=1000,  # Long timeout to ensure byte limit triggers first
        )
        broadcaster = StreamBroadcaster(
            name="test-bytes",
            logger=self.logger,
            batch_config=config,
        )
        sub = broadcaster.subscribe()

        # Feed more than max_bytes without newline
        broadcaster.feed(b"x" * 25)
        time.sleep(0.01)

        # Should get chunks of max_bytes
        data1 = sub.get(timeout=0.1)
        self.assertEqual(len(data1), 10)

        data2 = sub.get(timeout=0.1)
        self.assertEqual(len(data2), 10)

        broadcaster.stop()

    def test_timeout_triggers_flush(self):
        config = BatchConfig(
            strategy=BatchStrategy.NEWLINE_OR_BYTES,
            max_bytes=1000,
            timeout_ms=50,
        )
        broadcaster = StreamBroadcaster(
            name="test-timeout",
            logger=self.logger,
            batch_config=config,
        )

        # Start flush thread by starting with dummy source
        stop_event = threading.Event()

        def dummy_source():
            if stop_event.is_set():
                return None
            time.sleep(0.1)
            return None

        broadcaster.start_with_source(dummy_source)
        sub = broadcaster.subscribe()

        # Feed data without newline
        broadcaster.feed(b"partial data")

        # Wait for timeout flush
        time.sleep(0.15)

        data = sub.get(timeout=0.1)
        self.assertEqual(data, b"partial data")

        stop_event.set()
        broadcaster.stop()


class TestTimeoutBatching(unittest.TestCase):
    """Test timeout-based batching strategy."""

    def setUp(self):
        self.logger = MockLogger()

    def test_timeout_batching(self):
        config = BatchConfig(
            strategy=BatchStrategy.TIMEOUT_OR_BYTES,
            max_bytes=1000,
            timeout_ms=25,
        )
        broadcaster = StreamBroadcaster(
            name="test-timeout-batch",
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

        # Feed multiple small chunks
        broadcaster.feed(b"a")
        broadcaster.feed(b"b")
        broadcaster.feed(b"c")

        # Wait for timeout
        time.sleep(0.1)

        data = sub.get(timeout=0.1)
        self.assertEqual(data, b"abc")

        stop_event.set()
        broadcaster.stop()


class TestNoBatching(unittest.TestCase):
    """Test immediate delivery (no batching)."""

    def setUp(self):
        self.logger = MockLogger()
        config = BatchConfig(strategy=BatchStrategy.NONE)
        self.broadcaster = StreamBroadcaster(
            name="test-no-batch",
            logger=self.logger,
            batch_config=config,
        )

    def tearDown(self):
        self.broadcaster.stop()

    def test_immediate_delivery(self):
        sub = self.broadcaster.subscribe()

        # Each feed should immediately broadcast
        self.broadcaster.feed(b"a")
        data = sub.get(timeout=0.1)
        self.assertEqual(data, b"a")

        self.broadcaster.feed(b"b")
        data = sub.get(timeout=0.1)
        self.assertEqual(data, b"b")


class TestSubscription(unittest.TestCase):
    """Test Subscription class functionality."""

    def setUp(self):
        self.logger = MockLogger()
        config = BatchConfig(strategy=BatchStrategy.NONE)
        self.broadcaster = StreamBroadcaster(
            name="test-sub",
            logger=self.logger,
            batch_config=config,
        )

    def tearDown(self):
        self.broadcaster.stop()

    def test_context_manager(self):
        with self.broadcaster.subscribe() as sub:
            self.assertTrue(sub.active)
            self.broadcaster.feed(b"test")
            data = sub.get(timeout=0.1)
            self.assertEqual(data, b"test")
        self.assertFalse(sub.active)

    def test_iterator_protocol(self):
        sub = self.broadcaster.subscribe()

        # Feed some data
        def feed_data():
            for i in range(3):
                self.broadcaster.feed(f"chunk{i}".encode())
                time.sleep(0.05)
            time.sleep(0.1)
            sub.unsubscribe()

        feeder = threading.Thread(target=feed_data)
        feeder.start()

        received = []
        for data in sub:
            received.append(data)
            if len(received) >= 3:
                break

        feeder.join()
        self.assertEqual(len(received), 3)

    def test_get_nowait(self):
        sub = self.broadcaster.subscribe()

        # Should return None when no data
        data = sub.get_nowait()
        self.assertIsNone(data)

        # Feed and get
        self.broadcaster.feed(b"data")
        time.sleep(0.01)
        data = sub.get_nowait()
        self.assertEqual(data, b"data")


class TestMultiSubscriberFanOut(unittest.TestCase):
    """Test that multiple subscribers receive the same data."""

    def setUp(self):
        self.logger = MockLogger()
        config = BatchConfig(strategy=BatchStrategy.NONE)
        self.broadcaster = StreamBroadcaster(
            name="test-fanout",
            logger=self.logger,
            batch_config=config,
        )

    def tearDown(self):
        self.broadcaster.stop()

    def test_all_subscribers_receive_same_data(self):
        subs = [self.broadcaster.subscribe() for _ in range(10)]

        test_data = b"broadcast to all"
        self.broadcaster.feed(test_data)
        time.sleep(0.01)

        for i, sub in enumerate(subs):
            data = sub.get(timeout=0.1)
            self.assertEqual(data, test_data, f"Subscriber {i} didn't receive data")

    def test_late_subscriber_receives_new_data(self):
        sub1 = self.broadcaster.subscribe()

        # Send data before sub2 exists
        self.broadcaster.feed(b"old data")
        time.sleep(0.01)

        sub2 = self.broadcaster.subscribe()

        # sub1 should have the old data
        data = sub1.get(timeout=0.1)
        self.assertEqual(data, b"old data")

        # sub2 should not have the old data
        data = sub2.get_nowait()
        self.assertIsNone(data)

        # Both should receive new data
        self.broadcaster.feed(b"new data")
        time.sleep(0.01)

        self.assertEqual(sub1.get(timeout=0.1), b"new data")
        self.assertEqual(sub2.get(timeout=0.1), b"new data")

    def test_subscriber_disconnect_doesnt_affect_others(self):
        subs = [self.broadcaster.subscribe() for _ in range(3)]

        # Disconnect middle subscriber
        subs[1].unsubscribe()

        # Send data
        self.broadcaster.feed(b"after disconnect")
        time.sleep(0.01)

        # Remaining subscribers should still receive
        self.assertEqual(subs[0].get(timeout=0.1), b"after disconnect")
        self.assertEqual(subs[2].get(timeout=0.1), b"after disconnect")

        # Disconnected subscriber should return None
        self.assertIsNone(subs[1].get_nowait())


class TestLatency(unittest.TestCase):
    """Test latency characteristics."""

    def setUp(self):
        self.logger = MockLogger()

    def test_latency_no_batching(self):
        config = BatchConfig(strategy=BatchStrategy.NONE)
        broadcaster = StreamBroadcaster(
            name="test-latency-none",
            logger=self.logger,
            batch_config=config,
        )
        sub = broadcaster.subscribe()

        latencies = []
        for _ in range(100):
            start = time.time()
            broadcaster.feed(b"x")
            data = sub.get(timeout=1.0)
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            self.assertIsNotNone(data)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # Without batching, latency should be very low
        self.assertLess(avg_latency, 10, f"Average latency {avg_latency}ms too high")
        self.assertLess(max_latency, 50, f"Max latency {max_latency}ms too high")

        broadcaster.stop()

    def test_latency_with_newline_batching(self):
        config = BatchConfig(
            strategy=BatchStrategy.NEWLINE_OR_BYTES,
            max_bytes=256,
            timeout_ms=50,
        )
        broadcaster = StreamBroadcaster(
            name="test-latency-newline",
            logger=self.logger,
            batch_config=config,
        )
        sub = broadcaster.subscribe()

        latencies = []
        for _ in range(50):
            start = time.time()
            broadcaster.feed(b"test line\n")
            data = sub.get(timeout=1.0)
            latency = (time.time() - start) * 1000
            latencies.append(latency)
            self.assertIsNotNone(data)

        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)

        # With newline batching, latency should still be low
        self.assertLess(avg_latency, 20, f"Average latency {avg_latency}ms too high")
        self.assertLess(max_latency, 100, f"Max latency {max_latency}ms too high")

        broadcaster.stop()


class TestBroadcasterWithSource(unittest.TestCase):
    """Test broadcaster with source function."""

    def setUp(self):
        self.logger = MockLogger()

    def test_source_function(self):
        config = BatchConfig(strategy=BatchStrategy.NONE)
        broadcaster = StreamBroadcaster(
            name="test-source",
            logger=self.logger,
            batch_config=config,
        )

        counter = [0]

        def source():
            if counter[0] >= 5:
                return None
            counter[0] += 1
            time.sleep(0.01)
            return f"chunk{counter[0]}".encode()

        broadcaster.start_with_source(source)
        sub = broadcaster.subscribe()

        received = []
        for _ in range(10):
            data = sub.get(timeout=0.5)
            if data:
                received.append(data)
            if len(received) >= 5:
                break

        broadcaster.stop()
        self.assertEqual(len(received), 5)

    def test_stop_broadcaster(self):
        config = BatchConfig(strategy=BatchStrategy.NONE)
        broadcaster = StreamBroadcaster(
            name="test-stop",
            logger=self.logger,
            batch_config=config,
        )

        def source():
            time.sleep(0.01)
            return b"data"

        broadcaster.start_with_source(source)
        self.assertTrue(broadcaster.running)

        broadcaster.stop()
        self.assertFalse(broadcaster.running)


class TestStats(unittest.TestCase):
    """Test broadcaster statistics."""

    def setUp(self):
        self.logger = MockLogger()
        config = BatchConfig(strategy=BatchStrategy.NONE)
        self.broadcaster = StreamBroadcaster(
            name="test-stats",
            logger=self.logger,
            batch_config=config,
        )

    def tearDown(self):
        self.broadcaster.stop()

    def test_stats_tracking(self):
        sub = self.broadcaster.subscribe()

        # Initial stats
        stats = self.broadcaster.stats
        self.assertEqual(stats.total_bytes_read, 0)
        self.assertEqual(stats.total_chunks_delivered, 0)
        self.assertEqual(stats.subscriber_count, 1)

        # Feed data
        self.broadcaster.feed(b"hello")
        time.sleep(0.01)
        sub.get(timeout=0.1)

        stats = self.broadcaster.stats
        self.assertEqual(stats.total_bytes_read, 5)
        self.assertEqual(stats.total_chunks_delivered, 1)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def setUp(self):
        self.logger = MockLogger()

    def test_empty_feed(self):
        config = BatchConfig(strategy=BatchStrategy.NONE)
        broadcaster = StreamBroadcaster(
            name="test-empty",
            logger=self.logger,
            batch_config=config,
        )
        sub = broadcaster.subscribe()

        # Empty data should not produce output
        broadcaster.feed(b"")
        data = sub.get_nowait()
        self.assertIsNone(data)

        broadcaster.stop()

    def test_subscriber_queue_full(self):
        config = BatchConfig(strategy=BatchStrategy.NONE)
        broadcaster = StreamBroadcaster(
            name="test-full-queue",
            logger=self.logger,
            batch_config=config,
        )

        # Small queue
        sub = broadcaster.subscribe(queue_size=2)

        # Fill the queue
        broadcaster.feed(b"1")
        broadcaster.feed(b"2")
        broadcaster.feed(b"3")  # Should be dropped

        # Should only get first two
        data1 = sub.get(timeout=0.1)
        data2 = sub.get(timeout=0.1)
        data3 = sub.get_nowait()

        self.assertEqual(data1, b"1")
        self.assertEqual(data2, b"2")
        self.assertIsNone(data3)

        broadcaster.stop()

    def test_double_unsubscribe(self):
        config = BatchConfig(strategy=BatchStrategy.NONE)
        broadcaster = StreamBroadcaster(
            name="test-double-unsub",
            logger=self.logger,
            batch_config=config,
        )
        sub = broadcaster.subscribe()

        # Should not raise
        sub.unsubscribe()
        sub.unsubscribe()

        broadcaster.stop()

    def test_get_after_unsubscribe(self):
        config = BatchConfig(strategy=BatchStrategy.NONE)
        broadcaster = StreamBroadcaster(
            name="test-get-after-unsub",
            logger=self.logger,
            batch_config=config,
        )
        sub = broadcaster.subscribe()
        sub.unsubscribe()

        # Should return None
        data = sub.get(timeout=0.1)
        self.assertIsNone(data)

        broadcaster.stop()


if __name__ == "__main__":
    unittest.main()
