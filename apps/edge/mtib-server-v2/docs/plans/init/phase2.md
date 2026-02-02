# Phase 2: Protocol Migration

**Status:** 🔶 IN PROGRESS
**Priority:** P0 (Critical Path)
**Dependencies:** Phase 1 ✅

---

## Objectives

1. Generate Python bindings from `mtib_v2.proto`
2. Migrate all imports from `protocols.mtib` to `protocols.mtib_v2`
3. Update servicer to implement `MtibV2Servicer`
4. Ensure backward compatibility with existing RPC behavior
5. Add `HealthCheck` and `SystemInfo` RPCs

---

## Deliverables

### D2.1: Proto Generation

**Task:** Generate Python gRPC bindings from mtib_v2.proto

```bash
# From libs/protocols/mtib_v2/
python -m grpc_tools.protoc \
    -I. \
    --python_out=. \
    --grpc_python_out=. \
    mtib_v2.proto
```

**Output Files:**
- `mtib_v2_pb2.py` - Message classes
- `mtib_v2_pb2_grpc.py` - Service stubs

**Test:**
```python
def test_proto_imports():
    from protocols.mtib_v2 import mtib_v2_pb2, mtib_v2_pb2_grpc
    assert hasattr(mtib_v2_pb2, 'HealthCheckRequest')
    assert hasattr(mtib_v2_pb2_grpc, 'MtibV2Servicer')
```

---

### D2.2: Type Imports Migration

**File:** `src/shared/types.py`

**Before:**
```python
from protocols.mtib.mtib_pb2 import (
    HealthCheckResponse,
    GpioConfigRequest,
    # ...
)
from protocols.mtib.mtib_pb2_grpc import MtibV1Servicer
```

**After:**
```python
from protocols.mtib_v2.mtib_v2_pb2 import (
    HealthCheckRequest,
    HealthCheckResponse,
    SystemInfoRequest,
    SystemInfoResponse,
    # ... all V2 types
)
from protocols.mtib_v2.mtib_v2_pb2_grpc import MtibV2Servicer, MtibV2Stub
```

**Test:**
```python
def test_types_import():
    from src.shared.types import HealthCheckResponse, MtibV2Servicer
    assert HealthCheckResponse is not None
```

---

### D2.3: Servicer Migration

**File:** `src/providers/mtib.py`

**Before:**
```python
class MtibV2Provider(MtibV1Servicer):
    ...
```

**After:**
```python
class MtibV2Provider(MtibV2Servicer):
    ...
```

**Test:**
```python
def test_provider_inherits_v2_servicer():
    from src.providers.mtib import MtibV2Provider
    from protocols.mtib_v2.mtib_v2_pb2_grpc import MtibV2Servicer
    assert issubclass(MtibV2Provider, MtibV2Servicer)
```

---

### D2.4: Server Registration

**File:** `src/main.py`

**Before:**
```python
from protocols.mtib import mtib_pb2_grpc
mtib_pb2_grpc.add_MtibV1Servicer_to_server(provider, server)
```

**After:**
```python
from protocols.mtib_v2 import mtib_v2_pb2_grpc
mtib_v2_pb2_grpc.add_MtibV2Servicer_to_server(provider, server)
```

**Test:**
```python
def test_server_registers_v2():
    # Integration test: start server and verify service name
    pass
```

---

### D2.5: HealthCheck RPC

**Proto:**
```protobuf
rpc HealthCheck(HealthCheckRequest) returns (HealthCheckResponse);
```

**Implementation:**
```python
def HealthCheck(self, request: HealthCheckRequest, context) -> HealthCheckResponse:
    return HealthCheckResponse(
        status=HealthStatus.SERVING,
        hardware_revision=self.hardware.revision.id,
        uptime_seconds=int(time.time() - self._start_time),
        errors=self.errors,
    )
```

**Test:**
```python
def test_health_check_returns_revision():
    response = stub.HealthCheck(HealthCheckRequest())
    assert response.status == HealthStatus.SERVING
    assert response.hardware_revision in ["1.1", "1.2"]
```

---

### D2.6: SystemInfo RPC

**Proto:**
```protobuf
rpc SystemInfo(SystemInfoRequest) returns (SystemInfoResponse);
```

**Implementation:**
```python
def SystemInfo(self, request: SystemInfoRequest, context) -> SystemInfoResponse:
    import platform
    import psutil

    return SystemInfoResponse(
        hostname=socket.gethostname(),
        platform=platform.system(),
        cpu_percent=psutil.cpu_percent(),
        memory_total=psutil.virtual_memory().total,
        memory_available=psutil.virtual_memory().available,
        disk_total=psutil.disk_usage('/').total,
        disk_free=psutil.disk_usage('/').free,
    )
```

**Test:**
```python
def test_system_info_returns_stats():
    response = stub.SystemInfo(SystemInfoRequest())
    assert response.hostname != ""
    assert response.memory_total > 0
```

---

### D2.7: Port Update

**File:** `.env.example`

```bash
# V2 uses port 50054 (V1 was 50053)
SERVER_PORT=50054
```

**Test:**
```python
def test_server_listens_on_50054():
    # Start server and verify port
    pass
```

---

## Existing RPC Migration Checklist

Each existing RPC must be verified to work with V2 proto types.

| RPC | Handler | Status | Notes |
|-----|---------|--------|-------|
| `HealthCheck` | Provider | ⬜ TODO | Update to V2 response |
| `GpioConfig` | GpioHandler | ⬜ TODO | Verify types match |
| `GpioWrite` | GpioHandler | ⬜ TODO | Verify types match |
| `GpioRead` | GpioHandler | ⬜ TODO | Verify types match |
| `AdcRead` | AdcHandler | ⬜ TODO | Verify types match |
| `AdcReadAll` | AdcHandler | ⬜ TODO | Verify types match |
| `DutPowerEnable` | PowerHandler | ⬜ TODO | Map to `PowerEnable` |
| `DutPowerDisable` | PowerHandler | ⬜ TODO | Map to `PowerDisable` |
| `DutPowerRead` | PowerHandler | ⬜ TODO | Map to `PowerStatus` |
| `DutChargePowerEnable` | PowerHandler | ⬜ TODO | Map to `PowerEnable` |
| `DutChargePowerDisable` | PowerHandler | ⬜ TODO | Map to `PowerDisable` |
| `DutChargePowerRead` | PowerHandler | ⬜ TODO | Map to `PowerStatus` |
| `AltimeterRead` | SensorsHandler | ⬜ TODO | Verify types match |
| `AccelRead` | SensorsHandler | ⬜ TODO | Verify types match |
| `GetMotionStatus` | MotionHandler | ⬜ TODO | Verify types match |
| `MotionStart` | MotionHandler | ⬜ TODO | Verify types match |
| `MotionHome` | MotionHandler | ⬜ TODO | Verify types match |
| `MotionStop` | MotionHandler | ⬜ TODO | Verify types match |
| `ListProgrammers` | FirmwareHandler | ⬜ TODO | Verify types match |
| `ListFwFiles` | FirmwareHandler | ⬜ TODO | Verify types match |
| `UploadFwFile` | FirmwareHandler | ⬜ TODO | Verify types match |
| `DeleteFwFile` | FirmwareHandler | ⬜ TODO | Verify types match |
| `FlashFwFile` | FirmwareHandler | ⬜ TODO | Verify types match |
| `EraseFlash` | FirmwareHandler | ⬜ TODO | Verify types match |
| `EnableAppProtect` | FirmwareHandler | ⬜ TODO | Verify types match |
| `UartStream` | UartHandler | ⬜ TODO | Update to `UartOpen/Stream` |

---

## Test Cases

### T2.1: Proto Generation
```python
def test_proto_files_exist():
    """Verify generated Python files exist."""
    import protocols.mtib_v2.mtib_v2_pb2 as pb2
    import protocols.mtib_v2.mtib_v2_pb2_grpc as grpc_pb2

def test_all_message_types_available():
    """Verify all expected message types are generated."""
    from protocols.mtib_v2 import mtib_v2_pb2
    required = ['HealthCheckRequest', 'GpioConfigRequest', 'PowerEnableRequest']
    for msg in required:
        assert hasattr(mtib_v2_pb2, msg)
```

### T2.2: Backward Compatibility
```python
def test_gpio_config_still_works():
    """Existing GPIO config behavior unchanged."""
    response = stub.GpioConfig(GpioConfigRequest(
        pin=0,
        direction=GpioDirection.OUTPUT,
    ))
    assert response.success

def test_adc_read_all_still_works():
    """Existing ADC read behavior unchanged."""
    response = stub.AdcReadAll(Empty())
    assert len(response.channels) == 8
```

### T2.3: New RPCs
```python
def test_health_check_includes_revision():
    """HealthCheck returns hardware revision."""
    response = stub.HealthCheck(HealthCheckRequest())
    assert response.hardware_revision in ["1.1", "1.2"]

def test_system_info_returns_metrics():
    """SystemInfo returns system statistics."""
    response = stub.SystemInfo(SystemInfoRequest())
    assert response.memory_total > 0
    assert response.cpu_percent >= 0
```

---

## D2.8: Create V2 Client Package

**Location:** `libs/python/corekinect/mtib_client/v2/`

The V2 client must be created alongside the server. Copy structure from V1 client.

### Directory Structure
```
libs/python/corekinect/mtib_client/v2/
├── __init__.py              # Exports: MtibV2Client, NetConfig
├── setup.py                 # Package setup
└── client/
    ├── __init__.py
    ├── core.py              # MtibV2Client class
    ├── config.py            # NetConfig, etc.
    └── types.py             # Type definitions
```

### __init__.py
```python
from .client.core import MtibV2Client
from .client.config import NetConfig

__all__ = ['MtibV2Client', 'NetConfig']
```

### client/core.py
```python
from typing import Optional, Tuple, List
import grpc
from grpc import insecure_channel
from corekinect.utils import Logger

from protocols.mtib_v2.mtib_v2_pb2 import (
    HealthCheckRequest,
    HealthCheckResponse,
    SystemInfoRequest,
    SystemInfoResponse,
    # Add more as phases implement them
)
from protocols.mtib_v2.mtib_v2_pb2_grpc import MtibV2Stub

from .config import NetConfig

DEFAULT_GRPC_TIMEOUT_SECONDS = 10


class MtibV2Client:
    """gRPC client for MTIB V2 server."""

    class Config:
        def __init__(self, net: NetConfig = NetConfig()):
            self.net = net

    def __init__(self, config: Config, logger: Logger = None):
        self.config = config
        self.logger = logger or Logger("mtib_client_v2")
        self.channel = None
        self.stub = None

    def connect(self) -> Optional[str]:
        """Connect to server. Returns error string or None."""
        try:
            self.channel = insecure_channel(
                f"{self.config.net.addr}:{self.config.net.port}"
            )
            self.stub = MtibV2Stub(self.channel)
            return None
        except Exception as e:
            return str(e)

    def disconnect(self):
        """Disconnect from server."""
        if self.channel:
            self.channel.close()
            self.channel = None
            self.stub = None

    def HealthCheck(self, timeout: float = DEFAULT_GRPC_TIMEOUT_SECONDS) -> Tuple[bool, List[str], Optional[str]]:
        """Check server health.

        Returns:
            Tuple of (ready, errors, error_message)
        """
        try:
            resp = self.stub.HealthCheck(
                HealthCheckRequest(),
                timeout=timeout
            )
            return resp.ready, list(resp.errors), None
        except Exception as e:
            return False, [], str(e)

    def SystemInfo(self, timeout: float = DEFAULT_GRPC_TIMEOUT_SECONDS) -> Tuple[Optional[SystemInfoResponse], Optional[str]]:
        """Get system info.

        Returns:
            Tuple of (response, error_message)
        """
        try:
            resp = self.stub.SystemInfo(
                SystemInfoRequest(),
                timeout=timeout
            )
            return resp, None
        except Exception as e:
            return None, str(e)
```

### client/config.py
```python
class NetConfig:
    def __init__(self, addr: str = "127.0.0.1", port: int = 50054):
        self.addr = addr
        self.port = port
```

### Test
```python
def test_v2_client_connects():
    """V2 client should connect to localhost server."""
    from corekinect.mtib_client.v2 import MtibV2Client, NetConfig

    client = MtibV2Client(config=MtibV2Client.Config(
        net=NetConfig(addr="127.0.0.1", port=50054)
    ))
    error = client.connect()
    assert error is None

    ready, errors, err = client.HealthCheck()
    assert err is None
    assert ready

    client.disconnect()
```

---

## Files Changed

### Server Files
| File | Change Type | Description |
|------|-------------|-------------|
| `protocols/mtib_v2/mtib_v2_pb2.py` | Generated | Proto messages |
| `protocols/mtib_v2/mtib_v2_pb2_grpc.py` | Generated | gRPC stubs |
| `src/shared/types.py` | Modified | Import V2 types |
| `src/main.py` | Modified | Register V2 servicer |
| `src/providers/mtib.py` | Modified | Inherit MtibV2Servicer |
| `src/providers/handlers/*.py` | Modified | Update type hints |
| `.env.example` | Modified | Port 50054 |

### Client Files (NEW)
| File | Change Type | Description |
|------|-------------|-------------|
| `libs/python/corekinect/mtib_client/v2/__init__.py` | Created | Package exports |
| `libs/python/corekinect/mtib_client/v2/setup.py` | Created | Package setup |
| `libs/python/corekinect/mtib_client/v2/client/__init__.py` | Created | Client subpackage |
| `libs/python/corekinect/mtib_client/v2/client/core.py` | Created | MtibV2Client |
| `libs/python/corekinect/mtib_client/v2/client/config.py` | Created | NetConfig |
| `libs/python/corekinect/mtib_client/v2/client/types.py` | Created | Type definitions |

### Test Files
| File | Change Type | Description |
|------|-------------|-------------|
| `test/integration/test_health.py` | Created | Health/System tests |

---

## Completion Checklist

### Server
- [x] Proto files generated
- [x] Types imported from mtib_v2
- [x] Provider inherits MtibV2Servicer
- [x] Server registers V2 servicer
- [x] HealthCheck RPC implemented
- [x] SystemInfo RPC implemented
- [ ] All existing RPCs verified
- [x] Port updated to 50052 (not 50054)

### Client
- [x] V2 client package created
- [x] MtibV2Client class implemented
- [x] NetConfig class implemented
- [x] connect/disconnect methods
- [x] HealthCheck client method
- [x] SystemInfo client method

### Testing
- [ ] Unit tests passing
- [ ] Integration tests passing (need running server)
- [x] Client imports work
- [ ] HealthCheck returns valid response (need running server)
- [ ] SystemInfo returns valid response (need running server)
