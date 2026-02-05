from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from .shared import SUPPORTED_CHIPSETS, SUPPORTED_SOCS


@dataclass
class ProductCreateRequest:
    name: str
    description: Optional[str] = None
    active: bool = True

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ProductCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        description = data.get("description")
        active = data.get("active", True)

        if not name:
            return None, "Name is required"
        if not isinstance(active, bool):
            return None, "Active must be a boolean"

        return cls(
            name=name,
            description=description.strip() if description else None,
            active=active,
        ), None


@dataclass
class ProductUpdateRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    _has_description: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ProductUpdateRequest"], Optional[str]]:
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

        if name is None and not has_description and active is None:
            return None, "No fields to update"

        return cls(
            name=name,
            description=description.strip() if description else description,
            active=active,
            _has_description=has_description,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_description:
            update_data["description"] = self.description
        if self.active is not None:
            update_data["active"] = self.active
        return update_data


@dataclass
class BoardRevisionCreateRequest:
    version: str
    chipsets: list = None
    status: str = "ACTIVE"
    notes: Optional[str] = None

    def __post_init__(self):
        if self.chipsets is None:
            self.chipsets = []

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BoardRevisionCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        version = (data.get("version") or "").strip()
        chipsets = data.get("chipsets", [])
        status = (data.get("status") or "ACTIVE").strip()
        notes = data.get("notes")

        if not version:
            return None, "Version is required"
        if not isinstance(chipsets, list):
            return None, "Chipsets must be an array of strings"
        chipsets = [c.strip() for c in chipsets if isinstance(c, str) and c.strip()]
        invalid = [c for c in chipsets if c not in SUPPORTED_SOCS]
        if invalid:
            return None, f"Unsupported SoC(s): {', '.join(invalid)}. Supported: {', '.join(SUPPORTED_SOCS)}"
        if status not in ("ACTIVE", "DEPRECATED", "EOL"):
            return None, "Status must be ACTIVE, DEPRECATED, or EOL"

        return cls(
            version=version,
            chipsets=chipsets,
            status=status,
            notes=notes.strip() if notes else None,
        ), None


@dataclass
class BoardRevisionUpdateRequest:
    version: Optional[str] = None
    chipsets: Optional[list] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    _has_chipsets: bool = False
    _has_notes: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BoardRevisionUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        version = data.get("version")
        if version is not None:
            version = version.strip()
            if not version:
                return None, "Version cannot be empty"
        chipsets = data.get("chipsets")
        has_chipsets = "chipsets" in data
        if has_chipsets:
            if not isinstance(chipsets, list):
                return None, "Chipsets must be an array of strings"
            chipsets = [c.strip() for c in chipsets if isinstance(c, str) and c.strip()]
            invalid = [c for c in chipsets if c not in SUPPORTED_SOCS]
            if invalid:
                return None, f"Unsupported SoC(s): {', '.join(invalid)}. Supported: {', '.join(SUPPORTED_SOCS)}"
        status = data.get("status")
        if status is not None:
            status = status.strip()
            if status not in ("ACTIVE", "DEPRECATED", "EOL"):
                return None, "Status must be ACTIVE, DEPRECATED, or EOL"
        notes = data.get("notes")
        has_notes = "notes" in data

        if version is None and status is None and not has_chipsets and not has_notes:
            return None, "No fields to update"

        return cls(
            version=version,
            chipsets=chipsets,
            status=status,
            notes=notes.strip() if notes else notes,
            _has_chipsets=has_chipsets,
            _has_notes=has_notes,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.version is not None:
            update_data["version"] = self.version
        if self._has_chipsets:
            update_data["chipsets"] = self.chipsets
        if self.status is not None:
            update_data["status"] = self.status
        if self._has_notes:
            update_data["notes"] = self.notes
        return update_data


@dataclass
class FirmwareAppCreateRequest:
    applicationId: int
    name: str
    targetMcu: Optional[str] = None
    chipset: Optional[str] = None
    coreCloudDeviceType: Optional[str] = None
    coreCloudVariant: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FirmwareAppCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        application_id = data.get("applicationId")
        if application_id is None:
            return None, "Application ID is required"
        if not isinstance(application_id, int) or application_id < 0:
            return None, "Application ID must be a non-negative integer"

        name = (data.get("name") or "").strip()
        if not name:
            return None, "Name is required"

        target_mcu = data.get("targetMcu")
        chipset = data.get("chipset")
        core_cloud_device_type = data.get("coreCloudDeviceType")
        core_cloud_variant = data.get("coreCloudVariant")
        notes = data.get("notes")

        chipset_val = chipset.strip() if chipset else None
        target_mcu_val = target_mcu.strip() if target_mcu else None

        if chipset_val and chipset_val not in SUPPORTED_CHIPSETS:
            return None, f"Unsupported chipset: {chipset_val}. Supported: {', '.join(sorted(SUPPORTED_CHIPSETS.keys()))}"
        if target_mcu_val:
            if chipset_val:
                allowed_mcus = SUPPORTED_CHIPSETS[chipset_val]["targetMcus"]
                if target_mcu_val not in allowed_mcus:
                    return None, f"Target MCU '{target_mcu_val}' is not valid for chipset '{chipset_val}'. Valid: {', '.join(allowed_mcus)}"
            elif target_mcu_val not in SUPPORTED_SOCS:
                return None, f"Unsupported target MCU: {target_mcu_val}. Supported: {', '.join(SUPPORTED_SOCS)}"

        return cls(
            applicationId=application_id,
            name=name,
            targetMcu=target_mcu_val,
            chipset=chipset_val,
            coreCloudDeviceType=core_cloud_device_type.strip() if core_cloud_device_type else None,
            coreCloudVariant=core_cloud_variant.strip() if core_cloud_variant else None,
            notes=notes.strip() if notes else None,
        ), None


@dataclass
class FirmwareAppUpdateRequest:
    name: Optional[str] = None
    targetMcu: Optional[str] = None
    chipset: Optional[str] = None
    coreCloudDeviceType: Optional[str] = None
    coreCloudVariant: Optional[str] = None
    notes: Optional[str] = None
    _has_target_mcu: bool = False
    _has_chipset: bool = False
    _has_core_cloud_device_type: bool = False
    _has_core_cloud_variant: bool = False
    _has_notes: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FirmwareAppUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                return None, "Name cannot be empty"

        target_mcu = data.get("targetMcu")
        has_target_mcu = "targetMcu" in data
        chipset = data.get("chipset")
        has_chipset = "chipset" in data
        core_cloud_device_type = data.get("coreCloudDeviceType")
        has_core_cloud_device_type = "coreCloudDeviceType" in data
        core_cloud_variant = data.get("coreCloudVariant")
        has_core_cloud_variant = "coreCloudVariant" in data
        notes = data.get("notes")
        has_notes = "notes" in data

        if (name is None and not has_target_mcu and not has_chipset
                and not has_core_cloud_device_type and not has_core_cloud_variant and not has_notes):
            return None, "No fields to update"

        chipset_val = chipset.strip() if chipset else chipset
        target_mcu_val = target_mcu.strip() if target_mcu else target_mcu

        if has_chipset and chipset_val and chipset_val not in SUPPORTED_CHIPSETS:
            return None, f"Unsupported chipset: {chipset_val}. Supported: {', '.join(sorted(SUPPORTED_CHIPSETS.keys()))}"
        if has_target_mcu and target_mcu_val:
            if chipset_val and chipset_val in SUPPORTED_CHIPSETS:
                allowed_mcus = SUPPORTED_CHIPSETS[chipset_val]["targetMcus"]
                if target_mcu_val not in allowed_mcus:
                    return None, f"Target MCU '{target_mcu_val}' is not valid for chipset '{chipset_val}'. Valid: {', '.join(allowed_mcus)}"
            elif target_mcu_val not in SUPPORTED_SOCS:
                return None, f"Unsupported target MCU: {target_mcu_val}. Supported: {', '.join(SUPPORTED_SOCS)}"

        return cls(
            name=name,
            targetMcu=target_mcu_val,
            chipset=chipset_val,
            coreCloudDeviceType=core_cloud_device_type.strip() if core_cloud_device_type else core_cloud_device_type,
            coreCloudVariant=core_cloud_variant.strip() if core_cloud_variant else core_cloud_variant,
            notes=notes.strip() if notes else notes,
            _has_target_mcu=has_target_mcu,
            _has_chipset=has_chipset,
            _has_core_cloud_device_type=has_core_cloud_device_type,
            _has_core_cloud_variant=has_core_cloud_variant,
            _has_notes=has_notes,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_target_mcu:
            update_data["targetMcu"] = self.targetMcu
        if self._has_chipset:
            update_data["chipset"] = self.chipset
        if self._has_core_cloud_device_type:
            update_data["coreCloudDeviceType"] = self.coreCloudDeviceType
        if self._has_core_cloud_variant:
            update_data["coreCloudVariant"] = self.coreCloudVariant
        if self._has_notes:
            update_data["notes"] = self.notes
        return update_data


@dataclass
class FirmwareBuildUpdateRequest:
    status: Optional[str] = None
    notes: Optional[str] = None
    _has_notes: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FirmwareBuildUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        status = data.get("status")
        if status is not None:
            status = status.strip()
            if status not in ("DRAFT", "RELEASED", "DEPRECATED"):
                return None, "Status must be DRAFT, RELEASED, or DEPRECATED"
        notes = data.get("notes")
        has_notes = "notes" in data

        if status is None and not has_notes:
            return None, "No fields to update"

        return cls(
            status=status,
            notes=notes.strip() if notes else notes,
            _has_notes=has_notes,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.status is not None:
            update_data["status"] = self.status
        if self._has_notes:
            update_data["notes"] = self.notes
        return update_data
