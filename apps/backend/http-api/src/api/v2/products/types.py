from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from database import Json


@dataclass
class TargetInput:
    role: str
    soc: str
    appId: int


@dataclass
class ProductCreateRequest:
    name: str
    targets: List[TargetInput]
    description: Optional[str] = None
    active: bool = True
    slug: Optional[str] = None
    buildConfig: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

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

        # Targets are required
        raw_targets = data.get("targets")
        if not raw_targets or not isinstance(raw_targets, list):
            return None, "targets is required and must be a non-empty array"
        targets = []
        seen_roles = set()
        seen_app_ids = set()
        for i, t in enumerate(raw_targets):
            if not isinstance(t, dict):
                return None, f"targets[{i}] must be an object"
            role = (t.get("role") or "").strip()
            soc = (t.get("soc") or "").strip()
            app_id = t.get("appId")
            if not role:
                return None, f"targets[{i}].role is required"
            if not soc:
                return None, f"targets[{i}].soc is required"
            if app_id is None or not isinstance(app_id, int):
                return None, f"targets[{i}].appId is required and must be an integer"
            if role in seen_roles:
                return None, f"Duplicate target role: {role}"
            if app_id in seen_app_ids:
                return None, f"Duplicate target appId: {app_id}"
            seen_roles.add(role)
            seen_app_ids.add(app_id)
            targets.append(TargetInput(role=role, soc=soc, appId=app_id))

        slug = data.get("slug")
        if slug is not None:
            slug = slug.strip()
            if not slug:
                slug = None

        build_config = data.get("buildConfig")
        if build_config is not None and not isinstance(build_config, dict):
            return None, "buildConfig must be a JSON object"

        metadata = data.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            return None, "Metadata must be a JSON object"

        return cls(
            name=name,
            targets=targets,
            description=description.strip() if description else None,
            active=active,
            slug=slug,
            buildConfig=build_config,
            metadata=metadata,
        ), None


@dataclass
class ProductUpdateRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    slug: Optional[str] = None
    buildConfig: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    targets: Optional[List[TargetInput]] = None
    _has_description: bool = False
    _has_slug: bool = False
    _has_build_config: bool = False
    _has_metadata: bool = False
    _has_targets: bool = False

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

        slug = data.get("slug")
        has_slug = "slug" in data
        if slug is not None:
            slug = slug.strip() or None

        build_config = data.get("buildConfig")
        has_build_config = "buildConfig" in data
        if has_build_config and build_config is not None and not isinstance(build_config, dict):
            return None, "buildConfig must be a JSON object"

        metadata = data.get("metadata")
        has_metadata = "metadata" in data
        if has_metadata and metadata is not None and not isinstance(metadata, dict):
            return None, "Metadata must be a JSON object"

        raw_targets = data.get("targets")
        has_targets = "targets" in data
        targets = None
        if has_targets:
            if raw_targets is not None:
                if not isinstance(raw_targets, list) or len(raw_targets) == 0:
                    return None, "targets must be a non-empty array"
                targets = []
                seen_roles = set()
                seen_app_ids = set()
                for i, t in enumerate(raw_targets):
                    if not isinstance(t, dict):
                        return None, f"targets[{i}] must be an object"
                    role = (t.get("role") or "").strip()
                    soc = (t.get("soc") or "").strip()
                    app_id = t.get("appId")
                    if not role:
                        return None, f"targets[{i}].role is required"
                    if not soc:
                        return None, f"targets[{i}].soc is required"
                    if app_id is None or not isinstance(app_id, int):
                        return None, f"targets[{i}].appId is required and must be an integer"
                    if role in seen_roles:
                        return None, f"Duplicate target role: {role}"
                    if app_id in seen_app_ids:
                        return None, f"Duplicate target appId: {app_id}"
                    seen_roles.add(role)
                    seen_app_ids.add(app_id)
                    targets.append(TargetInput(role=role, soc=soc, appId=app_id))

        has_any_field = (
            name is not None or has_description or active is not None or
            has_slug or has_build_config or has_metadata or has_targets
        )
        if not has_any_field:
            return None, "No fields to update"

        return cls(
            name=name,
            description=description.strip() if description else description,
            active=active,
            slug=slug,
            buildConfig=build_config,
            metadata=metadata,
            targets=targets,
            _has_description=has_description,
            _has_slug=has_slug,
            _has_build_config=has_build_config,
            _has_metadata=has_metadata,
            _has_targets=has_targets,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_description:
            update_data["description"] = self.description
        if self.active is not None:
            update_data["active"] = self.active
        if self._has_slug:
            update_data["slug"] = self.slug
        if self._has_build_config:
            update_data["buildConfig"] = Json(self.buildConfig) if self.buildConfig else None
        if self._has_metadata:
            update_data["metadata"] = Json(self.metadata) if self.metadata else None
        return update_data


@dataclass
class BoardCreateRequest:
    name: str
    ckBoardsName: str
    ckBoardsBranch: str = "main"
    vendor: str = "corekinect"
    description: Optional[str] = None
    active: bool = True

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BoardCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        if not name:
            return None, "Name is required"
        ck_boards_name = (data.get("ckBoardsName") or "").strip()
        if not ck_boards_name:
            return None, "ckBoardsName is required"
        ck_boards_branch = (data.get("ckBoardsBranch") or "main").strip()
        vendor = (data.get("vendor") or "corekinect").strip()
        description = data.get("description")
        active = data.get("active", True)
        if not isinstance(active, bool):
            return None, "Active must be a boolean"
        return cls(
            name=name,
            ckBoardsName=ck_boards_name,
            ckBoardsBranch=ck_boards_branch,
            vendor=vendor,
            description=description.strip() if description else None,
            active=active,
        ), None


@dataclass
class BoardUpdateRequest:
    name: Optional[str] = None
    ckBoardsName: Optional[str] = None
    ckBoardsBranch: Optional[str] = None
    vendor: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    _has_description: bool = False
    _has_ck_boards_name: bool = False
    _has_ck_boards_branch: bool = False
    _has_vendor: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BoardUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = data.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                return None, "Name cannot be empty"
        ck_boards_name = data.get("ckBoardsName")
        has_ck_boards_name = "ckBoardsName" in data
        if ck_boards_name is not None:
            ck_boards_name = ck_boards_name.strip()
            if not ck_boards_name:
                return None, "ckBoardsName cannot be empty"
        ck_boards_branch = data.get("ckBoardsBranch")
        has_ck_boards_branch = "ckBoardsBranch" in data
        if ck_boards_branch is not None:
            ck_boards_branch = ck_boards_branch.strip() or None
        vendor = data.get("vendor")
        has_vendor = "vendor" in data
        if vendor is not None:
            vendor = vendor.strip() or None
        description = data.get("description")
        has_description = "description" in data
        active = data.get("active")
        if active is not None and not isinstance(active, bool):
            return None, "Active must be a boolean"

        if (name is None and not has_description and active is None and
                not has_ck_boards_name and not has_ck_boards_branch and not has_vendor):
            return None, "No fields to update"

        return cls(
            name=name,
            ckBoardsName=ck_boards_name,
            ckBoardsBranch=ck_boards_branch,
            vendor=vendor,
            description=description.strip() if description else description,
            active=active,
            _has_description=has_description,
            _has_ck_boards_name=has_ck_boards_name,
            _has_ck_boards_branch=has_ck_boards_branch,
            _has_vendor=has_vendor,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_ck_boards_name:
            update_data["ckBoardsName"] = self.ckBoardsName
        if self._has_ck_boards_branch:
            update_data["ckBoardsBranch"] = self.ckBoardsBranch
        if self._has_vendor:
            update_data["vendor"] = self.vendor
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
    peripherals: Optional[dict] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    _has_chipset_ids: bool = False
    _has_peripherals: bool = False
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
        peripherals = data.get("peripherals")
        has_peripherals = "peripherals" in data
        if has_peripherals and peripherals is not None:
            if not isinstance(peripherals, dict):
                return None, "peripherals must be a JSON object"
        status = data.get("status")
        if status is not None:
            status = status.strip()
            if status not in ("ACTIVE", "DEPRECATED", "EOL"):
                return None, "Status must be ACTIVE, DEPRECATED, or EOL"
        notes = data.get("notes")
        has_notes = "notes" in data

        if version is None and status is None and not has_chipset_ids and not has_notes and not has_peripherals:
            return None, "No fields to update"

        return cls(
            version=version,
            chipsetIds=chipset_ids,
            peripherals=peripherals,
            status=status,
            notes=notes.strip() if notes else notes,
            _has_chipset_ids=has_chipset_ids,
            _has_peripherals=has_peripherals,
            _has_notes=has_notes,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.version is not None:
            update_data["version"] = self.version
        if self._has_peripherals:
            update_data["peripherals"] = Json(self.peripherals) if self.peripherals else None
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
