"""Logic analyzer handler for V2 protocol.

Provides pluggable logic analyzer support with real-time streaming, multiple
backend providers (Saleae Logic 2, simulation), resource limits, and session
management following MTIB V2 patterns.

Architecture:
- AnalyzerProvider: Abstract interface for logic analyzer backends
- SimulationProvider: Mock provider for testing (no external dependencies)
- SaleaeProvider: Saleae Logic 2 automation backend (graceful degradation if not available)
- ProviderRegistry: Auto-detects available providers on init
- CaptureSession: Thread-safe session with streaming buffer and multi-client broadcast
- AnalyzerHandler: gRPC RPC implementation following PowerHandler/UartHandler patterns
"""

import os
import threading
import time
import uuid
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass, field
from enum import IntEnum
from queue import Empty as QueueEmpty, Full as QueueFull, Queue
from typing import TYPE_CHECKING, Dict, Iterator, List, Optional, Tuple

from corekinect.utils import Logger

# Import protocol types (Analyzer* names from regenerated proto)
from src.shared.types import (
    AnalyzerCaptureConfig,
    AnalyzerCaptureStartRequest,
    AnalyzerCaptureStartResponse,
    AnalyzerCaptureStatusRequest,
    AnalyzerCaptureStatusResponse,
    AnalyzerCaptureStopRequest,
    AnalyzerProviderInfo,
    ListAnalyzerProvidersResponse,
    AddDecoderRequest,
    AddDecoderResponse,
    GetDecodedDataRequest,
    GetDecodedDataResponse,
    Response,
    Protocol,
    I2cDecoderConfig,
    SpiDecoderConfig,
    UartDecoderConfig,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


# =============================================================================
# Core Types
# =============================================================================

class CaptureStatus(IntEnum):
    """Capture session status (mirrors proto enum)."""
    WAITING_TRIGGER = 0
    CAPTURING = 1
    COMPLETE = 2
    ERROR = 3


@dataclass
class ProviderCapabilities:
    """Capabilities reported by a logic analyzer provider."""
    name: str
    max_sample_rate_hz: int
    max_channels: int
    supports_analog: bool
    supported_protocols: List[str]
    supports_streaming: bool
    supports_triggers: bool


@dataclass
class CaptureHandle:
    """Opaque handle for a capture session (provider-specific)."""
    provider_id: str
    native_handle: object  # Provider's internal capture object


@dataclass
class AnalyzerSample:
    """Single logic analyzer sample."""
    timestamp_ns: int
    digital_values: List[bool]  # One bool per channel


# =============================================================================
# Provider Interface
# =============================================================================

class AnalyzerProvider(ABC):
    """Abstract interface for logic analyzer backends.

    Implementations: SimulationProvider, SaleaeProvider, SigrokProvider
    """

    def __init__(self, logger: Logger):
        self.logger = logger
        self.name = "unknown"

    @abstractmethod
    def connect(self) -> Optional[str]:
        """Connect to analyzer hardware/software.

        Returns:
            Error message or None on success.
        """
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Get supported features."""
        pass

    @abstractmethod
    def start_capture(self, config: AnalyzerCaptureConfig) -> Tuple[Optional[CaptureHandle], Optional[str]]:
        """Start a capture session.

        Args:
            config: Capture configuration from protocol

        Returns:
            (handle, error) tuple - handle is None on error
        """
        pass

    @abstractmethod
    def stream_samples(self, handle: CaptureHandle, max_samples: int) -> Iterator[List[AnalyzerSample]]:
        """Yield sample batches as they arrive (real-time).

        Blocks until capture completes. Generator pattern for streaming.

        Args:
            handle: Capture handle from start_capture
            max_samples: Maximum samples per batch

        Yields:
            Lists of AnalyzerSample objects
        """
        pass

    @abstractmethod
    def stop_capture(self, handle: CaptureHandle) -> Optional[str]:
        """Stop an active capture.

        Returns:
            Error message or None on success.
        """
        pass

    @abstractmethod
    def export_capture(self, handle: CaptureHandle, format: str, path: str) -> Optional[str]:
        """Export capture data to file.

        Args:
            handle: Capture handle
            format: Export format ('csv', 'binary', 'native')
            path: Output file path

        Returns:
            Error message or None on success.
        """
        pass

    @abstractmethod
    def add_analyzer(self, handle: CaptureHandle, protocol: str, config: dict) -> Tuple[Optional[str], Optional[str]]:
        """Add protocol analyzer to capture.

        Args:
            handle: Capture handle
            protocol: Protocol name (e.g., "I2C", "SPI")
            config: Protocol-specific configuration

        Returns:
            (analyzer_id, error) tuple
        """
        pass

    @abstractmethod
    def get_decoded_data(self, handle: CaptureHandle, analyzer_id: Optional[str] = None) -> List[dict]:
        """Get decoded protocol data.

        Args:
            handle: Capture handle
            analyzer_id: Specific analyzer ID, or None for all

        Returns:
            List of decoded transactions
        """
        pass


# =============================================================================
# Simulation Provider (No External Dependencies)
# =============================================================================

class SimulationProvider(AnalyzerProvider):
    """Mock provider for testing - generates synthetic data.

    Always available, requires no external dependencies. Generates
    realistic-looking digital waveforms for testing the handler infrastructure.
    """

    def __init__(self, logger: Logger):
        super().__init__(logger)
        self.name = "simulation"

    def connect(self) -> Optional[str]:
        """Always succeeds - no external dependencies."""
        return None

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name="Simulation",
            max_sample_rate_hz=100_000_000,  # 100 MS/s
            max_channels=16,
            supports_analog=False,
            supported_protocols=["I2C", "SPI", "UART"],
            supports_streaming=True,
            supports_triggers=False,
        )

    def start_capture(self, config: AnalyzerCaptureConfig) -> Tuple[Optional[CaptureHandle], Optional[str]]:
        """Start simulated capture."""
        handle = CaptureHandle(
            provider_id="simulation",
            native_handle={
                "config": config,
                "start_time": time.time(),
            },
        )
        return handle, None

    def stream_samples(self, handle: CaptureHandle, max_samples: int) -> Iterator[List[AnalyzerSample]]:
        """Generate synthetic sample stream.

        Simulates realistic capture timing with batched sample delivery.
        Generates square waves on each channel for visual debugging.
        """
        config = handle.native_handle["config"]
        start_time = handle.native_handle["start_time"]

        # Access config attributes safely (proto or dict)
        sample_rate = getattr(config, "sample_rate_hz", 1_000_000) if hasattr(config, "sample_rate_hz") else 1_000_000
        duration_s = getattr(config, "duration_s", 1.0) if hasattr(config, "duration_s") else 1.0
        channels = getattr(config, "channels", []) if hasattr(config, "channels") else []
        num_channels = len(channels) if channels else 4

        total_samples = int(duration_s * sample_rate)
        samples_sent = 0
        batch_size_time = 0.05  # Simulate 50ms batches

        while samples_sent < total_samples:
            batch_size = min(max_samples, int(batch_size_time * sample_rate), total_samples - samples_sent)
            batch = []

            for i in range(batch_size):
                sample_idx = samples_sent + i
                timestamp_ns = int(sample_idx * (1e9 / sample_rate))

                # Generate synthetic square waves (different frequencies per channel)
                values = [
                    (sample_idx % (100 * (ch + 1))) < (50 * (ch + 1))
                    for ch in range(num_channels)
                ]

                batch.append(AnalyzerSample(
                    timestamp_ns=timestamp_ns,
                    digital_values=values,
                ))

            yield batch
            samples_sent += batch_size

            # Simulate capture timing
            time.sleep(batch_size_time)

    def stop_capture(self, handle: CaptureHandle) -> Optional[str]:
        """Stop simulated capture."""
        return None

    def export_capture(self, handle: CaptureHandle, format: str, path: str) -> Optional[str]:
        """Export simulated data to file."""
        try:
            with open(path, "w") as f:
                if format == "csv":
                    f.write("timestamp_ns,CH0,CH1,CH2,CH3\n")
                    f.write("0,1,0,1,0\n")
                    f.write("1000,0,1,0,1\n")
                elif format == "binary":
                    f.write("# Simulated binary capture data\n")
                else:
                    return f"Unsupported format: {format}"
            return None
        except Exception as e:
            return str(e)

    def add_analyzer(self, handle: CaptureHandle, protocol: str, config: dict) -> Tuple[Optional[str], Optional[str]]:
        """Add simulated protocol analyzer."""
        analyzer_id = str(uuid.uuid4())
        return analyzer_id, None

    def get_decoded_data(self, handle: CaptureHandle, analyzer_id: Optional[str] = None) -> List[dict]:
        """Return simulated decoded protocol data."""
        # Return fake I2C transaction
        return [{
            "protocol": "I2C",
            "address": 0x76,
            "data": [0x00, 0x01],
            "read": False,
        }]


# =============================================================================
# Saleae Provider (Optional - Graceful Degradation)
# =============================================================================

class SaleaeProvider(AnalyzerProvider):
    """Saleae Logic 2 automation backend.

    Gracefully handles missing logic2-automation package. If unavailable,
    connect() returns an error and this provider won't be used.

    IMPORTANT: Saleae Logic 2 API does not support true streaming - samples
    are only available after capture completes. The stream_samples() method
    polls for completion but cannot deliver samples incrementally. This is
    a limitation of the Logic 2 automation API as of 2026-02.
    """

    def __init__(self, logger: Logger):
        super().__init__(logger)
        self.name = "saleae"
        self._manager = None
        self._device_id: Optional[str] = None

    def connect(self) -> Optional[str]:
        """Connect to Logic 2 software via automation API.

        Returns:
            Error if logic2-automation not installed, Logic 2 not running,
            or no devices detected.
        """
        try:
            from saleae import automation
            self._manager = automation.Manager.connect(port=10430)
            devices = self._manager.get_devices()

            if not devices:
                return "No Saleae devices detected"

            # Prefer real hardware over simulation
            real_devices = [d for d in devices if d.device_type != automation.DeviceType.SIMULATION]
            self._device_id = real_devices[0].device_id if real_devices else devices[0].device_id

            device_type = "real" if real_devices else "simulation"
            self.logger.info(f"Connected to Saleae device ({device_type}): {self._device_id}")
            return None

        except ImportError:
            return "logic2-automation package not installed"
        except Exception as e:
            return f"Failed to connect to Logic 2: {e}"

    def get_capabilities(self) -> ProviderCapabilities:
        """Get Saleae hardware capabilities."""
        return ProviderCapabilities(
            name="Saleae Logic 2",
            max_sample_rate_hz=500_000_000,  # 500 MS/s (Logic Pro 16)
            max_channels=16,
            supports_analog=True,
            supported_protocols=["I2C", "SPI", "UART", "CAN", "I2S", "1-Wire"],
            supports_streaming=False,  # API limitation - see docstring
            supports_triggers=True,
        )

    def start_capture(self, config: AnalyzerCaptureConfig) -> Tuple[Optional[CaptureHandle], Optional[str]]:
        """Start Saleae capture."""
        if not self._manager:
            return None, "Not connected to Logic 2"

        try:
            from saleae import automation

            # Extract enabled channels from config
            channels = getattr(config, "channels", [])
            enabled_channels = [
                getattr(ch, "channel", 0) for ch in channels
                if getattr(ch, "enabled", False)
            ]

            sample_rate = getattr(config, "sample_rate_hz", 10_000_000)

            device_config = automation.LogicDeviceConfiguration(
                enabled_digital_channels=enabled_channels,
                digital_sample_rate=sample_rate,
                digital_threshold_volts=3.3,
            )

            capture = self._manager.start_capture(
                device_id=self._device_id,
                device_configuration=device_config,
            )

            handle = CaptureHandle(provider_id="saleae", native_handle=capture)
            return handle, None

        except Exception as e:
            return None, f"Failed to start capture: {e}"

    def stream_samples(self, handle: CaptureHandle, max_samples: int) -> Iterator[List[AnalyzerSample]]:
        """Poll for Saleae capture completion.

        NOTE: Saleae Logic 2 API limitation - samples are only available after
        capture completes. Cannot stream incrementally. This method polls
        the capture status and yields samples once available.
        """
        capture = handle.native_handle

        # Poll for completion
        while True:
            try:
                if capture.is_complete():
                    # Capture finished - but API doesn't provide sample access yet
                    # This is where we'd get samples if API supported it
                    # For now, yield empty batch to signal completion
                    yield []
                    break

                time.sleep(0.1)  # Poll every 100ms

            except Exception as e:
                self.logger.error(f"Saleae capture poll error: {e}")
                break

    def stop_capture(self, handle: CaptureHandle) -> Optional[str]:
        """Stop Saleae capture."""
        try:
            capture = handle.native_handle
            capture.stop()
            return None
        except Exception as e:
            return f"Failed to stop capture: {e}"

    def export_capture(self, handle: CaptureHandle, format: str, path: str) -> Optional[str]:
        """Export Saleae capture to file."""
        capture = handle.native_handle

        try:
            if format == "csv":
                # Export to directory (Saleae creates CSV per channel)
                export_dir = os.path.dirname(path)
                capture.export_raw_data_csv(directory=export_dir)
            elif format == "native":
                capture.save_capture(filepath=path)
            else:
                return f"Unsupported format: {format}"
            return None
        except Exception as e:
            return f"Export failed: {e}"

    def add_analyzer(self, handle: CaptureHandle, protocol: str, config: dict) -> Tuple[Optional[str], Optional[str]]:
        """Add protocol analyzer to Saleae capture."""
        capture = handle.native_handle

        try:
            analyzer = capture.add_analyzer(protocol, settings=config)
            return str(analyzer.analyzer_id), None
        except Exception as e:
            return None, f"Failed to add analyzer: {e}"

    def get_decoded_data(self, handle: CaptureHandle, analyzer_id: Optional[str] = None) -> List[dict]:
        """Get decoded data from Saleae analyzers."""
        # TODO: Implement based on Saleae API export capabilities
        return []


# =============================================================================
# Provider Registry (Auto-Detection)
# =============================================================================

class ProviderRegistry:
    """Auto-detects and manages logic analyzer providers.

    Probes for available providers in priority order:
    1. Saleae Logic 2 (if logic2-automation installed and Logic 2 running)
    2. Simulation (always available)

    Follows PowerHandler pattern for graceful degradation.
    """

    def __init__(self, logger: Logger):
        self.logger = logger
        self.providers: List[AnalyzerProvider] = []
        self._auto_detect()

    def _auto_detect(self):
        """Probe for available providers in priority order."""
        # Try Saleae Logic 2
        try:
            saleae = SaleaeProvider(self.logger)
            if saleae.connect() is None:
                self.providers.append(saleae)
                self.logger.info("Logic analyzer provider available: Saleae Logic 2")
        except Exception as e:
            self.logger.debug(f"Saleae provider not available: {e}")

        # Always add simulation provider (fallback)
        self.providers.append(SimulationProvider(self.logger))
        self.logger.info("Logic analyzer provider available: Simulation")

    def get_provider(self, prefer: Optional[str] = None) -> Optional[AnalyzerProvider]:
        """Get best available provider.

        Args:
            prefer: Optional provider name to prefer (e.g., "saleae", "simulation")

        Returns:
            AnalyzerProvider instance or None if no providers available
        """
        if prefer:
            for p in self.providers:
                if p.name == prefer:
                    return p

        # Return first available (highest priority)
        return self.providers[0] if self.providers else None


# =============================================================================
# Streaming Buffer (Thread-Safe)
# =============================================================================

@dataclass
class StreamingBuffer:
    """Ring buffer for streaming logic samples with backpressure.

    Thread-safe circular buffer that drops oldest samples when full.
    Used for real-time streaming to multiple clients.
    """

    max_size: int = 100_000  # samples
    samples: deque = field(default_factory=deque)
    dropped_count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def __post_init__(self):
        """Initialize deque with correct maxlen."""
        if not isinstance(self.samples, deque) or self.samples.maxlen != self.max_size:
            self.samples = deque(maxlen=self.max_size)

    def push(self, samples: List[AnalyzerSample]) -> int:
        """Add samples, return number dropped if buffer full.

        Thread-safe. Older samples are automatically evicted by deque.
        """
        with self.lock:
            space_available = self.max_size - len(self.samples)
            if len(samples) > space_available:
                # deque with maxlen auto-drops oldest
                overflow = len(samples) - space_available
                self.dropped_count += overflow
            self.samples.extend(samples)
            return self.dropped_count

    def pop(self, max_count: int) -> List[AnalyzerSample]:
        """Pop up to max_count samples (non-blocking).

        Thread-safe. Returns empty list if no samples available.
        """
        with self.lock:
            result = []
            for _ in range(min(max_count, len(self.samples))):
                result.append(self.samples.popleft())
            return result


# =============================================================================
# Capture Session
# =============================================================================

@dataclass
class CaptureSession:
    """Shared capture session with streaming support.

    Follows UartConnection pattern - one session per capture, multiple
    clients can stream from it. Background thread pulls samples from
    provider and broadcasts to client queues.

    Thread-safety: All mutable state protected by locks.
    """

    capture_id: str
    config: AnalyzerCaptureConfig
    provider: AnalyzerProvider
    handle: CaptureHandle
    logger: Logger

    # Status (thread-safe via atomic operations on IntEnum)
    status: CaptureStatus = CaptureStatus.WAITING_TRIGGER
    start_time: float = field(default_factory=time.time)

    # Sample counters (protected by samples_lock)
    samples_captured: int = 0
    samples_dropped: int = 0
    samples_lock: threading.Lock = field(default_factory=threading.Lock)

    # Streaming
    stream_buffer: StreamingBuffer = field(default_factory=StreamingBuffer)

    # Export buffer (protected by export_lock)
    export_buffer: List[AnalyzerSample] = field(default_factory=list)
    export_lock: threading.Lock = field(default_factory=threading.Lock)

    # Background thread
    streaming_thread: Optional[threading.Thread] = None
    stop_event: threading.Event = field(default_factory=threading.Event)

    def start_streaming_thread(self):
        """Start background thread to pull samples from provider.

        Thread continuously reads from provider.stream_samples() and:
        1. Pushes to streaming buffer (for real-time clients)
        2. Appends to export buffer (for post-capture file export)
        3. Enforces memory limits
        """
        def stream_worker():
            try:
                captured = 0
                dropped = 0
                for sample_batch in self.provider.stream_samples(self.handle, max_samples=1000):
                    if self.stop_event.is_set():
                        break

                    # Add to streaming buffer (for real-time clients)
                    dropped = self.stream_buffer.push(sample_batch)

                    # Update counters (thread-safe)
                    with self.samples_lock:
                        self.samples_dropped = dropped
                        self.samples_captured += len(sample_batch)
                        captured = self.samples_captured

                    # Add to export buffer (thread-safe)
                    with self.export_lock:
                        self.export_buffer.extend(sample_batch)

                    # Check memory limit
                    max_memory_mb = getattr(self.config, "max_memory_mb", 512) if hasattr(self.config, "max_memory_mb") else 512
                    mem_usage_mb = self.estimate_memory_usage()
                    if mem_usage_mb > max_memory_mb:
                        self.logger.warning(
                            f"Capture {self.capture_id} hit memory limit "
                            f"({mem_usage_mb:.1f} MB > {max_memory_mb} MB)"
                        )
                        self.stop_event.set()
                        break

                self.status = CaptureStatus.COMPLETE
                self.logger.info(
                    f"Capture {self.capture_id} complete: {captured} samples, "
                    f"{dropped} dropped"
                )

            except Exception as e:
                self.logger.error(f"Streaming thread error for {self.capture_id}: {e}", exc_info=True)
                self.status = CaptureStatus.ERROR

        self.streaming_thread = threading.Thread(
            target=stream_worker,
            daemon=True,
            name=f"analyzer-stream-{self.capture_id[:8]}"
        )
        self.streaming_thread.start()
        self.status = CaptureStatus.CAPTURING

    def estimate_memory_usage(self) -> float:
        """Estimate current memory usage in MB.

        Thread-safe read of sample counters.
        """
        with self.samples_lock:
            samples = self.samples_captured

        # Rough estimate: 8 bytes timestamp + 1 byte per channel + overhead
        num_channels = len(getattr(self.config, "channels", [])) if hasattr(self.config, "channels") else 4
        bytes_per_sample = 8 + num_channels + 16  # timestamp + channels + overhead
        total_bytes = samples * bytes_per_sample
        return total_bytes / (1024 * 1024)


# =============================================================================
# Analyzer Handler (gRPC RPC Implementation)
# =============================================================================

class AnalyzerHandler:
    """Handles logic analyzer RPCs following MTIB V2 patterns.

    Follows PowerHandler/UartHandler initialization and error handling patterns:
    - Go-style error handling (Optional[str] returns)
    - Graceful degradation if no providers available
    - Thread-safe session management
    - Proper logging (info/warning/error with context)

    Architecture:
    - ProviderRegistry auto-detects available backends on init
    - CaptureSession manages streaming and export per capture
    - Background threads handle sample streaming from provider
    """

    def __init__(
        self,
        logger: Logger,
        hardware: "HardwareContext",
        analyzer_observer=None,
    ):
        """Initialize analyzer handler with provider auto-detection.

        Args:
            logger: Logger instance
            hardware: Hardware context (for capability checking)
            analyzer_observer: Optional observability engine integration
        """
        self.logger = logger
        self.hardware = hardware
        self._observer = analyzer_observer

        # Provider registry (auto-detects available backends)
        self._registry = ProviderRegistry(logger)

        # Active capture sessions
        self._sessions: Dict[str, CaptureSession] = {}
        self._sessions_lock = threading.Lock()

        # Check if any providers available
        if not self._registry.providers:
            self.logger.warning(
                "No logic analyzer providers available - running in disabled mode. "
                "Install logic2-automation for Saleae support."
            )
            self._disabled = True
        else:
            self._disabled = False
            providers = [p.name for p in self._registry.providers]
            self.logger.info(f"Logic analyzer providers available: {providers}")

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------

    def _start_capture_internal(
        self,
        config: AnalyzerCaptureConfig,
        provider_name: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """Internal capture start with error propagation.

        Args:
            config: Capture configuration
            provider_name: Optional provider to prefer

        Returns:
            (capture_id, error_message) tuple - capture_id is None on error
        """
        # Get provider
        provider = self._registry.get_provider(prefer=provider_name)
        if not provider:
            return None, "No logic analyzer providers available"

        # Start capture
        handle, err = provider.start_capture(config)
        if err:
            return None, f"Provider {provider.name} failed: {err}"

        # Create session
        capture_id = str(uuid.uuid4())
        session = CaptureSession(
            capture_id=capture_id,
            config=config,
            provider=provider,
            handle=handle,
            logger=self.logger,
        )

        # Start streaming thread
        session.start_streaming_thread()

        with self._sessions_lock:
            self._sessions[capture_id] = session

        self.logger.info(
            f"Logic capture started: {capture_id} (provider: {provider.name})"
        )
        return capture_id, None

    def _get_session(self, capture_id: str) -> Optional[CaptureSession]:
        """Get session by ID (thread-safe)."""
        with self._sessions_lock:
            return self._sessions.get(capture_id)

    # -------------------------------------------------------------------------
    # gRPC RPC Handlers
    # -------------------------------------------------------------------------

    def ListAnalyzerProviders(self, request, context):
        """List available logic analyzer providers (gRPC handler).

        Returns information about all detected analyzer backends (Saleae,
        simulation, etc.) including their capabilities and hardware detection status.
        """
        try:
            from src.shared.types import ListAnalyzerProvidersResponse, AnalyzerProviderInfo

            provider_infos = []
            for provider in self._registry.providers:
                caps = provider.get_capabilities()

                info = AnalyzerProviderInfo(
                    name=provider.name,
                    display_name=caps.name,
                    available=True,  # All providers in registry are available (connected successfully)
                    max_sample_rate_hz=caps.max_sample_rate_hz,
                    max_channels=caps.max_channels,
                    supported_protocols=caps.supported_protocols,
                    supports_streaming=caps.supports_streaming,
                    supports_triggers=caps.supports_triggers,
                    hardware_detected=getattr(caps, 'hardware_detected', ''),
                    supported_export_formats=getattr(caps, 'supported_export_formats', []),
                )
                provider_infos.append(info)

            return ListAnalyzerProvidersResponse(
                success=True,
                message=f"Found {len(provider_infos)} analyzer provider(s)",
                providers=provider_infos
            )
        except Exception as e:
            self.logger.error(f"ListAnalyzerProviders error: {e}")
            return ListAnalyzerProvidersResponse(
                success=False,
                message=f"Error listing providers: {str(e)}",
                providers=[]
            )

    def AnalyzerCaptureStart(
        self,
        request: AnalyzerCaptureStartRequest,
        context
    ) -> AnalyzerCaptureStartResponse:
        """Start a logic capture session (gRPC handler).

        Follows PowerHandler error pattern - internal method returns
        Go-style error, RPC handler converts to Response.
        """
        # Validate config
        if not request.config:
            return AnalyzerCaptureStartResponse(
                success=False,
                message="Capture config is required",
                capture_id=""
            )

        if self._disabled:
            # Placeholder response until proto is regenerated
            return AnalyzerCaptureStartResponse(
                success=False,
                message=(
                    "Logic analyzer not available (no providers detected). "
                    "Install logic2-automation or use simulation mode."
                ),
                capture_id=""
            )

        try:
            config = getattr(request, "config", None)
            if not config:
                return type('Response', (), {
                    'success': False,
                    'message': "Missing capture config",
                    'capture_id': "",
                })()

            capture_id, err = self._start_capture_internal(config)
            if err:
                return type('Response', (), {
                    'success': False,
                    'message': err,
                    'capture_id': "",
                })()

            return type('Response', (), {
                'success': True,
                'message': "",
                'capture_id': capture_id,
            })()

        except Exception as e:
            self.logger.error(f"Logic capture start failed: {e}", exc_info=True)
            return type('Response', (), {
                'success': False,
                'message': str(e),
                'capture_id': "",
            })()

    def AnalyzerCaptureStatus(
        self,
        request: AnalyzerCaptureStatusRequest,
        context
    ) -> AnalyzerCaptureStatusResponse:
        """Get capture status (gRPC handler)."""
        try:
            capture_id = getattr(request, "capture_id", "")
            session = self._get_session(capture_id)

            if not session:
                return type('Response', (), {
                    'success': False,
                    'message': f"Unknown capture: {capture_id}",
                    'status': CaptureStatus.ERROR,
                    'progress': 0.0,
                })()

            # Compute progress estimate
            duration_s = getattr(session.config, "duration_s", 1.0) if hasattr(session.config, "duration_s") else 1.0
            elapsed = time.time() - session.start_time
            progress = min(elapsed / duration_s, 0.99) if session.status == CaptureStatus.CAPTURING else 1.0

            return type('Response', (), {
                'success': True,
                'message': "",
                'status': session.status,
                'progress': progress,
            })()

        except Exception as e:
            self.logger.error(f"Logic capture status failed: {e}", exc_info=True)
            return type('Response', (), {
                'success': False,
                'message': str(e),
                'status': CaptureStatus.ERROR,
                'progress': 0.0,
            })()

    def AnalyzerCaptureStop(
        self,
        request: AnalyzerCaptureStopRequest,
        context
    ) -> Response:
        """Stop a logic capture session (gRPC handler)."""
        try:
            capture_id = getattr(request, "capture_id", "")
            session = self._get_session(capture_id)

            if not session:
                return type('Response', (), {
                    'success': False,
                    'message': f"Unknown capture: {capture_id}",
                })()

            # Signal streaming thread to stop
            session.stop_event.set()

            # Stop provider capture
            if err := session.provider.stop_capture(session.handle):
                self.logger.warning(f"Provider stop error for {capture_id}: {err}")

            # Wait for streaming thread to finish
            if session.streaming_thread and session.streaming_thread.is_alive():
                session.streaming_thread.join(timeout=2.0)

            session.status = CaptureStatus.COMPLETE

            # Remove from active sessions
            with self._sessions_lock:
                self._sessions.pop(capture_id, None)

            self.logger.info(f"Logic capture stopped: {capture_id}")
            return type('Response', (), {
                'success': True,
                'message': "Capture stopped",
            })()

        except Exception as e:
            self.logger.error(f"Logic capture stop failed: {e}", exc_info=True)
            return type('Response', (), {
                'success': False,
                'message': str(e),
            })()

    def AddDecoder(
        self,
        request: AddDecoderRequest,
        context
    ) -> AddDecoderResponse:
        """Add protocol decoder to capture (gRPC handler)."""
        try:
            capture_id = getattr(request, "capture_id", "")
            session = self._get_session(capture_id)

            if not session:
                return type('Response', (), {
                    'success': False,
                    'message': f"Unknown capture: {capture_id}",
                    'decoder_id': "",
                })()

            protocol = getattr(request, "decoder_name", "")
            config = {}  # TODO: Extract protocol-specific config from request

            analyzer_id, err = session.provider.add_analyzer(
                session.handle,
                protocol,
                config
            )

            if err:
                return type('Response', (), {
                    'success': False,
                    'message': err,
                    'decoder_id': "",
                })()

            self.logger.info(f"Decoder added to {capture_id}: {protocol} (ID: {analyzer_id})")
            return type('Response', (), {
                'success': True,
                'message': "",
                'decoder_id': analyzer_id,
            })()

        except Exception as e:
            self.logger.error(f"Add decoder failed: {e}", exc_info=True)
            return type('Response', (), {
                'success': False,
                'message': str(e),
                'decoder_id': "",
            })()

    def GetDecodedData(
        self,
        request: GetDecodedDataRequest,
        context
    ) -> GetDecodedDataResponse:
        """Get decoded protocol data (gRPC handler)."""
        try:
            capture_id = getattr(request, "capture_id", "")
            session = self._get_session(capture_id)

            if not session:
                return type('Response', (), {
                    'success': False,
                    'message': f"Unknown capture: {capture_id}",
                    'data': [],
                })()

            analyzer_id = getattr(request, "decoder_id", None)
            decoded = session.provider.get_decoded_data(session.handle, analyzer_id)

            return type('Response', (), {
                'success': True,
                'message': "",
                'data': decoded,
            })()

        except Exception as e:
            self.logger.error(f"Get decoded data failed: {e}", exc_info=True)
            return type('Response', (), {
                'success': False,
                'message': str(e),
                'data': [],
            })()

    # -------------------------------------------------------------------------
    # Resource Monitoring (for Observability)
    # -------------------------------------------------------------------------

    def get_resource_usage(self) -> Dict[str, any]:
        """Get current resource usage (for observability integration).

        Returns:
            Dict with active_captures, total_memory_mb, providers, etc.
        """
        with self._sessions_lock:
            total_memory_mb = 0.0
            active_captures = 0

            for session in self._sessions.values():
                if session.status in [CaptureStatus.WAITING_TRIGGER, CaptureStatus.CAPTURING]:
                    active_captures += 1
                total_memory_mb += session.estimate_memory_usage()

            return {
                "active_captures": active_captures,
                "total_memory_mb": total_memory_mb,
                "total_sessions": len(self._sessions),
                "providers_available": [p.name for p in self._registry.providers],
            }
