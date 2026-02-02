# Phase 7: Bus Masters

**Status:** ⬜ TODO
**Priority:** P2
**Dependencies:** Phase 2

---

## Objectives

1. Implement I2C master interface for testing I2C slave devices
2. Implement SPI master interface for testing SPI slave devices
3. Implement CAN bus interface for automotive testing
4. Use iMX8 peripheral interfaces via sysfs/device files

---

## Deliverables

### D7.1: I2C Master

**Proto:**
```protobuf
rpc I2cConfig(I2cConfigRequest) returns (I2cConfigResponse);
rpc I2cTransfer(I2cTransferRequest) returns (I2cTransferResponse);
rpc I2cScan(I2cScanRequest) returns (I2cScanResponse);
```

**Implementation:**
```python
class I2cHandler:
    def __init__(self, logger):
        self.logger = logger
        self.buses: Dict[int, smbus2.SMBus] = {}

    def I2cConfig(self, request, context) -> I2cConfigResponse:
        """Configure I2C bus."""
        bus_num = request.bus or 1
        if bus_num not in self.buses:
            self.buses[bus_num] = smbus2.SMBus(bus_num)
        return I2cConfigResponse(success=True, bus=bus_num)

    def I2cTransfer(self, request, context) -> I2cTransferResponse:
        """Perform I2C read/write transfer."""
        bus = self.buses.get(request.bus, smbus2.SMBus(request.bus))

        results = []
        for msg in request.messages:
            if msg.read:
                data = bus.read_i2c_block_data(msg.address, msg.register, msg.length)
                results.append(I2cMessage(data=bytes(data)))
            else:
                bus.write_i2c_block_data(msg.address, msg.register, list(msg.data))
                results.append(I2cMessage())

        return I2cTransferResponse(success=True, messages=results)

    def I2cScan(self, request, context) -> I2cScanResponse:
        """Scan I2C bus for devices."""
        bus = self.buses.get(request.bus, smbus2.SMBus(request.bus))

        found = []
        for addr in range(0x08, 0x78):
            try:
                bus.read_byte(addr)
                found.append(addr)
            except OSError:
                pass

        return I2cScanResponse(success=True, addresses=found)
```

**Tests:**
```python
def test_i2c_scan_finds_devices():
    """I2cScan should find devices on bus."""
    response = stub.I2cScan(I2cScanRequest(bus=1))
    assert response.success
    # Should find at least MCP4017, INA219, etc.
    assert 0x2F in response.addresses  # MCP4017

def test_i2c_read_write():
    """Should read and write I2C device."""
    # Write then read back
    stub.I2cTransfer(I2cTransferRequest(
        bus=1,
        messages=[
            I2cMessage(address=0x2F, write=True, data=b'\x40'),
            I2cMessage(address=0x2F, read=True, length=1),
        ],
    ))
```

---

### D7.2: SPI Master

**Proto:**
```protobuf
rpc SpiConfig(SpiConfigRequest) returns (SpiConfigResponse);
rpc SpiTransfer(SpiTransferRequest) returns (SpiTransferResponse);
```

**Implementation:**
```python
class SpiHandler:
    def __init__(self, logger):
        self.logger = logger
        self.devices: Dict[str, spidev.SpiDev] = {}

    def SpiConfig(self, request, context) -> SpiConfigResponse:
        """Configure SPI device."""
        device_path = f"/dev/spidev{request.bus}.{request.device}"

        spi = spidev.SpiDev()
        spi.open(request.bus, request.device)
        spi.max_speed_hz = request.speed_hz or 1_000_000
        spi.mode = request.mode or 0
        spi.bits_per_word = request.bits_per_word or 8

        self.devices[device_path] = spi
        return SpiConfigResponse(success=True, device=device_path)

    def SpiTransfer(self, request, context) -> SpiTransferResponse:
        """Perform SPI transfer (simultaneous read/write)."""
        spi = self.devices.get(request.device)
        if not spi:
            return SpiTransferResponse(success=False, message="Device not configured")

        # Full-duplex transfer
        rx_data = spi.xfer2(list(request.tx_data))

        return SpiTransferResponse(success=True, rx_data=bytes(rx_data))
```

**Tests:**
```python
def test_spi_loopback():
    """SPI loopback test (MOSI connected to MISO)."""
    stub.SpiConfig(SpiConfigRequest(bus=0, device=0, speed_hz=1_000_000))
    response = stub.SpiTransfer(SpiTransferRequest(
        device="/dev/spidev0.0",
        tx_data=b'\xAA\x55\xDE\xAD',
    ))
    assert response.rx_data == b'\xAA\x55\xDE\xAD'
```

---

### D7.3: CAN Bus

**Proto:**
```protobuf
rpc CanConfig(CanConfigRequest) returns (CanConfigResponse);
rpc CanSend(CanSendRequest) returns (CanSendResponse);
rpc CanSetFilter(CanSetFilterRequest) returns (CanSetFilterResponse);
rpc CanReceive(CanReceiveRequest) returns (stream CanFrame);
```

**Implementation:**
```python
import can

class CanHandler:
    def __init__(self, logger):
        self.logger = logger
        self.buses: Dict[str, can.Bus] = {}
        self.filters: Dict[str, List[dict]] = {}

    def CanConfig(self, request, context) -> CanConfigResponse:
        """Configure CAN interface."""
        interface = request.interface or "can0"

        # Configure bitrate via ip link (requires root)
        os.system(f"ip link set {interface} down")
        os.system(f"ip link set {interface} type can bitrate {request.bitrate}")
        os.system(f"ip link set {interface} up")

        bus = can.Bus(channel=interface, bustype='socketcan')
        self.buses[interface] = bus

        return CanConfigResponse(success=True, interface=interface)

    def CanSend(self, request, context) -> CanSendResponse:
        """Send CAN frame."""
        bus = self.buses.get(request.interface)
        if not bus:
            return CanSendResponse(success=False, message="Interface not configured")

        msg = can.Message(
            arbitration_id=request.id,
            data=request.data,
            is_extended_id=request.extended,
        )
        bus.send(msg)

        return CanSendResponse(success=True)

    def CanReceive(self, request, context):
        """Stream received CAN frames."""
        bus = self.buses.get(request.interface)
        if not bus:
            return

        while context.is_active():
            msg = bus.recv(timeout=0.1)
            if msg:
                yield CanFrame(
                    id=msg.arbitration_id,
                    data=bytes(msg.data),
                    extended=msg.is_extended_id,
                    timestamp_us=int(msg.timestamp * 1_000_000),
                )

    def CanSetFilter(self, request, context) -> CanSetFilterResponse:
        """Set CAN receive filters."""
        bus = self.buses.get(request.interface)
        if not bus:
            return CanSetFilterResponse(success=False)

        filters = [
            {"can_id": f.id, "can_mask": f.mask, "extended": f.extended}
            for f in request.filters
        ]
        bus.set_filters(filters)

        return CanSetFilterResponse(success=True)
```

**Tests:**
```python
def test_can_send_receive():
    """CAN send/receive loopback test."""
    stub.CanConfig(CanConfigRequest(interface="vcan0", bitrate=500000))

    # Start receiver
    frames = []
    def receiver():
        for frame in stub.CanReceive(CanReceiveRequest(interface="vcan0")):
            frames.append(frame)
            if len(frames) >= 1:
                break

    thread = threading.Thread(target=receiver)
    thread.start()

    # Send frame
    stub.CanSend(CanSendRequest(
        interface="vcan0",
        id=0x123,
        data=b'\x01\x02\x03\x04',
    ))

    thread.join(timeout=1)
    assert len(frames) == 1
    assert frames[0].id == 0x123
```

---

## Dependencies

- `smbus2>=0.4.0` - I2C access
- `spidev>=3.5` - SPI access
- `python-can>=4.0.0` - CAN bus access

---

## Files Changed

| File | Change Type | Description |
|------|-------------|-------------|
| `src/providers/handlers/i2c.py` | Created | I2cHandler |
| `src/providers/handlers/spi.py` | Created | SpiHandler |
| `src/providers/handlers/can.py` | Created | CanHandler |
| `src/providers/mtib.py` | Modified | Wire handlers |
| `requirements.txt` | Modified | Add dependencies |

---

## Completion Checklist

- [ ] I2cConfig/Transfer/Scan implemented
- [ ] SpiConfig/Transfer implemented
- [ ] CanConfig/Send/SetFilter/Receive implemented
- [ ] I2C multi-message transfers
- [ ] SPI full-duplex working
- [ ] CAN frame streaming
- [ ] Unit tests passing
- [ ] Integration tests with real peripherals
