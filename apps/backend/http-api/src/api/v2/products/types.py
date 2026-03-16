from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from database import Json


@dataclass
class ProductCreateRequest:
    name: str
    description: Optional[str] = None
    active: bool = True
    # Optional fields
    slug: Optional[str] = None
    repoSlug: Optional[str] = None
    repoSshUrl: Optional[str] = None
    repoBranch: Optional[str] = None
    mfgRepoSlug: Optional[str] = None
    mfgRepoSshUrl: Optional[str] = None
    buildBoard: Optional[str] = None
    buildWestDir: Optional[str] = None
    buildMfgDir: Optional[str] = None
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

        # Optional string fields - strip whitespace
        slug = data.get("slug")
        if slug is not None:
            slug = slug.strip()
            if not slug:
                slug = None
        repo_slug = data.get("repoSlug")
        if repo_slug is not None:
            repo_slug = repo_slug.strip() or None
        repo_ssh_url = data.get("repoSshUrl")
        if repo_ssh_url is not None:
            repo_ssh_url = repo_ssh_url.strip() or None
        repo_branch = data.get("repoBranch")
        if repo_branch is not None:
            repo_branch = repo_branch.strip() or None
        mfg_repo_slug = data.get("mfgRepoSlug")
        if mfg_repo_slug is not None:
            mfg_repo_slug = mfg_repo_slug.strip() or None
        mfg_repo_ssh_url = data.get("mfgRepoSshUrl")
        if mfg_repo_ssh_url is not None:
            mfg_repo_ssh_url = mfg_repo_ssh_url.strip() or None
        build_board = data.get("buildBoard")
        if build_board is not None:
            build_board = build_board.strip() or None
        build_west_dir = data.get("buildWestDir")
        if build_west_dir is not None:
            build_west_dir = build_west_dir.strip() or None
        build_mfg_dir = data.get("buildMfgDir")
        if build_mfg_dir is not None:
            build_mfg_dir = build_mfg_dir.strip() or None

        # Metadata must be a dict if provided
        metadata = data.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            return None, "Metadata must be a JSON object"

        return cls(
            name=name,
            description=description.strip() if description else None,
            active=active,
            slug=slug,
            repoSlug=repo_slug,
            repoSshUrl=repo_ssh_url,
            repoBranch=repo_branch,
            mfgRepoSlug=mfg_repo_slug,
            mfgRepoSshUrl=mfg_repo_ssh_url,
            buildBoard=build_board,
            buildWestDir=build_west_dir,
            buildMfgDir=build_mfg_dir,
            metadata=metadata,
        ), None


@dataclass
class ProductUpdateRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    slug: Optional[str] = None
    repoSlug: Optional[str] = None
    repoSshUrl: Optional[str] = None
    repoBranch: Optional[str] = None
    mfgRepoSlug: Optional[str] = None
    mfgRepoSshUrl: Optional[str] = None
    buildBoard: Optional[str] = None
    buildWestDir: Optional[str] = None
    buildMfgDir: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    # Track explicitly-set-to-null vs omitted
    _has_description: bool = False
    _has_slug: bool = False
    _has_repo_slug: bool = False
    _has_repo_ssh_url: bool = False
    _has_repo_branch: bool = False
    _has_mfg_repo_slug: bool = False
    _has_mfg_repo_ssh_url: bool = False
    _has_build_board: bool = False
    _has_build_west_dir: bool = False
    _has_build_mfg_dir: bool = False
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

        # Optional string fields - track presence and strip values
        slug = data.get("slug")
        has_slug = "slug" in data
        if slug is not None:
            slug = slug.strip() or None

        repo_slug = data.get("repoSlug")
        has_repo_slug = "repoSlug" in data
        if repo_slug is not None:
            repo_slug = repo_slug.strip() or None

        repo_ssh_url = data.get("repoSshUrl")
        has_repo_ssh_url = "repoSshUrl" in data
        if repo_ssh_url is not None:
            repo_ssh_url = repo_ssh_url.strip() or None

        repo_branch = data.get("repoBranch")
        has_repo_branch = "repoBranch" in data
        if repo_branch is not None:
            repo_branch = repo_branch.strip() or None

        mfg_repo_slug = data.get("mfgRepoSlug")
        has_mfg_repo_slug = "mfgRepoSlug" in data
        if mfg_repo_slug is not None:
            mfg_repo_slug = mfg_repo_slug.strip() or None

        mfg_repo_ssh_url = data.get("mfgRepoSshUrl")
        has_mfg_repo_ssh_url = "mfgRepoSshUrl" in data
        if mfg_repo_ssh_url is not None:
            mfg_repo_ssh_url = mfg_repo_ssh_url.strip() or None

        build_board = data.get("buildBoard")
        has_build_board = "buildBoard" in data
        if build_board is not None:
            build_board = build_board.strip() or None

        build_west_dir = data.get("buildWestDir")
        has_build_west_dir = "buildWestDir" in data
        if build_west_dir is not None:
            build_west_dir = build_west_dir.strip() or None

        build_mfg_dir = data.get("buildMfgDir")
        has_build_mfg_dir = "buildMfgDir" in data
        if build_mfg_dir is not None:
            build_mfg_dir = build_mfg_dir.strip() or None

        metadata = data.get("metadata")
        has_metadata = "metadata" in data
        if has_metadata and metadata is not None and not isinstance(metadata, dict):
            return None, "Metadata must be a JSON object"

        # Check if any field was provided
        has_any_field = (
            name is not None or has_description or active is not None or
            has_slug or has_repo_slug or has_repo_ssh_url or has_repo_branch or
            has_mfg_repo_slug or has_mfg_repo_ssh_url or
            has_build_board or has_build_west_dir or has_build_mfg_dir or has_metadata
        )
        if not has_any_field:
            return None, "No fields to update"

        return cls(
            name=name,
            description=description.strip() if description else description,
            active=active,
            slug=slug,
            repoSlug=repo_slug,
            repoSshUrl=repo_ssh_url,
            repoBranch=repo_branch,
            mfgRepoSlug=mfg_repo_slug,
            mfgRepoSshUrl=mfg_repo_ssh_url,
            buildBoard=build_board,
            buildWestDir=build_west_dir,
            buildMfgDir=build_mfg_dir,
            metadata=metadata,
            _has_description=has_description,
            _has_slug=has_slug,
            _has_repo_slug=has_repo_slug,
            _has_repo_ssh_url=has_repo_ssh_url,
            _has_repo_branch=has_repo_branch,
            _has_mfg_repo_slug=has_mfg_repo_slug,
            _has_mfg_repo_ssh_url=has_mfg_repo_ssh_url,
            _has_build_board=has_build_board,
            _has_build_west_dir=has_build_west_dir,
            _has_build_mfg_dir=has_build_mfg_dir,
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
        if self._has_repo_slug:
            update_data["repoSlug"] = self.repoSlug
        if self._has_repo_ssh_url:
            update_data["repoSshUrl"] = self.repoSshUrl
        if self._has_repo_branch:
            update_data["repoBranch"] = self.repoBranch
        if self._has_mfg_repo_slug:
            update_data["mfgRepoSlug"] = self.mfgRepoSlug
        if self._has_mfg_repo_ssh_url:
            update_data["mfgRepoSshUrl"] = self.mfgRepoSshUrl
        if self._has_build_board:
            update_data["buildBoard"] = self.buildBoard
        if self._has_build_west_dir:
            update_data["buildWestDir"] = self.buildWestDir
        if self._has_build_mfg_dir:
            update_data["buildMfgDir"] = self.buildMfgDir
        if self._has_metadata:
            update_data["metadata"] = Json(self.metadata) if self.metadata else None
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
