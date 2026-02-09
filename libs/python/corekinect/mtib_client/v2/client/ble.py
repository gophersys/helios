from typing import Iterator, List, Optional, Tuple

from protocols.mtib_v2.mtib_v2_pb2 import (
    BleConnectRequest,
    BleDiscoverServicesRequest,
    BleDisconnectRequest,
    BleReadRequest,
    BleScanRequest,
    BleWriteRequest,
)

from ._base import BaseClient
from ..types.ble import (
    BleCharacteristic,
    BleConnection,
    BleDevice,
    BleNotification,
    BleService,
)


class BleMixin(BaseClient):
    """BLE central operations."""

    def ble_scan(
        self, duration_s: float = 5.0, active: bool = True
    ) -> Tuple[Optional[str], List[BleDevice]]:
        """Scan for BLE devices.

        Args:
            duration_s: Scan duration in seconds.
            active: Use active scanning (requests scan responses).

        Returns:
            (error, list[BleDevice]) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "BleScan", BleScanRequest(duration_s=duration_s, active=active)
            )
            if not resp.success:
                return resp.message, []
            devices = [
                BleDevice(
                    address=d.address,
                    name=d.name,
                    rssi=d.rssi,
                    advertising_data=d.advertising_data,
                    connectable=d.connectable,
                )
                for d in resp.devices
            ]
            return None, devices
        except Exception as e:
            return f"ble_scan error: {e}", []

    def ble_connect(self, address: str) -> Tuple[Optional[str], Optional[BleConnection]]:
        """Connect to a BLE peripheral.

        Args:
            address: BLE MAC address.

        Returns:
            (error, BleConnection) tuple. error is None on success.
        """
        try:
            resp = self._call("BleConnect", BleConnectRequest(address=address))
            if not resp.success:
                return resp.message, None
            return None, BleConnection(connection_id=resp.connection_id)
        except Exception as e:
            return f"ble_connect error: {e}", None

    def ble_disconnect(self, connection_id: str) -> Optional[str]:
        """Disconnect from a BLE peripheral.

        Args:
            connection_id: Active BLE connection ID.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "BleDisconnect", BleDisconnectRequest(connection_id=connection_id)
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"ble_disconnect error: {e}"

    def ble_discover_services(
        self, connection_id: str
    ) -> Tuple[Optional[str], List[BleService]]:
        """Discover GATT services and characteristics.

        Args:
            connection_id: Active BLE connection ID.

        Returns:
            (error, list[BleService]) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "BleDiscoverServices",
                BleDiscoverServicesRequest(connection_id=connection_id),
            )
            if not resp.success:
                return resp.message, []
            services = [
                BleService(
                    uuid=s.uuid,
                    characteristics=[
                        BleCharacteristic(uuid=c.uuid, properties=c.properties, handle=c.handle)
                        for c in s.characteristics
                    ],
                )
                for s in resp.services
            ]
            return None, services
        except Exception as e:
            return f"ble_discover_services error: {e}", []

    def ble_read(self, connection_id: str, handle: int) -> Tuple[Optional[str], bytes]:
        """Read a GATT characteristic.

        Args:
            connection_id: Active BLE connection ID.
            handle: Characteristic attribute handle.

        Returns:
            (error, data) tuple. error is None on success.
        """
        try:
            resp = self._call(
                "BleRead", BleReadRequest(connection_id=connection_id, handle=handle)
            )
            if not resp.success:
                return resp.message, b""
            return None, resp.data
        except Exception as e:
            return f"ble_read error: {e}", b""

    def ble_write(
        self, connection_id: str, handle: int, data: bytes, with_response: bool = True
    ) -> Optional[str]:
        """Write to a GATT characteristic.

        Args:
            connection_id: Active BLE connection ID.
            handle: Characteristic attribute handle.
            data: Data to write.
            with_response: Whether to request a write response.

        Returns:
            Error message string, or None on success.
        """
        try:
            resp = self._call(
                "BleWrite",
                BleWriteRequest(
                    connection_id=connection_id,
                    handle=handle,
                    data=data,
                    with_response=with_response,
                ),
            )
            if not resp.success:
                return resp.message
            return None
        except Exception as e:
            return f"ble_write error: {e}"

    def ble_notifications(
        self, address: str, timeout: float = None
    ) -> Iterator[BleNotification]:
        """Subscribe to BLE notifications from a peripheral.

        Args:
            address: BLE device address.
            timeout: Stream timeout in seconds.

        Yields:
            BleNotification objects for each received notification.
        """
        stream = self._server_stream(
            "BleNotifications", BleConnectRequest(address=address), timeout=timeout
        )
        for resp in stream:
            yield BleNotification(
                connection_id=resp.connection_id,
                handle=resp.handle,
                data=resp.data,
                timestamp_s=resp.timestamp.seconds if resp.timestamp else 0,
                timestamp_ns=resp.timestamp.nanos if resp.timestamp else 0,
            )
