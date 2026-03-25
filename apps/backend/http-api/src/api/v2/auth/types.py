from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LoginRequest:
    email: str
    password: str

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["LoginRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        email = (data.get("email") or "").strip().lower()
        password = data.get("password") or ""
        if not email:
            return None, "Email is required"
        if not password:
            return None, "Password is required"
        return cls(email=email, password=password), None


@dataclass
class UserResponse:
    id: str
    email: str
    name: str
    permissionSetId: Optional[str]
    permissionSetName: Optional[str]
    active: bool
    lastSeenAt: Optional[str]
    createdAt: str
    updatedAt: Optional[str] = None

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        perm_set_name = None
        if hasattr(user, "permissionSet") and user.permissionSet is not None:
            perm_set_name = user.permissionSet.name
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            permissionSetId=user.permissionSetId,
            permissionSetName=perm_set_name,
            active=user.active,
            lastSeenAt=user.lastSeenAt.isoformat() if user.lastSeenAt else None,
            createdAt=user.createdAt.isoformat(),
            updatedAt=user.updatedAt.isoformat() if hasattr(user, "updatedAt") and user.updatedAt is not None else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "permissionSetId": self.permissionSetId,
            "permissionSetName": self.permissionSetName,
            "active": self.active,
            "lastSeenAt": self.lastSeenAt,
            "createdAt": self.createdAt,
        }
        if self.updatedAt is not None:
            d["updatedAt"] = self.updatedAt
        return d


@dataclass
class UserCreateRequest:
    email: str
    name: str
    permissionSetId: Optional[str]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["UserCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        email = data.get("email", "").strip().lower()
        name = data.get("name", "").strip()
        permission_set_id = data.get("permissionSetId")
        if isinstance(permission_set_id, str):
            permission_set_id = permission_set_id.strip() or None

        if not email:
            return None, "Email is required"
        if not name:
            return None, "Name is required"

        return cls(email=email, name=name, permissionSetId=permission_set_id), None


@dataclass
class UserUpdateRequest:
    name: Optional[str] = None
    permissionSetId: Optional[str] = None
    active: Optional[bool] = None
    _has_permission_set_id: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["UserUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                return None, "Name cannot be empty"

        permission_set_id = data.get("permissionSetId")
        has_permission_set_id = "permissionSetId" in data

        active = data.get("active")
        if active is not None and not isinstance(active, bool):
            return None, "Active must be a boolean"

        if name is None and not has_permission_set_id and active is None:
            return None, "No fields to update"

        req = cls(name=name, permissionSetId=permission_set_id, active=active, _has_permission_set_id=has_permission_set_id)
        return req, None

    def to_update_data(self) -> Dict[str, Any]:
        update_data = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_permission_set_id:
            update_data["permissionSetId"] = self.permissionSetId
        if self.active is not None:
            update_data["active"] = self.active
        return update_data


@dataclass
class PermissionSetCreateRequest:
    name: str
    description: Optional[str]
    permissions: List[str]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["PermissionSetCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name", "").strip()
        if not name:
            return None, "Name is required"

        permissions = data.get("permissions")
        if not permissions or not isinstance(permissions, list):
            return None, "Permissions must be a non-empty list"
        permissions = [p.strip() for p in permissions if isinstance(p, str) and p.strip()]
        if not permissions:
            return None, "Permissions must contain valid strings"

        description = data.get("description")

        return cls(
            name=name,
            description=description.strip() if description else None,
            permissions=permissions,
        ), None


@dataclass
class PermissionSetUpdateRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    _has_description: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["PermissionSetUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                return None, "Name cannot be empty"

        description = data.get("description")
        has_description = "description" in data

        permissions = data.get("permissions")
        if permissions is not None and not isinstance(permissions, list):
            return None, "Permissions must be a list"
        if permissions is not None:
            permissions = [p.strip() for p in permissions if isinstance(p, str) and p.strip()]

        if name is None and not has_description and permissions is None:
            return None, "No fields to update"

        return cls(
            name=name,
            description=description.strip() if description else description,
            permissions=permissions,
            _has_description=has_description,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_description:
            update_data["description"] = self.description
        if self.permissions is not None:
            update_data["permissions"] = self.permissions
        return update_data




@dataclass
class ApiKeyCreateRequest:
    name: str
    expiresAt: Optional[str]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ApiKeyCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name", "").strip()
        if not name:
            return None, "Name is required"

        expires_at = data.get("expiresAt")

        return cls(name=name, expiresAt=expires_at), None
