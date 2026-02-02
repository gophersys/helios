# Phase 8: Logic Analyzer

**Status:** ⬜ TODO
**Priority:** P3
**Dependencies:** Phase 2

---

## Objectives

1. Implement logic capture via external analyzer (Saleae Logic 2)
2. Add protocol decoder support (I2C, SPI, UART)
3. Enable correlation with power samples and debug events
4. Support remote logic analyzer via Saleae automation API

---

## Deliverables

### D8.1: Logic Capture Control

**Proto:**
```protobuf
rpc LogicCaptureStart(LogicCaptureStartRequest) returns (LogicCaptureStartResponse);
rpc LogicCaptureStatus(LogicCaptureStatusRequest) returns (LogicCaptureStatusResponse);
rpc LogicCaptureStop(LogicCaptureStopRequest) returns (LogicCaptureStopResponse);
```

**Implementation:**
```python
from saleae import automation

class LogicHandler:
    def __init__(self, logger):
        self.logger = logger
        self.manager = None
        self.captures: Dict[str, Capture] = {}

    def _ensure_connected(self):
        if self.manager is None:
            self.manager = automation.Manager.connect()

    def LogicCaptureStart(self, request, context) -> LogicCaptureStartResponse:
        """Start logic capture."""
        self._ensure_connected()

        device_config = automation.LogicDeviceConfiguration(
            enabled_digital_channels=list(request.digital_channels),
            enabled_analog_channels=list(request.analog_channels),
            digital_sample_rate=request.sample_rate_hz,
            analog_sample_rate=request.analog_sample_rate_hz or request.sample_rate_hz,
        )

        capture = self.manager.start_capture(
            device_configuration=device_config,
            capture_mode=automation.TimedCaptureMode(
                duration_seconds=request.duration_seconds,
            ) if request.duration_seconds else automation.ManualCaptureMode(),
        )

        capture_id = str(uuid.uuid4())
        self.captures[capture_id] = capture

        return LogicCaptureStartResponse(
            success=True,
            capture_id=capture_id,
        )

    def LogicCaptureStatus(self, request, context) -> LogicCaptureStatusResponse:
        """Get capture status."""
        capture = self.captures.get(request.capture_id)
        if not capture:
            return LogicCaptureStatusResponse(success=False)

        return LogicCaptureStatusResponse(
            success=True,
            is_complete=capture.is_complete,
            samples_captured=capture.samples_captured,
        )

    def LogicCaptureStop(self, request, context) -> LogicCaptureStopResponse:
        """Stop capture and save."""
        capture = self.captures.get(request.capture_id)
        if not capture:
            return LogicCaptureStopResponse(success=False)

        capture.stop()

        # Save to file if requested
        if request.save_path:
            capture.save_capture(filepath=request.save_path)

        return LogicCaptureStopResponse(success=True)
```

**Tests:**
```python
def test_logic_capture_start_stop():
    """Should start and stop capture."""
    start_resp = stub.LogicCaptureStart(LogicCaptureStartRequest(
        digital_channels=[0, 1, 2, 3],
        sample_rate_hz=24_000_000,
        duration_seconds=1.0,
    ))
    assert start_resp.success

    time.sleep(1.5)

    status = stub.LogicCaptureStatus(LogicCaptureStatusRequest(
        capture_id=start_resp.capture_id,
    ))
    assert status.is_complete
```

---

### D8.2: Protocol Decoders

**Proto:**
```protobuf
rpc AddDecoder(AddDecoderRequest) returns (AddDecoderResponse);
rpc GetDecodedData(GetDecodedDataRequest) returns (GetDecodedDataResponse);
```

**Implementation:**
```python
def AddDecoder(self, request, context) -> AddDecoderResponse:
    """Add protocol decoder to capture."""
    capture = self.captures.get(request.capture_id)
    if not capture:
        return AddDecoderResponse(success=False)

    if request.protocol == DecoderProtocol.I2C:
        analyzer = capture.add_analyzer(
            'I2C',
            label='I2C Decoder',
            settings={
                'SDA': automation.DigitalChannelSettings(request.sda_channel),
                'SCL': automation.DigitalChannelSettings(request.scl_channel),
            },
        )
    elif request.protocol == DecoderProtocol.SPI:
        analyzer = capture.add_analyzer(
            'SPI',
            label='SPI Decoder',
            settings={
                'MOSI': automation.DigitalChannelSettings(request.mosi_channel),
                'MISO': automation.DigitalChannelSettings(request.miso_channel),
                'Clock': automation.DigitalChannelSettings(request.clk_channel),
                'Enable': automation.DigitalChannelSettings(request.cs_channel),
            },
        )
    elif request.protocol == DecoderProtocol.UART:
        analyzer = capture.add_analyzer(
            'Async Serial',
            label='UART Decoder',
            settings={
                'Input Channel': automation.DigitalChannelSettings(request.rx_channel),
                'Bit Rate (Bits/s)': request.baud_rate,
            },
        )

    return AddDecoderResponse(success=True, decoder_id=str(analyzer.analyzer_id))

def GetDecodedData(self, request, context) -> GetDecodedDataResponse:
    """Get decoded protocol data."""
    capture = self.captures.get(request.capture_id)
    if not capture:
        return GetDecodedDataResponse(success=False)

    # Export analyzer data
    data_table = capture.get_analyzer_data_table(
        analyzer_id=request.decoder_id,
        radix=automation.RadixType.HEXADECIMAL,
    )

    transactions = []
    for row in data_table.rows:
        transactions.append(DecodedTransaction(
            timestamp_ns=int(row.start_time * 1e9),
            duration_ns=int((row.end_time - row.start_time) * 1e9),
            data=row.data,
            type=row.type,
        ))

    return GetDecodedDataResponse(success=True, transactions=transactions)
```

**Tests:**
```python
def test_add_i2c_decoder():
    """Should add I2C decoder."""
    # Start capture with I2C activity
    start_resp = stub.LogicCaptureStart(...)

    # Add decoder
    decoder_resp = stub.AddDecoder(AddDecoderRequest(
        capture_id=start_resp.capture_id,
        protocol=DecoderProtocol.I2C,
        sda_channel=0,
        scl_channel=1,
    ))
    assert decoder_resp.success

    # Get decoded data
    data_resp = stub.GetDecodedData(GetDecodedDataRequest(
        capture_id=start_resp.capture_id,
        decoder_id=decoder_resp.decoder_id,
    ))
    assert len(data_resp.transactions) > 0
```

---

### D8.3: Mock Logic Analyzer

For testing without hardware:

```python
class MockLogicAnalyzer:
    """Mock logic analyzer for testing."""

    def start_capture(self, config, mode):
        return MockCapture()

class MockCapture:
    def __init__(self):
        self.is_complete = False
        self.samples_captured = 0
        self._timer = None

    def start_timer(self, duration):
        self._timer = threading.Timer(duration, self._complete)
        self._timer.start()

    def _complete(self):
        self.is_complete = True
        self.samples_captured = 24_000_000

    def stop(self):
        if self._timer:
            self._timer.cancel()
        self.is_complete = True

    def add_analyzer(self, name, label, settings):
        return MockAnalyzer()
```

---

## Dependencies

- `logic2-automation>=1.0.0` - Saleae Logic 2 API (optional)

---

## Hardware Requirements

- Saleae Logic Pro 8 or Logic Pro 16
- Logic 2 software running (provides automation server)
- Network access to Logic 2 automation port (10430)

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/handlers/logic.py` | Created | LogicHandler |
| `src/services/mock_logic.py` | Created | Mock for testing |
| `src/providers/mtib.py` | Modified | Wire handler |
| `requirements.txt` | Modified | Add optional dependency |

---

## Completion Checklist

- [ ] LogicCaptureStart/Status/Stop implemented
- [ ] AddDecoder for I2C/SPI/UART
- [ ] GetDecodedData implemented
- [ ] Mock analyzer for testing
- [ ] Capture file saving
- [ ] Unit tests with mock
- [ ] Integration tests with Saleae
