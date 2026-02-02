# Phase 4: Debug Probe

**Status:** ⬜ TODO
**Priority:** P1
**Dependencies:** Phase 2

---

## Objectives

1. Implement full debug probe support via PyOCD or J-Link SDK
2. Add execution control (halt, resume, step, reset)
3. Add memory and register access
4. Add breakpoint and watchpoint support
5. Add stack backtrace capture
6. Support J-Link multiplexer on REV 1.2

---

## Deliverables

### D4.1: Debug Session Management

**Proto:**
```protobuf
rpc DebugConnect(DebugConnectRequest) returns (DebugConnectResponse);
rpc DebugDisconnect(DebugDisconnectRequest) returns (DebugDisconnectResponse);
rpc DebugStatus(DebugStatusRequest) returns (DebugStatusResponse);
```

**Implementation:**
```python
class DebugHandler:
    def __init__(self, logger, hardware: HardwareContext):
        self.hardware = hardware
        self.sessions: Dict[str, DebugSession] = {}

    def DebugConnect(self, request, context) -> DebugConnectResponse:
        """Connect to target via debug probe."""
        # Select J-Link if REV 1.2 with multiplexer
        if self.hardware.has_jlink_mux and request.probe_index:
            self.hardware.set_jlink_mux(swap=(request.probe_index == 1))

        session = DebugSession(
            probe_type=request.probe_type,
            probe_serial=request.probe_serial,
            target=request.target,
            interface=request.interface,
            speed_khz=request.speed_khz,
        )
        session.connect()

        session_id = str(uuid.uuid4())
        self.sessions[session_id] = session

        return DebugConnectResponse(
            success=True,
            session_id=session_id,
            target_info=session.get_target_info(),
        )

    def DebugDisconnect(self, request, context) -> DebugDisconnectResponse:
        """Disconnect debug session."""
        session = self.sessions.pop(request.session_id, None)
        if session:
            session.disconnect()
        return DebugDisconnectResponse(success=True)

    def DebugStatus(self, request, context) -> DebugStatusResponse:
        """Get debug session status."""
        session = self.sessions.get(request.session_id)
        if not session:
            return DebugStatusResponse(success=False, message="Session not found")

        return DebugStatusResponse(
            success=True,
            state=session.get_state(),
            pc=session.read_pc(),
        )
```

**Test:**
```python
def test_debug_connect_creates_session():
    """DebugConnect should establish session."""
    response = stub.DebugConnect(DebugConnectRequest(
        probe_type=ProbeType.JLINK,
        target="nrf52840",
        interface=DebugInterface.SWD,
    ))
    assert response.success
    assert response.session_id != ""

def test_debug_connect_rev_1_2_mux():
    """REV 1.2 should set J-Link mux before connect."""
    # Verify mux is set when probe_index specified
    pass
```

---

### D4.2: Execution Control

**Proto:**
```protobuf
rpc DebugHalt(DebugHaltRequest) returns (DebugHaltResponse);
rpc DebugResume(DebugResumeRequest) returns (DebugResumeResponse);
rpc DebugStep(DebugStepRequest) returns (DebugStepResponse);
rpc DebugReset(DebugResetRequest) returns (DebugResetResponse);
```

**Implementation:**
```python
def DebugHalt(self, request, context) -> DebugHaltResponse:
    """Halt target execution."""
    session = self._get_session(request.session_id)
    session.halt()
    return DebugHaltResponse(success=True, pc=session.read_pc())

def DebugResume(self, request, context) -> DebugResumeResponse:
    """Resume target execution."""
    session = self._get_session(request.session_id)
    session.resume()
    return DebugResumeResponse(success=True)

def DebugStep(self, request, context) -> DebugStepResponse:
    """Single-step target."""
    session = self._get_session(request.session_id)
    session.step(count=request.count or 1)
    return DebugStepResponse(success=True, pc=session.read_pc())

def DebugReset(self, request, context) -> DebugResetResponse:
    """Reset target."""
    session = self._get_session(request.session_id)
    session.reset(reset_type=request.reset_type)
    return DebugResetResponse(success=True)
```

**Tests:**
```python
def test_debug_halt_stops_execution():
    """DebugHalt should stop target."""
    stub.DebugHalt(DebugHaltRequest(session_id=session_id))
    status = stub.DebugStatus(DebugStatusRequest(session_id=session_id))
    assert status.state == TargetState.HALTED

def test_debug_step_advances_pc():
    """DebugStep should increment PC."""
    stub.DebugHalt(DebugHaltRequest(session_id=session_id))
    pc_before = stub.DebugStatus(...).pc
    stub.DebugStep(DebugStepRequest(session_id=session_id))
    pc_after = stub.DebugStatus(...).pc
    assert pc_after > pc_before
```

---

### D4.3: Memory Access

**Proto:**
```protobuf
rpc ReadMemory(ReadMemoryRequest) returns (ReadMemoryResponse);
rpc WriteMemory(WriteMemoryRequest) returns (WriteMemoryResponse);
```

**Implementation:**
```python
def ReadMemory(self, request, context) -> ReadMemoryResponse:
    """Read target memory."""
    session = self._get_session(request.session_id)

    # Ensure target is halted
    if session.get_state() != TargetState.HALTED:
        return ReadMemoryResponse(success=False, message="Target must be halted")

    data = session.read_memory(
        address=request.address,
        size=request.size,
        access_width=request.width,  # 8, 16, or 32 bits
    )

    return ReadMemoryResponse(success=True, data=data)

def WriteMemory(self, request, context) -> WriteMemoryResponse:
    """Write target memory."""
    session = self._get_session(request.session_id)

    if session.get_state() != TargetState.HALTED:
        return WriteMemoryResponse(success=False, message="Target must be halted")

    session.write_memory(
        address=request.address,
        data=request.data,
        access_width=request.width,
    )

    return WriteMemoryResponse(success=True)
```

**Tests:**
```python
def test_read_memory_returns_data():
    """ReadMemory should return target memory contents."""
    response = stub.ReadMemory(ReadMemoryRequest(
        session_id=session_id,
        address=0x20000000,  # RAM
        size=256,
    ))
    assert response.success
    assert len(response.data) == 256

def test_write_memory_modifies_target():
    """WriteMemory should modify target memory."""
    data = bytes([0xDE, 0xAD, 0xBE, 0xEF])
    stub.WriteMemory(WriteMemoryRequest(
        session_id=session_id,
        address=0x20000000,
        data=data,
    ))
    readback = stub.ReadMemory(ReadMemoryRequest(
        session_id=session_id,
        address=0x20000000,
        size=4,
    ))
    assert readback.data == data
```

---

### D4.4: Register Access

**Proto:**
```protobuf
rpc ReadRegisters(ReadRegistersRequest) returns (ReadRegistersResponse);
rpc WriteRegister(WriteRegisterRequest) returns (WriteRegisterResponse);
```

**Implementation:**
```python
def ReadRegisters(self, request, context) -> ReadRegistersResponse:
    """Read CPU registers."""
    session = self._get_session(request.session_id)

    regs = {}
    if not request.registers:
        # Read all core registers
        regs = session.read_core_registers()
    else:
        for reg_name in request.registers:
            regs[reg_name] = session.read_register(reg_name)

    return ReadRegistersResponse(
        success=True,
        registers={name: value for name, value in regs.items()},
    )
```

**Tests:**
```python
def test_read_registers_returns_core_regs():
    """ReadRegisters should return R0-R15, SP, PC, etc."""
    response = stub.ReadRegisters(ReadRegistersRequest(session_id=session_id))
    assert "pc" in response.registers
    assert "sp" in response.registers
    assert "r0" in response.registers
```

---

### D4.5: Breakpoints

**Proto:**
```protobuf
rpc SetBreakpoint(SetBreakpointRequest) returns (SetBreakpointResponse);
rpc ClearBreakpoint(ClearBreakpointRequest) returns (ClearBreakpointResponse);
rpc SetWatchpoint(SetWatchpointRequest) returns (SetWatchpointResponse);
```

**Implementation:**
```python
def SetBreakpoint(self, request, context) -> SetBreakpointResponse:
    """Set hardware breakpoint."""
    session = self._get_session(request.session_id)

    bp_id = session.set_breakpoint(
        address=request.address,
        bp_type=request.type,  # HARDWARE, SOFTWARE
    )

    return SetBreakpointResponse(success=True, breakpoint_id=bp_id)

def ClearBreakpoint(self, request, context) -> ClearBreakpointResponse:
    """Clear breakpoint."""
    session = self._get_session(request.session_id)
    session.clear_breakpoint(request.breakpoint_id)
    return ClearBreakpointResponse(success=True)

def SetWatchpoint(self, request, context) -> SetWatchpointResponse:
    """Set data watchpoint."""
    session = self._get_session(request.session_id)

    wp_id = session.set_watchpoint(
        address=request.address,
        size=request.size,
        access_type=request.access_type,  # READ, WRITE, READ_WRITE
    )

    return SetWatchpointResponse(success=True, watchpoint_id=wp_id)
```

**Tests:**
```python
def test_breakpoint_halts_at_address():
    """Breakpoint should halt execution at address."""
    stub.SetBreakpoint(SetBreakpointRequest(
        session_id=session_id,
        address=0x00001000,
    ))
    stub.DebugResume(DebugResumeRequest(session_id=session_id))
    # Wait for halt
    time.sleep(0.1)
    status = stub.DebugStatus(DebugStatusRequest(session_id=session_id))
    assert status.state == TargetState.HALTED
    assert status.pc == 0x00001000
```

---

### D4.6: Backtrace

**Proto:**
```protobuf
rpc Backtrace(BacktraceRequest) returns (BacktraceResponse);
```

**Implementation:**
```python
def Backtrace(self, request, context) -> BacktraceResponse:
    """Get stack backtrace."""
    session = self._get_session(request.session_id)

    frames = session.get_backtrace(max_frames=request.max_frames or 32)

    return BacktraceResponse(
        success=True,
        frames=[
            StackFrame(
                frame_number=i,
                pc=f.pc,
                sp=f.sp,
                function_name=f.function_name or "",
                file=f.file or "",
                line=f.line or 0,
            )
            for i, f in enumerate(frames)
        ],
    )
```

**Tests:**
```python
def test_backtrace_returns_frames():
    """Backtrace should return call stack."""
    response = stub.Backtrace(BacktraceRequest(session_id=session_id))
    assert response.success
    assert len(response.frames) > 0
    assert response.frames[0].pc > 0
```

---

### D4.7: Debug Session Class

**New File:** `src/services/debug_session.py`

```python
from pyocd.core.helpers import ConnectHelper
from pyocd.core.target import Target

class DebugSession:
    def __init__(self, probe_type, probe_serial, target, interface, speed_khz):
        self.probe_type = probe_type
        self.probe_serial = probe_serial
        self.target_name = target
        self.interface = interface
        self.speed_khz = speed_khz
        self._session = None
        self._target = None

    def connect(self):
        self._session = ConnectHelper.session_with_chosen_probe(
            target_override=self.target_name,
            unique_id=self.probe_serial,
        )
        self._session.open()
        self._target = self._session.target

    def disconnect(self):
        if self._session:
            self._session.close()

    def halt(self):
        self._target.halt()

    def resume(self):
        self._target.resume()

    def step(self, count=1):
        for _ in range(count):
            self._target.step()

    def reset(self, reset_type="default"):
        self._target.reset_and_halt() if reset_type == "halt" else self._target.reset()

    def read_memory(self, address, size, access_width=32):
        return self._target.read_memory_block8(address, size)

    def write_memory(self, address, data, access_width=32):
        self._target.write_memory_block8(address, data)

    def read_pc(self):
        return self._target.read_core_register('pc')

    def read_core_registers(self):
        return {reg.name: self._target.read_core_register(reg.name)
                for reg in self._target.core_registers}

    def set_breakpoint(self, address, bp_type="hardware"):
        return self._target.set_breakpoint(address)

    def clear_breakpoint(self, bp_id):
        self._target.remove_breakpoint(bp_id)

    def get_backtrace(self, max_frames=32):
        # Use DWARF unwinder if available
        pass
```

---

## Dependencies

- `pyocd>=0.35.0` - Debug probe interface
- `intelhex>=2.3.0` - Hex file parsing (for ELF/hex loading)

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/handlers/debug.py` | Created | DebugHandler |
| `src/services/debug_session.py` | Created | PyOCD wrapper |
| `src/providers/mtib.py` | Modified | Wire DebugHandler |
| `requirements.txt` | Modified | Add pyocd |

---

## Completion Checklist

- [ ] DebugConnect/Disconnect/Status implemented
- [ ] DebugHalt/Resume/Step/Reset implemented
- [ ] ReadMemory/WriteMemory implemented
- [ ] ReadRegisters/WriteRegister implemented
- [ ] SetBreakpoint/ClearBreakpoint implemented
- [ ] SetWatchpoint implemented
- [ ] Backtrace implemented
- [ ] J-Link mux support (REV 1.2)
- [ ] Unit tests with mock
- [ ] Integration tests with real target
