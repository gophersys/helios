from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LoginRequest:
    """Parsed login credentials from a POST /auth/login request body."""

    email: str
    password: str

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["LoginRequest"], Optional[str]]:
        """Parse and validate login credentials from a JSON request body.

        Args:
            data: Parsed JSON dict from the request body.

        Returns:
            Tuple of (LoginRequest, None) on success, or (None, error_message) on failure.
        """
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
    """Serialized user record returned by auth and user management endpoints."""

    id: str
    email: str
    name: str
    role: str
    permissionSetId: Optional[str]
    permissionSetName: Optional[str]
    active: bool
    lastSeenAt: Optional[str]
    createdAt: str
    updatedAt: Optional[str] = None

    @classmethod
    def from_user(cls, user) -> "UserResponse":
        """Construct a UserResponse from a Prisma User model instance.

        Args:
            user: Prisma User model with optional permissionSet relation loaded.

        Returns:
            UserResponse with all fields populated.
        """
        perm_set_name = None
        if hasattr(user, "permissionSet") and user.permissionSet is not None:
            perm_set_name = user.permissionSet.name
        return cls(
            id=user.id,
            email=user.email,
            name=user.name,
            role=getattr(user, "role", "DEVELOPER") or "DEVELOPER",
            permissionSetId=user.permissionSetId,
            permissionSetName=perm_set_name,
            active=user.active,
            lastSeenAt=user.lastSeenAt.isoformat() if user.lastSeenAt else None,
            createdAt=user.createdAt.isoformat(),
            updatedAt=user.updatedAt.isoformat() if hasattr(user, "updatedAt") and user.updatedAt is not None else None,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a JSON-safe dict for API responses.

        Returns:
            Dict with user fields. updatedAt is omitted when None.
        """
        d = {
            "id": self.id,
            "email": self.email,
            "name": self.name,
            "role": self.role,
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
    """Validated input for creating a new user account."""

    email: str
    name: str
    role: Optional[str]
    permissionSetId: Optional[str]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["UserCreateRequest"], Optional[str]]:
        """Parse and validate user creation fields from a JSON request body.

        Args:
            data: Parsed JSON dict from the request body.

        Returns:
            Tuple of (UserCreateRequest, None) on success, or (None, error_message) on failure.
        """
        if not data:
            return None, "Request body must contain JSON data"

        email = data.get("email", "").strip().lower()
        name = data.get("name", "").strip()
        role = data.get("role")
        if isinstance(role, str):
            role = role.strip().upper() or None
        permission_set_id = data.get("permissionSetId")
        if isinstance(permission_set_id, str):
            permission_set_id = permission_set_id.strip() or None

        if not email:
            return None, "Email is required"
        if not name:
            return None, "Name is required"

        return cls(email=email, name=name, role=role, permissionSetId=permission_set_id), None


@dataclass
class UserUpdateRequest:
    """Validated input for updating an existing user account.

    Only fields explicitly included in the request body are applied.
    Internal _has_* flags distinguish "field set to null" from "field omitted".
    """

    name: Optional[str] = None
    role: Optional[str] = None
    permissionSetId: Optional[str] = None
    active: Optional[bool] = None
    _has_permission_set_id: bool = False
    _has_role: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["UserUpdateRequest"], Optional[str]]:
        """Parse and validate user update fields from a JSON request body.

        Args:
            data: Parsed JSON dict from the request body.

        Returns:
            Tuple of (UserUpdateRequest, None) on success, or (None, error_message) on failure.
        """
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                return None, "Name cannot be empty"

        role = data.get("role")
        has_role = "role" in data
        if role is not None:
            role = role.strip().upper() if isinstance(role, str) else role

        permission_set_id = data.get("permissionSetId")
        has_permission_set_id = "permissionSetId" in data

        active = data.get("active")
        if active is not None and not isinstance(active, bool):
            return None, "Active must be a boolean"

        if name is None and not has_permission_set_id and active is None and not has_role:
            return None, "No fields to update"

        req = cls(
            name=name,
            role=role,
            permissionSetId=permission_set_id,
            active=active,
            _has_permission_set_id=has_permission_set_id,
            _has_role=has_role,
        )
        return req, None

    def to_update_data(self) -> Dict[str, Any]:
        """Build the Prisma update dict containing only explicitly-set fields.

        Returns:
            Dict of fields to pass to db.user.update(data=...).
        """
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_role:
            update_data["role"] = self.role
        if self._has_permission_set_id:
            update_data["permissionSetId"] = self.permissionSetId
        if self.active is not None:
            update_data["active"] = self.active
        return update_data


@dataclass
class PermissionSetCreateRequest:
    """Validated input for creating a new permission set (role)."""

    name: str
    description: Optional[str]
    permissions: List[str]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["PermissionSetCreateRequest"], Optional[str]]:
        """Parse and validate permission set creation fields from a JSON request body.

        Args:
            data: Parsed JSON dict from the request body.

        Returns:
            Tuple of (PermissionSetCreateRequest, None) on success, or (None, error_message) on failure.
        """
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
    """Validated input for updating an existing permission set.

    Only fields explicitly included in the request body are applied.
    """

    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    _has_description: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["PermissionSetUpdateRequest"], Optional[str]]:
        """Parse and validate permission set update fields from a JSON request body.

        Args:
            data: Parsed JSON dict from the request body.

        Returns:
            Tuple of (PermissionSetUpdateRequest, None) on success, or (None, error_message) on failure.
        """
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
        """Build the Prisma update dict containing only explicitly-set fields.

        Returns:
            Dict of fields to pass to db.permissionset.update(data=...).
        """
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
    """Validated input for creating a new API key."""

    name: str
    expiresAt: Optional[str]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ApiKeyCreateRequest"], Optional[str]]:
        """Parse and validate API key creation fields from a JSON request body.

        Args:
            data: Parsed JSON dict from the request body.

        Returns:
            Tuple of (ApiKeyCreateRequest, None) on success, or (None, error_message) on failure.
        """
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name", "").strip()
        if not name:
            return None, "Name is required"

        expires_at = data.get("expiresAt")

        return cls(name=name, expiresAt=expires_at), None


VALID_ACCESS_LEVELS = {"admin", "develop", "operate", "view"}


@dataclass
class ProductAccessSetRequest:
    """Validated input for setting per-product access levels for a user."""

    access: List[Dict[str, str]]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ProductAccessSetRequest"], Optional[str]]:
        """Parse and validate product access entries from a JSON request body.

        Args:
            data: Parsed JSON dict containing an 'access' array.

        Returns:
            Tuple of (ProductAccessSetRequest, None) on success, or (None, error_message) on failure.
        """
        if not data:
            return None, "Request body must contain JSON data"

        access = data.get("access")
        if access is None:
            return None, "'access' field is required"
        if not isinstance(access, list):
            return None, "'access' must be an array"

        validated = []
        for i, entry in enumerate(access):
            if not isinstance(entry, dict):
                return None, f"access[{i}] must be an object"
            product_id = (entry.get("productId") or "").strip()
            level = (entry.get("level") or "").strip().lower()
            if not product_id:
                return None, f"access[{i}].productId is required"
            if level not in VALID_ACCESS_LEVELS:
                return None, f"access[{i}].level must be one of: {', '.join(sorted(VALID_ACCESS_LEVELS))}"
            validated.append({"productId": product_id, "level": level})

        return cls(access=validated), None
