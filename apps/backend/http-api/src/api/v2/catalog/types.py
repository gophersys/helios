from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from database import Json


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
class BoardCreateRequest:
    name: str
    description: Optional[str] = None
    active: bool = True

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BoardCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        if not name:
            return None, "Name is required"
        description = data.get("description")
        active = data.get("active", True)
        if not isinstance(active, bool):
            return None, "Active must be a boolean"
        return cls(
            name=name,
            description=description.strip() if description else None,
            active=active,
        ), None


@dataclass
class BoardUpdateRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    _has_description: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BoardUpdateRequest"], Optional[str]]:
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
    chipsetIds: list = None
    status: str = "ACTIVE"
    notes: Optional[str] = None

    def __post_init__(self):
        if self.chipsetIds is None:
            self.chipsetIds = []

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BoardRevisionCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        version = (data.get("version") or "").strip()
        chipset_ids = data.get("chipsetIds", [])
        status = (data.get("status") or "ACTIVE").strip()
        notes = data.get("notes")

        if not version:
            return None, "Version is required"
        if not isinstance(chipset_ids, list):
            return None, "chipsetIds must be an array of strings"
        chipset_ids = [c.strip() for c in chipset_ids if isinstance(c, str) and c.strip()]
        if status not in ("ACTIVE", "DEPRECATED", "EOL"):
            return None, "Status must be ACTIVE, DEPRECATED, or EOL"

        return cls(
            version=version,
            chipsetIds=chipset_ids,
            status=status,
            notes=notes.strip() if notes else None,
        ), None


@dataclass
class BoardRevisionUpdateRequest:
    version: Optional[str] = None
    chipsetIds: Optional[list] = None
    selectedBuilds: Optional[dict] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    _has_chipset_ids: bool = False
    _has_selected_builds: bool = False
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
        chipset_ids = data.get("chipsetIds")
        has_chipset_ids = "chipsetIds" in data
        if has_chipset_ids:
            if not isinstance(chipset_ids, list):
                return None, "chipsetIds must be an array of strings"
            chipset_ids = [c.strip() for c in chipset_ids if isinstance(c, str) and c.strip()]
        selected_builds = data.get("selectedBuilds")
        has_selected_builds = "selectedBuilds" in data
        if has_selected_builds and selected_builds is not None:
            if not isinstance(selected_builds, dict):
                return None, "selectedBuilds must be an object mapping chipset IDs to build IDs"
            for k, v in selected_builds.items():
                if not isinstance(k, str) or not k.strip():
                    return None, "selectedBuilds keys must be non-empty chipset IDs"
                if not isinstance(v, str) or not v.strip():
                    return None, "selectedBuilds values must be non-empty build IDs"
            selected_builds = {k.strip(): v.strip() for k, v in selected_builds.items()}
        status = data.get("status")
        if status is not None:
            status = status.strip()
            if status not in ("ACTIVE", "DEPRECATED", "EOL"):
                return None, "Status must be ACTIVE, DEPRECATED, or EOL"
        notes = data.get("notes")
        has_notes = "notes" in data

        if version is None and status is None and not has_chipset_ids and not has_notes and not has_selected_builds:
            return None, "No fields to update"

        return cls(
            version=version,
            chipsetIds=chipset_ids,
            selectedBuilds=selected_builds,
            status=status,
            notes=notes.strip() if notes else notes,
            _has_chipset_ids=has_chipset_ids,
            _has_selected_builds=has_selected_builds,
            _has_notes=has_notes,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.version is not None:
            update_data["version"] = self.version
        if self._has_selected_builds:
            update_data["selectedBuilds"] = Json(self.selectedBuilds) if self.selectedBuilds else Json({})
        if self.status is not None:
            update_data["status"] = self.status
        if self._has_notes:
            update_data["notes"] = self.notes
        return update_data


@dataclass
class ChipsetCreateRequest:
    name: str
    manufacturer: Optional[str] = None
    isModem: bool = False
    description: Optional[str] = None
    active: bool = True

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ChipsetCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        if not name:
            return None, "Name is required"
        manufacturer = data.get("manufacturer")
        is_modem = data.get("isModem", False)
        if not isinstance(is_modem, bool):
            return None, "isModem must be a boolean"
        description = data.get("description")
        active = data.get("active", True)
        if not isinstance(active, bool):
            return None, "Active must be a boolean"
        return cls(
            name=name,
            manufacturer=manufacturer.strip() if manufacturer else None,
            isModem=is_modem,
            description=description.strip() if description else None,
            active=active,
        ), None


@dataclass
class ChipsetUpdateRequest:
    name: Optional[str] = None
    manufacturer: Optional[str] = None
    isModem: Optional[bool] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    _has_manufacturer: bool = False
    _has_description: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ChipsetUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = data.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                return None, "Name cannot be empty"
        manufacturer = data.get("manufacturer")
        has_manufacturer = "manufacturer" in data
        is_modem = data.get("isModem")
        if is_modem is not None and not isinstance(is_modem, bool):
            return None, "isModem must be a boolean"
        description = data.get("description")
        has_description = "description" in data
        active = data.get("active")
        if active is not None and not isinstance(active, bool):
            return None, "Active must be a boolean"

        if name is None and not has_manufacturer and is_modem is None and not has_description and active is None:
            return None, "No fields to update"

        return cls(
            name=name,
            manufacturer=manufacturer.strip() if manufacturer else manufacturer,
            isModem=is_modem,
            description=description.strip() if description else description,
            active=active,
            _has_manufacturer=has_manufacturer,
            _has_description=has_description,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_manufacturer:
            update_data["manufacturer"] = self.manufacturer
        if self.isModem is not None:
            update_data["isModem"] = self.isModem
        if self._has_description:
            update_data["description"] = self.description
        if self.active is not None:
            update_data["active"] = self.active
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
