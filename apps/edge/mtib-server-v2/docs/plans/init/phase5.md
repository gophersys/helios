# Phase 5: RTT & SWO

**Status:** ⬜ TODO
**Priority:** P2
**Dependencies:** Phase 4

---

## Objectives

1. Implement Real-Time Transfer (RTT) for high-speed bidirectional logging
2. Implement Serial Wire Output (SWO) for ITM trace data
3. Support multiple RTT channels (up/down buffers)
4. Parse SWO ITM stimulus port data

---

## Deliverables

### D5.1: RTT Session Management

**Proto:**
```protobuf
rpc RttStart(RttStartRequest) returns (RttStartResponse);
rpc RttStop(RttStopRequest) returns (RttStopResponse);
rpc RttStream(stream RttStreamRequest) returns (stream RttStreamResponse);
```

**Implementation:**
```python
class RttHandler:
    def __init__(self, logger, debug_handler: DebugHandler):
        self.debug_handler = debug_handler
        self.rtt_sessions: Dict[str, RttSession] = {}

    def RttStart(self, request, context) -> RttStartResponse:
        """Start RTT on a debug session."""
        debug_session = self.debug_handler.sessions.get(request.session_id)
        if not debug_session:
            return RttStartResponse(success=False, message="Debug session not found")

        rtt = RttSession(debug_session)
        rtt.start(
            control_block_address=request.control_block_address or 0,
            search_range=request.search_range or 0x10000,
        )

        self.rtt_sessions[request.session_id] = rtt

        return RttStartResponse(
            success=True,
            up_channels=[
                RttChannel(index=i, name=ch.name, size=ch.size)
                for i, ch in enumerate(rtt.up_channels)
            ],
            down_channels=[
                RttChannel(index=i, name=ch.name, size=ch.size)
                for i, ch in enumerate(rtt.down_channels)
            ],
        )

    def RttStop(self, request, context) -> RttStopResponse:
        """Stop RTT session."""
        rtt = self.rtt_sessions.pop(request.session_id, None)
        if rtt:
            rtt.stop()
        return RttStopResponse(success=True)
```

**Tests:**
```python
def test_rtt_start_discovers_channels():
    """RttStart should discover up/down channels."""
    response = stub.RttStart(RttStartRequest(session_id=session_id))
    assert response.success
    assert len(response.up_channels) > 0

def test_rtt_finds_control_block():
    """RTT should find SEGGER control block in RAM."""
    pass
```

---

### D5.2: RTT Streaming

**Implementation:**
```python
def RttStream(self, request_iterator, context):
    """Bidirectional RTT data stream."""
    session_id = None
    rtt = None

    # Start reader thread for up channels
    def reader_thread():
        while context.is_active() and rtt:
            for channel in rtt.up_channels:
                data = rtt.read(channel.index)
                if data:
                    yield RttStreamResponse(
                        channel=channel.index,
                        data=data,
                        timestamp_us=int(time.time() * 1_000_000),
                    )
            time.sleep(0.001)  # 1ms poll

    # Process incoming write requests
    for request in request_iterator:
        if request.HasField('start'):
            session_id = request.start.session_id
            rtt = self.rtt_sessions.get(session_id)
            # Start yielding data
            yield from reader_thread()
        elif request.HasField('write'):
            if rtt:
                rtt.write(request.write.channel, request.write.data)
```

**Tests:**
```python
def test_rtt_stream_receives_data():
    """Should receive RTT data from target."""
    # Flash firmware that prints to RTT
    # Verify data received via stream

def test_rtt_stream_sends_data():
    """Should send RTT data to target."""
    # Send command via RTT down channel
    # Verify target received it
```

---

### D5.3: SWO Session Management

**Proto:**
```protobuf
rpc SwoStart(SwoStartRequest) returns (SwoStartResponse);
rpc SwoStop(SwoStopRequest) returns (SwoStopResponse);
rpc SwoStream(SwoStreamRequest) returns (stream SwoStreamResponse);
```

**Implementation:**
```python
class SwoHandler:
    def SwoStart(self, request, context) -> SwoStartResponse:
        """Start SWO trace capture."""
        debug_session = self.debug_handler.sessions.get(request.session_id)

        swo = SwoSession(debug_session)
        swo.start(
            clock_hz=request.cpu_clock_hz,
            baud_rate=request.swo_baud_rate or 4_000_000,
            enabled_ports=request.stimulus_ports or [0],
        )

        self.swo_sessions[request.session_id] = swo
        return SwoStartResponse(success=True)

    def SwoStop(self, request, context) -> SwoStopResponse:
        swo = self.swo_sessions.pop(request.session_id, None)
        if swo:
            swo.stop()
        return SwoStopResponse(success=True)
```

---

### D5.4: SWO Streaming

**Implementation:**
```python
def SwoStream(self, request, context):
    """Stream decoded SWO/ITM data."""
    swo = self.swo_sessions.get(request.session_id)
    if not swo:
        return

    while context.is_active():
        packets = swo.read_packets()
        for pkt in packets:
            if pkt.type == ItmPacketType.INSTRUMENTATION:
                yield SwoStreamResponse(
                    stimulus_port=pkt.port,
                    data=pkt.data,
                    timestamp_us=int(time.time() * 1_000_000),
                )
            elif pkt.type == ItmPacketType.EXCEPTION:
                yield SwoStreamResponse(
                    exception_number=pkt.exception_number,
                    is_entry=pkt.is_entry,
                )
        time.sleep(0.001)
```

**Tests:**
```python
def test_swo_stream_receives_itm():
    """Should receive ITM printf output."""
    # Flash firmware with ITM_SendChar calls
    # Verify data received

def test_swo_multiple_stimulus_ports():
    """Should separate data by stimulus port."""
    pass
```

---

### D5.5: RTT Session Class

**New File:** `src/services/rtt_session.py`

```python
class RttSession:
    """SEGGER RTT implementation."""

    RTT_MAGIC = b"SEGGER RTT"

    def __init__(self, debug_session: DebugSession):
        self.debug = debug_session
        self.control_block_addr = None
        self.up_channels = []
        self.down_channels = []

    def start(self, control_block_address=0, search_range=0x10000):
        """Find RTT control block and configure."""
        if control_block_address:
            self.control_block_addr = control_block_address
        else:
            self.control_block_addr = self._find_control_block(search_range)

        self._read_channel_info()

    def _find_control_block(self, search_range) -> int:
        """Search RAM for RTT magic string."""
        ram_start = 0x20000000
        chunk_size = 1024

        for addr in range(ram_start, ram_start + search_range, chunk_size):
            data = self.debug.read_memory(addr, chunk_size)
            idx = data.find(self.RTT_MAGIC)
            if idx >= 0:
                return addr + idx

        raise RuntimeError("RTT control block not found")

    def _read_channel_info(self):
        """Parse control block for channel descriptors."""
        # Control block structure:
        # char acID[16]
        # int32_t MaxNumUpBuffers
        # int32_t MaxNumDownBuffers
        # SEGGER_RTT_BUFFER_UP aUp[MaxNumUpBuffers]
        # SEGGER_RTT_BUFFER_DOWN aDown[MaxNumDownBuffers]
        pass

    def read(self, channel: int) -> bytes:
        """Read data from up channel."""
        # Read ring buffer, update read pointer
        pass

    def write(self, channel: int, data: bytes):
        """Write data to down channel."""
        # Write to ring buffer, update write pointer
        pass
```

---

### D5.6: SWO Session Class

**New File:** `src/services/swo_session.py`

```python
class SwoSession:
    """SWO/ITM trace decoder."""

    def __init__(self, debug_session: DebugSession):
        self.debug = debug_session
        self.enabled_ports = set()

    def start(self, clock_hz, baud_rate, enabled_ports):
        """Configure SWO on target."""
        # Configure TPIU
        self._configure_tpiu(baud_rate, clock_hz)
        # Configure ITM
        self._configure_itm(enabled_ports)
        # Start probe SWO capture
        self.debug.start_swo(baud_rate)

        self.enabled_ports = set(enabled_ports)

    def _configure_tpiu(self, baud_rate, clock_hz):
        """Configure Trace Port Interface Unit."""
        TPIU_BASE = 0xE0040000
        # Set async clock prescaler
        prescaler = (clock_hz // baud_rate) - 1
        self.debug.write_memory(TPIU_BASE + 0x010, prescaler.to_bytes(4, 'little'))
        # Set formatter: bypass
        self.debug.write_memory(TPIU_BASE + 0x304, b'\x00\x00\x00\x00')

    def _configure_itm(self, enabled_ports):
        """Configure Instrumentation Trace Macrocell."""
        ITM_BASE = 0xE0000000
        # Unlock ITM
        self.debug.write_memory(ITM_BASE + 0xFB0, b'\xC5\xAC\xCE\x55')
        # Enable ITM and stimulus ports
        mask = sum(1 << p for p in enabled_ports)
        self.debug.write_memory(ITM_BASE + 0xE00, mask.to_bytes(4, 'little'))

    def read_packets(self) -> List[ItmPacket]:
        """Read and decode SWO packets."""
        raw = self.debug.read_swo()
        return self._decode_itm(raw)

    def _decode_itm(self, data: bytes) -> List[ItmPacket]:
        """Decode ITM packet stream."""
        packets = []
        i = 0
        while i < len(data):
            header = data[i]
            if header == 0:
                i += 1
                continue
            # Parse based on header type
            # ...
        return packets
```

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/handlers/rtt.py` | Created | RttHandler |
| `src/providers/handlers/swo.py` | Created | SwoHandler |
| `src/services/rtt_session.py` | Created | RTT implementation |
| `src/services/swo_session.py` | Created | SWO decoder |
| `src/providers/mtib.py` | Modified | Wire RTT/SWO handlers |

---

## Completion Checklist

- [ ] RttStart/Stop implemented
- [ ] RttStream bidirectional implemented
- [ ] RTT control block discovery
- [ ] RTT ring buffer read/write
- [ ] SwoStart/Stop implemented
- [ ] SwoStream implemented
- [ ] TPIU configuration
- [ ] ITM configuration
- [ ] ITM packet decoder
- [ ] Unit tests with mock
- [ ] Integration tests with real target
