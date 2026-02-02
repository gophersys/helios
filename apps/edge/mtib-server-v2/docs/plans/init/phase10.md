# Phase 10: Zephyr Integration

**Status:** ⬜ TODO
**Priority:** P2
**Dependencies:** Phase 4, Phase 5

---

## Objectives

1. Implement Zephyr shell command execution
2. Add Zephyr log streaming with filtering
3. Expose device tree inspection
4. Add thread state inspection
5. Integrate with Twister test framework

---

## Deliverables

### D10.1: Zephyr Shell

**Proto:**
```protobuf
rpc ZephyrShell(ZephyrShellRequest) returns (ZephyrShellResponse);
```

**Implementation:**
```python
class ZephyrHandler:
    def __init__(self, logger, uart_handler: UartHandler, rtt_handler: RttHandler):
        self.uart = uart_handler
        self.rtt = rtt_handler

    def ZephyrShell(self, request, context) -> ZephyrShellResponse:
        """Execute Zephyr shell command."""
        # Determine transport (UART or RTT)
        if request.transport == ShellTransport.UART:
            return self._shell_via_uart(request)
        elif request.transport == ShellTransport.RTT:
            return self._shell_via_rtt(request)
        else:
            # Auto-detect: try RTT first, fall back to UART
            try:
                return self._shell_via_rtt(request)
            except:
                return self._shell_via_uart(request)

    def _shell_via_uart(self, request) -> ZephyrShellResponse:
        """Execute shell command via UART."""
        # Send command
        self.uart.write(request.target, f"{request.command}\r\n".encode())

        # Read response until prompt
        response = b""
        timeout = time.time() + (request.timeout_seconds or 5.0)

        while time.time() < timeout:
            data = self.uart.read(request.target, timeout=0.1)
            response += data
            if b"uart:~$" in response or b"rtt:~$" in response:
                break

        # Parse output (remove echo and prompt)
        lines = response.decode(errors='replace').split('\n')
        output = '\n'.join(lines[1:-1])  # Skip command echo and prompt

        return ZephyrShellResponse(success=True, output=output)

    def _shell_via_rtt(self, request) -> ZephyrShellResponse:
        """Execute shell command via RTT."""
        rtt_session = self.rtt.rtt_sessions.get(request.session_id)
        if not rtt_session:
            raise RuntimeError("RTT session not started")

        # RTT shell typically on channel 0
        rtt_session.write(0, f"{request.command}\r\n".encode())

        response = b""
        timeout = time.time() + (request.timeout_seconds or 5.0)

        while time.time() < timeout:
            data = rtt_session.read(0)
            response += data
            if b"rtt:~$" in response:
                break
            time.sleep(0.01)

        return ZephyrShellResponse(success=True, output=response.decode(errors='replace'))
```

**Tests:**
```python
def test_zephyr_shell_kernel_version():
    """Should execute 'kernel version' command."""
    response = stub.ZephyrShell(ZephyrShellRequest(
        target="nrf52840",
        command="kernel version",
    ))
    assert response.success
    assert "Zephyr" in response.output

def test_zephyr_shell_via_rtt():
    """Should execute shell via RTT."""
    # Start debug and RTT session first
    stub.DebugConnect(...)
    stub.RttStart(...)

    response = stub.ZephyrShell(ZephyrShellRequest(
        session_id=session_id,
        transport=ShellTransport.RTT,
        command="help",
    ))
    assert response.success
```

---

### D10.2: Zephyr Log Streaming

**Proto:**
```protobuf
rpc ZephyrLogStream(ZephyrLogStreamRequest) returns (stream ZephyrLogEntry);
```

**Implementation:**
```python
def ZephyrLogStream(self, request, context):
    """Stream Zephyr log messages."""
    # Determine source: RTT or UART
    if request.source == LogSource.RTT:
        yield from self._log_via_rtt(request, context)
    else:
        yield from self._log_via_uart(request, context)

def _log_via_rtt(self, request, context):
    """Stream logs via RTT (typically channel 1 for logs)."""
    rtt = self.rtt.rtt_sessions.get(request.session_id)
    log_channel = 1  # Zephyr LOG backend uses channel 1

    while context.is_active():
        data = rtt.read(log_channel)
        if data:
            for entry in self._parse_log_entries(data):
                # Filter by level
                if entry.level >= request.min_level:
                    # Filter by module
                    if not request.modules or entry.module in request.modules:
                        yield entry
        time.sleep(0.001)

def _parse_log_entries(self, data: bytes) -> List[ZephyrLogEntry]:
    """Parse Zephyr log format."""
    entries = []
    for line in data.decode(errors='replace').split('\n'):
        if not line.strip():
            continue

        # Parse: [timestamp] <level> module: message
        match = re.match(r'\[(\d+)\] <(\w+)> (\w+): (.+)', line)
        if match:
            entries.append(ZephyrLogEntry(
                timestamp_ms=int(match.group(1)),
                level=self._parse_level(match.group(2)),
                module=match.group(3),
                message=match.group(4),
            ))

    return entries
```

**Tests:**
```python
def test_zephyr_log_stream():
    """Should receive log messages."""
    logs = []
    for entry in stub.ZephyrLogStream(ZephyrLogStreamRequest(
        session_id=session_id,
        source=LogSource.RTT,
        min_level=LogLevel.INFO,
    )):
        logs.append(entry)
        if len(logs) >= 10:
            break

    assert len(logs) >= 10

def test_zephyr_log_filter_by_module():
    """Should filter logs by module."""
    logs = list(stub.ZephyrLogStream(ZephyrLogStreamRequest(
        session_id=session_id,
        modules=["bt_hci"],
        timeout_seconds=5,
    )))

    for log in logs:
        assert log.module == "bt_hci"
```

---

### D10.3: Device Tree Inspection

**Proto:**
```protobuf
rpc ZephyrDevicetree(ZephyrDevicetreeRequest) returns (ZephyrDevicetreeResponse);
```

**Implementation:**
```python
def ZephyrDevicetree(self, request, context) -> ZephyrDevicetreeResponse:
    """Inspect Zephyr device tree."""
    # Execute shell command to dump device tree
    shell_resp = self.ZephyrShell(ZephyrShellRequest(
        session_id=request.session_id,
        command="device list",
        transport=request.transport,
    ))

    if not shell_resp.success:
        return ZephyrDevicetreeResponse(success=False, message=shell_resp.message)

    # Parse device list output
    devices = []
    for line in shell_resp.output.split('\n'):
        # Format: "- device_name (READY)" or "- device_name (NOT READY)"
        match = re.match(r'- (\S+)\s+\((\w+)\)', line)
        if match:
            devices.append(DeviceInfo(
                name=match.group(1),
                status=match.group(2),
            ))

    return ZephyrDevicetreeResponse(success=True, devices=devices)
```

**Tests:**
```python
def test_zephyr_devicetree():
    """Should list Zephyr devices."""
    response = stub.ZephyrDevicetree(ZephyrDevicetreeRequest(
        session_id=session_id,
    ))
    assert response.success
    assert len(response.devices) > 0
```

---

### D10.4: Thread Inspection

**Proto:**
```protobuf
rpc ZephyrThreads(ZephyrThreadsRequest) returns (ZephyrThreadsResponse);
```

**Implementation:**
```python
def ZephyrThreads(self, request, context) -> ZephyrThreadsResponse:
    """Inspect Zephyr threads."""
    shell_resp = self.ZephyrShell(ZephyrShellRequest(
        session_id=request.session_id,
        command="kernel threads",
        transport=request.transport,
    ))

    if not shell_resp.success:
        return ZephyrThreadsResponse(success=False)

    # Parse thread list
    threads = []
    for line in shell_resp.output.split('\n'):
        # Parse thread info from kernel threads output
        # Format varies by Zephyr version
        match = re.match(r'\s*(\S+)\s+:\s+.*prio\s+(-?\d+).*', line)
        if match:
            threads.append(ThreadInfo(
                name=match.group(1),
                priority=int(match.group(2)),
            ))

    return ZephyrThreadsResponse(success=True, threads=threads)
```

---

### D10.5: Twister Integration

**Proto:**
```protobuf
rpc TwisterRun(TwisterRunRequest) returns (stream TwisterEvent);
```

**Implementation:**
```python
def TwisterRun(self, request, context):
    """Run Zephyr Twister tests."""
    # Build twister command
    cmd = ["twister"]

    if request.platform:
        cmd.extend(["-p", request.platform])
    if request.testsuite:
        cmd.extend(["-T", request.testsuite])
    if request.test_filter:
        cmd.extend(["--test", request.test_filter])

    # Add device under test options
    cmd.extend([
        "--device-testing",
        "--device-serial", f"socket://{self.host}:{self.uart_port}",
    ])

    # Run twister
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Stream output
    for line in process.stdout:
        if not context.is_active():
            process.terminate()
            break

        event = self._parse_twister_line(line)
        if event:
            yield event

    process.wait()

    yield TwisterEvent(
        type=TwisterEventType.COMPLETE,
        exit_code=process.returncode,
    )

def _parse_twister_line(self, line: str) -> Optional[TwisterEvent]:
    """Parse twister output line."""
    if "PASS" in line:
        return TwisterEvent(type=TwisterEventType.TEST_PASS, message=line)
    elif "FAIL" in line:
        return TwisterEvent(type=TwisterEventType.TEST_FAIL, message=line)
    elif "SKIP" in line:
        return TwisterEvent(type=TwisterEventType.TEST_SKIP, message=line)
    elif "ERROR" in line:
        return TwisterEvent(type=TwisterEventType.ERROR, message=line)
    return None
```

**Tests:**
```python
def test_twister_run():
    """Should run Twister tests."""
    events = list(stub.TwisterRun(TwisterRunRequest(
        platform="nrf52840dk_nrf52840",
        testsuite="samples/hello_world",
    )))

    assert any(e.type == TwisterEventType.COMPLETE for e in events)
```

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/handlers/zephyr.py` | Created | ZephyrHandler |
| `src/providers/mtib.py` | Modified | Wire handler |

---

## Completion Checklist

- [ ] ZephyrShell (UART and RTT)
- [ ] ZephyrLogStream with filtering
- [ ] ZephyrDevicetree inspection
- [ ] ZephyrThreads inspection
- [ ] TwisterRun integration
- [ ] Log entry parsing
- [ ] Unit tests with mock
- [ ] Integration tests with Zephyr device
