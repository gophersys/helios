"""Typed response models for the CoreCloud REST API.

All API responses are parsed into typed dataclasses instead of raw dicts.
Each model provides a ``from_api()`` classmethod for constructing from
the CoreCloud JSON response shape, and domain models provide ``to_api()``
for serialization back to the API format.

Hierarchy:
    Device Status
    ├── DeviceInfo          Search result for a single device
    ├── DeviceStatus        Full status snapshot for a device
    ├── BootInfo            Boot event details
    ├── PositionInfo        Position/GPS fix details
    ├── HwFailInfo          App hardware failure counters
    └── CommsHwFailInfo     Comms coprocessor failure counters

    Configuration
    └── GroundModeConfig    GroundModeConfigV2 read/write model

    FUOTA
    ├── FuotaPlan           FUOTA plan metadata
    ├── FuotaStage          Single stage within a plan
    ├── FuotaProgress       Delivery progress for a device
    ├── FuotaDeviceSettings Device FUOTA enrollment settings
    └── FuotaAssignResult   Result of device assignment operation

    Device Registration
    └── RegistrationResult  Result of device registration call
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from typing import Any, Dict, List, Optional


# ═══════════════════════════════════════════════════════════════════════════
# Device Status Models
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class BootInfo:
    """Boot event from ``/System/Devices/Status`` → ``bootInfo``."""

    record_id: int = 0
    time_of_boot: str = ""
    boot_reason: str = ""

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> BootInfo:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            record_id=data.get("recordId", 0),
            time_of_boot=data.get("timeOfBoot", ""),
            boot_reason=data.get("bootReason", ""),
        )

    def to_api(self) -> Dict[str, Any]:
        """Serialize to CoreCloud API JSON (camelCase keys)."""
        return {
            "recordId": self.record_id,
            "timeOfBoot": self.time_of_boot,
            "bootReason": self.boot_reason,
        }


@dataclass
class PositionInfo:
    """Position fix from ``/System/Devices/Status`` → ``positionInfo``."""

    record_id: int = 0
    time_of_fix: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    gps_altitude: float = 0.0
    horizontal_accuracy: int = 0
    vertical_accuracy: int = 0
    batt_percent: int = 0
    batt_voltage: float = 0.0
    update_reason: str = ""
    is_in_motion: bool = False
    num_sat: int = 0
    ground_speed: int = 0
    heading: int = 0
    temperature: float = 0.0
    on_charger: bool = False

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> PositionInfo:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            record_id=data.get("recordId", 0),
            time_of_fix=data.get("timeOfFix", ""),
            latitude=data.get("latitude", 0.0),
            longitude=data.get("longitude", 0.0),
            gps_altitude=data.get("gpsAltitude", 0.0),
            horizontal_accuracy=data.get("horizontalAccuracy", 0),
            vertical_accuracy=data.get("verticalAccuracy", 0),
            batt_percent=data.get("battPercent", 0),
            batt_voltage=data.get("battVoltage", 0.0),
            update_reason=data.get("updateReason", ""),
            is_in_motion=data.get("isInMotion", False),
            num_sat=data.get("numSat", 0),
            ground_speed=data.get("groundSpeed", 0),
            heading=data.get("heading", 0),
            temperature=data.get("temperature", 0.0),
            on_charger=data.get("onCharger", False),
        )

    def to_api(self) -> Dict[str, Any]:
        """Serialize to CoreCloud API JSON (camelCase keys)."""
        return {
            "recordId": self.record_id,
            "timeOfFix": self.time_of_fix,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "gpsAltitude": self.gps_altitude,
            "horizontalAccuracy": self.horizontal_accuracy,
            "verticalAccuracy": self.vertical_accuracy,
            "battPercent": self.batt_percent,
            "battVoltage": self.batt_voltage,
            "updateReason": self.update_reason,
            "isInMotion": self.is_in_motion,
            "numSat": self.num_sat,
            "groundSpeed": self.ground_speed,
            "heading": self.heading,
            "temperature": self.temperature,
            "onCharger": self.on_charger,
        }


@dataclass
class HwFailInfo:
    """App hardware failure info from ``/System/Devices/Status`` → ``appHwFailInfo``."""

    record_id: int = 0
    time_of_event: str = ""
    xlr_fails: int = 0
    alt_fails: int = 0
    gps_fails: int = 0
    bms_fails: int = 0
    ext_flash_fails: int = 0
    batt_charger_fails: int = 0
    ppg_fails: int = 0
    imu_fails: int = 0
    ir_fails: int = 0

    @property
    def has_failures(self) -> bool:
        """True if any failure counter is non-zero."""
        return any([
            self.xlr_fails, self.alt_fails, self.gps_fails,
            self.bms_fails, self.ext_flash_fails, self.batt_charger_fails,
            self.ppg_fails, self.imu_fails, self.ir_fails,
        ])

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> HwFailInfo:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            record_id=data.get("recordId", 0),
            time_of_event=data.get("timeOfEvent", ""),
            xlr_fails=data.get("xlrFails", 0),
            alt_fails=data.get("altFails", 0),
            gps_fails=data.get("gpsFails", 0),
            bms_fails=data.get("bmsFails", 0),
            ext_flash_fails=data.get("extFlashFails", 0),
            batt_charger_fails=data.get("battChargerFails", 0),
            ppg_fails=data.get("ppgFails", 0),
            imu_fails=data.get("imuFails", 0),
            ir_fails=data.get("irFails", 0),
        )

    def to_api(self) -> Dict[str, Any]:
        """Serialize to CoreCloud API JSON (camelCase keys)."""
        return {
            "recordId": self.record_id,
            "timeOfEvent": self.time_of_event,
            "xlrFails": self.xlr_fails,
            "altFails": self.alt_fails,
            "gpsFails": self.gps_fails,
            "bmsFails": self.bms_fails,
            "extFlashFails": self.ext_flash_fails,
            "battChargerFails": self.batt_charger_fails,
            "ppgFails": self.ppg_fails,
            "imuFails": self.imu_fails,
            "irFails": self.ir_fails,
        }


@dataclass
class CommsHwFailInfo:
    """Comms coprocessor failure info from ``/System/Devices/Status`` → ``commsHwFailInfo``."""

    record_id: int = 0
    time_of_event: str = ""
    sim_fails: int = 0
    lora_fails: int = 0
    ipc_fails: int = 0
    ext_flash_fails: int = 0
    sec_elem_fails: int = 0
    sat_modem_fails: int = 0

    @property
    def has_failures(self) -> bool:
        """True if any failure counter is non-zero."""
        return any([
            self.sim_fails, self.lora_fails, self.ipc_fails,
            self.ext_flash_fails, self.sec_elem_fails, self.sat_modem_fails,
        ])

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> CommsHwFailInfo:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            record_id=data.get("recordId", 0),
            time_of_event=data.get("timeOfEvent", ""),
            sim_fails=data.get("simFails", 0),
            lora_fails=data.get("loraFails", 0),
            ipc_fails=data.get("ipcFails", 0),
            ext_flash_fails=data.get("extFlashFails", 0),
            sec_elem_fails=data.get("secElemFails", 0),
            sat_modem_fails=data.get("satModemFails", 0),
        )

    def to_api(self) -> Dict[str, Any]:
        """Serialize to CoreCloud API JSON (camelCase keys)."""
        return {
            "recordId": self.record_id,
            "timeOfEvent": self.time_of_event,
            "simFails": self.sim_fails,
            "loraFails": self.lora_fails,
            "ipcFails": self.ipc_fails,
            "extFlashFails": self.ext_flash_fails,
            "secElemFails": self.sec_elem_fails,
            "satModemFails": self.sat_modem_fails,
        }


@dataclass
class DeviceStatus:
    """Full device status snapshot from ``/System/Devices/Status``.

    Contains boot, position, and hardware failure sections. Each section
    is optional since the API may return partial data for devices that
    haven't reported all message types.
    """

    device_id: str = ""
    boot_info: Optional[BootInfo] = None
    position_info: Optional[PositionInfo] = None
    app_hw_fail_info: Optional[HwFailInfo] = None
    comms_hw_fail_info: Optional[CommsHwFailInfo] = None

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> DeviceStatus:
        """Parse a single device entry from the Status API response.

        The API returns ``{"devices": [...]}``. This parses one element
        of that array.
        """
        if not data:
            return cls()

        boot_raw = data.get("bootInfo")
        pos_raw = data.get("positionInfo")
        app_hw_raw = data.get("appHwFailInfo")
        comms_hw_raw = data.get("commsHwFailInfo")

        return cls(
            device_id=data.get("deviceId", ""),
            boot_info=BootInfo.from_api(boot_raw) if boot_raw else None,
            position_info=PositionInfo.from_api(pos_raw) if pos_raw else None,
            app_hw_fail_info=HwFailInfo.from_api(app_hw_raw) if app_hw_raw else None,
            comms_hw_fail_info=CommsHwFailInfo.from_api(comms_hw_raw) if comms_hw_raw else None,
        )


@dataclass
class DeviceInfo:
    """Device search result from ``/System/Devices/Search``.

    Contains basic device registration metadata.
    """

    device_id: str = ""
    device_type: int = 0
    device_variant_id: int = 0
    is_active: bool = False

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> DeviceInfo:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            device_id=data.get("deviceId", ""),
            device_type=data.get("deviceType", 0),
            device_variant_id=data.get("deviceVariantId", 0),
            is_active=data.get("isActive", False),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Configuration Models
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class GroundModeConfig:
    """GroundModeConfigV2 — device GPS/motion timing configuration.

    Readable via ``POST /System/Devices/Configurations/GroundModeV2/Search``
    and writable via ``PUT /System/Devices/Configurations/GroundModeV2``.

    All time values are in their native units as returned by the API
    (minutes for heartbeat period, seconds for timeouts).
    """

    device_id: str = ""
    gps_heartbeat_period: int = 0
    continuous_motion_period: int = 0
    stop_motion_timeout: int = 0
    heartbeat_acquisition_timeout: int = 0
    motion_acquisition_timeout: int = 0
    motion_acquisition_on_time: int = 0
    motion_initial_acquisition_on_time: int = 0
    xlr_motion_threshold: int = 0
    xlr_motion_duration: int = 0
    start_motion_window_start: int = 0
    start_motion_window_end: int = 0

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> GroundModeConfig:
        """Parse from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            device_id=data.get("deviceId", ""),
            gps_heartbeat_period=data.get("gpsHeartbeatPeriod", 0),
            continuous_motion_period=data.get("continuousMotionPeriod", 0),
            stop_motion_timeout=data.get("stopMotionTimeout", 0),
            heartbeat_acquisition_timeout=data.get("heartbeatAcquisitionTimeout", 0),
            motion_acquisition_timeout=data.get("motionAcquisitionTimeout", 0),
            motion_acquisition_on_time=data.get("motionAcquisitionOnTime", 0),
            motion_initial_acquisition_on_time=data.get("motionInitialAcquisitionOnTime", 0),
            xlr_motion_threshold=data.get("xlrMotionThreshold", 0),
            xlr_motion_duration=data.get("xlrMotionDuration", 0),
            start_motion_window_start=data.get("startMotionWindowStart", 0),
            start_motion_window_end=data.get("startMotionWindowEnd", 0),
        )

    def to_api(self) -> Dict[str, Any]:
        """Serialize to CoreCloud API JSON (camelCase keys).

        Includes deviceId — required for PUT operations.
        """
        return {
            "deviceId": self.device_id,
            "gpsHeartbeatPeriod": self.gps_heartbeat_period,
            "continuousMotionPeriod": self.continuous_motion_period,
            "stopMotionTimeout": self.stop_motion_timeout,
            "heartbeatAcquisitionTimeout": self.heartbeat_acquisition_timeout,
            "motionAcquisitionTimeout": self.motion_acquisition_timeout,
            "motionAcquisitionOnTime": self.motion_acquisition_on_time,
            "motionInitialAcquisitionOnTime": self.motion_initial_acquisition_on_time,
            "xlrMotionThreshold": self.xlr_motion_threshold,
            "xlrMotionDuration": self.xlr_motion_duration,
            "startMotionWindowStart": self.start_motion_window_start,
            "startMotionWindowEnd": self.start_motion_window_end,
        }

    def with_updates(self, **kwargs: Any) -> GroundModeConfig:
        """Return a new config with the given fields updated.

        Uses dataclasses field names (snake_case), not API keys.

        Example:
            new_config = config.with_updates(gps_heartbeat_period=120)
        """
        current = {f.name: getattr(self, f.name) for f in fields(self)}
        current.update(kwargs)
        return GroundModeConfig(**current)


# ═══════════════════════════════════════════════════════════════════════════
# FUOTA Models
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class FuotaStage:
    """Single stage within a FUOTA plan."""

    targets: List[str] = field(default_factory=list)
    description: str = ""
    is_skippable: bool = False

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> FuotaStage:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            targets=data.get("targets", []),
            description=data.get("description", ""),
            is_skippable=data.get("isSkippable", False),
        )

    def to_api(self) -> Dict[str, Any]:
        """Serialize to CoreCloud API JSON (camelCase keys)."""
        return {
            "targets": self.targets,
            "description": self.description,
            "isSkippable": self.is_skippable,
        }


@dataclass
class FuotaPlan:
    """FUOTA plan metadata from ``/singleton/firmwareupdates/plans``."""

    plan_id: int = 0
    description: str = ""
    device_type_id: int = 0
    device_variant_id: int = 0
    stages: List[FuotaStage] = field(default_factory=list)

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> FuotaPlan:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        raw_stages = data.get("stages", [])
        return cls(
            plan_id=data.get("planId", 0),
            description=data.get("description", ""),
            device_type_id=data.get("deviceTypeId", 0),
            device_variant_id=data.get("deviceVariantId", 0),
            stages=[FuotaStage.from_api(s) for s in raw_stages],
        )


@dataclass
class FuotaProgress:
    """FUOTA delivery progress from ``/singleton/firmwareupdates/progress``."""

    device_id: str = ""
    version: str = ""
    percent_complete: int = 0
    pages_applied: int = 0
    total_pages: int = 0
    time_started: str = ""
    last_updated: str = ""

    @property
    def is_complete(self) -> bool:
        """True if delivery has reached 100%."""
        return self.percent_complete >= 100

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> FuotaProgress:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            device_id=data.get("deviceId", ""),
            version=data.get("version", ""),
            percent_complete=data.get("percentComplete", 0),
            pages_applied=data.get("pagesApplied", 0),
            total_pages=data.get("totalPages", 0),
            time_started=data.get("timeStarted", ""),
            last_updated=data.get("lastUpdated", ""),
        )


@dataclass
class FuotaDeviceSettings:
    """Device FUOTA enrollment from ``/singleton/firmwareupdates/settings/devices``."""

    device_id: str = ""
    plan_id: int = 0
    enable_fuota: bool = False
    max_stage: int = 0

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> FuotaDeviceSettings:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            device_id=data.get("deviceId", ""),
            plan_id=data.get("planId", 0),
            enable_fuota=data.get("enableFuota", False),
            max_stage=data.get("maxStage", 0),
        )


@dataclass
class FuotaAssignResult:
    """Result of a FUOTA device assignment operation."""

    num_devices_updated: int = 0

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> FuotaAssignResult:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            num_devices_updated=data.get("numDevicesUpdated", 0),
        )


# ═══════════════════════════════════════════════════════════════════════════
# Device Registration Models
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class RegistrationResult:
    """Result of ``POST /System/Devices/Register``."""

    registered_devices: List[str] = field(default_factory=list)
    already_registered: List[str] = field(default_factory=list)

    @property
    def any_newly_registered(self) -> bool:
        """True if at least one device was newly registered."""
        return len(self.registered_devices) > 0

    @classmethod
    def from_api(cls, data: Dict[str, Any]) -> RegistrationResult:
        """Construct from CoreCloud API JSON (camelCase keys)."""
        if not data:
            return cls()
        return cls(
            registered_devices=data.get("registeredDevices", []),
            already_registered=data.get("devicesAlreadyRegistered", []),
        )
