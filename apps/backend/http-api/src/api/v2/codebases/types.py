from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class CodebaseCreateRequest:
    name: str
    description: Optional[str] = None
    repoUrl: Optional[str] = None
    defaultBranch: str = "main"

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["CodebaseCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        description = data.get("description")
        repo_url = data.get("repoUrl")
        default_branch = (data.get("defaultBranch") or "main").strip()

        if not name:
            return None, "Name is required"

        return cls(
            name=name,
            description=description.strip() if description else None,
            repoUrl=repo_url.strip() if repo_url else None,
            defaultBranch=default_branch,
        ), None


@dataclass
class CodebaseUpdateRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    repoUrl: Optional[str] = None
    defaultBranch: Optional[str] = None
    _has_description: bool = False
    _has_repo_url: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["CodebaseUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                return None, "Name cannot be empty"
        description = data.get("description")
        has_description = "description" in data
        repo_url = data.get("repoUrl")
        has_repo_url = "repoUrl" in data
        default_branch = data.get("defaultBranch")
        if default_branch is not None:
            default_branch = default_branch.strip()
            if not default_branch:
                return None, "Default branch cannot be empty"

        if name is None and not has_description and not has_repo_url and default_branch is None:
            return None, "No fields to update"

        return cls(
            name=name,
            description=description.strip() if description else description,
            repoUrl=repo_url.strip() if repo_url else repo_url,
            defaultBranch=default_branch,
            _has_description=has_description,
            _has_repo_url=has_repo_url,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_description:
            update_data["description"] = self.description
        if self._has_repo_url:
            update_data["repoUrl"] = self.repoUrl
        if self.defaultBranch is not None:
            update_data["defaultBranch"] = self.defaultBranch
        return update_data


@dataclass
class ReleaseCreateRequest:
    version: str
    status: str = "DRAFT"
    releaseNotes: Optional[str] = None
    tagName: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReleaseCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        version = (data.get("version") or "").strip()
        status = (data.get("status") or "DRAFT").strip()
        release_notes = data.get("releaseNotes")
        tag_name = data.get("tagName")

        if not version:
            return None, "Version is required"
        if status not in ("DRAFT", "RELEASED", "DEPRECATED"):
            return None, "Status must be DRAFT, RELEASED, or DEPRECATED"

        return cls(
            version=version,
            status=status,
            releaseNotes=release_notes.strip() if release_notes else None,
            tagName=tag_name.strip() if tag_name else None,
        ), None


@dataclass
class ReleaseUpdateRequest:
    version: Optional[str] = None
    status: Optional[str] = None
    releaseNotes: Optional[str] = None
    tagName: Optional[str] = None
    _has_release_notes: bool = False
    _has_tag_name: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReleaseUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        version = data.get("version")
        if version is not None:
            version = version.strip()
            if not version:
                return None, "Version cannot be empty"
        status = data.get("status")
        if status is not None:
            status = status.strip()
            if status not in ("DRAFT", "RELEASED", "DEPRECATED"):
                return None, "Status must be DRAFT, RELEASED, or DEPRECATED"
        release_notes = data.get("releaseNotes")
        has_release_notes = "releaseNotes" in data
        tag_name = data.get("tagName")
        has_tag_name = "tagName" in data

        if version is None and status is None and not has_release_notes and not has_tag_name:
            return None, "No fields to update"

        return cls(
            version=version,
            status=status,
            releaseNotes=release_notes.strip() if release_notes else release_notes,
            tagName=tag_name.strip() if tag_name else tag_name,
            _has_release_notes=has_release_notes,
            _has_tag_name=has_tag_name,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.version is not None:
            update_data["version"] = self.version
        if self.status is not None:
            update_data["status"] = self.status
        if self._has_release_notes:
            update_data["releaseNotes"] = self.releaseNotes
        if self._has_tag_name:
            update_data["tagName"] = self.tagName
        return update_data


@dataclass
class ArtifactCreateRequest:
    name: str
    externalUrl: str

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ArtifactCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        external_url = (data.get("externalUrl") or "").strip()

        if not name:
            return None, "Name is required"
        if not external_url:
            return None, "External URL is required"

        return cls(name=name, externalUrl=external_url), None
