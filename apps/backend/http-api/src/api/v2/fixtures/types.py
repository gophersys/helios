from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FixtureCreateRequest:
    name: str
    productId: str
    type: str  # MANUFACTURING or VALIDATION
    description: Optional[str] = None
    metadata: Optional[dict] = None
    slots: Optional[List[dict]] = None  # [{slotIndex: 0, label: "Slot 1"}, ...]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FixtureCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        product_id = (data.get("productId") or "").strip()
        fixture_type = (data.get("type") or "").strip().upper()

        if not name:
            return None, "Name is required"
        if not product_id:
            return None, "Product ID is required"
        if fixture_type not in ("MANUFACTURING", "VALIDATION"):
            return None, "Type must be MANUFACTURING or VALIDATION"

        description = data.get("description")
        metadata = data.get("metadata")
        slots = data.get("slots")
        if slots is not None:
            if not isinstance(slots, list):
                return None, "Slots must be an array"
            for i, s in enumerate(slots):
                if not isinstance(s, dict):
                    return None, f"Slot {i} must be an object"
                if "slotIndex" not in s:
                    return None, f"Slot {i} must have a slotIndex"

        return cls(
            name=name,
            productId=product_id,
            type=fixture_type,
            description=description.strip() if description else None,
            metadata=metadata,
            slots=slots,
        ), None


@dataclass
class FixtureUpdateRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    active: Optional[bool] = None
    metadata: Optional[dict] = None
    _has_description: bool = False
    _has_metadata: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FixtureUpdateRequest"], Optional[str]]:
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

        metadata = data.get("metadata")
        has_metadata = "metadata" in data

        if name is None and not has_description and active is None and not has_metadata:
            return None, "No fields to update"

        return cls(
            name=name,
            description=description.strip() if description else description,
            active=active,
            metadata=metadata,
            _has_description=has_description,
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
        if self._has_metadata:
            update_data["metadata"] = self.metadata
        return update_data


@dataclass
class SlotCreateRequest:
    slotIndex: int
    label: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["SlotCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        slot_index = data.get("slotIndex")
        if slot_index is None:
            return None, "slotIndex is required"
        if not isinstance(slot_index, int) or slot_index < 0:
            return None, "slotIndex must be a non-negative integer"

        label = data.get("label")

        return cls(
            slotIndex=slot_index,
            label=label.strip() if label else None,
        ), None


@dataclass
class SlotUpdateRequest:
    label: Optional[str] = None
    active: Optional[bool] = None
    _has_label: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["SlotUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        label = data.get("label")
        has_label = "label" in data

        active = data.get("active")
        if active is not None and not isinstance(active, bool):
            return None, "Active must be a boolean"

        if not has_label and active is None:
            return None, "No fields to update"

        return cls(
            label=label.strip() if label else label,
            active=active,
            _has_label=has_label,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self._has_label:
            update_data["label"] = self.label
        if self.active is not None:
            update_data["active"] = self.active
        return update_data


@dataclass
class SlotAssignRequest:
    nodeId: Optional[str] = None  # null to unassign

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["SlotAssignRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        node_id = data.get("nodeId")
        if node_id is not None:
            node_id = node_id.strip()
            if not node_id:
                return None, "nodeId cannot be an empty string"

        return cls(nodeId=node_id), None
