from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FixtureCreateRequest:
    name: str
    productId: str
    type: str  # MANUFACTURING or VALIDATION
    stationId: Optional[str] = None
    designId: Optional[str] = None
    description: Optional[str] = None
    metadata: Optional[dict] = None
    slots: Optional[List[dict]] = None  # [{slotIndex: 0, label: "Slot 1"}, ...]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FixtureCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        product_id = (data.get("productId") or "").strip()
        fixture_type = (data.get("type") or "").strip().upper()

        if not name:
            return None, "Name is required"
        if not product_id:
            return None, "Product ID is required"
        if fixture_type not in ("MANUFACTURING", "VALIDATION"):
            return None, "Type must be MANUFACTURING or VALIDATION"

        station_id = data.get("stationId")
        if station_id is not None:
            station_id = station_id.strip() or None

        design_id = data.get("designId")
        if design_id is not None:
            design_id = design_id.strip() or None

        description = data.get("description")
        metadata = data.get("metadata")
        slots = data.get("slots")
        if slots is not None:
            if not isinstance(slots, list):
                return None, "Slots must be an array"
            for i, s in enumerate(slots):
                if not isinstance(s, dict):
                    return None, f"Slot {i} must be an object"
                if "slotIndex" not in s:
                    return None, f"Slot {i} must have a slotIndex"

        return cls(
            name=name,
            productId=product_id,
            type=fixture_type,
            stationId=station_id,
            designId=design_id,
            description=description.strip() if description else None,
            metadata=metadata,
            slots=slots,
        ), None


@dataclass
class FixtureUpdateRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    metadata: Optional[dict] = None
    _has_description: bool = False
    _has_metadata: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FixtureUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                return None, "Name cannot be empty"

        description = data.get("description")
        has_description = "description" in data

        active = data.get("active")
        if active is not None and not isinstance(active, bool):
            return None, "Active must be a boolean"

        metadata = data.get("metadata")
        has_metadata = "metadata" in data

        if name is None and not has_description and active is None and not has_metadata:
            return None, "No fields to update"

        return cls(
            name=name,
            description=description.strip() if description else description,
            active=active,
            metadata=metadata,
            _has_description=has_description,
            _has_metadata=has_metadata,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_description:
            update_data["description"] = self.description
        if self.active is not None:
            update_data["active"] = self.active
        if self._has_metadata:
            update_data["metadata"] = self.metadata
        return update_data


@dataclass
class SlotCreateRequest:
    slotIndex: int
    label: Optional[str] = None
    # Hardware paths
    jlinkAppSerial: Optional[str] = None
    jlinkCommsSerial: Optional[str] = None
    uartAppPath: Optional[str] = None
    uartCommsPath: Optional[str] = None
    # DUT identity
    dutDeviceId: Optional[str] = None
    dutSnr: Optional[str] = None
    dutImei: Optional[str] = None
    dutIccids: Optional[List[str]] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["SlotCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        slot_index = data.get("slotIndex")
        if slot_index is None:
            return None, "slotIndex is required"
        if not isinstance(slot_index, int) or slot_index < 0:
            return None, "slotIndex must be a non-negative integer"

        label = data.get("label")

        # Hardware paths
        jlink_app = data.get("jlinkAppSerial")
        if jlink_app:
            jlink_app = jlink_app.strip()
        jlink_comms = data.get("jlinkCommsSerial")
        if jlink_comms:
            jlink_comms = jlink_comms.strip()
        uart_app = data.get("uartAppPath")
        if uart_app:
            uart_app = uart_app.strip()
        uart_comms = data.get("uartCommsPath")
        if uart_comms:
            uart_comms = uart_comms.strip()

        # DUT identity
        dut_device_id = data.get("dutDeviceId")
        if dut_device_id:
            dut_device_id = dut_device_id.strip().upper()
        dut_snr = data.get("dutSnr")
        if dut_snr:
            dut_snr = dut_snr.strip()
        dut_imei = data.get("dutImei")
        if dut_imei:
            dut_imei = dut_imei.strip()
        dut_iccids = data.get("dutIccids")
        if dut_iccids is not None and not isinstance(dut_iccids, list):
            return None, "dutIccids must be an array"

        return cls(
            slotIndex=slot_index,
            label=label.strip() if label else None,
            jlinkAppSerial=jlink_app,
            jlinkCommsSerial=jlink_comms,
            uartAppPath=uart_app,
            uartCommsPath=uart_comms,
            dutDeviceId=dut_device_id,
            dutSnr=dut_snr,
            dutImei=dut_imei,
            dutIccids=dut_iccids,
        ), None


@dataclass
class SlotUpdateRequest:
    label: Optional[str] = None
    active: Optional[bool] = None
    jlinkAppSerial: Optional[str] = None
    jlinkCommsSerial: Optional[str] = None
    uartAppPath: Optional[str] = None
    uartCommsPath: Optional[str] = None
    dutDeviceId: Optional[str] = None
    dutSnr: Optional[str] = None
    dutImei: Optional[str] = None
    dutIccids: Optional[List[str]] = None
    _has_label: bool = False
    _has_jlink_app: bool = False
    _has_jlink_comms: bool = False
    _has_uart_app: bool = False
    _has_uart_comms: bool = False
    _has_dut_device_id: bool = False
    _has_dut_snr: bool = False
    _has_dut_imei: bool = False
    _has_dut_iccids: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["SlotUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        req = cls()
        has_any = False

        if "label" in data:
            req._has_label = True
            req.label = data["label"].strip() if data["label"] else data["label"]
            has_any = True

        if "active" in data:
            req.active = data["active"]
            if req.active is not None and not isinstance(req.active, bool):
                return None, "Active must be a boolean"
            has_any = True

        # Hardware paths
        for field, attr, flag in [
            ("jlinkAppSerial", "jlinkAppSerial", "_has_jlink_app"),
            ("jlinkCommsSerial", "jlinkCommsSerial", "_has_jlink_comms"),
            ("uartAppPath", "uartAppPath", "_has_uart_app"),
            ("uartCommsPath", "uartCommsPath", "_has_uart_comms"),
        ]:
            if field in data:
                setattr(req, flag, True)
                val = data[field]
                setattr(req, attr, val.strip() if val else val)
                has_any = True

        # DUT identity
        if "dutDeviceId" in data:
            req._has_dut_device_id = True
            val = data["dutDeviceId"]
            req.dutDeviceId = val.strip().upper() if val else val
            has_any = True
        if "dutSnr" in data:
            req._has_dut_snr = True
            val = data["dutSnr"]
            req.dutSnr = val.strip() if val else val
            has_any = True
        if "dutImei" in data:
            req._has_dut_imei = True
            val = data["dutImei"]
            req.dutImei = val.strip() if val else val
            has_any = True
        if "dutIccids" in data:
            req._has_dut_iccids = True
            if data["dutIccids"] is not None and not isinstance(data["dutIccids"], list):
                return None, "dutIccids must be an array"
            req.dutIccids = data["dutIccids"]
            has_any = True

        if not has_any:
            return None, "No fields to update"

        return req, None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self._has_label:
            update_data["label"] = self.label
        if self.active is not None:
            update_data["active"] = self.active
        if self._has_jlink_app:
            update_data["jlinkAppSerial"] = self.jlinkAppSerial
        if self._has_jlink_comms:
            update_data["jlinkCommsSerial"] = self.jlinkCommsSerial
        if self._has_uart_app:
            update_data["uartAppPath"] = self.uartAppPath
        if self._has_uart_comms:
            update_data["uartCommsPath"] = self.uartCommsPath
        if self._has_dut_device_id:
            update_data["dutDeviceId"] = self.dutDeviceId
        if self._has_dut_snr:
            update_data["dutSnr"] = self.dutSnr
        if self._has_dut_imei:
            update_data["dutImei"] = self.dutImei
        if self._has_dut_iccids:
            update_data["dutIccids"] = self.dutIccids or []
        return update_data


@dataclass
class SlotAssignRequest:
    nodeId: Optional[str] = None  # null to unassign

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["SlotAssignRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        node_id = data.get("nodeId")
        if node_id is not None:
            node_id = node_id.strip()
            if not node_id:
                return None, "nodeId cannot be an empty string"

        return cls(nodeId=node_id), None


# ─── Bench types (merged from validation/benches/types.py) ───────────────────


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


# ─── Fixture Design types (merged from validation/designs/types.py) ──────────


@dataclass
class FixtureDesignCreateRequest:
    """POST /v2/fixtures/designs - Create a new fixture design."""

    name: str
    product: str
    revision: str
    capabilities: List[str]
    profile_template: Dict[str, Any]
    schematic_url: Optional[str] = None
    bom_url: Optional[str] = None
    assembly_guide: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FixtureDesignCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body required"

        name = (data.get("name") or "").strip()
        if not name:
            return None, "name is required"

        product = (data.get("product") or "").strip().lower()
        if not product:
            return None, "product is required"

        revision = (data.get("revision") or "").strip()
        if not revision:
            return None, "revision is required"

        capabilities = data.get("capabilities", [])
        if not isinstance(capabilities, list):
            return None, "capabilities must be an array"

        profile_template = data.get("profileTemplate", {})
        if not isinstance(profile_template, dict):
            return None, "profileTemplate must be an object"

        return cls(
            name=name,
            product=product,
            revision=revision,
            capabilities=[str(c).strip() for c in capabilities],
            profile_template=profile_template,
            schematic_url=data.get("schematicUrl"),
            bom_url=data.get("bomUrl"),
            assembly_guide=data.get("assemblyGuide"),
            notes=data.get("notes"),
        ), None


@dataclass
class FixtureDesignUpdateRequest:
    """PATCH /v2/fixtures/designs/<id> - Update a fixture design."""

    _has_name: bool = False
    _has_capabilities: bool = False
    _has_profile_template: bool = False
    _has_schematic_url: bool = False
    _has_bom_url: bool = False
    _has_assembly_guide: bool = False
    _has_notes: bool = False

    name: Optional[str] = None
    capabilities: Optional[List[str]] = None
    profile_template: Optional[Dict[str, Any]] = None
    schematic_url: Optional[str] = None
    bom_url: Optional[str] = None
    assembly_guide: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FixtureDesignUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body required"

        inst = cls()

        if "name" in data:
            inst._has_name = True
            inst.name = (data["name"] or "").strip() or None

        if "capabilities" in data:
            inst._has_capabilities = True
            caps = data["capabilities"]
            if caps is not None and not isinstance(caps, list):
                return None, "capabilities must be an array"
            inst.capabilities = [str(c).strip() for c in caps] if caps else []

        if "profileTemplate" in data:
            inst._has_profile_template = True
            tpl = data["profileTemplate"]
            if tpl is not None and not isinstance(tpl, dict):
                return None, "profileTemplate must be an object"
            inst.profile_template = tpl

        if "schematicUrl" in data:
            inst._has_schematic_url = True
            inst.schematic_url = data["schematicUrl"]

        if "bomUrl" in data:
            inst._has_bom_url = True
            inst.bom_url = data["bomUrl"]

        if "assemblyGuide" in data:
            inst._has_assembly_guide = True
            inst.assembly_guide = data["assemblyGuide"]

        if "notes" in data:
            inst._has_notes = True
            inst.notes = data["notes"]

        return inst, None

    def to_update_data(self) -> Dict[str, Any]:
        """Return dict of fields to update in DB."""
        data = {}
        if self._has_name and self.name:
            data["name"] = self.name
        if self._has_capabilities:
            data["capabilities"] = self.capabilities
        if self._has_profile_template:
            data["profileTemplate"] = self.profile_template
        if self._has_schematic_url:
            data["schematicUrl"] = self.schematic_url
        if self._has_bom_url:
            data["bomUrl"] = self.bom_url
        if self._has_assembly_guide:
            data["assemblyGuide"] = self.assembly_guide
        if self._has_notes:
            data["notes"] = self.notes
        return data
