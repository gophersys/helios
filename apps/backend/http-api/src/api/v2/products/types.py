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
    description: Optional[str] = None
    active: bool = True
    slug: Optional[str] = None
    fwRepoSlug: Optional[str] = None
    mfgFwRepoSlug: Optional[str] = None
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

        slug = data.get("slug")
        if slug is not None:
            slug = slug.strip()
            if not slug:
                slug = None

        fw_repo_slug = data.get("fwRepoSlug")
        if fw_repo_slug is not None:
            fw_repo_slug = fw_repo_slug.strip() or None

        mfg_fw_repo_slug = data.get("mfgFwRepoSlug")
        if mfg_fw_repo_slug is not None:
            mfg_fw_repo_slug = mfg_fw_repo_slug.strip() or None

        build_config = data.get("buildConfig")
        if build_config is not None and not isinstance(build_config, dict):
            return None, "buildConfig must be a JSON object"

        metadata = data.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            return None, "Metadata must be a JSON object"

        return cls(
            name=name,
            description=description.strip() if description else None,
            active=active,
            slug=slug,
            fwRepoSlug=fw_repo_slug,
            mfgFwRepoSlug=mfg_fw_repo_slug,
            buildConfig=build_config,
            metadata=metadata,
        ), None


@dataclass
class ProductUpdateRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    slug: Optional[str] = None
    fwRepoSlug: Optional[str] = None
    mfgFwRepoSlug: Optional[str] = None
    buildConfig: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    _has_description: bool = False
    _has_slug: bool = False
    _has_fw_repo_slug: bool = False
    _has_mfg_fw_repo_slug: bool = False
    _has_build_config: bool = False
    _has_metadata: bool = False

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

        fw_repo_slug = data.get("fwRepoSlug")
        has_fw_repo_slug = "fwRepoSlug" in data
        if fw_repo_slug is not None:
            fw_repo_slug = fw_repo_slug.strip() or None

        mfg_fw_repo_slug = data.get("mfgFwRepoSlug")
        has_mfg_fw_repo_slug = "mfgFwRepoSlug" in data
        if mfg_fw_repo_slug is not None:
            mfg_fw_repo_slug = mfg_fw_repo_slug.strip() or None

        build_config = data.get("buildConfig")
        has_build_config = "buildConfig" in data
        if has_build_config and build_config is not None and not isinstance(build_config, dict):
            return None, "buildConfig must be a JSON object"

        metadata = data.get("metadata")
        has_metadata = "metadata" in data
        if has_metadata and metadata is not None and not isinstance(metadata, dict):
            return None, "Metadata must be a JSON object"

        has_any_field = (
            name is not None or has_description or active is not None or
            has_slug or has_fw_repo_slug or has_mfg_fw_repo_slug or
            has_build_config or has_metadata
        )
        if not has_any_field:
            return None, "No fields to update"

        return cls(
            name=name,
            description=description.strip() if description else description,
            active=active,
            slug=slug,
            fwRepoSlug=fw_repo_slug,
            mfgFwRepoSlug=mfg_fw_repo_slug,
            buildConfig=build_config,
            metadata=metadata,
            _has_description=has_description,
            _has_slug=has_slug,
            _has_fw_repo_slug=has_fw_repo_slug,
            _has_mfg_fw_repo_slug=has_mfg_fw_repo_slug,
            _has_build_config=has_build_config,
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
        if self._has_slug:
            update_data["slug"] = self.slug
        if self._has_fw_repo_slug:
            update_data["fwRepoSlug"] = self.fwRepoSlug
        if self._has_mfg_fw_repo_slug:
            update_data["mfgFwRepoSlug"] = self.mfgFwRepoSlug
        if self._has_build_config:
            update_data["buildConfig"] = Json(self.buildConfig) if self.buildConfig else None
        if self._has_metadata:
            update_data["metadata"] = Json(self.metadata) if self.metadata else None
        return update_data


@dataclass
class BoardCreateRequest:
    name: str
    ckBoardsFamily: str
    vendor: str = "corekinect"
    description: Optional[str] = None
    active: bool = True
    revisions: Optional[List[Dict[str, Any]]] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BoardCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        if not name:
            return None, "Name is required"
        ck_boards_family = (data.get("ckBoardsFamily") or "").strip()
        if not ck_boards_family:
            return None, "ckBoardsFamily is required"
        vendor = (data.get("vendor") or "corekinect").strip()
        description = data.get("description")
        active = data.get("active", True)
        if not isinstance(active, bool):
            return None, "Active must be a boolean"

        # Optional inline revisions
        raw_revisions = data.get("revisions")
        revisions = None
        if raw_revisions is not None:
            if not isinstance(raw_revisions, list):
                return None, "revisions must be an array"
            revisions = []
            for i, r in enumerate(raw_revisions):
                if not isinstance(r, dict):
                    return None, f"revisions[{i}] must be an object"
                rev_version = (r.get("version") or "").strip()
                rev_ck_name = (r.get("ckBoardsName") or "").strip()
                if not rev_version:
                    return None, f"revisions[{i}].version is required"
                if not rev_ck_name:
                    return None, f"revisions[{i}].ckBoardsName is required"
                rev_socs = r.get("socs", [])
                if not isinstance(rev_socs, list):
                    return None, f"revisions[{i}].socs must be an array"
                # Optional inline targets per revision
                raw_targets = r.get("targets")
                rev_targets = None
                if raw_targets is not None:
                    if not isinstance(raw_targets, list):
                        return None, f"revisions[{i}].targets must be an array"
                    rev_targets = []
                    seen_roles = set()
                    seen_app_ids = set()
                    for j, t in enumerate(raw_targets):
                        if not isinstance(t, dict):
                            return None, f"revisions[{i}].targets[{j}] must be an object"
                        role = (t.get("role") or "").strip()
                        soc = (t.get("soc") or "").strip()
                        app_id = t.get("appId")
                        if not role:
                            return None, f"revisions[{i}].targets[{j}].role is required"
                        if not soc:
                            return None, f"revisions[{i}].targets[{j}].soc is required"
                        if app_id is None or not isinstance(app_id, int):
                            return None, f"revisions[{i}].targets[{j}].appId is required and must be an integer"
                        if role in seen_roles:
                            return None, f"revisions[{i}]: duplicate target role '{role}'"
                        if app_id in seen_app_ids:
                            return None, f"revisions[{i}]: duplicate target appId {app_id}"
                        seen_roles.add(role)
                        seen_app_ids.add(app_id)
                        rev_targets.append(TargetInput(role=role, soc=soc, appId=app_id))
                revisions.append({
                    "version": rev_version,
                    "ckBoardsName": rev_ck_name,
                    "socs": rev_socs,
                    "targets": rev_targets,
                })

        return cls(
            name=name,
            ckBoardsFamily=ck_boards_family,
            vendor=vendor,
            description=description.strip() if description else None,
            active=active,
            revisions=revisions,
        ), None


@dataclass
class BoardUpdateRequest:
    name: Optional[str] = None
    ckBoardsFamily: Optional[str] = None
    vendor: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    _has_description: bool = False
    _has_ck_boards_family: bool = False
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
        ck_boards_family = data.get("ckBoardsFamily")
        has_ck_boards_family = "ckBoardsFamily" in data
        if ck_boards_family is not None:
            ck_boards_family = ck_boards_family.strip()
            if not ck_boards_family:
                return None, "ckBoardsFamily cannot be empty"
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
                not has_ck_boards_family and not has_vendor):
            return None, "No fields to update"

        return cls(
            name=name,
            ckBoardsFamily=ck_boards_family,
            vendor=vendor,
            description=description.strip() if description else description,
            active=active,
            _has_description=has_description,
            _has_ck_boards_family=has_ck_boards_family,
            _has_vendor=has_vendor,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_ck_boards_family:
            update_data["ckBoardsFamily"] = self.ckBoardsFamily
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
    ckBoardsName: str
    socs: List[str]
    deviceType: Optional[int] = None
    deviceVariant: Optional[int] = None
    status: str = "ACTIVE"
    notes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BoardRevisionCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        version = (data.get("version") or "").strip()
        ck_boards_name = (data.get("ckBoardsName") or "").strip()
        socs = data.get("socs", [])
        status = (data.get("status") or "ACTIVE").strip()
        notes = data.get("notes")

        if not version:
            return None, "Version is required"
        if not ck_boards_name:
            return None, "ckBoardsName is required"
        if not isinstance(socs, list):
            return None, "socs must be an array"
        if status not in ("ACTIVE", "DEPRECATED", "EOL"):
            return None, "Status must be ACTIVE, DEPRECATED, or EOL"

        device_type = data.get("deviceType")
        if device_type is not None and not isinstance(device_type, int):
            return None, "deviceType must be an integer"

        device_variant = data.get("deviceVariant")
        if device_variant is not None and not isinstance(device_variant, int):
            return None, "deviceVariant must be an integer"

        return cls(
            version=version,
            ckBoardsName=ck_boards_name,
            socs=socs,
            deviceType=device_type,
            deviceVariant=device_variant,
            status=status,
            notes=notes.strip() if notes else None,
        ), None


@dataclass
class BoardRevisionUpdateRequest:
    version: Optional[str] = None
    ckBoardsName: Optional[str] = None
    socs: Optional[List[str]] = None
    deviceType: Optional[int] = None
    deviceVariant: Optional[int] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    _has_notes: bool = False
    _has_ck_boards_name: bool = False
    _has_socs: bool = False
    _has_device_type: bool = False
    _has_device_variant: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["BoardRevisionUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        version = data.get("version")
        if version is not None:
            version = version.strip()
            if not version:
                return None, "Version cannot be empty"
        ck_boards_name = data.get("ckBoardsName")
        has_ck_boards_name = "ckBoardsName" in data
        if ck_boards_name is not None:
            ck_boards_name = ck_boards_name.strip()
            if not ck_boards_name:
                return None, "ckBoardsName cannot be empty"
        socs = data.get("socs")
        has_socs = "socs" in data
        if has_socs and socs is not None and not isinstance(socs, list):
            return None, "socs must be an array"

        device_type = data.get("deviceType")
        has_device_type = "deviceType" in data
        if has_device_type and device_type is not None and not isinstance(device_type, int):
            return None, "deviceType must be an integer"

        device_variant = data.get("deviceVariant")
        has_device_variant = "deviceVariant" in data
        if has_device_variant and device_variant is not None and not isinstance(device_variant, int):
            return None, "deviceVariant must be an integer"

        status = data.get("status")
        if status is not None:
            status = status.strip()
            if status not in ("ACTIVE", "DEPRECATED", "EOL"):
                return None, "Status must be ACTIVE, DEPRECATED, or EOL"
        notes = data.get("notes")
        has_notes = "notes" in data

        if (version is None and status is None and not has_notes and not has_ck_boards_name
                and not has_socs and not has_device_type and not has_device_variant):
            return None, "No fields to update"

        return cls(
            version=version,
            ckBoardsName=ck_boards_name,
            socs=socs,
            deviceType=device_type,
            deviceVariant=device_variant,
            status=status,
            notes=notes.strip() if notes else notes,
            _has_notes=has_notes,
            _has_ck_boards_name=has_ck_boards_name,
            _has_socs=has_socs,
            _has_device_type=has_device_type,
            _has_device_variant=has_device_variant,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.version is not None:
            update_data["version"] = self.version
        if self._has_ck_boards_name:
            update_data["ckBoardsName"] = self.ckBoardsName
        if self._has_socs:
            update_data["socs"] = self.socs
        if self._has_device_type:
            update_data["deviceType"] = self.deviceType
        if self._has_device_variant:
            update_data["deviceVariant"] = self.deviceVariant
        if self.status is not None:
            update_data["status"] = self.status
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


@dataclass
class TargetCreateRequest:
    role: str
    soc: str
    appId: int

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["TargetCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        role = (data.get("role") or "").strip()
        if not role:
            return None, "role is required"
        soc = (data.get("soc") or "").strip()
        if not soc:
            return None, "soc is required"
        app_id = data.get("appId")
        if app_id is None or not isinstance(app_id, int):
            return None, "appId is required and must be an integer"
        return cls(role=role, soc=soc, appId=app_id), None


@dataclass
class TargetUpdateRequest:
    role: Optional[str] = None
    soc: Optional[str] = None
    appId: Optional[int] = None
    _has_role: bool = False
    _has_soc: bool = False
    _has_app_id: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["TargetUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        role = data.get("role")
        has_role = "role" in data
        if role is not None:
            role = role.strip()
            if not role:
                return None, "role cannot be empty"
        soc = data.get("soc")
        has_soc = "soc" in data
        if soc is not None:
            soc = soc.strip()
            if not soc:
                return None, "soc cannot be empty"
        app_id = data.get("appId")
        has_app_id = "appId" in data
        if has_app_id and app_id is not None and not isinstance(app_id, int):
            return None, "appId must be an integer"

        if not has_role and not has_soc and not has_app_id:
            return None, "No fields to update"

        return cls(
            role=role,
            soc=soc,
            appId=app_id,
            _has_role=has_role,
            _has_soc=has_soc,
            _has_app_id=has_app_id,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self._has_role:
            update_data["role"] = self.role
        if self._has_soc:
            update_data["soc"] = self.soc
        if self._has_app_id:
            update_data["appId"] = self.appId
        return update_data


@dataclass
class RevisionConfigUpdateRequest:
    """Bulk update a revision's deviceType/deviceVariant and its targets in one call."""
    deviceType: Optional[int] = None
    deviceVariant: Optional[int] = None
    targets: Optional[List[Dict[str, Any]]] = None
    _has_device_type: bool = False
    _has_device_variant: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["RevisionConfigUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        device_type = data.get("deviceType")
        has_device_type = "deviceType" in data
        if has_device_type and device_type is not None and not isinstance(device_type, int):
            return None, "deviceType must be an integer"

        device_variant = data.get("deviceVariant")
        has_device_variant = "deviceVariant" in data
        if has_device_variant and device_variant is not None and not isinstance(device_variant, int):
            return None, "deviceVariant must be an integer"

        targets = data.get("targets")
        if targets is not None:
            if not isinstance(targets, list):
                return None, "targets must be an array"
            for i, t in enumerate(targets):
                if not isinstance(t, dict):
                    return None, f"targets[{i}] must be an object"
                if "role" not in t or not (t.get("role") or "").strip():
                    return None, f"targets[{i}].role is required"
                if "soc" not in t or not (t.get("soc") or "").strip():
                    return None, f"targets[{i}].soc is required"
                if "appId" not in t or not isinstance(t.get("appId"), int):
                    return None, f"targets[{i}].appId is required and must be an integer"

        if not has_device_type and not has_device_variant and targets is None:
            return None, "No fields to update"

        return cls(
            deviceType=device_type,
            deviceVariant=device_variant,
            targets=targets,
            _has_device_type=has_device_type,
            _has_device_variant=has_device_variant,
        ), None
