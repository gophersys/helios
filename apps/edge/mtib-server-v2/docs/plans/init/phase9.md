# Phase 9: BLE Support

**Status:** ⬜ TODO
**Priority:** P3
**Dependencies:** Phase 2

---

## Objectives

1. Implement BLE scanning for device discovery
2. Implement BLE connection management
3. Add GATT service discovery
4. Add characteristic read/write operations
5. Add notification streaming

---

## Deliverables

### D9.1: BLE Scanning

**Proto:**
```protobuf
rpc BleScan(BleScanRequest) returns (stream BleAdvertisement);
```

**Implementation:**
```python
from bleak import BleakScanner

class BleHandler:
    def __init__(self, logger):
        self.logger = logger
        self.connections: Dict[str, BleakClient] = {}

    async def BleScan(self, request, context):
        """Scan for BLE devices."""
        scanner = BleakScanner()

        def callback(device, adv_data):
            if not context.is_active():
                return

            # Filter by name if specified
            if request.name_filter and request.name_filter not in (device.name or ""):
                return

            # Filter by service UUID if specified
            if request.service_uuid:
                if request.service_uuid not in adv_data.service_uuids:
                    return

            yield BleAdvertisement(
                address=device.address,
                name=device.name or "",
                rssi=adv_data.rssi,
                service_uuids=adv_data.service_uuids,
                manufacturer_data=dict(adv_data.manufacturer_data),
            )

        scanner.register_detection_callback(callback)

        try:
            await scanner.start()
            while context.is_active():
                await asyncio.sleep(0.1)
        finally:
            await scanner.stop()
```

**Tests:**
```python
def test_ble_scan_finds_devices():
    """BleScan should find nearby BLE devices."""
    devices = []
    for adv in stub.BleScan(BleScanRequest(timeout_seconds=5)):
        devices.append(adv)
        if len(devices) >= 3:
            break
    assert len(devices) > 0

def test_ble_scan_filters_by_name():
    """Should filter devices by name."""
    devices = list(stub.BleScan(BleScanRequest(
        name_filter="Nordic",
        timeout_seconds=5,
    )))
    for d in devices:
        assert "Nordic" in d.name
```

---

### D9.2: BLE Connection

**Proto:**
```protobuf
rpc BleConnect(BleConnectRequest) returns (BleConnectResponse);
rpc BleDisconnect(BleDisconnectRequest) returns (BleDisconnectResponse);
```

**Implementation:**
```python
from bleak import BleakClient

async def BleConnect(self, request, context) -> BleConnectResponse:
    """Connect to BLE device."""
    try:
        client = BleakClient(request.address)
        await client.connect(timeout=request.timeout_seconds or 10.0)

        self.connections[request.address] = client

        return BleConnectResponse(
            success=True,
            mtu=client.mtu_size,
        )
    except Exception as e:
        return BleConnectResponse(success=False, message=str(e))

async def BleDisconnect(self, request, context) -> BleDisconnectResponse:
    """Disconnect from BLE device."""
    client = self.connections.pop(request.address, None)
    if client:
        await client.disconnect()
    return BleDisconnectResponse(success=True)
```

**Tests:**
```python
def test_ble_connect_disconnect():
    """Should connect and disconnect from device."""
    # Connect
    resp = stub.BleConnect(BleConnectRequest(address="AA:BB:CC:DD:EE:FF"))
    assert resp.success

    # Disconnect
    resp = stub.BleDisconnect(BleDisconnectRequest(address="AA:BB:CC:DD:EE:FF"))
    assert resp.success
```

---

### D9.3: GATT Discovery

**Proto:**
```protobuf
rpc BleDiscoverServices(BleDiscoverServicesRequest) returns (BleDiscoverServicesResponse);
```

**Implementation:**
```python
async def BleDiscoverServices(self, request, context) -> BleDiscoverServicesResponse:
    """Discover GATT services and characteristics."""
    client = self.connections.get(request.address)
    if not client:
        return BleDiscoverServicesResponse(success=False, message="Not connected")

    services = []
    for service in client.services:
        chars = []
        for char in service.characteristics:
            chars.append(BleCharacteristic(
                uuid=str(char.uuid),
                handle=char.handle,
                properties=list(char.properties),
                descriptors=[
                    BleDescriptor(uuid=str(d.uuid), handle=d.handle)
                    for d in char.descriptors
                ],
            ))

        services.append(BleService(
            uuid=str(service.uuid),
            characteristics=chars,
        ))

    return BleDiscoverServicesResponse(success=True, services=services)
```

**Tests:**
```python
def test_ble_discover_services():
    """Should discover GATT services."""
    stub.BleConnect(BleConnectRequest(address="AA:BB:CC:DD:EE:FF"))
    resp = stub.BleDiscoverServices(BleDiscoverServicesRequest(address="AA:BB:CC:DD:EE:FF"))
    assert resp.success
    assert len(resp.services) > 0
```

---

### D9.4: Characteristic Read/Write

**Proto:**
```protobuf
rpc BleRead(BleReadRequest) returns (BleReadResponse);
rpc BleWrite(BleWriteRequest) returns (BleWriteResponse);
```

**Implementation:**
```python
async def BleRead(self, request, context) -> BleReadResponse:
    """Read characteristic value."""
    client = self.connections.get(request.address)
    if not client:
        return BleReadResponse(success=False, message="Not connected")

    try:
        data = await client.read_gatt_char(request.characteristic_uuid)
        return BleReadResponse(success=True, data=bytes(data))
    except Exception as e:
        return BleReadResponse(success=False, message=str(e))

async def BleWrite(self, request, context) -> BleWriteResponse:
    """Write characteristic value."""
    client = self.connections.get(request.address)
    if not client:
        return BleWriteResponse(success=False, message="Not connected")

    try:
        await client.write_gatt_char(
            request.characteristic_uuid,
            request.data,
            response=request.with_response,
        )
        return BleWriteResponse(success=True)
    except Exception as e:
        return BleWriteResponse(success=False, message=str(e))
```

**Tests:**
```python
def test_ble_read_characteristic():
    """Should read characteristic value."""
    stub.BleConnect(BleConnectRequest(address="AA:BB:CC:DD:EE:FF"))
    resp = stub.BleRead(BleReadRequest(
        address="AA:BB:CC:DD:EE:FF",
        characteristic_uuid="00002a19-0000-1000-8000-00805f9b34fb",  # Battery Level
    ))
    assert resp.success
    assert len(resp.data) > 0
```

---

### D9.5: Notifications

**Proto:**
```protobuf
rpc BleNotifications(BleNotificationsRequest) returns (stream BleNotification);
```

**Implementation:**
```python
async def BleNotifications(self, request, context):
    """Stream characteristic notifications."""
    client = self.connections.get(request.address)
    if not client:
        return

    queue = asyncio.Queue()

    def callback(sender, data):
        if context.is_active():
            queue.put_nowait((sender, data))

    # Enable notifications
    await client.start_notify(request.characteristic_uuid, callback)

    try:
        while context.is_active():
            try:
                sender, data = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield BleNotification(
                    characteristic_uuid=str(sender.uuid),
                    data=bytes(data),
                    timestamp_us=int(time.time() * 1_000_000),
                )
            except asyncio.TimeoutError:
                continue
    finally:
        await client.stop_notify(request.characteristic_uuid)
```

**Tests:**
```python
def test_ble_notifications():
    """Should receive characteristic notifications."""
    stub.BleConnect(BleConnectRequest(address="AA:BB:CC:DD:EE:FF"))

    notifications = []
    for notif in stub.BleNotifications(BleNotificationsRequest(
        address="AA:BB:CC:DD:EE:FF",
        characteristic_uuid="...",
    )):
        notifications.append(notif)
        if len(notifications) >= 3:
            break

    assert len(notifications) >= 3
```

---

## Dependencies

- `bleak>=0.20.0` - Cross-platform BLE library

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/handlers/ble.py` | Created | BleHandler |
| `src/providers/mtib.py` | Modified | Wire handler |
| `requirements.txt` | Modified | Add bleak |

---

## Completion Checklist

- [ ] BleScan implemented
- [ ] BleConnect/Disconnect implemented
- [ ] BleDiscoverServices implemented
- [ ] BleRead/Write implemented
- [ ] BleNotifications streaming implemented
- [ ] Async/await integration with gRPC
- [ ] Unit tests with mock
- [ ] Integration tests with BLE device
