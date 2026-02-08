from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple


@dataclass
class NodeCreateRequest:
    name: str
    hostname: str
    type: str
    ipAddress: Optional[str] = None
    hardwareRevision: Optional[str] = None
    metadata: Optional[dict] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["NodeCreateRequest"], Optional[str]]:
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


@dataclass
class NodeUpdateRequest:
    name: Optional[str] = None
    type: Optional[str] = None
    status: Optional[str] = None
    ipAddress: Optional[str] = None
    hardwareRevision: Optional[str] = None
    metadata: Optional[dict] = None
    _has_ip: bool = False
    _has_revision: bool = False
    _has_metadata: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["NodeUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name")
        if name is not None:
            name = name.strip()
            if not name:
                return None, "Name cannot be empty"
        node_type = data.get("type")
        if node_type is not None:
            node_type = node_type.strip().upper()
            if node_type not in ("MANUFACTURING", "VALIDATION"):
                return None, "Type must be MANUFACTURING or VALIDATION"
        status = data.get("status")
        if status is not None:
            status = status.strip().upper()
            if status not in ("ONLINE", "OFFLINE", "MAINTENANCE", "ERROR"):
                return None, "Status must be ONLINE, OFFLINE, MAINTENANCE, or ERROR"
        ip_address = data.get("ipAddress")
        has_ip = "ipAddress" in data
        hardware_revision = data.get("hardwareRevision")
        has_revision = "hardwareRevision" in data
        metadata = data.get("metadata")
        has_metadata = "metadata" in data

        if name is None and node_type is None and status is None and not has_ip and not has_revision and not has_metadata:
            return None, "No fields to update"

        return cls(
            name=name,
            type=node_type,
            status=status,
            ipAddress=ip_address.strip() if ip_address else ip_address,
            hardwareRevision=hardware_revision.strip() if hardware_revision else hardware_revision,
            metadata=metadata,
            _has_ip=has_ip,
            _has_revision=has_revision,
            _has_metadata=has_metadata,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self.type is not None:
            update_data["type"] = self.type
        if self.status is not None:
            update_data["status"] = self.status
        if self._has_ip:
            update_data["ipAddress"] = self.ipAddress
        if self._has_revision:
            update_data["hardwareRevision"] = self.hardwareRevision
        if self._has_metadata:
            update_data["metadata"] = self.metadata
        return update_data
