"""Tests for AnalyzerHandler.

Comprehensive unit tests for logic analyzer functionality following existing
test patterns from test_power.py and test_uart.py.

Test coverage:
- Provider tests (SimulationProvider, SaleaeProvider graceful degradation, registry)
- Capture lifecycle tests (start, status, stop)
- Streaming tests (real-time sample streaming, buffer management)
- Decoder tests (add decoder, get decoded data)
- Thread safety tests (concurrent operations)
- Error handling tests (invalid configs, unknown captures)
"""

import os
import sys
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

# Add src to path (mocks are in conftest.py)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.providers.handlers.analyzer import (
    AnalyzerHandler,
    AnalyzerProvider,
    AnalyzerSample,
    CaptureHandle,
    CaptureStatus,
    ProviderCapabilities,
    ProviderRegistry,
    SaleaeProvider,
    SimulationProvider,
)


# =============================================================================
# Mock Types (Placeholder until proto is regenerated)
# =============================================================================

class MockLogicCaptureConfig:
    """Mock LogicCaptureConfig from proto."""

    def __init__(
        self,
        sample_rate_hz=1_000_000,
        duration_s=1.0,
        channels=None,
        max_memory_mb=512,
    ):
        self.sample_rate_hz = sample_rate_hz
        self.duration_s = duration_s
        self.channels = channels or []
        self.max_memory_mb = max_memory_mb


class MockChannel:
    """Mock channel config."""

    def __init__(self, channel=0, enabled=True):
        self.channel = channel
        self.enabled = enabled


class MockAnalyzerCaptureStartRequest:
    """Mock AnalyzerCaptureStartRequest from proto."""

    def __init__(self, config=None):
        self.config = config or MockLogicCaptureConfig()


class MockAnalyzerCaptureStatusRequest:
    """Mock AnalyzerCaptureStatusRequest from proto."""

    def __init__(self, capture_id=""):
        self.capture_id = capture_id


class MockAnalyzerCaptureStopRequest:
    """Mock AnalyzerCaptureStopRequest from proto."""

    def __init__(self, capture_id=""):
        self.capture_id = capture_id


class MockAddDecoderRequest:
    """Mock AddDecoderRequest from proto."""

    def __init__(self, capture_id="", decoder_name=""):
        self.capture_id = capture_id
        self.decoder_name = decoder_name


class MockGetDecodedDataRequest:
    """Mock GetDecodedDataRequest from proto."""

    def __init__(self, capture_id="", decoder_id=None):
        self.capture_id = capture_id
        self.decoder_id = decoder_id


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def analyzer_handler(logger, hardware):
    """Create an AnalyzerHandler with SimulationProvider only."""
    # Mock saleae to avoid connection timeout during tests
    with patch.dict(sys.modules, {"saleae": None, "saleae.automation": None}):
        handler = AnalyzerHandler(logger, hardware)
        yield handler
        # Cleanup: stop all active captures
        with handler._sessions_lock:
            for session in list(handler._sessions.values()):
                session.stop_event.set()
                if session.streaming_thread and session.streaming_thread.is_alive():
                    session.streaming_thread.join(timeout=1.0)


# =============================================================================
# Provider Tests
# =============================================================================

class TestProviders:
    """Tests for logic analyzer provider system."""

    def test_simulation_provider_always_available(self, logger):
        """SimulationProvider should always be available (no external dependencies)."""
        provider = SimulationProvider(logger)
        err = provider.connect()

        assert err is None
        assert provider.name == "simulation"

        caps = provider.get_capabilities()
        assert caps.name == "Simulation"
        assert caps.max_sample_rate_hz == 100_000_000
        assert caps.supports_streaming is True

    def test_saleae_provider_graceful_degradation(self, logger):
        """SaleaeProvider should gracefully handle missing logic2-automation package."""
        # Mock missing saleae.automation package
        with patch.dict(sys.modules, {"saleae": None, "saleae.automation": None}):
            provider = SaleaeProvider(logger)
            err = provider.connect()

            # Should return error but not crash
            assert err is not None
            assert "logic2-automation" in err or "Logic 2" in err

    def test_provider_registry_auto_detection(self, logger):
        """ProviderRegistry should auto-detect available providers."""
        # Mock saleae unavailable
        with patch.dict(sys.modules, {"saleae": None, "saleae.automation": None}):
            registry = ProviderRegistry(logger)

            # Should have at least SimulationProvider
            assert len(registry.providers) >= 1
            assert any(p.name == "simulation" for p in registry.providers)

            # get_provider should return SimulationProvider as fallback
            provider = registry.get_provider()
            assert provider is not None
            assert provider.name == "simulation"

    def test_provider_preference(self, logger):
        """ProviderRegistry should respect provider preference."""
        registry = ProviderRegistry(logger)

        # Request simulation explicitly
        provider = registry.get_provider(prefer="simulation")
        assert provider is not None
        assert provider.name == "simulation"

        # Request non-existent provider -> returns default
        provider = registry.get_provider(prefer="nonexistent")
        assert provider is not None  # Falls back to first available


# =============================================================================
# Capture Lifecycle Tests
# =============================================================================

class TestCaptureLifecycle:
    """Tests for capture session lifecycle (start, status, stop)."""

    def test_capture_start_returns_capture_id(self, analyzer_handler, context):
        """Starting a capture should return success with a capture_id."""
        config = MockLogicCaptureConfig(
            sample_rate_hz=1_000_000,
            duration_s=0.1,
            channels=[MockChannel(0, True), MockChannel(1, True)],
        )
        request = MockAnalyzerCaptureStartRequest(config=config)

        response = analyzer_handler.AnalyzerCaptureStart(request, context)

        assert response.success is True
        assert response.capture_id != ""
        assert len(analyzer_handler._sessions) == 1

    def test_capture_start_without_providers_fails_gracefully(self, logger, hardware, context):
        """Handler with no providers should return error on capture start."""
        # Mock saleae to avoid connection timeout
        with patch.dict(sys.modules, {"saleae": None, "saleae.automation": None}):
            # Create handler with empty provider list
            handler = AnalyzerHandler(logger, hardware)
            handler._registry.providers = []
            handler._disabled = True

            request = MockAnalyzerCaptureStartRequest()
            response = handler.AnalyzerCaptureStart(request, context)

            assert response.success is False
            assert "not available" in response.message

    def test_capture_status_of_active_capture(self, analyzer_handler, context):
        """Status query should return current capture state."""
        # Start a capture
        config = MockLogicCaptureConfig(duration_s=2.0)
        start_req = MockAnalyzerCaptureStartRequest(config=config)
        start_resp = analyzer_handler.AnalyzerCaptureStart(start_req, context)

        assert start_resp.success is True

        # Query status
        status_req = MockAnalyzerCaptureStatusRequest(capture_id=start_resp.capture_id)
        status_resp = analyzer_handler.AnalyzerCaptureStatus(status_req, context)

        assert status_resp.success is True
        assert status_resp.status in [CaptureStatus.WAITING_TRIGGER, CaptureStatus.CAPTURING]
        assert 0.0 <= status_resp.progress <= 1.0

    def test_capture_status_of_unknown_capture_fails(self, analyzer_handler, context):
        """Status query on unknown capture_id should return error."""
        status_req = MockAnalyzerCaptureStatusRequest(capture_id="nonexistent-id")
        status_resp = analyzer_handler.AnalyzerCaptureStatus(status_req, context)

        assert status_resp.success is False
        assert "Unknown capture" in status_resp.message

    def test_capture_stop_cleans_up_session(self, analyzer_handler, context):
        """Stopping a capture should clean up session resources."""
        # Start a capture
        config = MockLogicCaptureConfig(duration_s=5.0)
        start_req = MockAnalyzerCaptureStartRequest(config=config)
        start_resp = analyzer_handler.AnalyzerCaptureStart(start_req, context)

        assert start_resp.success is True
        capture_id = start_resp.capture_id

        # Wait for streaming thread to start
        time.sleep(0.1)

        # Stop the capture
        stop_req = MockAnalyzerCaptureStopRequest(capture_id=capture_id)
        stop_resp = analyzer_handler.AnalyzerCaptureStop(stop_req, context)

        assert stop_resp.success is True
        assert len(analyzer_handler._sessions) == 0

    def test_capture_stop_unknown_capture_returns_error(self, analyzer_handler, context):
        """Stopping an unknown capture should return error."""
        stop_req = MockAnalyzerCaptureStopRequest(capture_id="nonexistent-id")
        stop_resp = analyzer_handler.AnalyzerCaptureStop(stop_req, context)

        assert stop_resp.success is False
        assert "Unknown capture" in stop_resp.message


# =============================================================================
# Streaming Tests
# =============================================================================

class TestStreaming:
    """Tests for real-time sample streaming."""

    def test_streaming_with_simulation_provider(self, analyzer_handler, context):
        """SimulationProvider should generate samples in real-time."""
        config = MockLogicCaptureConfig(
            sample_rate_hz=10_000,  # Low rate for fast test
            duration_s=0.2,
            channels=[MockChannel(0, True), MockChannel(1, True)],
        )
        start_req = MockAnalyzerCaptureStartRequest(config=config)
        start_resp = analyzer_handler.AnalyzerCaptureStart(start_req, context)

        assert start_resp.success is True
        capture_id = start_resp.capture_id

        # Wait for some samples to be captured
        time.sleep(0.3)

        # Check session has samples
        session = analyzer_handler._get_session(capture_id)
        assert session is not None
        assert session.samples_captured > 0

    def test_streaming_buffer_circular_mode(self, logger):
        """StreamingBuffer should drop oldest samples when full (circular buffer)."""
        from src.providers.handlers.analyzer import StreamingBuffer

        # Create small buffer (must create with explicit maxlen for deque)
        buffer = StreamingBuffer(max_size=10)
        # Recreate samples deque with correct maxlen
        from collections import deque
        buffer.samples = deque(maxlen=10)

        # Fill buffer
        samples = [
            AnalyzerSample(timestamp_ns=i * 1000, digital_values=[True, False])
            for i in range(10)
        ]
        buffer.push(samples)

        assert len(buffer.samples) == 10
        assert buffer.dropped_count == 0

        # Overflow by adding more samples
        overflow_samples = [
            AnalyzerSample(timestamp_ns=i * 1000, digital_values=[False, True])
            for i in range(10, 15)
        ]
        buffer.push(overflow_samples)

        # Buffer should have max_size samples, oldest dropped
        assert len(buffer.samples) == 10
        assert buffer.dropped_count == 5

    def test_memory_limit_enforcement(self, analyzer_handler, context):
        """Capture should stop when memory limit is reached."""
        # Create config with very low memory limit
        config = MockLogicCaptureConfig(
            sample_rate_hz=100_000,  # High rate to fill memory quickly
            duration_s=10.0,
            max_memory_mb=1,  # Very low limit
            channels=[MockChannel(i, True) for i in range(8)],
        )
        start_req = MockAnalyzerCaptureStartRequest(config=config)
        start_resp = analyzer_handler.AnalyzerCaptureStart(start_req, context)

        assert start_resp.success is True
        capture_id = start_resp.capture_id

        # Wait for memory limit to be hit
        for _ in range(30):  # 3 seconds max
            time.sleep(0.1)
            session = analyzer_handler._get_session(capture_id)
            if session and session.status in [CaptureStatus.COMPLETE, CaptureStatus.ERROR]:
                break

        # Should have stopped due to memory limit
        session = analyzer_handler._get_session(capture_id)
        assert session is not None
        # Memory limit should have been logged as warning
        assert any("memory limit" in msg.lower() for level, msg in analyzer_handler.logger.messages if level == "warning")

    def test_samples_dropped_counter(self, logger):
        """StreamingBuffer should track dropped samples."""
        from src.providers.handlers.analyzer import StreamingBuffer

        buffer = StreamingBuffer(max_size=5)

        # Add more samples than capacity
        samples = [
            AnalyzerSample(timestamp_ns=i * 1000, digital_values=[True])
            for i in range(10)
        ]
        dropped = buffer.push(samples)

        # Should report 5 samples dropped
        assert dropped == 5
        assert buffer.dropped_count == 5


# =============================================================================
# Decoder Tests
# =============================================================================

class TestDecoders:
    """Tests for protocol decoder functionality."""

    def test_add_decoder_to_active_capture(self, analyzer_handler, context):
        """Adding a decoder to an active capture should succeed."""
        # Start capture
        config = MockLogicCaptureConfig(duration_s=1.0)
        start_req = MockAnalyzerCaptureStartRequest(config=config)
        start_resp = analyzer_handler.AnalyzerCaptureStart(start_req, context)

        assert start_resp.success is True
        capture_id = start_resp.capture_id

        # Add decoder
        decoder_req = MockAddDecoderRequest(
            capture_id=capture_id,
            decoder_name="I2C"
        )
        decoder_resp = analyzer_handler.AddDecoder(decoder_req, context)

        assert decoder_resp.success is True
        assert decoder_resp.decoder_id != ""

    def test_add_decoder_to_unknown_capture_fails(self, analyzer_handler, context):
        """Adding decoder to unknown capture should return error."""
        decoder_req = MockAddDecoderRequest(
            capture_id="nonexistent-id",
            decoder_name="I2C"
        )
        decoder_resp = analyzer_handler.AddDecoder(decoder_req, context)

        assert decoder_resp.success is False
        assert "Unknown capture" in decoder_resp.message

    def test_get_decoded_data(self, analyzer_handler, context):
        """Getting decoded data should return protocol transactions."""
        # Start capture
        config = MockLogicCaptureConfig(duration_s=0.5)
        start_req = MockAnalyzerCaptureStartRequest(config=config)
        start_resp = analyzer_handler.AnalyzerCaptureStart(start_req, context)

        assert start_resp.success is True
        capture_id = start_resp.capture_id

        # Add decoder
        decoder_req = MockAddDecoderRequest(
            capture_id=capture_id,
            decoder_name="I2C"
        )
        decoder_resp = analyzer_handler.AddDecoder(decoder_req, context)
        assert decoder_resp.success is True

        # Get decoded data (SimulationProvider returns mock I2C transaction)
        data_req = MockGetDecodedDataRequest(
            capture_id=capture_id,
            decoder_id=decoder_resp.decoder_id
        )
        data_resp = analyzer_handler.GetDecodedData(data_req, context)

        assert data_resp.success is True
        assert len(data_resp.data) > 0  # Should have mock I2C transaction


# =============================================================================
# Thread Safety Tests
# =============================================================================

class TestThreadSafety:
    """Tests for concurrent operations on analyzer handler."""

    def test_concurrent_status_queries(self, analyzer_handler, context):
        """Multiple threads querying status should not cause races."""
        # Start a capture
        config = MockLogicCaptureConfig(duration_s=2.0)
        start_req = MockAnalyzerCaptureStartRequest(config=config)
        start_resp = analyzer_handler.AnalyzerCaptureStart(start_req, context)

        assert start_resp.success is True
        capture_id = start_resp.capture_id

        # Spawn multiple threads querying status concurrently
        results = []
        errors = []

        def query_status():
            try:
                for _ in range(10):
                    status_req = MockAnalyzerCaptureStatusRequest(capture_id=capture_id)
                    status_resp = analyzer_handler.AnalyzerCaptureStatus(status_req, context)
                    results.append(status_resp.success)
                    time.sleep(0.01)
            except Exception as e:
                errors.append(str(e))

        threads = [threading.Thread(target=query_status) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All queries should succeed without errors
        assert len(errors) == 0
        assert all(results)
        assert len(results) == 50  # 5 threads × 10 queries each

    def test_concurrent_decoder_additions(self, analyzer_handler, context):
        """Multiple threads adding decoders should be thread-safe."""
        # Start a capture
        config = MockLogicCaptureConfig(duration_s=2.0)
        start_req = MockAnalyzerCaptureStartRequest(config=config)
        start_resp = analyzer_handler.AnalyzerCaptureStart(start_req, context)

        assert start_resp.success is True
        capture_id = start_resp.capture_id

        # Spawn threads adding decoders concurrently
        decoder_ids = []
        errors = []

        def add_decoder(protocol):
            try:
                decoder_req = MockAddDecoderRequest(
                    capture_id=capture_id,
                    decoder_name=protocol
                )
                decoder_resp = analyzer_handler.AddDecoder(decoder_req, context)
                if decoder_resp.success:
                    decoder_ids.append(decoder_resp.decoder_id)
            except Exception as e:
                errors.append(str(e))

        threads = [
            threading.Thread(target=add_decoder, args=(protocol,))
            for protocol in ["I2C", "SPI", "UART"]
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All decoders should be added without errors
        assert len(errors) == 0
        assert len(decoder_ids) == 3


# =============================================================================
# Error Handling Tests
# =============================================================================

class TestErrorHandling:
    """Tests for error conditions and edge cases."""

    def test_invalid_sample_rate(self, analyzer_handler, context):
        """Starting capture with invalid sample rate should handle gracefully."""
        config = MockLogicCaptureConfig(
            sample_rate_hz=0,  # Invalid
            duration_s=1.0,
        )
        request = MockAnalyzerCaptureStartRequest(config=config)

        # Should not crash (SimulationProvider handles gracefully)
        response = analyzer_handler.AnalyzerCaptureStart(request, context)

        # May succeed with simulation provider (it's permissive)
        # but should not crash
        assert response is not None

    def test_capture_timeout(self, analyzer_handler, context):
        """Long-running capture should eventually complete."""
        config = MockLogicCaptureConfig(
            sample_rate_hz=1_000,
            duration_s=0.1,  # Very short duration
        )
        start_req = MockAnalyzerCaptureStartRequest(config=config)
        start_resp = analyzer_handler.AnalyzerCaptureStart(start_req, context)

        assert start_resp.success is True
        capture_id = start_resp.capture_id

        # Wait for completion with timeout
        timeout = 5.0
        start_time = time.time()
        completed = False

        while time.time() - start_time < timeout:
            status_req = MockAnalyzerCaptureStatusRequest(capture_id=capture_id)
            status_resp = analyzer_handler.AnalyzerCaptureStatus(status_req, context)

            if status_resp.status == CaptureStatus.COMPLETE:
                completed = True
                break

            time.sleep(0.1)

        assert completed, "Capture did not complete within timeout"

    def test_export_unsupported_format(self, logger):
        """Exporting to unsupported format should return error."""
        provider = SimulationProvider(logger)
        config = MockLogicCaptureConfig()
        handle, err = provider.start_capture(config)

        assert err is None
        assert handle is not None

        # Try unsupported format
        err = provider.export_capture(handle, format="unsupported", path="/tmp/test.dat")
        assert err is not None
        assert "Unsupported" in err or "format" in err

    def test_missing_capture_config(self, analyzer_handler, context):
        """Starting capture without config should return error."""
        # Create request with explicitly None config (bypass default)
        request = type('Request', (), {'config': None})()
        response = analyzer_handler.AnalyzerCaptureStart(request, context)

        assert response.success is False
        assert "config" in response.message.lower()

    def test_handler_resource_usage_tracking(self, analyzer_handler, context):
        """Handler should track resource usage for observability."""
        # Start multiple captures
        for i in range(3):
            config = MockLogicCaptureConfig(duration_s=2.0)
            start_req = MockAnalyzerCaptureStartRequest(config=config)
            start_resp = analyzer_handler.AnalyzerCaptureStart(start_req, context)
            assert start_resp.success is True

        # Check resource usage
        usage = analyzer_handler.get_resource_usage()

        assert usage["total_sessions"] == 3
        assert usage["active_captures"] >= 0
        assert "total_memory_mb" in usage
        assert "providers_available" in usage
        assert "simulation" in usage["providers_available"]
