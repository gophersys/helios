from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from database import Json


@dataclass
class NodeCreateRequest:
    """Request body for creating a new MTIB node."""

    name: str
    hostname: str
    type: str
    ipAddress: Optional[str] = None
    hardwareRevision: Optional[str] = None
    metadata: Optional[dict] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["NodeCreateRequest"], Optional[str]]:
        """Parse and validate JSON into a NodeCreateRequest."""
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        hostname = (data.get("hostname") or "").strip()
        node_type = (data.get("type") or "").strip().upper()
        ip_address = data.get("ipAddress")
        hardware_revision = data.get("hardwareRevision")
        metadata = data.get("metadata")

        if not name:
            return None, "Name is required"
        if not hostname:
            return None, "Hostname is required"
        if node_type not in ("MANUFACTURING", "VALIDATION"):
            return None, "Type must be MANUFACTURING or VALIDATION"

        return cls(
            name=name,
            hostname=hostname,
            type=node_type,
            ipAddress=ip_address.strip() if ip_address else None,
            hardwareRevision=hardware_revision.strip() if hardware_revision else None,
            metadata=metadata,
        ), None


def _parse_nonempty_str(data: dict, field: str) -> Tuple[Optional[str], Optional[str]]:
    """Parse an optional string field, returning error if explicitly set to empty."""
    value = data.get(field)
    if value is None:
        return None, None
    value = value.strip()
    if not value:
        return None, f"{field.replace('_', ' ').title()} cannot be empty"
    return value, None


def _parse_enum_str(data: dict, field: str, valid: set, label: str = "") -> Tuple[Optional[str], Optional[str]]:
    """Parse an optional string field and validate against an enum set."""
    value = data.get(field)
    if value is None:
        return None, None
    value = value.strip().upper()
    if value not in valid:
        display = label or field.replace("_", " ").title()
        return None, f"{display} must be {', '.join(sorted(valid))}"
    return value, None


@dataclass
class NodeUpdateRequest:
    """Request body for updating an MTIB node.

    The only operator-settable flag is ``disabled``: ``true`` takes the
    node out of rotation (the API surfaces it as ``status=MAINTENANCE``).
    Reachability is computed live — never accepted from the client.
    """

    name: Optional[str] = None
    type: Optional[str] = None
    disabled: Optional[bool] = None
    ipAddress: Optional[str] = None
    hardwareRevision: Optional[str] = None
    metadata: Optional[dict] = None
    _has_disabled: bool = False
    _has_ip: bool = False
    _has_revision: bool = False
    _has_metadata: bool = False

    _VALID_TYPES = {"MANUFACTURING", "VALIDATION"}

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["NodeUpdateRequest"], Optional[str]]:
        """Parse and validate JSON into a NodeUpdateRequest."""
        if not data:
            return None, "Request body must contain JSON data"

        name, err = _parse_nonempty_str(data, "name")
        if err:
            return None, err

        node_type, err = _parse_enum_str(data, "type", cls._VALID_TYPES)
        if err:
            return None, err

        has_disabled = "disabled" in data
        disabled: Optional[bool] = None
        if has_disabled:
            raw = data.get("disabled")
            if not isinstance(raw, bool):
                return None, "disabled must be a boolean"
            disabled = raw

        has_ip = "ipAddress" in data
        has_revision = "hardwareRevision" in data
        has_metadata = "metadata" in data

        if (
            name is None and node_type is None and not has_disabled
            and not has_ip and not has_revision and not has_metadata
        ):
            return None, "No fields to update"

        ip_address = data.get("ipAddress")
        hardware_revision = data.get("hardwareRevision")
        return cls(
            name=name,
            type=node_type,
            disabled=disabled,
            ipAddress=ip_address.strip() if ip_address else ip_address,
            hardwareRevision=hardware_revision.strip() if hardware_revision else hardware_revision,
            metadata=data.get("metadata"),
            _has_disabled=has_disabled,
            _has_ip=has_ip,
            _has_revision=has_revision,
            _has_metadata=has_metadata,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        """Build a dict of changed fields for the Prisma update call."""
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self.type is not None:
            update_data["type"] = self.type
        if self._has_disabled:
            update_data["disabled"] = bool(self.disabled)
        if self._has_ip:
            update_data["ipAddress"] = self.ipAddress
        if self._has_revision:
            update_data["hardwareRevision"] = self.hardwareRevision
        if self._has_metadata:
            update_data["metadata"] = Json(self.metadata) if self.metadata is not None else None
        return update_data
