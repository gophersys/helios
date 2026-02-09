from dataclasses import dataclass, field
from typing import List


@dataclass
class BleDevice:
    """A discovered BLE device.

    Args:
        address: BLE MAC address.
        name: Device name from advertising data.
        rssi: Signal strength in dBm.
        advertising_data: Raw advertising data bytes.
        connectable: Whether the device accepts connections.
    """

    address: str
    name: str
    rssi: int
    advertising_data: bytes = b""
    connectable: bool = False


@dataclass
class BleCharacteristic:
    """A GATT characteristic.

    Args:
        uuid: Characteristic UUID.
        properties: Property flags (read, write, notify, etc.).
        handle: Attribute handle for read/write operations.
    """

    uuid: str
    properties: int
    handle: int


@dataclass
class BleService:
    """A GATT service.

    Args:
        uuid: Service UUID.
        characteristics: List of characteristics in this service.
    """

    uuid: str
    characteristics: List[BleCharacteristic] = field(default_factory=list)


@dataclass
class BleConnection:
    """An active BLE connection.

    Args:
        connection_id: Unique connection identifier.
    """

    connection_id: str


@dataclass
class BleNotification:
    """A BLE notification received from the peripheral.

    Args:
        connection_id: Connection that sent the notification.
        handle: Characteristic handle.
        data: Notification payload.
        timestamp_s: Timestamp seconds.
        timestamp_ns: Timestamp nanoseconds.
    """

    connection_id: str
    handle: int
    data: bytes
    timestamp_s: int = 0
    timestamp_ns: int = 0
