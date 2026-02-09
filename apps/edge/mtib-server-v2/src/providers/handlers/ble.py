"""BLE handler for V2 protocol."""

import uuid
from typing import TYPE_CHECKING, Dict, Iterator

from corekinect.utils import Logger
from src.shared.types import (
    BleCharacteristic,
    BleConnectRequest,
    BleConnectResponse,
    BleDevice,
    BleDisconnectRequest,
    BleDiscoverServicesRequest,
    BleDiscoverServicesResponse,
    BleNotificationResponse,
    BleReadRequest,
    BleReadResponse,
    BleScanRequest,
    BleScanResponse,
    BleService,
    BleWriteRequest,
    Response,
    Timestamp,
)

if TYPE_CHECKING:
    from src.hardware import HardwareContext


class BleHandler:
    """Handles BLE central RPCs."""

    def __init__(self, logger: Logger, hardware: "HardwareContext"):
        self.logger = logger
        self.hardware = hardware
        self._connections: Dict[str, object] = {}  # connection_id -> bleak client

    def scan(self, request: BleScanRequest, context) -> BleScanResponse:
        """Scan for BLE devices."""
        try:
            import asyncio
            from bleak import BleakScanner

            async def do_scan():
                scanner = BleakScanner()
                devices = await scanner.discover(timeout=request.duration_s or 5.0)
                return devices

            loop = asyncio.new_event_loop()
            try:
                discovered = loop.run_until_complete(do_scan())
            finally:
                loop.close()

            ble_devices = []
            for d in discovered:
                ble_devices.append(BleDevice(
                    address=d.address,
                    name=d.name or "",
                    rssi=d.rssi if hasattr(d, "rssi") else 0,
                    advertising_data=b"",
                    connectable=True,
                ))

            return BleScanResponse(success=True, message="", devices=ble_devices)

        except ImportError:
            return BleScanResponse(success=False, message="bleak not available", devices=[])
        except Exception as e:
            return BleScanResponse(success=False, message=str(e), devices=[])

    def connect(self, request: BleConnectRequest, context) -> BleConnectResponse:
        """Connect to a BLE device."""
        try:
            import asyncio
            from bleak import BleakClient

            connection_id = str(uuid.uuid4())

            async def do_connect():
                client = BleakClient(request.address)
                await client.connect()
                return client

            loop = asyncio.new_event_loop()
            try:
                client = loop.run_until_complete(do_connect())
            finally:
                loop.close()

            self._connections[connection_id] = client
            self.logger.info(f"BLE connected: {request.address} -> {connection_id}")
            return BleConnectResponse(success=True, message="", connection_id=connection_id)

        except ImportError:
            return BleConnectResponse(success=False, message="bleak not available", connection_id="")
        except Exception as e:
            return BleConnectResponse(success=False, message=str(e), connection_id="")

    def disconnect(self, request: BleDisconnectRequest, context) -> Response:
        """Disconnect from a BLE device."""
        client = self._connections.pop(request.connection_id, None)
        if client is None:
            return Response(success=False, message=f"Unknown connection: {request.connection_id}")

        try:
            import asyncio

            async def do_disconnect():
                await client.disconnect()

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(do_disconnect())
            finally:
                loop.close()

            return Response(success=True, message="Disconnected")
        except Exception as e:
            return Response(success=False, message=str(e))

    def discover_services(self, request: BleDiscoverServicesRequest, context) -> BleDiscoverServicesResponse:
        """Discover GATT services on a connected device."""
        client = self._connections.get(request.connection_id)
        if client is None:
            return BleDiscoverServicesResponse(
                success=False,
                message=f"Unknown connection: {request.connection_id}",
            )

        try:
            import asyncio

            async def do_discover():
                return client.services

            loop = asyncio.new_event_loop()
            try:
                services = loop.run_until_complete(do_discover())
            finally:
                loop.close()

            proto_services = []
            for svc in services:
                chars = []
                for char in svc.characteristics:
                    chars.append(BleCharacteristic(
                        uuid=str(char.uuid),
                        properties=0,  # TODO: map properties
                        handle=char.handle,
                    ))
                proto_services.append(BleService(
                    uuid=str(svc.uuid),
                    characteristics=chars,
                ))

            return BleDiscoverServicesResponse(success=True, message="", services=proto_services)
        except Exception as e:
            return BleDiscoverServicesResponse(success=False, message=str(e))

    def read(self, request: BleReadRequest, context) -> BleReadResponse:
        """Read a GATT characteristic."""
        client = self._connections.get(request.connection_id)
        if client is None:
            return BleReadResponse(success=False, message=f"Unknown connection: {request.connection_id}")

        try:
            import asyncio

            async def do_read():
                return await client.read_gatt_char(request.handle)

            loop = asyncio.new_event_loop()
            try:
                data = loop.run_until_complete(do_read())
            finally:
                loop.close()

            return BleReadResponse(success=True, message="", data=bytes(data))
        except Exception as e:
            return BleReadResponse(success=False, message=str(e))

    def write(self, request: BleWriteRequest, context) -> Response:
        """Write a GATT characteristic."""
        client = self._connections.get(request.connection_id)
        if client is None:
            return Response(success=False, message=f"Unknown connection: {request.connection_id}")

        try:
            import asyncio

            async def do_write():
                await client.write_gatt_char(
                    request.handle,
                    request.data,
                    response=request.with_response,
                )

            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(do_write())
            finally:
                loop.close()

            return Response(success=True, message="Written")
        except Exception as e:
            return Response(success=False, message=str(e))

    def notifications(self, request: BleConnectRequest, context) -> Iterator[BleNotificationResponse]:
        """Server-streaming BLE notifications."""
        # This uses BleConnectRequest (address) as per proto definition
        # First connect, then subscribe
        loop = None
        thread = None
        try:
            import asyncio
            import queue
            import threading
            import time
            from bleak import BleakClient

            notification_queue: queue.Queue = queue.Queue()

            async def notification_handler(sender, data):
                notification_queue.put((sender, data))

            async def run_notifications():
                async with BleakClient(request.address) as client:
                    # Subscribe to all notify-capable characteristics
                    for service in client.services:
                        for char in service.characteristics:
                            if "notify" in char.properties:
                                await client.start_notify(char, notification_handler)

                    # Wait until context is cancelled
                    while context.is_active():
                        await asyncio.sleep(0.01)

            loop = asyncio.new_event_loop()
            thread = threading.Thread(target=loop.run_until_complete, args=(run_notifications(),), daemon=True)
            thread.start()

            while context.is_active():
                try:
                    sender, data = notification_queue.get(timeout=0.1)
                    now = time.time()
                    yield BleNotificationResponse(
                        connection_id="",
                        handle=sender if isinstance(sender, int) else 0,
                        data=bytes(data),
                        timestamp=Timestamp(seconds=int(now), nanos=int((now % 1) * 1e9)),
                    )
                except queue.Empty:
                    continue

        except ImportError:
            self.logger.error("bleak not available for BLE notifications")
        except Exception as e:
            self.logger.error(f"BLE notification error: {e}")
        finally:
            if loop is not None:
                loop.call_soon_threadsafe(loop.stop)
            if thread is not None:
                thread.join(timeout=5.0)
            if loop is not None:
                loop.close()
