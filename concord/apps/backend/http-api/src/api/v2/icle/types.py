from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from database import Json


@dataclass
class PowerReading:
    """Structure for power readings from ICLE device"""

    channel: int
    voltage_mv: float
    current_ma: float
    power_mw: float


@dataclass
class HeartbeatRequest:
    """Request structure for ICLE device heartbeat"""

    device_id: str
    firmware_version: str
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    status: str = "online"
    uptime_seconds: Optional[int] = None
    free_heap_bytes: Optional[int] = None
    wifi_rssi: Optional[int] = None
    sd_card_free_mb: Optional[int] = None
    current_log_file: Optional[str] = None
    power_readings: Optional[List["PowerReading"]] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["HeartbeatRequest"], Optional[str]]:
        """Parse JSON data into request object with validation"""
        if not data:
            return None, "Request body must contain JSON data"

        device_id = (data.get("device_id") or data.get("deviceId") or "").strip()
        if not device_id:
            return None, "Field 'device_id' is required"

        firmware_version = (data.get("firmware_version") or data.get("firmwareVersion") or "").strip()
        if not firmware_version:
            return None, "Field 'firmware_version' is required"

        # Parse optional fields
        ip_address = (data.get("ip_address") or data.get("ipAddress") or "").strip() or None
        mac_address = (data.get("mac_address") or data.get("macAddress") or "").strip() or None
        status = (data.get("status") or "online").strip().lower()

        # Validate status
        valid_statuses = ["online", "offline", "logging", "config", "boot", "ota"]
        if status not in valid_statuses:
            return None, f"Invalid status '{status}'. Valid values: {', '.join(valid_statuses)}"

        uptime_seconds = data.get("uptime_seconds") or data.get("uptimeSeconds")
        if uptime_seconds is not None:
            if not isinstance(uptime_seconds, (int, float)):
                return None, "Field 'uptime_seconds' must be a number"
            uptime_seconds = int(uptime_seconds)

        free_heap_bytes = data.get("free_heap_bytes") or data.get("freeHeapBytes")
        if free_heap_bytes is not None:
            if not isinstance(free_heap_bytes, (int, float)):
                return None, "Field 'free_heap_bytes' must be a number"
            free_heap_bytes = int(free_heap_bytes)

        wifi_rssi = data.get("wifi_rssi") or data.get("wifiRssi")
        if wifi_rssi is not None:
            if not isinstance(wifi_rssi, (int, float)):
                return None, "Field 'wifi_rssi' must be a number"
            wifi_rssi = int(wifi_rssi)

        sd_card_free_mb = data.get("sd_card_free_mb") or data.get("sdCardFreeMb")
        if sd_card_free_mb is not None:
            if not isinstance(sd_card_free_mb, (int, float)):
                return None, "Field 'sd_card_free_mb' must be a number"
            sd_card_free_mb = int(sd_card_free_mb)

        current_log_file = (data.get("current_log_file") or data.get("currentLogFile") or "").strip() or None

        # Parse power readings
        power_readings_data = data.get("power_readings") or data.get("powerReadings")
        power_readings = None
        if power_readings_data:
            if not isinstance(power_readings_data, list):
                return None, "Field 'power_readings' must be a list"
            power_readings = []
            for i, reading in enumerate(power_readings_data):
                if not isinstance(reading, dict):
                    return None, f"Power reading at index {i} must be an object"
                try:
                    pr = PowerReading(
                        channel=int(reading.get("channel", 0)),
                        voltage_mv=float(reading.get("voltage_mv") or reading.get("voltageMv") or 0),
                        current_ma=float(reading.get("current_ma") or reading.get("currentMa") or 0),
                        power_mw=float(reading.get("power_mw") or reading.get("powerMw") or 0),
                    )
                    power_readings.append(pr)
                except (ValueError, TypeError) as e:
                    return None, f"Invalid power reading at index {i}: {e}"

        return cls(
            device_id=device_id,
            firmware_version=firmware_version,
            ip_address=ip_address,
            mac_address=mac_address,
            status=status,
            uptime_seconds=uptime_seconds,
            free_heap_bytes=free_heap_bytes,
            wifi_rssi=wifi_rssi,
            sd_card_free_mb=sd_card_free_mb,
            current_log_file=current_log_file,
            power_readings=power_readings,
        ), None

    def to_status_data(self) -> Dict[str, Any]:
        """Convert to lastStatusData JSON format"""
        data: Dict[str, Any] = {
            "firmwareVersion": self.firmware_version,
        }
        if self.uptime_seconds is not None:
            data["uptimeSeconds"] = self.uptime_seconds
        if self.free_heap_bytes is not None:
            data["freeHeapBytes"] = self.free_heap_bytes
        if self.wifi_rssi is not None:
            data["wifiRssi"] = self.wifi_rssi
        if self.sd_card_free_mb is not None:
            data["sdCardFreeMb"] = self.sd_card_free_mb
        if self.current_log_file:
            data["currentLogFile"] = self.current_log_file
        if self.power_readings:
            data["powerReadings"] = [
                {
                    "channel": pr.channel,
                    "voltageMv": pr.voltage_mv,
                    "currentMa": pr.current_ma,
                    "powerMw": pr.power_mw,
                }
                for pr in self.power_readings
            ]
        return data


@dataclass
class DeviceUpdateRequest:
    """Request structure for updating an ICLE device"""

    name: Optional[str] = None
    registered: Optional[bool] = None
    pending_config: Optional[Dict[str, Any]] = None

    _has_name: bool = False
    _has_registered: bool = False
    _has_pending_config: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["DeviceUpdateRequest"], Optional[str]]:
        """Parse JSON data into request object with validation"""
        if not data:
            return None, "Request body must contain JSON data"

        req = cls()

        if "name" in data:
            req._has_name = True
            name = data.get("name")
            if name is not None:
                name = str(name).strip()
                if len(name) > 255:
                    return None, "Field 'name' must be 255 characters or less"
            req.name = name if name else None

        if "registered" in data:
            req._has_registered = True
            registered = data.get("registered")
            if registered is not None and not isinstance(registered, bool):
                return None, "Field 'registered' must be a boolean"
            req.registered = registered

        if "pendingConfig" in data or "pending_config" in data:
            req._has_pending_config = True
            pending_config = data.get("pendingConfig") or data.get("pending_config")
            if pending_config is not None and not isinstance(pending_config, dict):
                return None, "Field 'pendingConfig' must be an object"
            req.pending_config = pending_config

        return req, None

    def to_update_data(self) -> Dict[str, Any]:
        """Convert to Prisma update data dict"""
        data: Dict[str, Any] = {}
        if self._has_name:
            data["name"] = self.name
        if self._has_registered:
            data["registered"] = self.registered
        if self._has_pending_config:
            data["pendingConfig"] = Json(self.pending_config) if self.pending_config else None
        return data


@dataclass
class ConfigPushRequest:
    """Request structure for pushing config to an ICLE device"""

    config: Dict[str, Any]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ConfigPushRequest"], Optional[str]]:
        """Parse JSON data into request object with validation"""
        if not data:
            return None, "Request body must contain JSON data"

        config = data.get("config")
        if config is None:
            return None, "Field 'config' is required"
        if not isinstance(config, dict):
            return None, "Field 'config' must be an object"

        return cls(config=config), None


@dataclass
class OtaTriggerRequest:
    """Request structure for triggering OTA update on an ICLE device"""

    url: str
    version: str
    checksum: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["OtaTriggerRequest"], Optional[str]]:
        """Parse JSON data into request object with validation"""
        if not data:
            return None, "Request body must contain JSON data"

        url = (data.get("url") or "").strip()
        if not url:
            return None, "Field 'url' is required"

        # Basic URL validation
        if not url.startswith(("http://", "https://")):
            return None, "Field 'url' must be a valid HTTP/HTTPS URL"

        version = (data.get("version") or "").strip()
        if not version:
            return None, "Field 'version' is required"

        checksum = (data.get("checksum") or "").strip() or None

        return cls(url=url, version=version, checksum=checksum), None
