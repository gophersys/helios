"""Request dataclasses for TestBench endpoints."""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class BenchCreateRequest:
    """Create a new test bench."""

    station_id: str
    name: str
    mtib_address: str
    dut_product: str
    dut_revision: str
    capabilities: List[str] = field(default_factory=list)
    fixture_design_id: Optional[str] = None
    profile_overrides: Optional[Dict[str, Any]] = None
    mtib_revision: Optional[str] = None
    dut_device_id: Optional[str] = None
    dut_snr: Optional[str] = None
    dut_imei: Optional[str] = None
    dut_iccids: List[str] = field(default_factory=list)
    jlink_app_serial: Optional[str] = None
    jlink_comms_serial: Optional[str] = None
    uart_app_path: Optional[str] = None
    uart_comms_path: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BenchCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        station_id = (data.get("stationId") or "").strip()
        if not station_id:
            return None, "stationId is required"

        name = (data.get("name") or "").strip()
        if not name:
            return None, "name is required"

        mtib_address = (data.get("mtibAddress") or "").strip()
        if not mtib_address:
            return None, "mtibAddress is required"

        dut_product = (data.get("dutProduct") or "").strip()
        if not dut_product:
            return None, "dutProduct is required"

        dut_revision = (data.get("dutRevision") or "").strip()
        if not dut_revision:
            return None, "dutRevision is required"

        capabilities = data.get("capabilities", [])
        if not isinstance(capabilities, list):
            return None, "capabilities must be an array"

        fixture_design_id = data.get("fixtureDesignId")
        if fixture_design_id:
            fixture_design_id = fixture_design_id.strip()

        profile_overrides = data.get("profileOverrides")
        if profile_overrides is not None and not isinstance(profile_overrides, dict):
            return None, "profileOverrides must be an object"

        mtib_revision = data.get("mtibRevision")
        if mtib_revision:
            mtib_revision = mtib_revision.strip()

        dut_device_id = data.get("dutDeviceId")
        if dut_device_id:
            dut_device_id = dut_device_id.strip().upper()

        dut_snr = data.get("dutSnr")
        if dut_snr:
            dut_snr = dut_snr.strip()

        dut_imei = data.get("dutImei")
        if dut_imei:
            dut_imei = dut_imei.strip()

        dut_iccids = data.get("dutIccids", [])
        if not isinstance(dut_iccids, list):
            return None, "dutIccids must be an array"

        jlink_app_serial = data.get("jlinkAppSerial")
        if jlink_app_serial:
            jlink_app_serial = jlink_app_serial.strip()

        jlink_comms_serial = data.get("jlinkCommsSerial")
        if jlink_comms_serial:
            jlink_comms_serial = jlink_comms_serial.strip()

        uart_app_path = data.get("uartAppPath")
        if uart_app_path:
            uart_app_path = uart_app_path.strip()

        uart_comms_path = data.get("uartCommsPath")
        if uart_comms_path:
            uart_comms_path = uart_comms_path.strip()

        metadata = data.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            return None, "metadata must be an object"

        return cls(
            station_id=station_id,
            name=name,
            mtib_address=mtib_address,
            dut_product=dut_product,
            dut_revision=dut_revision,
            capabilities=capabilities,
            fixture_design_id=fixture_design_id,
            profile_overrides=profile_overrides,
            mtib_revision=mtib_revision,
            dut_device_id=dut_device_id,
            dut_snr=dut_snr,
            dut_imei=dut_imei,
            dut_iccids=dut_iccids,
            jlink_app_serial=jlink_app_serial,
            jlink_comms_serial=jlink_comms_serial,
            uart_app_path=uart_app_path,
            uart_comms_path=uart_comms_path,
            metadata=metadata,
        ), None


@dataclass
class BenchUpdateRequest:
    """Update a test bench."""

    name: Optional[str] = None
    mtib_address: Optional[str] = None
    mtib_revision: Optional[str] = None
    capabilities: Optional[List[str]] = None
    fixture_design_id: Optional[str] = None
    profile_overrides: Optional[Dict[str, Any]] = None
    dut_device_id: Optional[str] = None
    dut_snr: Optional[str] = None
    dut_imei: Optional[str] = None
    dut_iccids: Optional[List[str]] = None
    jlink_app_serial: Optional[str] = None
    jlink_comms_serial: Optional[str] = None
    uart_app_path: Optional[str] = None
    uart_comms_path: Optional[str] = None
    status: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    # Track which fields were explicitly set
    _has_name: bool = field(default=False, repr=False)
    _has_mtib_address: bool = field(default=False, repr=False)
    _has_mtib_revision: bool = field(default=False, repr=False)
    _has_capabilities: bool = field(default=False, repr=False)
    _has_fixture_design_id: bool = field(default=False, repr=False)
    _has_profile_overrides: bool = field(default=False, repr=False)
    _has_dut_device_id: bool = field(default=False, repr=False)
    _has_dut_snr: bool = field(default=False, repr=False)
    _has_dut_imei: bool = field(default=False, repr=False)
    _has_dut_iccids: bool = field(default=False, repr=False)
    _has_jlink_app_serial: bool = field(default=False, repr=False)
    _has_jlink_comms_serial: bool = field(default=False, repr=False)
    _has_uart_app_path: bool = field(default=False, repr=False)
    _has_uart_comms_path: bool = field(default=False, repr=False)
    _has_status: bool = field(default=False, repr=False)
    _has_metadata: bool = field(default=False, repr=False)

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BenchUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        req = cls()

        if "name" in data:
            req._has_name = True
            req.name = (data["name"] or "").strip() or None

        if "mtibAddress" in data:
            req._has_mtib_address = True
            req.mtib_address = (data["mtibAddress"] or "").strip() or None

        if "mtibRevision" in data:
            req._has_mtib_revision = True
            req.mtib_revision = (data["mtibRevision"] or "").strip() or None

        if "capabilities" in data:
            req._has_capabilities = True
            if data["capabilities"] is not None and not isinstance(data["capabilities"], list):
                return None, "capabilities must be an array"
            req.capabilities = data["capabilities"]

        if "fixtureDesignId" in data:
            req._has_fixture_design_id = True
            req.fixture_design_id = (data["fixtureDesignId"] or "").strip() or None

        if "profileOverrides" in data:
            req._has_profile_overrides = True
            if data["profileOverrides"] is not None and not isinstance(data["profileOverrides"], dict):
                return None, "profileOverrides must be an object"
            req.profile_overrides = data["profileOverrides"]

        if "dutDeviceId" in data:
            req._has_dut_device_id = True
            val = (data["dutDeviceId"] or "").strip()
            req.dut_device_id = val.upper() if val else None

        if "dutSnr" in data:
            req._has_dut_snr = True
            req.dut_snr = (data["dutSnr"] or "").strip() or None

        if "dutImei" in data:
            req._has_dut_imei = True
            req.dut_imei = (data["dutImei"] or "").strip() or None

        if "dutIccids" in data:
            req._has_dut_iccids = True
            if data["dutIccids"] is not None and not isinstance(data["dutIccids"], list):
                return None, "dutIccids must be an array"
            req.dut_iccids = data["dutIccids"]

        if "jlinkAppSerial" in data:
            req._has_jlink_app_serial = True
            req.jlink_app_serial = (data["jlinkAppSerial"] or "").strip() or None

        if "jlinkCommsSerial" in data:
            req._has_jlink_comms_serial = True
            req.jlink_comms_serial = (data["jlinkCommsSerial"] or "").strip() or None

        if "uartAppPath" in data:
            req._has_uart_app_path = True
            req.uart_app_path = (data["uartAppPath"] or "").strip() or None

        if "uartCommsPath" in data:
            req._has_uart_comms_path = True
            req.uart_comms_path = (data["uartCommsPath"] or "").strip() or None

        if "status" in data:
            req._has_status = True
            status = (data["status"] or "").strip().upper()
            if status and status not in ("AVAILABLE", "LOCKED", "OFFLINE", "MAINTENANCE"):
                return None, "status must be one of: AVAILABLE, LOCKED, OFFLINE, MAINTENANCE"
            req.status = status or None

        if "metadata" in data:
            req._has_metadata = True
            if data["metadata"] is not None and not isinstance(data["metadata"], dict):
                return None, "metadata must be an object"
            req.metadata = data["metadata"]

        return req, None

    def to_update_data(self) -> Dict[str, Any]:
        """Return dict of fields to update (only those explicitly set)."""
        update = {}
        if self._has_name and self.name:
            update["name"] = self.name
        if self._has_mtib_address and self.mtib_address:
            update["mtibAddress"] = self.mtib_address
        if self._has_mtib_revision:
            update["mtibRevision"] = self.mtib_revision
        if self._has_capabilities:
            update["capabilities"] = self.capabilities or []
        if self._has_fixture_design_id:
            update["fixtureDesignId"] = self.fixture_design_id
        if self._has_profile_overrides:
            update["profileOverrides"] = self.profile_overrides
        if self._has_dut_device_id:
            update["dutDeviceId"] = self.dut_device_id
        if self._has_dut_snr:
            update["dutSnr"] = self.dut_snr
        if self._has_dut_imei:
            update["dutImei"] = self.dut_imei
        if self._has_dut_iccids:
            update["dutIccids"] = self.dut_iccids or []
        if self._has_jlink_app_serial:
            update["jlinkAppSerial"] = self.jlink_app_serial
        if self._has_jlink_comms_serial:
            update["jlinkCommsSerial"] = self.jlink_comms_serial
        if self._has_uart_app_path:
            update["uartAppPath"] = self.uart_app_path
        if self._has_uart_comms_path:
            update["uartCommsPath"] = self.uart_comms_path
        if self._has_status and self.status:
            update["status"] = self.status
        if self._has_metadata:
            update["metadata"] = self.metadata
        return update


@dataclass
class BenchLockRequest:
    """Lock a bench for a pipeline/job."""

    locked_by: str

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BenchLockRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        locked_by = (data.get("lockedBy") or "").strip()
        if not locked_by:
            return None, "lockedBy is required"

        return cls(locked_by=locked_by), None
