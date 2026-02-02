# Phase 11: File Management & System RPCs

**Status:** ⬜ TODO
**Priority:** P2
**Dependencies:** Phase 2

---

## Objectives

1. Implement file listing on DUT filesystem
2. Add file upload/download over debug interface
3. Implement file deletion
4. Add health check RPC
5. Add system info RPC

---

## Deliverables

### D11.1: List Files

**Proto:**
```protobuf
rpc ListFiles(ListFilesRequest) returns (ListFilesResponse);
```

**Implementation:**
```python
class FileHandler:
    def __init__(self, logger, debug_handler: DebugHandler):
        self.logger = logger
        self.debug = debug_handler

    def ListFiles(self, request, context) -> ListFilesResponse:
        """List files on DUT filesystem via debug interface."""
        # Use RTT or semihosting to list files
        if request.method == FileMethod.SEMIHOSTING:
            return self._list_via_semihosting(request)
        elif request.method == FileMethod.LITTLEFS:
            return self._list_via_littlefs(request)
        else:
            return self._list_via_shell(request)

    def _list_via_shell(self, request) -> ListFilesResponse:
        """List files via Zephyr shell 'fs ls' command."""
        shell_resp = self.zephyr.ZephyrShell(ZephyrShellRequest(
            session_id=request.session_id,
            command=f"fs ls {request.path}",
        ))

        if not shell_resp.success:
            return ListFilesResponse(success=False, message=shell_resp.message)

        files = []
        for line in shell_resp.output.split('\n'):
            # Parse: "<DIR> dirname" or "     1234 filename"
            match = re.match(r'\s*(<DIR>|\d+)\s+(.+)', line)
            if match:
                is_dir = match.group(1) == '<DIR>'
                files.append(FileInfo(
                    name=match.group(2),
                    is_directory=is_dir,
                    size=0 if is_dir else int(match.group(1)),
                ))

        return ListFilesResponse(success=True, files=files)

    def _list_via_littlefs(self, request) -> ListFilesResponse:
        """List files by reading LittleFS structures via memory."""
        # Read filesystem superblock to find root
        # Walk directory entries
        # This requires knowing the LittleFS layout in memory
        pass
```

**Tests:**
```python
def test_list_files_root():
    """Should list files in root directory."""
    response = stub.ListFiles(ListFilesRequest(
        session_id=session_id,
        path="/",
    ))
    assert response.success
    assert len(response.files) >= 0

def test_list_files_via_shell():
    """Should list files using shell command."""
    response = stub.ListFiles(ListFilesRequest(
        session_id=session_id,
        path="/lfs",
        method=FileMethod.SHELL,
    ))
    assert response.success
```

---

### D11.2: Upload File

**Proto:**
```protobuf
rpc UploadFile(stream UploadFileChunk) returns (UploadFileResponse);
```

**Implementation:**
```python
def UploadFile(self, request_iterator, context) -> UploadFileResponse:
    """Upload file to DUT filesystem."""
    file_path = None
    total_bytes = 0
    chunks = []

    for chunk in request_iterator:
        if chunk.HasField('metadata'):
            file_path = chunk.metadata.path
            self.logger.info(f"Uploading to {file_path}")
        else:
            chunks.append(chunk.data)
            total_bytes += len(chunk.data)

    if not file_path:
        return UploadFileResponse(success=False, message="No file path specified")

    # Combine chunks
    file_data = b''.join(chunks)

    # Write via appropriate method
    if self._is_debug_connected():
        return self._upload_via_debug(file_path, file_data)
    else:
        return self._upload_via_shell(file_path, file_data)

def _upload_via_shell(self, path: str, data: bytes) -> UploadFileResponse:
    """Upload file by writing chunks via shell."""
    # Create file
    self.zephyr.ZephyrShell(ZephyrShellRequest(
        command=f"fs rm {path}",  # Remove if exists
    ))

    # Write in chunks (shell has line length limits)
    chunk_size = 64
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i+chunk_size]
        hex_data = chunk.hex()
        self.zephyr.ZephyrShell(ZephyrShellRequest(
            command=f"fs write {path} {hex_data}",
        ))

    return UploadFileResponse(success=True, bytes_written=len(data))

def _upload_via_debug(self, path: str, data: bytes) -> UploadFileResponse:
    """Upload file via debug memory write + semihosting."""
    # Write data to RAM buffer
    buffer_addr = 0x20010000  # Configurable RAM address
    self.debug.write_memory(buffer_addr, data)

    # Trigger semihosting file write
    # This requires firmware support
    pass
```

**Tests:**
```python
def test_upload_small_file():
    """Should upload small file."""
    def generate_chunks():
        yield UploadFileChunk(metadata=FileMetadata(path="/lfs/test.txt"))
        yield UploadFileChunk(data=b"Hello, World!")

    response = stub.UploadFile(generate_chunks())
    assert response.success
    assert response.bytes_written == 13

def test_upload_large_file():
    """Should upload large file in chunks."""
    data = b"X" * 4096

    def generate_chunks():
        yield UploadFileChunk(metadata=FileMetadata(path="/lfs/large.bin"))
        for i in range(0, len(data), 256):
            yield UploadFileChunk(data=data[i:i+256])

    response = stub.UploadFile(generate_chunks())
    assert response.success
    assert response.bytes_written == 4096
```

---

### D11.3: Download File

**Proto:**
```protobuf
rpc DownloadFile(DownloadFileRequest) returns (stream DownloadFileChunk);
```

**Implementation:**
```python
def DownloadFile(self, request, context):
    """Download file from DUT filesystem."""
    # First get file size
    list_resp = self.ListFiles(ListFilesRequest(path=request.path))
    if not list_resp.success:
        return

    file_info = next((f for f in list_resp.files if f.name == os.path.basename(request.path)), None)
    if not file_info:
        return

    # Send metadata first
    yield DownloadFileChunk(metadata=FileMetadata(
        path=request.path,
        size=file_info.size,
    ))

    # Read and stream chunks
    chunk_size = request.chunk_size or 256
    offset = 0

    while offset < file_info.size:
        # Read chunk via shell
        shell_resp = self.zephyr.ZephyrShell(ZephyrShellRequest(
            command=f"fs read {request.path} {offset} {chunk_size}",
        ))

        if not shell_resp.success:
            break

        # Parse hex output
        data = bytes.fromhex(shell_resp.output.strip())
        yield DownloadFileChunk(data=data)
        offset += len(data)
```

**Tests:**
```python
def test_download_file():
    """Should download file."""
    chunks = list(stub.DownloadFile(DownloadFileRequest(
        session_id=session_id,
        path="/lfs/test.txt",
    )))

    assert len(chunks) >= 1
    assert chunks[0].HasField('metadata')

    data = b''.join(c.data for c in chunks[1:])
    assert len(data) > 0
```

---

### D11.4: Delete File

**Proto:**
```protobuf
rpc DeleteFile(DeleteFileRequest) returns (DeleteFileResponse);
```

**Implementation:**
```python
def DeleteFile(self, request, context) -> DeleteFileResponse:
    """Delete file from DUT filesystem."""
    shell_resp = self.zephyr.ZephyrShell(ZephyrShellRequest(
        session_id=request.session_id,
        command=f"fs rm {request.path}",
    ))

    if not shell_resp.success:
        return DeleteFileResponse(success=False, message=shell_resp.message)

    # Verify deletion
    list_resp = self.ListFiles(ListFilesRequest(path=os.path.dirname(request.path)))
    still_exists = any(f.name == os.path.basename(request.path) for f in list_resp.files)

    return DeleteFileResponse(
        success=not still_exists,
        message="" if not still_exists else "File still exists after delete",
    )
```

**Tests:**
```python
def test_delete_file():
    """Should delete file."""
    # Create file first
    stub.UploadFile(...)

    # Delete it
    response = stub.DeleteFile(DeleteFileRequest(
        session_id=session_id,
        path="/lfs/test.txt",
    ))
    assert response.success

    # Verify gone
    list_resp = stub.ListFiles(ListFilesRequest(path="/lfs"))
    assert "test.txt" not in [f.name for f in list_resp.files]
```

---

### D11.5: Health Check

**Proto:**
```protobuf
rpc HealthCheck(HealthCheckRequest) returns (HealthCheckResponse);
```

**Implementation:**
```python
class SystemHandler:
    def __init__(self, logger, hardware: HardwareContext):
        self.logger = logger
        self.hardware = hardware

    def HealthCheck(self, request, context) -> HealthCheckResponse:
        """Check server health and connectivity."""
        checks = []

        # Check hardware initialization
        checks.append(HealthStatus(
            component="hardware",
            healthy=self.hardware is not None,
            message=f"Revision {self.hardware.revision.name}" if self.hardware else "Not initialized",
        ))

        # Check I2C bus
        try:
            import smbus2
            bus = smbus2.SMBus(1)
            bus.read_byte(0x00)  # Dummy read
            checks.append(HealthStatus(component="i2c", healthy=True))
        except Exception as e:
            checks.append(HealthStatus(component="i2c", healthy=False, message=str(e)))

        # Check USB devices (J-Link)
        try:
            import pylink
            jlink = pylink.JLink()
            emulators = jlink.connected_emulators()
            checks.append(HealthStatus(
                component="jlink",
                healthy=len(emulators) > 0,
                message=f"{len(emulators)} emulator(s) found",
            ))
        except Exception as e:
            checks.append(HealthStatus(component="jlink", healthy=False, message=str(e)))

        # Check motion controller
        checks.append(HealthStatus(
            component="motion",
            healthy=os.path.exists("/dev/ttyACM0"),
            message="ODrive connected" if os.path.exists("/dev/ttyACM0") else "ODrive not found",
        ))

        overall_healthy = all(c.healthy for c in checks)
        return HealthCheckResponse(
            healthy=overall_healthy,
            checks=checks,
        )
```

**Tests:**
```python
def test_health_check():
    """Should return health status."""
    response = stub.HealthCheck(HealthCheckRequest())
    assert response.HasField('healthy')
    assert len(response.checks) > 0

def test_health_check_identifies_components():
    """Should identify all major components."""
    response = stub.HealthCheck(HealthCheckRequest())
    components = [c.component for c in response.checks]
    assert "hardware" in components
    assert "i2c" in components
```

---

### D11.6: System Info

**Proto:**
```protobuf
rpc SystemInfo(SystemInfoRequest) returns (SystemInfoResponse);
```

**Implementation:**
```python
def SystemInfo(self, request, context) -> SystemInfoResponse:
    """Get server system information."""
    import platform
    import psutil

    return SystemInfoResponse(
        hostname=platform.node(),
        platform=platform.system(),
        platform_version=platform.release(),
        python_version=platform.python_version(),
        server_version="2.0.0",
        hardware_revision=self.hardware.revision.name if self.hardware else "unknown",
        uptime_seconds=int(time.time() - self._start_time),
        cpu_percent=psutil.cpu_percent(),
        memory_percent=psutil.virtual_memory().percent,
        disk_percent=psutil.disk_usage('/').percent,
    )
```

**Tests:**
```python
def test_system_info():
    """Should return system information."""
    response = stub.SystemInfo(SystemInfoRequest())
    assert response.hostname
    assert response.server_version == "2.0.0"
    assert response.hardware_revision in ["REV_1_1", "REV_1_2"]
```

---

## Dependencies

- `psutil>=5.9.0` - System metrics

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/handlers/file.py` | Created | FileHandler |
| `src/providers/handlers/system.py` | Created | SystemHandler |
| `src/providers/mtib.py` | Modified | Wire handlers |
| `requirements.txt` | Modified | Add psutil |

---

## Completion Checklist

- [ ] ListFiles implemented (shell method)
- [ ] UploadFile with streaming
- [ ] DownloadFile with streaming
- [ ] DeleteFile implemented
- [ ] HealthCheck with component checks
- [ ] SystemInfo with metrics
- [ ] Unit tests passing
- [ ] Integration tests with DUT filesystem
