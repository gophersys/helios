# Logic Analyzer Integration for MTIB Server V2 (Revised)

**Date:** 2026-02-10
**Status:** Design Phase (Revision 2 - Generalized Architecture)

## Overview

Integrate **pluggable logic analyzer support** into MTIB Server V2 with:
- **Real-time streaming** of samples during capture
- **Multiple backend support** (Saleae Logic 2, sigrok/PulseView, simulation)
- **Resource limits** (memory, duration, sample count)
- **Remote capture export** alongside streaming

## Motivation

The MTIB server provides comprehensive hardware test capabilities but was missing actual logic analyzer integration. This design:

1. **Supports multiple analyzers** - Saleae, sigrok, simulation, future analyzers
2. **Streams in real-time** - Don't wait for capture to finish, stream samples as they arrive
3. **Resource-safe** - Memory limits, duration limits, circular buffers
4. **Protocol-agnostic** - Generic provider interface, not tied to one vendor
5. **Remote + Local** - Stream to client OR export to file (or both)

## Key Design Improvements (Revision 2)

### 1. Provider Abstraction Layer

Replace `SaleaeManager` with pluggable `LogicAnalyzerProvider` interface:

```python
class LogicAnalyzerProvider(ABC):
    """Abstract interface for logic analyzer backends."""

    @abstractmethod
    def connect(self) -> Optional[str]:
        """Connect to analyzer. Returns error or None."""
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Get supported features (sample rates, channels, protocols)."""
        pass

    @abstractmethod
    def start_capture(self, config: AnalyzerCaptureConfig) -> Tuple[Optional[CaptureHandle], Optional[str]]:
        """Start capture. Returns (handle, error)."""
        pass

    @abstractmethod
    def stream_samples(self, handle: CaptureHandle, max_samples: int) -> Iterator[List[AnalyzerSample]]:
        """Yield sample batches as they arrive (real-time)."""
        pass

    @abstractmethod
    def stop_capture(self, handle: CaptureHandle) -> Optional[str]:
        """Stop capture. Returns error or None."""
        pass

    @abstractmethod
    def export_capture(self, handle: CaptureHandle, format: str, path: str) -> Optional[str]:
        """Export to file. Returns error or None."""
        pass
```

**Concrete implementations:**
- `SaleaeProvider` - Logic 2 automation API
- `SigrokProvider` - libsigrok (PulseView backend)
- `SimulationProvider` - Mock data for testing

### 2. Real-Time Streaming

**NEW gRPC RPC** (add to `mtib_v2.proto`):

```protobuf
// Real-time sample streaming
message AnalyzerStreamRequest {
  string capture_id = 1;
  uint32 max_samples_per_chunk = 2;  // Limit chunk size (default 1000)
  float interval_s = 3;               // Polling interval (default 0.1s)
}

message AnalyzerSample {
  uint64 timestamp_ns = 1;
  repeated bool digital_values = 2;  // One bool per channel
}

message AnalyzerStreamResponse {
  bool success = 1;
  string message = 2;
  repeated AnalyzerSample samples = 3;
  bool capture_complete = 4;
  uint64 total_samples = 5;
  uint64 samples_dropped = 6;        // If memory limit hit
}

// Add to MtibV2 service:
rpc AnalyzerStream(AnalyzerStreamRequest) returns (stream AnalyzerStreamResponse);
```

**Client usage:**
```python
# Start capture
capture_id, _ = client.analyzer_capture_start(channels=[0, 1, 2, 3], duration_s=10.0)

# Stream samples in real-time
for chunk in client.analyzer_stream(capture_id):
    for sample in chunk.samples:
        print(f"t={sample.timestamp_ns}ns CH0={sample.digital_values[0]}")

    if chunk.capture_complete:
        break
```

### 3. Resource Limits

**Enhanced `AnalyzerCaptureConfig`** (extend proto):

```protobuf
message AnalyzerCaptureConfig {
  repeated AnalyzerChannelConfig channels = 1;
  uint64 sample_rate_hz = 2;
  float duration_s = 3;

  // Trigger config (unchanged)
  bool trigger_enabled = 4;
  // ...

  // NEW: Resource limits
  uint64 max_samples = 10;           // Hard limit on total samples
  uint64 max_memory_mb = 11;         // Memory limit (default 512 MB)
  bool circular_buffer = 12;         // Overwrite oldest when limit hit
  bool auto_export_on_stop = 13;    // Save to file when stopped
}
```

**Server-side enforcement:**
```python
class CaptureSession:
    # ...
    max_samples: int = 1_000_000_000  # 1B samples default (~125MB @ 1 byte/sample)
    max_memory_mb: int = 512
    circular_buffer: bool = False
    samples_dropped: int = 0

    def add_samples(self, new_samples: List[AnalyzerSample]):
        """Add samples with memory limit enforcement."""
        if len(self.samples) + len(new_samples) > self.max_samples:
            if self.circular_buffer:
                # Drop oldest samples
                overflow = (len(self.samples) + len(new_samples)) - self.max_samples
                self.samples = self.samples[overflow:]
                self.samples_dropped += overflow
            else:
                # Stop capture
                self.status = CaptureStatus.COMPLETE
                self.logger.warning(f"Capture {self.capture_id} hit sample limit")
                return

        self.samples.extend(new_samples)
```

## Architecture (Revised)

### Layered Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  MTIB Client (Python)                                       │
│  ├─ analyzer_capture_start(channels, limits, trigger)       │
│  ├─ analyzer_stream(capture_id) → Iterator[samples]         │
│  ├─ analyzer_capture_stop(capture_id)                       │
│  └─ analyzer_download(capture_id, format) → bytes           │
└─────────────────────┬───────────────────────────────────────┘
                      │ gRPC (mtib_v2.proto) + NEW AnalyzerStream RPC
┌─────────────────────▼───────────────────────────────────────┐
│  MTIB Server V2 - AnalyzerHandler                           │
│  ├─ Provider Registry (auto-detect available backends)      │
│  │   ├─ SaleaeProvider (if Logic 2 running)                 │
│  │   ├─ SigrokProvider (if libsigrok available)             │
│  │   └─ SimulationProvider (always available)               │
│  ├─ CaptureSession (per capture_id)                         │
│  │   ├─ Sample buffer (with memory limits)                  │
│  │   ├─ Streaming queue (non-blocking)                      │
│  │   └─ Export manager (CSV, binary, capture files)         │
│  └─ Resource Monitor                                        │
│      ├─ Per-capture memory tracking                         │
│      └─ Global memory limit enforcement                     │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬──────────────────┐
        │             │             │                  │
┌───────▼──────┐ ┌────▼─────┐ ┌────▼─────┐ ┌─────────▼──────┐
│ Saleae Logic │ │  sigrok  │ │ Simulation│ │ Future Analyzer│
│      2       │ │ (libsrok)│ │  (mock)   │ │  (DSLogic, etc)│
└───────┬──────┘ └────┬─────┘ └──────────┘ └────────────────┘
        │             │
        │ USB         │ USB/Serial
        ▼             ▼
   ┌────────┐    ┌────────┐
   │ Saleae │    │ fx2lafw│
   │Hardware│    │ DSLogic│
   │        │    │ etc.   │
   └────────┘    └────────┘
```

### Provider Selection Strategy

```python
class ProviderRegistry:
    """Auto-detects and manages logic analyzer providers."""

    def __init__(self, logger: Logger):
        self.logger = logger
        self.providers: List[LogicAnalyzerProvider] = []
        self._auto_detect()

    def _auto_detect(self):
        """Probe for available providers in priority order."""
        # Try Saleae Logic 2
        try:
            saleae = SaleaeProvider(self.logger)
            if saleae.connect() is None:
                self.providers.append(saleae)
                self.logger.info("✓ Saleae Logic 2 available")
        except Exception as e:
            self.logger.debug(f"Saleae not available: {e}")

        # Try sigrok
        try:
            sigrok = SigrokProvider(self.logger)
            if sigrok.connect() is None:
                self.providers.append(sigrok)
                self.logger.info("✓ sigrok available")
        except Exception as e:
            self.logger.debug(f"sigrok not available: {e}")

        # Always add simulation (for testing)
        self.providers.append(SimulationProvider(self.logger))
        self.logger.info("✓ Simulation provider available")

    def get_provider(self, prefer: Optional[str] = None) -> LogicAnalyzerProvider:
        """Get best available provider (or preferred if specified)."""
        if prefer:
            for p in self.providers:
                if p.name == prefer:
                    return p

        # Return first available (highest priority)
        return self.providers[0] if self.providers else SimulationProvider(self.logger)
```

### Package Dependencies

- **`logic2-automation`** (optional) - Saleae Logic 2 support
- **`libsigrok`** (optional) - sigrok/PulseView support
- **Core:** No dependencies for simulation mode

## Streaming Architecture Details

### Buffer Management

```python
@dataclass
class StreamingBuffer:
    """Ring buffer for streaming logic samples with backpressure."""

    max_size: int = 100_000  # samples
    samples: deque = field(default_factory=lambda: deque(maxlen=100_000))
    dropped_count: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)

    def push(self, samples: List[AnalyzerSample]) -> int:
        """Add samples, return number dropped if buffer full."""
        with self.lock:
            space_available = self.max_size - len(self.samples)
            if len(samples) > space_available:
                # Drop oldest samples
                overflow = len(samples) - space_available
                self.dropped_count += overflow
                # deque with maxlen will auto-drop oldest
            self.samples.extend(samples)
            return self.dropped_count

    def pop(self, max_count: int) -> List[AnalyzerSample]:
        """Pop up to max_count samples (non-blocking)."""
        with self.lock:
            result = []
            for _ in range(min(max_count, len(self.samples))):
                result.append(self.samples.popleft())
            return result
```

### Streaming Thread Architecture

```python
class CaptureSession:
    """Enhanced session with streaming support."""

    def __init__(self, capture_id: str, config: AnalyzerCaptureConfig, provider: LogicAnalyzerProvider):
        self.capture_id = capture_id
        self.config = config
        self.provider = provider

        # Capture state
        self.handle: Optional[CaptureHandle] = None
        self.status: CaptureStatus = CaptureStatus.STARTING
        self.start_time: float = 0.0

        # Streaming
        self.stream_buffer = StreamingBuffer(max_size=config.max_samples or 1_000_000)
        self.streaming_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()

        # Export
        self.export_buffer: List[AnalyzerSample] = []  # For post-capture export
        self.samples_captured: int = 0
        self.samples_dropped: int = 0

    def start_streaming_thread(self):
        """Background thread that pulls samples from provider and buffers them."""
        def stream_worker():
            try:
                for sample_batch in self.provider.stream_samples(self.handle, max_samples=1000):
                    if self.stop_event.is_set():
                        break

                    # Add to streaming buffer (for real-time clients)
                    dropped = self.stream_buffer.push(sample_batch)
                    self.samples_dropped = dropped

                    # Also keep in export buffer if auto-export enabled
                    if self.config.auto_export_on_stop:
                        self.export_buffer.extend(sample_batch)

                    self.samples_captured += len(sample_batch)

                    # Check memory limit
                    mem_usage_mb = self.estimate_memory_usage()
                    if mem_usage_mb > self.config.max_memory_mb:
                        self.logger.warning(f"Capture {self.capture_id} hit memory limit")
                        self.stop_event.set()
                        break

                self.status = CaptureStatus.COMPLETE
            except Exception as e:
                self.logger.error(f"Streaming thread error: {e}")
                self.status = CaptureStatus.ERROR

        self.streaming_thread = threading.Thread(target=stream_worker, daemon=True)
        self.streaming_thread.start()

    def estimate_memory_usage(self) -> float:
        """Estimate current memory usage in MB."""
        # Rough estimate: 8 bytes per bool + 8 bytes timestamp + overhead
        bytes_per_sample = 16 + (len(self.config.channels) * 1)  # 1 byte per channel
        total_bytes = self.samples_captured * bytes_per_sample
        return total_bytes / (1024 * 1024)
```

### gRPC Streaming Handler

```python
def AnalyzerStream(self, request: AnalyzerStreamRequest, context):
    """Stream logic samples in real-time (server streaming RPC)."""
    session = self._sessions.get(request.capture_id)
    if not session:
        yield AnalyzerStreamResponse(
            success=False,
            message=f"Unknown capture: {request.capture_id}",
        )
        return

    max_samples = request.max_samples_per_chunk or 1000
    interval_s = request.interval_s or 0.1

    try:
        while context.is_active():
            # Pop samples from buffer (non-blocking)
            samples = session.stream_buffer.pop(max_samples)

            if samples or session.status in [CaptureStatus.COMPLETE, CaptureStatus.ERROR]:
                yield AnalyzerStreamResponse(
                    success=True,
                    message="",
                    samples=samples,
                    capture_complete=(session.status == CaptureStatus.COMPLETE),
                    total_samples=session.samples_captured,
                    samples_dropped=session.samples_dropped,
                )

            if session.status == CaptureStatus.COMPLETE:
                break

            # Wait before next poll
            time.sleep(interval_s)

    except Exception as e:
        yield AnalyzerStreamResponse(
            success=False,
            message=f"Stream error: {e}",
        )
```

## Implementation Design

### 1. Provider Interface (Abstract Base)

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator, Optional, Tuple, List

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

class LogicAnalyzerProvider(ABC):
    """Abstract interface for logic analyzer backends."""

    def __init__(self, logger: Logger):
        self.logger = logger
        self.name = "unknown"

    @abstractmethod
    def connect(self) -> Optional[str]:
        """Connect to analyzer. Returns error or None on success."""
        pass

    @abstractmethod
    def get_capabilities(self) -> ProviderCapabilities:
        """Get supported features."""
        pass

    @abstractmethod
    def start_capture(self, config: AnalyzerCaptureConfig) -> Tuple[Optional[CaptureHandle], Optional[str]]:
        """Start capture. Returns (handle, error)."""
        pass

    @abstractmethod
    def stream_samples(self, handle: CaptureHandle, max_samples: int) -> Iterator[List[AnalyzerSample]]:
        """Yield sample batches as they arrive (real-time). Blocks until capture completes."""
        pass

    @abstractmethod
    def stop_capture(self, handle: CaptureHandle) -> Optional[str]:
        """Stop capture. Returns error or None."""
        pass

    @abstractmethod
    def export_capture(self, handle: CaptureHandle, format: str, path: str) -> Optional[str]:
        """Export to file. Supported formats: 'csv', 'binary', 'native'. Returns error or None."""
        pass

    @abstractmethod
    def add_analyzer(self, handle: CaptureHandle, protocol: str, config: dict) -> Tuple[Optional[str], Optional[str]]:
        """Add protocol analyzer. Returns (analyzer_id, error)."""
        pass

    @abstractmethod
    def get_decoded_data(self, handle: CaptureHandle, analyzer_id: Optional[str] = None) -> List[dict]:
        """Get decoded protocol data. If analyzer_id is None, return all analyzers."""
        pass
```

### 2. Saleae Provider (Logic 2 Backend)

```python
class SaleaeProvider(LogicAnalyzerProvider):
    """Saleae Logic 2 automation backend."""

    def __init__(self, logger: Logger):
        super().__init__(logger)
        self.name = "saleae"
        self._manager: Optional[automation.Manager] = None
        self._device_id: Optional[str] = None

    def connect(self) -> Optional[str]:
        """Connect to Logic 2 software."""
        try:
            from saleae import automation
            self._manager = automation.Manager.connect(port=10430)
            devices = self._manager.get_devices()

            if not devices:
                return "No Saleae devices detected"

            # Prefer first real device
            real_devices = [d for d in devices if d.device_type != automation.DeviceType.SIMULATION]
            self._device_id = real_devices[0].device_id if real_devices else devices[0].device_id
            self.logger.info(f"Connected to Saleae device: {self._device_id}")
            return None

        except ImportError:
            return "logic2-automation package not installed"
        except Exception as e:
            return f"Failed to connect to Logic 2: {e}"

    def get_capabilities(self) -> ProviderCapabilities:
        """Get Saleae capabilities."""
        return ProviderCapabilities(
            name="Saleae Logic 2",
            max_sample_rate_hz=500_000_000,  # 500 MS/s
            max_channels=16,  # Logic Pro 16
            supports_analog=True,
            supported_protocols=["I2C", "SPI", "UART", "CAN", "I2S", "1-Wire"],
            supports_streaming=True,
            supports_triggers=True,
        )

    def start_capture(self, config: AnalyzerCaptureConfig) -> Tuple[Optional[CaptureHandle], Optional[str]]:
        """Start Saleae capture."""
        if not self._manager:
            return None, "Not connected"

        try:
            from saleae import automation

            device_config = automation.LogicDeviceConfiguration(
                enabled_digital_channels=[ch.channel for ch in config.channels if ch.enabled],
                digital_sample_rate=config.sample_rate_hz,
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
        """Stream samples from Saleae capture."""
        capture = handle.native_handle

        # Poll capture for samples
        last_sample_count = 0
        while True:
            # Check if capture is complete
            if capture.is_complete():
                # Get remaining samples
                final_samples = self._get_samples_since(capture, last_sample_count)
                if final_samples:
                    yield final_samples
                break

            # Get new samples
            samples = self._get_samples_since(capture, last_sample_count)
            if samples:
                last_sample_count += len(samples)
                yield samples

            time.sleep(0.05)  # Poll every 50ms

    def _get_samples_since(self, capture, start_index: int) -> List[AnalyzerSample]:
        """Get samples from Saleae capture starting at index."""
        # NOTE: Logic 2 API doesn't support incremental sample retrieval
        # This is a limitation - we'd need to wait for full capture or use
        # custom implementation. For now, return empty until complete.
        # TODO: Check if Logic 2 API has added streaming support
        return []

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
                capture.export_raw_data_csv(directory=os.path.dirname(path))
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
        capture = handle.native_handle

        # Export analyzer data to temp file, then parse
        # TODO: Implement based on Saleae API
        return []
```

### 3. Sigrok Provider (Open-Source Backend)

```python
class SigrokProvider(LogicAnalyzerProvider):
    """sigrok/PulseView backend (supports many analyzers: fx2lafw, DSLogic, etc.)."""

    def __init__(self, logger: Logger):
        super().__init__(logger)
        self.name = "sigrok"
        self._context = None
        self._device = None

    def connect(self) -> Optional[str]:
        """Connect to sigrok device."""
        try:
            import sigrok.core as sr
            self._context = sr.Context.create()

            # Scan for devices
            devices = self._context.drivers["fx2lafw"].scan()  # Example: fx2lafw-compatible
            if not devices:
                return "No sigrok devices found"

            self._device = devices[0]
            self._device.open()
            return None

        except ImportError:
            return "libsigrok Python bindings not installed"
        except Exception as e:
            return f"Failed to connect to sigrok: {e}"

    def get_capabilities(self) -> ProviderCapabilities:
        """Get sigrok capabilities."""
        return ProviderCapabilities(
            name="sigrok",
            max_sample_rate_hz=24_000_000,  # Depends on device
            max_channels=8,  # fx2lafw typical
            supports_analog=False,
            supported_protocols=["I2C", "SPI", "UART", "CAN", "1-Wire"],
            supports_streaming=True,
            supports_triggers=True,
        )

    # ... implement other methods similar to Saleae
```

### 4. Simulation Provider (Testing Backend)

```python
class SimulationProvider(LogicAnalyzerProvider):
    """Mock provider for testing (generates fake data)."""

    def __init__(self, logger: Logger):
        super().__init__(logger)
        self.name = "simulation"

    def connect(self) -> Optional[str]:
        """Always succeeds."""
        return None

    def get_capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            name="Simulation",
            max_sample_rate_hz=100_000_000,
            max_channels=16,
            supports_analog=False,
            supported_protocols=["I2C", "SPI", "UART"],
            supports_streaming=True,
            supports_triggers=False,
        )

    def start_capture(self, config: AnalyzerCaptureConfig) -> Tuple[Optional[CaptureHandle], Optional[str]]:
        """Start fake capture."""
        handle = CaptureHandle(
            provider_id="simulation",
            native_handle={"config": config, "start_time": time.time()},
        )
        return handle, None

    def stream_samples(self, handle: CaptureHandle, max_samples: int) -> Iterator[List[AnalyzerSample]]:
        """Generate fake samples."""
        config = handle.native_handle["config"]
        start_time = handle.native_handle["start_time"]

        sample_rate = config.sample_rate_hz
        total_samples = int(config.duration_s * sample_rate)
        samples_sent = 0

        while samples_sent < total_samples:
            # Generate batch of fake samples
            batch_size = min(max_samples, total_samples - samples_sent)
            batch = []

            for i in range(batch_size):
                timestamp_ns = int((samples_sent + i) * (1e9 / sample_rate))
                # Generate fake square wave on each channel
                values = [(samples_sent + i) % 100 < 50 for _ in config.channels]
                batch.append(AnalyzerSample(timestamp_ns=timestamp_ns, digital_values=values))

            yield batch
            samples_sent += batch_size
            time.sleep(0.05)  # Simulate capture delay

    def stop_capture(self, handle: CaptureHandle) -> Optional[str]:
        return None

    def export_capture(self, handle: CaptureHandle, format: str, path: str) -> Optional[str]:
        # Write fake CSV
        with open(path, "w") as f:
            f.write("timestamp,CH0,CH1,CH2\n")
            f.write("0,1,0,1\n")
        return None

    def add_analyzer(self, handle: CaptureHandle, protocol: str, config: dict) -> Tuple[Optional[str], Optional[str]]:
        return str(uuid.uuid4()), None

    def get_decoded_data(self, handle: CaptureHandle, analyzer_id: Optional[str] = None) -> List[dict]:
        # Return fake I2C transaction
        return [{"address": 0x76, "data": [0x00, 0x01], "read": False}]
```

### 2. Enhanced Capture Session

```python
@dataclass
class CaptureSession:
    """Tracks state for a logic capture session."""

    capture_id: str
    config: AnalyzerCaptureConfig
    status: int = 0  # STATUS_WAITING_TRIGGER
    progress: float = 0.0

    # Saleae-specific state
    saleae_capture: Optional[object] = None  # automation.Capture object
    analyzers: Dict[str, object] = field(default_factory=dict)  # decoder_id -> analyzer

    # Export paths
    export_dir: Optional[str] = None
    csv_path: Optional[str] = None
    capture_file_path: Optional[str] = None
```

### 3. Protocol Analyzer Mapping

Map MTIB protocol enum to Logic 2 analyzer names:

```python
PROTOCOL_TO_ANALYZER: Dict[Protocol, str] = {
    Protocol.PROTOCOL_I2C: "I2C",
    Protocol.PROTOCOL_SPI: "SPI",
    Protocol.PROTOCOL_UART: "Async Serial",
    Protocol.PROTOCOL_1WIRE: "1-Wire",
    Protocol.PROTOCOL_CAN: "CAN",
    Protocol.PROTOCOL_I2S: "I2S / PCM",
    # JTAG, SWD, LIN, PWM may need custom analyzers
}

def add_analyzer(self, capture: object, protocol: Protocol, config: object) -> Tuple[Optional[str], Optional[str]]:
    """Add a protocol analyzer to a Logic 2 capture.

    Returns:
        (analyzer_id, error_message) tuple.
    """
    analyzer_name = PROTOCOL_TO_ANALYZER.get(protocol)
    if not analyzer_name:
        return None, f"Protocol {protocol} not supported"

    # Configure analyzer based on protocol type
    if protocol == Protocol.PROTOCOL_I2C:
        analyzer_config = {
            "sda_channel": config.i2c.sda_channel,
            "scl_channel": config.i2c.scl_channel,
        }
    elif protocol == Protocol.PROTOCOL_SPI:
        analyzer_config = {
            "clock_channel": config.spi.clk_channel,
            "mosi_channel": config.spi.mosi_channel,
            "miso_channel": config.spi.miso_channel,
            "cs_channel": config.spi.cs_channel,
            "cpol": config.spi.cpol,
            "cpha": config.spi.cpha,
        }
    # ... other protocols

    try:
        analyzer = capture.add_analyzer(analyzer_name, settings=analyzer_config)
        return str(analyzer.analyzer_id), None
    except Exception as e:
        return None, f"Failed to add analyzer: {e}"
```

### 4. Data Export

```python
def export_capture_data(self, session: CaptureSession) -> Optional[str]:
    """Export capture data to filesystem.

    Returns:
        Error message if export fails, None on success.
    """
    if not session.saleae_capture:
        return "No active capture"

    # Create export directory
    session.export_dir = f"/tmp/mtib-captures/{session.capture_id}"
    os.makedirs(session.export_dir, exist_ok=True)

    try:
        # Export raw digital data as CSV
        session.csv_path = os.path.join(session.export_dir, "raw_data.csv")
        session.saleae_capture.export_raw_data_csv(
            directory=session.export_dir,
            digital_channels=[ch.channel for ch in session.config.channels if ch.enabled],
        )

        # Export capture file (can be opened in Logic 2 GUI)
        session.capture_file_path = os.path.join(session.export_dir, "capture.sal")
        session.saleae_capture.save_capture(filepath=session.capture_file_path)

        # Export analyzer data for each decoder
        for decoder_id, analyzer in session.analyzers.items():
            analyzer_csv_path = os.path.join(session.export_dir, f"analyzer_{decoder_id}.csv")
            session.saleae_capture.export_data_table(
                filepath=analyzer_csv_path,
                analyzers=[analyzer],
            )

        return None
    except Exception as e:
        return f"Failed to export data: {e}"
```

### 5. AnalyzerHandler Update

```python
class AnalyzerHandler:
    """Handles logic analyzer RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._sessions: Dict[str, CaptureSession] = {}
        self._saleae = SaleaeManager(logger)

        # Connect to Logic 2 on initialization (non-blocking)
        error = self._saleae.connect()
        if error:
            logger.warning(f"Logic analyzer not available: {error}")

    def capture_start(self, request: AnalyzerCaptureStartRequest, context) -> AnalyzerCaptureStartResponse:
        """Start a logic capture session."""
        # Check if Saleae is available
        if not self._saleae.is_available():
            return AnalyzerCaptureStartResponse(
                success=False,
                message="Logic 2 software not running or no hardware connected",
                capture_id="",
            )

        try:
            capture_id = str(uuid.uuid4())

            # Start Saleae capture
            saleae_capture, error = self._saleae.start_capture(request.config)
            if error:
                return AnalyzerCaptureStartResponse(success=False, message=error, capture_id="")

            # Create session
            session = CaptureSession(
                capture_id=capture_id,
                config=request.config,
                saleae_capture=saleae_capture,
            )
            self._sessions[capture_id] = session

            self.logger.info(f"Logic capture started: {capture_id}")
            return AnalyzerCaptureStartResponse(success=True, message="", capture_id=capture_id)
        except Exception as e:
            return AnalyzerCaptureStartResponse(success=False, message=str(e), capture_id="")

    def capture_stop(self, request: AnalyzerCaptureStopRequest, context) -> Response:
        """Stop a logic capture session."""
        session = self._sessions.get(request.capture_id)
        if session is None:
            return Response(success=False, message=f"Unknown capture: {request.capture_id}")

        try:
            # Stop Saleae capture
            if session.saleae_capture:
                session.saleae_capture.stop()

                # Export data to filesystem
                error = self.export_capture_data(session)
                if error:
                    self.logger.warning(f"Export failed for {request.capture_id}: {error}")

            # Clean up session
            del self._sessions[request.capture_id]

            self.logger.info(f"Logic capture stopped: {request.capture_id}")
            return Response(success=True, message="Capture stopped and exported")
        except Exception as e:
            return Response(success=False, message=str(e))
```

## Error Handling Strategy

### 1. Logic 2 Not Running

**Scenario:** Logic 2 software is not running on host/container.

**Handling:**
```python
def connect(self) -> Optional[str]:
    try:
        self._manager = automation.Manager.connect(port=10430)
        # ...
    except grpc.RpcError as e:
        if "failed to connect" in str(e).lower():
            return "Logic 2 software not running. Start Logic 2 or run with: logic2-automation --start"
        return f"gRPC error: {e}"
    except Exception as e:
        return f"Connection failed: {e}"
```

**Client response:**
```python
response = client.AnalyzerCaptureStart(...)
if not response.success:
    print(f"⚠️  {response.message}")
    # Test continues without logic capture
```

### 2. No Hardware Connected

**Scenario:** Logic 2 software is running, but no Saleae device is connected.

**Handling:**
```python
devices = self._manager.get_devices()
if not devices:
    return "No Saleae hardware detected. Connect a Logic analyzer via USB."

# Check for demo/simulation devices
real_devices = [d for d in devices if d.device_type != DeviceType.SIMULATION]
if not real_devices:
    self.logger.info("Using simulation device (no real hardware)")
    self._device_id = devices[0].device_id  # Use demo device
```

**Client behavior:**
- Tests can run with simulation device (generates fake data)
- Warning logged but test doesn't fail

### 3. Unsupported Protocol

**Scenario:** Client requests a protocol decoder not available in Logic 2.

**Handling:**
```python
def add_decoder(self, request: AddDecoderRequest, context) -> AddDecoderResponse:
    # ...
    analyzer_name = PROTOCOL_TO_ANALYZER.get(request.protocol)
    if not analyzer_name:
        return AddDecoderResponse(
            success=False,
            message=f"Protocol {request.protocol} not supported. Available: {list(PROTOCOL_TO_ANALYZER.keys())}",
            decoder_id="",
        )
```

### 4. Capture Timeout

**Scenario:** Capture runs longer than expected (trigger never fires, duration too long).

**Handling:**
```python
def capture_status(self, request: AnalyzerCaptureStatusRequest, context) -> AnalyzerCaptureStatusResponse:
    session = self._sessions.get(request.capture_id)
    if not session:
        return AnalyzerCaptureStatusResponse(success=False, message="Unknown capture")

    # Check if capture is complete
    if session.saleae_capture:
        try:
            # Poll capture status (non-blocking)
            is_complete = session.saleae_capture.is_complete()
            if is_complete:
                session.status = 2  # STATUS_COMPLETE
                session.progress = 1.0
            else:
                session.status = 1  # STATUS_CAPTURING
                # Estimate progress based on duration
                elapsed = time.time() - session.start_time
                session.progress = min(elapsed / session.config.duration_s, 0.99)
        except Exception as e:
            session.status = 3  # STATUS_ERROR
            return AnalyzerCaptureStatusResponse(success=False, message=str(e))

    return AnalyzerCaptureStatusResponse(
        success=True,
        message="",
        status=session.status,
        progress=session.progress,
    )
```

### 5. Server Crash Recovery

**Scenario:** MTIB server restarts while Logic 2 captures are active.

**Handling:**
- Active captures in Logic 2 continue running
- On restart, `SaleaeManager` reconnects to Logic 2
- Orphaned captures can be listed via `manager.get_active_captures()`
- Option to resume or clean up orphaned captures

```python
def recover_orphaned_captures(self) -> List[str]:
    """Find and clean up captures from previous server session."""
    if not self._manager:
        return []

    orphaned = []
    try:
        active_captures = self._manager.get_active_captures()
        for capture in active_captures:
            # Stop orphaned captures
            capture.stop()
            orphaned.append(str(capture.capture_id))

        self.logger.info(f"Cleaned up {len(orphaned)} orphaned captures")
    except Exception as e:
        self.logger.error(f"Failed to recover orphaned captures: {e}")

    return orphaned
```

## File Export & Storage

### Export Directory Structure

```
/tmp/mtib-captures/
└── <capture_id>/
    ├── raw_data.csv           # Raw digital samples (timestamp, CH0, CH1, ...)
    ├── capture.sal            # Logic 2 capture file (can open in GUI)
    ├── analyzer_<decoder_id>.csv  # Decoded protocol data (one per analyzer)
    └── metadata.json          # Capture config + session info
```

### Download via gRPC

Clients can download capture data using existing file management RPCs:

```python
# Client example
response = client.AnalyzerCaptureStop(capture_id="abc-123")
if response.success:
    # Download raw CSV
    for chunk in client.DownloadFile(filename=f"mtib-captures/abc-123/raw_data.csv"):
        csv_data += chunk.data

    # Download capture file (can open in Logic 2 GUI)
    for chunk in client.DownloadFile(filename=f"mtib-captures/abc-123/capture.sal"):
        capture_data += chunk.data
```

## Client API Updates

Add convenience methods to `MtibV2Client`:

```python
class MtibV2Client:
    # ... existing methods

    def analyzer_capture_start(
        self,
        channels: List[int],
        sample_rate_hz: int = 10_000_000,
        duration_s: float = 1.0,
        trigger_channel: Optional[int] = None,
        trigger_edge: str = "rising",
    ) -> Tuple[Optional[str], Optional[str]]:
        """Start a logic analyzer capture.

        Args:
            channels: List of digital channel numbers to capture (e.g., [0, 1, 2, 3])
            sample_rate_hz: Sample rate in Hz (e.g., 10 MHz)
            duration_s: Capture duration in seconds
            trigger_channel: Optional channel to trigger on
            trigger_edge: "rising", "falling", or "either"

        Returns:
            (capture_id, error_message) tuple.
        """
        config = AnalyzerCaptureConfig(
            channels=[AnalyzerChannelConfig(channel=ch, enabled=True) for ch in channels],
            sample_rate_hz=sample_rate_hz,
            duration_s=duration_s,
            trigger_enabled=trigger_channel is not None,
            trigger_channel=trigger_channel or 0,
            trigger_edge={"rising": 0, "falling": 1, "either": 2}[trigger_edge],
        )

        response = self.stub.AnalyzerCaptureStart(AnalyzerCaptureStartRequest(config=config))
        if response.success:
            return response.capture_id, None
        else:
            return None, response.message

    def analyzer_capture_wait(self, capture_id: str, timeout_s: float = 30.0) -> Optional[str]:
        """Wait for a capture to complete.

        Returns:
            Error message if capture fails, None on success.
        """
        start = time.time()
        while time.time() - start < timeout_s:
            response = self.stub.AnalyzerCaptureStatus(AnalyzerCaptureStatusRequest(capture_id=capture_id))
            if not response.success:
                return response.message

            if response.status == 2:  # STATUS_COMPLETE
                return None
            elif response.status == 3:  # STATUS_ERROR
                return "Capture failed"

            time.sleep(0.1)

        return f"Capture timeout after {timeout_s}s"

    def analyzer_add_i2c_decoder(
        self,
        capture_id: str,
        sda_channel: int,
        scl_channel: int,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Add an I2C protocol decoder to a capture.

        Returns:
            (decoder_id, error_message) tuple.
        """
        response = self.stub.AddDecoder(AddDecoderRequest(
            capture_id=capture_id,
            decoder_name="I2C",
            protocol=Protocol.PROTOCOL_I2C,
            i2c=I2cDecoderConfig(sda_channel=sda_channel, scl_channel=scl_channel),
        ))

        if response.success:
            return response.decoder_id, None
        else:
            return None, response.message
```

## Test Plan

### Unit Tests (Mock Hardware)

```python
# test/test_analyzer_mock.py
def test_capture_start_no_hardware(analyzer_handler_mock):
    """Starting capture without Logic 2 should fail gracefully."""
    analyzer_handler_mock._saleae._available = False

    response = analyzer_handler_mock.capture_start(AnalyzerCaptureStartRequest(...))
    assert not response.success
    assert "Logic 2 software not running" in response.message

def test_add_unsupported_protocol(analyzer_handler):
    """Adding unsupported protocol should fail with helpful message."""
    # Start capture
    start_resp = analyzer_handler.capture_start(...)

    # Try to add unsupported protocol
    response = analyzer_handler.add_decoder(AddDecoderRequest(
        capture_id=start_resp.capture_id,
        protocol=999,  # Invalid
    ))

    assert not response.success
    assert "not supported" in response.message
```

### Integration Tests (Real Hardware)

```python
# test/test_analyzer_integration.py
@pytest.mark.requires_hardware
@pytest.mark.requires_saleae
def test_capture_and_decode_i2c(mtib_client):
    """Capture I2C bus and decode transactions."""
    # Start capture
    capture_id, error = mtib_client.analyzer_capture_start(
        channels=[0, 1],  # SDA=0, SCL=1
        sample_rate_hz=10_000_000,
        duration_s=1.0,
    )
    assert error is None

    # Trigger some I2C activity on the bus
    mtib_client.i2c_transfer(bus=1, address=0x76, write_data=b"\x00", read_size=1)

    # Wait for capture to complete
    error = mtib_client.analyzer_capture_wait(capture_id, timeout_s=5.0)
    assert error is None

    # Add I2C decoder
    decoder_id, error = mtib_client.analyzer_add_i2c_decoder(
        capture_id=capture_id,
        sda_channel=0,
        scl_channel=1,
    )
    assert error is None

    # Get decoded data
    response = mtib_client.stub.GetDecodedData(GetDecodedDataRequest(capture_id=capture_id))
    assert response.success
    assert len(response.data) > 0

    # Verify transaction
    transaction = response.data[0].i2c
    assert transaction.address == 0x76
    assert not transaction.read  # Write operation

    # Stop capture
    mtib_client.analyzer_capture_stop(capture_id)
```

## Deployment Considerations

### Container Environment (K8s at 10.4.45.33)

**Option 1: Logic 2 in same container as MTIB server**

```dockerfile
FROM python:3.10

# Install Logic 2 AppImage
RUN apt-get update && apt-get install -y xvfb libfuse2 wget
RUN wget -O /opt/Logic-2.AppImage https://downloads.saleae.com/logic2/Logic-2.latest.AppImage
RUN chmod +x /opt/Logic-2.AppImage

# Install MTIB server
COPY . /app
WORKDIR /app
RUN pip install -r requirements.txt

# Start Logic 2 in headless mode, then start MTIB server
CMD xvfb-run /opt/Logic-2.AppImage --automation-port=10430 & \
    sleep 5 && \
    python -m src.main
```

**Option 2: Logic 2 as separate service (sidecar pattern)**

```yaml
# deploy/helm/templates/mtib-server-deployment.yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
      - name: mtib-server
        image: ghcr.io/concord/mtib-server-v2:latest
        env:
        - name: LOGIC2_HOST
          value: "localhost"
        - name: LOGIC2_PORT
          value: "10430"

      - name: logic2
        image: ghcr.io/concord/logic2-headless:latest
        command: ["xvfb-run", "/opt/Logic-2.AppImage", "--automation-port=10430"]
        volumeMounts:
        - name: usb-devices
          mountPath: /dev/bus/usb

      volumes:
      - name: usb-devices
        hostPath:
          path: /dev/bus/usb
```

**USB device passthrough:**
```yaml
# Grant pod access to Saleae USB device
securityContext:
  privileged: true  # Required for USB access
```

### Host Environment (Direct on 10.4.45.33)

If Logic 2 is already running on the host:

```bash
# Start Logic 2 (if not running)
Logic\ 2 --automation-port=10430 &

# Start MTIB server (will connect to Logic 2)
cd /workspaces/concord/apps/edge/mtib-server-v2
python -m src.main
```

## Configuration

Add to `src/config.py`:

```python
@dataclass
class Config:
    # ... existing config

    # Logic analyzer (Saleae)
    logic2_enabled: bool = field(default=True)
    logic2_host: str = field(default="localhost")
    logic2_port: int = field(default=10430)
    logic2_export_dir: str = field(default="/tmp/mtib-captures")
    logic2_auto_cleanup: bool = field(default=True)  # Delete captures after 24h
```

Environment variables:

```bash
LOGIC2_ENABLED=true
LOGIC2_HOST=localhost
LOGIC2_PORT=10430
LOGIC2_EXPORT_DIR=/tmp/mtib-captures
```

## Future Enhancements

### 1. Live Streaming

Instead of capturing to file, stream samples directly to client:

```python
def AnalyzerStream(self, request: AnalyzerStreamRequest, context):
    """Stream live logic analyzer samples."""
    session = self._sessions.get(request.capture_id)
    if not session or not session.saleae_capture:
        return

    # Stream samples as they arrive
    while context.is_active():
        samples = session.saleae_capture.get_samples(count=1000)
        yield AnalyzerStreamResponse(samples=samples)
        time.sleep(0.01)
```

### 2. High-Level Test Helpers

```python
@contextmanager
def capture_during(self, channels: List[int], sample_rate_hz: int = 10_000_000):
    """Context manager to capture during a block of code.

    Usage:
        with client.capture_during(channels=[0, 1]) as capture_id:
            client.uart_write(b"test")
            client.i2c_transfer(...)

        # Capture automatically stopped and exported
        data = client.download_capture(capture_id)
    """
    capture_id, _ = self.analyzer_capture_start(channels, sample_rate_hz)
    try:
        yield capture_id
    finally:
        self.analyzer_capture_stop(capture_id)
```

### 3. Automated Protocol Verification

```python
def verify_i2c_transaction(
    self,
    capture_id: str,
    expected_address: int,
    expected_data: bytes,
) -> bool:
    """Verify that an I2C transaction occurred with expected data."""
    decoded = self.stub.GetDecodedData(GetDecodedDataRequest(capture_id=capture_id))

    for transaction in decoded.data:
        if transaction.i2c.address == expected_address:
            if bytes(transaction.i2c.data) == expected_data:
                return True

    return False
```

### 4. Multi-Analyzer Support

```python
# Add multiple analyzers to same capture
capture_id, _ = client.analyzer_capture_start(channels=[0, 1, 2, 3, 4, 5])

# I2C on CH0/CH1
client.analyzer_add_i2c_decoder(capture_id, sda_channel=0, scl_channel=1)

# SPI on CH2/CH3/CH4/CH5
client.analyzer_add_spi_decoder(capture_id, clk=2, mosi=3, miso=4, cs=5)

# Get all decoded data
data = client.get_decoded_data(capture_id)
```

## Resources

- **Saleae Logic 2 Automation Docs:** https://saleae.github.io/logic2-automation/
- **Python API (PyPI):** https://pypi.org/project/logic2-automation/
- **gRPC Proto:** https://github.com/saleae/logic2-automation/blob/develop/proto/saleae/grpc/saleae.proto
- **MTIB V2 Protocol:** `/workspaces/concord/libs/protocols/mtib_v2/mtib_v2.proto` (lines 550-694)

## Implementation Checklist

- [ ] Install `logic2-automation` package in container
- [ ] Update `AnalyzerHandler` with `SaleaeManager`
- [ ] Implement `capture_start`, `capture_stop`, `capture_status`
- [ ] Implement `add_decoder`, `get_decoded_data`
- [ ] Add error handling for "Logic 2 not running" case
- [ ] Add client convenience methods to `MtibV2Client`
- [ ] Write unit tests (mocked Saleae)
- [ ] Write integration tests (real hardware)
- [ ] Update deployment config for USB passthrough
- [ ] Document usage in CLAUDE.md
- [ ] Add example test scripts

---

**Next Steps:**
1. Review this design doc with the team
2. Verify Saleae hardware is available at 10.4.45.33
3. Test Logic 2 connection in K8s pod
4. Implement `SaleaeManager` and `AnalyzerHandler` updates
5. Add client methods and integration tests

## Architecture Consistency with MTIB Server V2

### Handler Pattern Compliance

The `AnalyzerHandler` follows the same patterns as other MTIB handlers (`PowerHandler`, `UartHandler`, etc.):

#### 1. Initialization Pattern

```python
class AnalyzerHandler:
    """Handles logic analyzer RPCs following MTIB V2 patterns."""

    def __init__(
        self,
        logger: Logger,
        hardware: "HardwareContext",
        analyzer_observer: Optional["AnalyzerObserver"] = None,
    ):
        """Initialize logic handler with provider auto-detection.

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

        # Log available providers
        providers = [p.name for p in self._registry.providers]
        self.logger.info(f"Logic analyzer providers available: {providers}")
```

#### 2. Error Handling Pattern (Go-Style)

All internal methods return `Optional[str]` for errors:

```python
def _start_capture_internal(self, config: AnalyzerCaptureConfig, provider_name: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """Internal capture start with error propagation.

    Returns:
        (capture_id, error_message) tuple.
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
    )

    # Start streaming thread
    if err := self._start_streaming_thread(session):
        provider.stop_capture(handle)
        return None, err

    with self._sessions_lock:
        self._sessions[capture_id] = session

    return capture_id, None
```

RPC handlers convert errors to Response objects:

```python
def capture_start(self, request: AnalyzerCaptureStartRequest, context) -> AnalyzerCaptureStartResponse:
    """Start a logic capture session (gRPC handler)."""
    try:
        capture_id, err = self._start_capture_internal(request.config)
        if err:
            return AnalyzerCaptureStartResponse(success=False, message=err, capture_id="")

        self.logger.info(f"Logic capture started: {capture_id}")
        return AnalyzerCaptureStartResponse(success=True, message="", capture_id=capture_id)

    except Exception as e:
        self.logger.error(f"Logic capture start failed: {e}", exc_info=True)
        return AnalyzerCaptureStartResponse(success=False, message=str(e), capture_id="")
```

#### 3. Session Management Pattern

Follows the same shared-connection pattern as `UartHandler`:

- **One provider per backend** (like one serial port per UART device)
- **Multiple clients can stream from same capture** (via session.stream_buffer)
- **Thread-safe access** with locks (`self._sessions_lock`)
- **Background threads** for RX (streaming samples from provider)
- **Per-client queues** for broadcast (if multiple clients subscribe)

```python
class CaptureSession:
    """Shared capture session with multi-client streaming (mirrors UartConnection pattern)."""

    def __init__(self, capture_id: str, config: AnalyzerCaptureConfig, provider: LogicAnalyzerProvider, handle: CaptureHandle):
        self.capture_id = capture_id
        self.config = config
        self.provider = provider
        self.handle = handle

        # Status
        self.status: CaptureStatus = CaptureStatus.STARTING
        self.start_time: float = time.time()
        self.samples_captured: int = 0
        self.samples_dropped: int = 0

        # Multi-client streaming (like UART broadcast)
        self.stream_buffer = StreamingBuffer(max_size=config.max_samples or 1_000_000)
        self._client_queues: Dict[str, Queue] = {}  # client_id -> Queue
        self._clients_lock = threading.Lock()

        # Background streaming thread
        self._streaming_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

        # Export buffer (for post-capture file export)
        self.export_buffer: List[AnalyzerSample] = []

    def register_client(self, client_id: str) -> Queue:
        """Register a client for streaming (returns dedicated queue)."""
        with self._clients_lock:
            if client_id in self._client_queues:
                return self._client_queues[client_id]

            queue = Queue(maxsize=RX_QUEUE_MAX)  # Same pattern as UART
            self._client_queues[client_id] = queue
            self.logger.info(f"Client {client_id} subscribed to capture {self.capture_id}")
            return queue

    def unregister_client(self, client_id: str):
        """Unregister a client from streaming."""
        with self._clients_lock:
            if client_id in self._client_queues:
                del self._client_queues[client_id]
                self.logger.info(f"Client {client_id} unsubscribed from capture {self.capture_id}")

    def _broadcast_samples(self, samples: List[AnalyzerSample]):
        """Broadcast samples to all registered clients (like UART._broadcast)."""
        with self._clients_lock:
            for client_id, queue in list(self._client_queues.items()):
                try:
                    queue.put_nowait(samples)
                except QueueFull:
                    # Drop oldest chunk
                    try:
                        queue.get_nowait()
                        queue.put_nowait(samples)
                    except:
                        pass
```

#### 4. Logging Pattern

Consistent with other handlers:

- **info:** Important state changes (capture started, stopped, provider connected)
- **warning:** Degraded functionality (no providers available, memory limit hit, samples dropped)
- **error:** Failures with context (provider errors, export failures, thread crashes)
- **debug:** Verbose details (sample counts, provider selection)

```python
# Good examples from existing handlers:
self.logger.info(f"Logic capture started: {capture_id} (provider: {provider.name})")
self.logger.warning(f"Capture {capture_id} hit memory limit ({mem_mb:.1f} MB), stopping")
self.logger.error(f"Streaming thread crashed for {capture_id}: {e}", exc_info=True)
self.logger.debug(f"Received {len(samples)} samples for {capture_id} ({self.samples_captured} total)")
```

#### 5. Graceful Degradation

Like `PowerHandler` checking GPIO availability:

```python
# PowerHandler pattern:
if err := self._pwr_en.init():
    self.logger.warning(f"DUT power enable GPIO not available: {err}")
    self._gpio_available = False

# AnalyzerHandler equivalent:
def __init__(self, logger, hardware, analyzer_observer=None):
    # ...
    self._registry = ProviderRegistry(logger)

    if not self._registry.providers:
        self.logger.warning("No logic analyzer providers available - running in disabled mode")
        self._disabled = True
    else:
        self._disabled = False

def capture_start(self, request, context):
    if self._disabled:
        return AnalyzerCaptureStartResponse(
            success=False,
            message="Logic analyzer not available (no providers detected). Install logic2-automation or libsigrok.",
            capture_id="",
        )
    # ... proceed with capture
```

#### 6. Hardware Context Integration

Although logic analyzers are external devices (not on MTIB board), we still check hardware capabilities:

```python
def __init__(self, logger: Logger, hardware: "HardwareContext", analyzer_observer=None):
    # ...
    self.hardware = hardware

    # Check if USB host is available (needed for logic analyzer hardware)
    usb_available = os.path.exists("/sys/bus/usb/devices")
    if not usb_available:
        self.logger.warning("USB bus not available - logic analyzers may not be detected")

    # REV-specific notes (future: if MTIB gets built-in logic analyzer)
    if self.hardware.revision == HardwareRevision.REV_1_1:
        self.logger.info("REV 1.1 - external logic analyzer only")
    elif self.hardware.revision == HardwareRevision.REV_1_2:
        self.logger.info("REV 1.2 - external logic analyzer only (future: built-in?)")
```

### Resource Limits & Monitoring

Follows observability patterns:

```python
class AnalyzerHandler:
    # ...

    def get_resource_usage(self) -> Dict[str, any]:
        """Get current resource usage (for observability)."""
        with self._sessions_lock:
            total_memory_mb = 0.0
            active_captures = 0

            for session in self._sessions.values():
                if session.status in [CaptureStatus.STARTING, CaptureStatus.CAPTURING]:
                    active_captures += 1
                total_memory_mb += session.estimate_memory_usage()

            return {
                "active_captures": active_captures,
                "total_memory_mb": total_memory_mb,
                "total_sessions": len(self._sessions),
                "providers_available": [p.name for p in self._registry.providers],
            }
```

Integrate with ObservabilityEngine (optional):

```python
# In src/providers/observability/analyzer_observer.py (future)
class AnalyzerObserver:
    """Monitors logic analyzer state for observability snapshots."""

    def __init__(self, analyzer_handler: AnalyzerHandler):
        self.handler = analyzer_handler

    def get_snapshot(self) -> Dict[str, any]:
        """Get current logic analyzer state for observability RPC."""
        usage = self.handler.get_resource_usage()
        return {
            "logic_analyzer": {
                "providers": usage["providers_available"],
                "active_captures": usage["active_captures"],
                "memory_usage_mb": usage["total_memory_mb"],
            }
        }
```

### Testing Pattern

Follow existing test structure:

```python
# tests/test_analyzer.py (unit tests with mocked providers)
@pytest.fixture
def analyzer_handler(logger, hardware):
    """Logic handler with simulation provider only."""
    handler = AnalyzerHandler(logger, hardware)
    # Force simulation provider
    handler._registry.providers = [SimulationProvider(logger)]
    return handler

# tests/integration/test_analyzer_real.py (integration tests)
@pytest.mark.requires_hardware
@pytest.mark.requires_saleae
def test_capture_with_real_hardware(mtib_client):
    """Test against real Saleae hardware."""
    capture_id, err = mtib_client.analyzer_capture_start(channels=[0, 1], duration_s=1.0)
    assert err is None
    # ...
```

### Configuration Pattern

Add to server config (same as existing `PowerConfig`, `UartConfig`):

```python
# src/config.py
@dataclass
class AnalyzerConfig:
    """Logic analyzer configuration."""
    enabled: bool = field(default=True)
    prefer_provider: Optional[str] = field(default=None)  # "saleae", "sigrok", "simulation"
    default_max_memory_mb: int = field(default=512)
    default_max_samples: int = field(default=10_000_000)
    export_dir: str = field(default="/tmp/mtib-captures")
    auto_cleanup_hours: int = field(default=24)

@dataclass
class Config:
    # ... existing config fields
    analyzer: AnalyzerConfig = field(default_factory=AnalyzerConfig)
```

Environment variables:

```bash
ANALYZER_ENABLED=true
ANALYZER_PREFER_PROVIDER=saleae
ANALYZER_DEFAULT_MAX_MEMORY_MB=512
ANALYZER_EXPORT_DIR=/tmp/mtib-captures
```

## Updated Implementation Checklist

- [ ] **Protocol:** Add `AnalyzerStream` RPC to `mtib_v2.proto`
- [ ] **Provider Interface:** Implement `LogicAnalyzerProvider` ABC
- [ ] **Providers:** Implement Saleae, sigrok, simulation providers
- [ ] **Handler:** Update `AnalyzerHandler` following MTIB patterns
- [ ] **Streaming:** Implement background streaming threads + multi-client broadcast
- [ ] **Resource Limits:** Add memory tracking and enforcement
- [ ] **Config:** Add `AnalyzerConfig` to server config
- [ ] **Client:** Add convenience methods to `MtibV2Client`
- [ ] **Tests:** Unit tests (mocked), integration tests (real hardware)
- [ ] **Observability:** Optional integration with `ObservabilityEngine`
- [ ] **Deployment:** Update container for USB passthrough, Logic 2 installation
- [ ] **Documentation:** Update CLAUDE.md, add usage examples

---

**Implementation Priority:**

1. **Phase 1: Core Architecture**
   - Provider interface + simulation provider (no external deps)
   - Updated `AnalyzerHandler` with session management
   - Unit tests with mocked providers

2. **Phase 2: Saleae Integration**
   - `SaleaeProvider` implementation
   - Test with real Saleae hardware
   - Client convenience methods

3. **Phase 3: Streaming**
   - Add `AnalyzerStream` RPC to proto
   - Implement background streaming threads
   - Multi-client broadcast support

4. **Phase 4: Advanced Features**
   - sigrok provider (if needed)
   - Protocol decoders
   - Observability integration
   - Auto-cleanup of old captures
