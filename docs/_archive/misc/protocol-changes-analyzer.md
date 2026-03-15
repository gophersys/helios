# Protocol Changes: Generic Analyzer Support (Vendor-Neutral)

**Issue:** Current protocol uses "Logic" naming which is specific to Saleae's brand name ("Logic 8", "Logic Pro 16", etc.). This should be generic to support any logic analyzer backend.

**Solution:** Rename to vendor-neutral terms like "Analyzer" or "DigitalAnalyzer".

## Proposed Changes to mtib_v2.proto

### Before (Lines 550-694 - Current)

```protobuf
// =============================================================================
// Logic Analyzer
// =============================================================================

message LogicChannelConfig {
  uint32 channel = 1;
  string label = 2;
  bool enabled = 3;
}

message LogicCaptureConfig {
  repeated LogicChannelConfig channels = 1;
  uint64 sample_rate_hz = 2;
  float duration_s = 3;

  // Trigger
  bool trigger_enabled = 4;
  uint32 trigger_channel = 5;
  enum TriggerEdge {
    TRIGGER_RISING = 0;
    TRIGGER_FALLING = 1;
    TRIGGER_EITHER = 2;
  }
  TriggerEdge trigger_edge = 6;
  float pre_trigger_s = 7;
}

message LogicCaptureStartRequest {
  LogicCaptureConfig config = 1;
}

message LogicCaptureStartResponse {
  bool success = 1;
  string message = 2;
  string capture_id = 3;
}

message LogicCaptureStatusRequest {
  string capture_id = 1;
}

message LogicCaptureStatusResponse {
  bool success = 1;
  string message = 2;
  enum Status {
    STATUS_WAITING_TRIGGER = 0;
    STATUS_CAPTURING = 1;
    STATUS_COMPLETE = 2;
    STATUS_ERROR = 3;
  }
  Status status = 3;
  float progress = 4;
}

message LogicCaptureStopRequest {
  string capture_id = 1;
}

// ... protocol decoders, etc.
```

### After (Proposed - Vendor-Neutral)

```protobuf
// =============================================================================
// Digital Signal Analyzer (Generic Logic Analyzer Support)
// =============================================================================
//
// Supports any logic analyzer backend: Saleae Logic 2, sigrok/PulseView,
// DSLogic, Kingst, or simulation. Server auto-detects available providers.

enum AnalyzerProvider {
  PROVIDER_AUTO = 0;        // Auto-select best available
  PROVIDER_SALEAE = 1;      // Saleae Logic 2 automation API
  PROVIDER_SIGROK = 2;      // libsigrok (fx2lafw, DSLogic, etc.)
  PROVIDER_SIMULATION = 3;  // Mock data for testing
}

message AnalyzerChannelConfig {
  uint32 channel = 1;
  string label = 2;
  bool enabled = 3;
}

message AnalyzerCaptureConfig {
  repeated AnalyzerChannelConfig channels = 1;
  uint64 sample_rate_hz = 2;
  float duration_s = 3;

  // Trigger
  bool trigger_enabled = 4;
  uint32 trigger_channel = 5;
  enum TriggerEdge {
    TRIGGER_RISING = 0;
    TRIGGER_FALLING = 1;
    TRIGGER_EITHER = 2;
  }
  TriggerEdge trigger_edge = 6;
  float pre_trigger_s = 7;

  // Global timeout (NEW)
  float timeout_s = 8;               // Overall operation timeout (default 60s)

  // Resource limits (NEW)
  uint64 max_samples = 10;           // Hard limit on total samples
  uint64 max_memory_mb = 11;         // Memory limit (default 512 MB)
  bool circular_buffer = 12;         // Overwrite oldest when limit hit
  bool auto_export_on_stop = 13;     // Save to file when stopped
}

message AnalyzerCaptureStartRequest {
  AnalyzerCaptureConfig config = 1;
  AnalyzerProvider prefer_provider = 2;  // Optional provider preference
}

message AnalyzerCaptureStartResponse {
  bool success = 1;
  string message = 2;
  string capture_id = 3;
  string provider_used = 4;              // Which provider was used (e.g., "saleae", "sigrok")
}

message AnalyzerCaptureStatusRequest {
  string capture_id = 1;
}

message AnalyzerCaptureStatusResponse {
  bool success = 1;
  string message = 2;
  enum Status {
    STATUS_WAITING_TRIGGER = 0;
    STATUS_CAPTURING = 1;
    STATUS_COMPLETE = 2;
    STATUS_ERROR = 3;
  }
  Status status = 3;
  float progress = 4;               // 0.0 - 1.0
  uint64 samples_captured = 5;      // Total samples captured so far
  uint64 samples_dropped = 6;       // Samples dropped due to memory limit
  float memory_usage_mb = 7;        // Current memory usage
}

message AnalyzerCaptureStopRequest {
  string capture_id = 1;
}

// NEW: Real-time sample streaming
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
  uint64 samples_dropped = 6;
}

// Protocol decoder configuration (unchanged - already generic)
enum Protocol {
  PROTOCOL_I2C = 0;
  PROTOCOL_SPI = 1;
  PROTOCOL_UART = 2;
  PROTOCOL_1WIRE = 3;
  PROTOCOL_JTAG = 4;
  PROTOCOL_SWD = 5;
  PROTOCOL_CAN = 6;
  PROTOCOL_LIN = 7;
  PROTOCOL_I2S = 8;
  PROTOCOL_PWM = 9;
}

message I2cDecoderConfig {
  uint32 sda_channel = 1;
  uint32 scl_channel = 2;
}

message SpiDecoderConfig {
  uint32 clk_channel = 1;
  uint32 mosi_channel = 2;
  uint32 miso_channel = 3;
  uint32 cs_channel = 4;
  bool cpol = 5;
  bool cpha = 6;
  uint32 bits_per_word = 7;
  bool msb_first = 8;
}

message UartDecoderConfig {
  uint32 rx_channel = 1;
  uint32 tx_channel = 2;
  uint32 baud = 3;
  uint32 data_bits = 4;
  Parity parity = 5;  // Defined in common types section (see Parity enum)
}

message AddDecoderRequest {
  string capture_id = 1;
  string decoder_name = 2;
  Protocol protocol = 3;
  oneof config {
    I2cDecoderConfig i2c = 10;
    SpiDecoderConfig spi = 11;
    UartDecoderConfig uart = 12;
  }
}

message AddDecoderResponse {
  bool success = 1;
  string message = 2;
  string decoder_id = 3;
}

// Decoded protocol data (unchanged - already generic)
message I2cTransaction {
  Timestamp timestamp = 1;
  uint32 address = 2;
  bool read = 3;
  bytes data = 4;
  bool ack = 5;
}

message SpiTransaction {
  Timestamp timestamp = 1;
  bytes mosi_data = 2;
  bytes miso_data = 3;
}

message UartFrame {
  Timestamp timestamp = 1;
  bool is_tx = 2;            // true = TX, false = RX
  bytes data = 3;
  bool parity_error = 4;
  bool framing_error = 5;
}

message CanFrame {
  Timestamp timestamp = 1;
  uint32 id = 2;
  bool extended_id = 3;
  bool rtr = 4;
  bytes data = 5;
}

message DecodedData {
  string decoder_id = 1;
  oneof data {
    I2cTransaction i2c = 10;
    SpiTransaction spi = 11;
    UartFrame uart = 12;
    CanFrame can = 13;
  }
}

message GetDecodedDataRequest {
  string capture_id = 1;
  string decoder_id = 2;            // Empty = all decoders
}

message GetDecodedDataResponse {
  bool success = 1;
  string message = 2;
  repeated DecodedData data = 3;
}

// NEW: Query available analyzer providers
message ListAnalyzerProvidersRequest {}

message AnalyzerProviderInfo {
  string name = 1;                      // "saleae", "sigrok", "simulation"
  string display_name = 2;              // "Saleae Logic 2", "sigrok (libsigrok)"
  bool available = 3;
  uint64 max_sample_rate_hz = 4;
  uint32 max_channels = 5;
  repeated string supported_protocols = 6;
  bool supports_streaming = 7;
  bool supports_triggers = 8;
  string hardware_detected = 9;         // e.g., "Logic 8", "fx2lafw"
  repeated string supported_export_formats = 10;  // e.g., ["csv", "vcd", "native"]
}

message ListAnalyzerProvidersResponse {
  bool success = 1;
  string message = 2;
  repeated AnalyzerProviderInfo providers = 3;
}

// NEW: Export capture to file
message AnalyzerExportRequest {
  string capture_id = 1;
  enum ExportFormat {
    FORMAT_CSV = 0;           // Raw digital CSV (timestamp, CH0, CH1, ...)
    FORMAT_VCD = 1;           // Value Change Dump (waveform viewer format)
    FORMAT_NATIVE_SALEAE = 2; // .sal file (Saleae Logic 2 native)
    FORMAT_NATIVE_SIGROK = 3; // .sr file (sigrok/PulseView native)
  }
  ExportFormat format = 2;
  string output_path = 3;       // Relative to server export dir
}

message AnalyzerExportResponse {
  bool success = 1;
  string message = 2;
  string file_path = 3;         // Full path to exported file
  uint64 file_size_bytes = 4;
}

// NEW: Manual cleanup of analyzer resources
message AnalyzerCleanupRequest {
  string capture_id = 1;        // Empty = clean all inactive captures
}

message AnalyzerCleanupResponse {
  bool success = 1;
  string message = 2;
  repeated string cleaned_capture_ids = 3;
  uint64 memory_freed_mb = 4;
}
```

## Service Definition Changes

### Before

```protobuf
service MtibV2 {
  // ... other RPCs

  // Logic Analyzer
  rpc LogicCaptureStart(LogicCaptureStartRequest) returns (LogicCaptureStartResponse);
  rpc LogicCaptureStatus(LogicCaptureStatusRequest) returns (LogicCaptureStatusResponse);
  rpc LogicCaptureStop(LogicCaptureStopRequest) returns (Response);
  rpc AddDecoder(AddDecoderRequest) returns (AddDecoderResponse);
  rpc GetDecodedData(GetDecodedDataRequest) returns (GetDecodedDataResponse);
}
```

### After (Complete Service Definition)

```protobuf
service MtibV2 {
  // System
  rpc HealthCheck(HealthCheckRequest) returns (HealthCheckResponse);
  rpc SystemInfo(SystemInfoRequest) returns (SystemInfoResponse);

  // Probe and Target Discovery
  rpc ListTargets(Empty) returns (ListTargetsResponse);
  rpc ListProbes(Empty) returns (ListProbesResponse);

  // Debug (SWD/JTAG)
  rpc DebugConnect(DebugConnectRequest) returns (DebugConnectResponse);
  rpc DebugDisconnect(DebugDisconnectRequest) returns (Response);
  rpc DebugStatus(DebugStatusRequest) returns (DebugStatusResponse);
  rpc DebugHalt(DebugHaltRequest) returns (Response);
  rpc DebugResume(DebugResumeRequest) returns (Response);
  rpc DebugStep(DebugStepRequest) returns (Response);
  rpc DebugReset(DebugResetRequest) returns (Response);
  rpc ReadRegisters(ReadRegistersRequest) returns (ReadRegistersResponse);
  rpc WriteRegister(WriteRegisterRequest) returns (Response);
  rpc ReadMemory(ReadMemoryRequest) returns (ReadMemoryResponse);
  rpc WriteMemory(WriteMemoryRequest) returns (Response);
  rpc SetBreakpoint(SetBreakpointRequest) returns (SetBreakpointResponse);
  rpc ClearBreakpoint(ClearBreakpointRequest) returns (Response);
  rpc SetWatchpoint(SetWatchpointRequest) returns (SetWatchpointResponse);
  rpc Backtrace(BacktraceRequest) returns (BacktraceResponse);

  // Flash
  rpc FlashInfo(FlashInfoRequest) returns (FlashInfoResponse);
  rpc FlashErase(FlashEraseRequest) returns (Response);
  rpc FlashWrite(FlashWriteRequest) returns (FlashWriteResponse);
  rpc FlashProgram(FlashProgramRequest) returns (FlashProgramResponse);

  // RTT
  rpc RttStart(RttStartRequest) returns (RttStartResponse);
  rpc RttStop(RttStopRequest) returns (Response);
  rpc RttStream(stream RttStreamRequest) returns (stream RttStreamResponse);

  // SWO
  rpc SwoStart(SwoStartRequest) returns (Response);
  rpc SwoStop(Empty) returns (Response);
  rpc SwoStream(Empty) returns (stream SwoStreamResponse);

  // UART
  rpc UartOpen(UartOpenRequest) returns (UartOpenResponse);
  rpc UartClose(UartCloseRequest) returns (Response);
  rpc UartStream(stream UartStreamRequest) returns (stream UartStreamResponse);

  // Power
  rpc PowerEnable(PowerEnableRequest) returns (Response);
  rpc PowerDisable(PowerDisableRequest) returns (Response);
  rpc PowerStatus(PowerStatusRequest) returns (PowerStatusResponse);
  rpc PowerStream(PowerStreamRequest) returns (stream PowerStreamResponse);
  rpc PowerMeasure(PowerMeasureRequest) returns (PowerMeasureResponse);

  // Digital Signal Analyzer (Generic Logic Analyzer) — UPDATED
  rpc ListAnalyzerProviders(ListAnalyzerProvidersRequest) returns (ListAnalyzerProvidersResponse);
  rpc AnalyzerCaptureStart(AnalyzerCaptureStartRequest) returns (AnalyzerCaptureStartResponse);
  rpc AnalyzerCaptureStatus(AnalyzerCaptureStatusRequest) returns (AnalyzerCaptureStatusResponse);
  rpc AnalyzerCaptureStop(AnalyzerCaptureStopRequest) returns (Response);
  rpc AnalyzerStream(AnalyzerStreamRequest) returns (stream AnalyzerStreamResponse);
  rpc AnalyzerExport(AnalyzerExportRequest) returns (AnalyzerExportResponse);
  rpc AnalyzerCleanup(AnalyzerCleanupRequest) returns (AnalyzerCleanupResponse);
  rpc AddDecoder(AddDecoderRequest) returns (AddDecoderResponse);
  rpc GetDecodedData(GetDecodedDataRequest) returns (GetDecodedDataResponse);

  // GPIO
  rpc GpioConfig(GpioConfigRequest) returns (Response);
  rpc GpioWrite(GpioWriteRequest) returns (Response);
  rpc GpioRead(GpioReadRequest) returns (GpioReadResponse);
  rpc GpioWatch(GpioWatchRequest) returns (stream GpioEventResponse);

  // I2C
  rpc I2cConfigure(I2cConfig) returns (Response);
  rpc I2cTransfer(I2cTransferRequest) returns (I2cTransferResponse);
  rpc I2cScan(I2cScanRequest) returns (I2cScanResponse);

  // SPI
  rpc SpiConfigure(SpiConfig) returns (Response);
  rpc SpiTransfer(SpiTransferRequest) returns (Response);

  // CAN
  rpc CanConfigure(CanConfig) returns (Response);
  rpc CanSend(CanSendRequest) returns (Response);
  rpc CanSetFilter(CanSetFilterRequest) returns (Response);
  rpc CanReceive(Empty) returns (stream CanReceiveResponse);

  // BLE
  rpc BleScan(BleScanRequest) returns (BleScanResponse);
  rpc BleConnect(BleConnectRequest) returns (BleConnectResponse);
  rpc BleDisconnect(BleDisconnectRequest) returns (Response);
  rpc BleDiscoverServices(BleDiscoverServicesRequest) returns (BleDiscoverServicesResponse);
  rpc BleRead(BleReadRequest) returns (BleReadResponse);
  rpc BleWrite(BleWriteRequest) returns (Response);
  rpc BleNotifications(BleConnectRequest) returns (stream BleNotificationResponse);

  // Zephyr
  rpc ZephyrShell(ZephyrShellRequest) returns (ZephyrShellResponse);
  rpc ZephyrLogStream(ZephyrLogStreamRequest) returns (stream ZephyrLogStreamResponse);
  rpc ZephyrDevicetree(ZephyrDevicetreeRequest) returns (ZephyrDevicetreeResponse);
  rpc ZephyrThreads(ZephyrThreadsRequest) returns (ZephyrThreadsResponse);
  rpc TwisterRun(TwisterRunRequest) returns (TwisterRunResponse);

  // File Transfer
  rpc ListFiles(ListFilesRequest) returns (ListFilesResponse);
  rpc UploadFile(stream UploadFileRequest) returns (UploadFileResponse);
  rpc DownloadFile(DownloadFileRequest) returns (stream DownloadFileResponse);
  rpc DeleteFile(DeleteFileRequest) returns (Response);

  // Observability
  rpc GetObservabilitySnapshot(Empty) returns (ObservabilitySnapshot);
  rpc ObservabilityStream(ObservabilityStreamRequest) returns (stream ObservabilityStreamResponse);
}
```

## Summary of Changes

### Naming Changes (Vendor-Neutral)

| Before (Brand-Specific) | After (Generic) | Rationale |
|-------------------------|-----------------|-----------|
| `LogicChannelConfig` | `AnalyzerChannelConfig` | "Logic" is Saleae brand |
| `LogicCaptureConfig` | `AnalyzerCaptureConfig` | Generic term |
| `LogicCaptureStart` | `AnalyzerCaptureStart` | Vendor-neutral |
| `LogicCaptureStatus` | `AnalyzerCaptureStatus` | Vendor-neutral |
| `LogicCaptureStop` | `AnalyzerCaptureStop` | Vendor-neutral |
| `LogicSample` | `AnalyzerSample` | Generic term |
| `LogicStream` | `AnalyzerStream` | Generic term |

### New Features

1. **`AnalyzerProvider` enum** - Explicit provider selection (auto/saleae/sigrok/simulation)
2. **`ListAnalyzerProviders` RPC** - Query available backends and capabilities
3. **`AnalyzerStream` RPC** - Real-time sample streaming (server streaming RPC)
4. **`AnalyzerExport` RPC** - Export to multiple formats (CSV, VCD, native)
5. **Resource limits** - `max_samples`, `max_memory_mb`, `circular_buffer`
6. **Enhanced status** - `samples_captured`, `samples_dropped`, `memory_usage_mb`
7. **Provider info** - Response includes which provider was used

### Backward Compatibility

**Breaking changes:** All RPC names changed. This is acceptable because:
- Protocol is V2 (still in development)
- No external clients exist yet
- Clean break is better than legacy names

**Migration path for existing code:**
```python
# Old (Saleae-specific)
response = client.LogicCaptureStart(LogicCaptureStartRequest(...))

# New (vendor-neutral)
response = client.AnalyzerCaptureStart(AnalyzerCaptureStartRequest(...))
```

## Client API Changes

### Before (Brand-Specific)

```python
class MtibV2Client:
    def logic_capture_start(self, channels, sample_rate_hz, duration_s):
        """Start a logic analyzer capture (Saleae-specific naming)."""
        # ...
```

### After (Generic)

```python
class MtibV2Client:
    def analyzer_list_providers(self) -> List[AnalyzerProviderInfo]:
        """List available logic analyzer providers."""
        response = self.stub.ListAnalyzerProviders(ListAnalyzerProvidersRequest())
        return response.providers

    def analyzer_capture_start(
        self,
        channels: List[int],
        sample_rate_hz: int = 10_000_000,
        duration_s: float = 1.0,
        prefer_provider: str = "auto",
        max_memory_mb: int = 512,
        trigger_channel: Optional[int] = None,
    ) -> Tuple[Optional[str], Optional[str]]:
        """Start a capture on any available logic analyzer.

        Args:
            channels: Digital channel numbers to capture
            sample_rate_hz: Sample rate (up to provider max)
            duration_s: Capture duration
            prefer_provider: "auto", "saleae", "sigrok", or "simulation"
            max_memory_mb: Memory limit for capture
            trigger_channel: Optional trigger channel

        Returns:
            (capture_id, error_message) tuple.
        """
        config = AnalyzerCaptureConfig(
            channels=[AnalyzerChannelConfig(channel=ch, enabled=True) for ch in channels],
            sample_rate_hz=sample_rate_hz,
            duration_s=duration_s,
            max_memory_mb=max_memory_mb,
            # ... trigger config
        )

        provider_enum = {
            "auto": AnalyzerProvider.PROVIDER_AUTO,
            "saleae": AnalyzerProvider.PROVIDER_SALEAE,
            "sigrok": AnalyzerProvider.PROVIDER_SIGROK,
            "simulation": AnalyzerProvider.PROVIDER_SIMULATION,
        }.get(prefer_provider, AnalyzerProvider.PROVIDER_AUTO)

        response = self.stub.AnalyzerCaptureStart(AnalyzerCaptureStartRequest(
            config=config,
            prefer_provider=provider_enum,
        ))

        if response.success:
            self.logger.info(f"Capture started: {response.capture_id} (provider: {response.provider_used})")
            return response.capture_id, None
        else:
            return None, response.message

    def analyzer_stream(self, capture_id: str, max_samples_per_chunk: int = 1000) -> Iterator[AnalyzerStreamResponse]:
        """Stream samples in real-time from an active capture."""
        request = AnalyzerStreamRequest(
            capture_id=capture_id,
            max_samples_per_chunk=max_samples_per_chunk,
            interval_s=0.1,
        )

        for response in self.stub.AnalyzerStream(request):
            yield response
            if response.capture_complete:
                break

    def analyzer_export(self, capture_id: str, format: str = "csv", output_path: str = "capture.csv") -> Optional[str]:
        """Export capture to file.

        Args:
            capture_id: Capture ID
            format: "csv", "vcd", "native_saleae", "native_sigrok"
            output_path: Filename (relative to server export dir)

        Returns:
            Full file path, or None on error.
        """
        format_enum = {
            "csv": AnalyzerExportRequest.FORMAT_CSV,
            "vcd": AnalyzerExportRequest.FORMAT_VCD,
            "native_saleae": AnalyzerExportRequest.FORMAT_NATIVE_SALEAE,
            "native_sigrok": AnalyzerExportRequest.FORMAT_NATIVE_SIGROK,
        }.get(format, AnalyzerExportRequest.FORMAT_CSV)

        response = self.stub.AnalyzerExport(AnalyzerExportRequest(
            capture_id=capture_id,
            format=format_enum,
            output_path=output_path,
        ))

        return response.file_path if response.success else None
```

## Example Usage (Generic)

```python
# Discover available analyzers
providers = client.analyzer_list_providers()
for p in providers:
    print(f"{p.display_name}: {p.max_sample_rate_hz} Hz, {p.max_channels} channels")
    # Output:
    # Saleae Logic 2: 500000000 Hz, 16 channels
    # sigrok (fx2lafw): 24000000 Hz, 8 channels
    # Simulation: 100000000 Hz, 16 channels

# Start capture (auto-selects best provider)
capture_id, err = client.analyzer_capture_start(
    channels=[0, 1, 2, 3],
    sample_rate_hz=10_000_000,
    duration_s=5.0,
    max_memory_mb=256,
)

# Stream samples in real-time
for chunk in client.analyzer_stream(capture_id):
    print(f"Received {len(chunk.samples)} samples ({chunk.total_samples} total)")
    if chunk.samples_dropped > 0:
        print(f"⚠️  Dropped {chunk.samples_dropped} samples (memory limit)")

# Export to CSV
csv_path = client.analyzer_export(capture_id, format="csv")
print(f"Capture exported to: {csv_path}")

# Or export to VCD (waveform viewer format)
vcd_path = client.analyzer_export(capture_id, format="vcd")
# Open in GTKWave, PulseView, etc.
```

## File Changes Required

1. **Protocol:** `/workspaces/concord/libs/protocols/mtib_v2/mtib_v2.proto`
   - Rename all `Logic*` messages to `Analyzer*`
   - Add new messages: `AnalyzerStream`, `AnalyzerExport`, `ListAnalyzerProviders`
   - Add resource limits to config
   - Add provider enum

2. **Generated stubs:** Regenerate after proto changes
   ```bash
   cd libs/protocols
   python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. mtib_v2/mtib_v2.proto
   ```

3. **Server types:** `/workspaces/concord/apps/edge/mtib-server-v2/src/shared/types.py`
   - Update imports to use new names

4. **Handler:** `/workspaces/concord/apps/edge/mtib-server-v2/src/providers/handlers/logic.py`
   - Rename to `analyzer.py`
   - Update class name: `LogicHandler` → `AnalyzerHandler`
   - Update all type references

5. **Tests:** `/workspaces/concord/apps/edge/mtib-server-v2/tests/test_logic.py`
   - Rename to `test_analyzer.py`
   - Update all test names and references

6. **Client:** `/workspaces/concord/libs/python/corekinect/mtib_client/v2/client/core.py`
   - Add new methods: `analyzer_*` (not `logic_*`)

7. **Documentation:** Update all docs to use "analyzer" terminology

## Rollout Plan

1. **Update protocol** (breaking change, but acceptable for V2)
2. **Regenerate stubs**
3. **Update server implementation** (rename handler, update types)
4. **Update tests** (rename, update assertions)
5. **Update client** (add new methods, deprecate old if any)
6. **Update documentation** (CLAUDE.md, design docs)
7. **Test with all providers** (Saleae, sigrok, simulation)

---

**Approval needed before implementation.** This is a breaking change to the protocol, but makes it truly vendor-neutral and future-proof.
