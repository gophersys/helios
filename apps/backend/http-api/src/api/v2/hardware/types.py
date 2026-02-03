from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class ComponentCreateRequest:
    name: str
    category: str
    manufacturer: str
    partNumber: str
    description: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ComponentCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        category = (data.get("category") or "").strip()
        manufacturer = (data.get("manufacturer") or "").strip()
        part_number = (data.get("partNumber") or "").strip()
        description = data.get("description")

        if not name:
            return None, "Name is required"
        if category not in ("SOM", "CARRIER_BOARD", "ACCESSORY"):
            return None, "Category must be SOM, CARRIER_BOARD, or ACCESSORY"
        if not manufacturer:
            return None, "Manufacturer is required"
        if not part_number:
            return None, "Part number is required"

        return cls(
            name=name,
            category=category,
            manufacturer=manufacturer,
            partNumber=part_number,
            description=description.strip() if description else None,
        ), None


@dataclass
class ComponentUpdateRequest:
    name: Optional[str] = None
    category: Optional[str] = None
    manufacturer: Optional[str] = None
    partNumber: Optional[str] = None
    description: Optional[str] = None
    _has_description: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ComponentUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name")
        if name is not None:
            name = name.strip()
        category = data.get("category")
        if category is not None:
            category = category.strip()
            if category not in ("SOM", "CARRIER_BOARD", "ACCESSORY"):
                return None, "Category must be SOM, CARRIER_BOARD, or ACCESSORY"
        manufacturer = data.get("manufacturer")
        if manufacturer is not None:
            manufacturer = manufacturer.strip()
        part_number = data.get("partNumber")
        if part_number is not None:
            part_number = part_number.strip()
        description = data.get("description")
        has_description = "description" in data

        if name is None and category is None and manufacturer is None and part_number is None and not has_description:
            return None, "No fields to update"

        return cls(
            name=name,
            category=category,
            manufacturer=manufacturer,
            partNumber=part_number,
            description=description.strip() if description else description,
            _has_description=has_description,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self.category is not None:
            update_data["category"] = self.category
        if self.manufacturer is not None:
            update_data["manufacturer"] = self.manufacturer
        if self.partNumber is not None:
            update_data["partNumber"] = self.partNumber
        if self._has_description:
            update_data["description"] = self.description
        return update_data


@dataclass
class RevisionCreateRequest:
    version: str
    status: str = "ACTIVE"
    releaseNotes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["RevisionCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        version = (data.get("version") or "").strip()
        status = (data.get("status") or "ACTIVE").strip()
        release_notes = data.get("releaseNotes")

        if not version:
            return None, "Version is required"
        if status not in ("ACTIVE", "DEPRECATED", "EOL"):
            return None, "Status must be ACTIVE, DEPRECATED, or EOL"

        return cls(
            version=version,
            status=status,
            releaseNotes=release_notes.strip() if release_notes else None,
        ), None


@dataclass
class RevisionUpdateRequest:
    version: Optional[str] = None
    status: Optional[str] = None
    releaseNotes: Optional[str] = None
    _has_release_notes: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["RevisionUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        version = data.get("version")
        if version is not None:
            version = version.strip()
        status = data.get("status")
        if status is not None:
            status = status.strip()
            if status not in ("ACTIVE", "DEPRECATED", "EOL"):
                return None, "Status must be ACTIVE, DEPRECATED, or EOL"
        release_notes = data.get("releaseNotes")
        has_release_notes = "releaseNotes" in data

        if version is None and status is None and not has_release_notes:
            return None, "No fields to update"

        return cls(
            version=version,
            status=status,
            releaseNotes=release_notes.strip() if release_notes else release_notes,
            _has_release_notes=has_release_notes,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.version is not None:
            update_data["version"] = self.version
        if self.status is not None:
            update_data["status"] = self.status
        if self._has_release_notes:
            update_data["releaseNotes"] = self.releaseNotes
        return update_data


@dataclass
class AssemblyCreateRequest:
    name: str
    description: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["AssemblyCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        description = data.get("description")

        if not name:
            return None, "Name is required"

        return cls(
            name=name,
            description=description.strip() if description else None,
        ), None


@dataclass
class AssemblyUpdateRequest:
    name: Optional[str] = None
    description: Optional[str] = None
    _has_description: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["AssemblyUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        name = data.get("name")
        if name is not None:
            name = name.strip()
        description = data.get("description")
        has_description = "description" in data

        if name is None and not has_description:
            return None, "No fields to update"

        return cls(
            name=name,
            description=description.strip() if description else description,
            _has_description=has_description,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.name is not None:
            update_data["name"] = self.name
        if self._has_description:
            update_data["description"] = self.description
        return update_data


@dataclass
class BomItem:
    hardwareRevisionId: str
    quantity: int = 1


@dataclass
class AssemblyRevisionCreateRequest:
    version: str
    status: str = "ACTIVE"
    releaseNotes: Optional[str] = None
    bom: List[BomItem] = None  # type: ignore

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["AssemblyRevisionCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        version = (data.get("version") or "").strip()
        status = (data.get("status") or "ACTIVE").strip()
        release_notes = data.get("releaseNotes")
        bom_raw = data.get("bom", [])

        if not version:
            return None, "Version is required"
        if status not in ("ACTIVE", "DEPRECATED", "EOL"):
            return None, "Status must be ACTIVE, DEPRECATED, or EOL"

        bom_items: List[BomItem] = []
        if bom_raw:
            if not isinstance(bom_raw, list):
                return None, "BOM must be an array"
            for item in bom_raw:
                hr_id = item.get("hardwareRevisionId")
                if not hr_id:
                    return None, "Each BOM item must have hardwareRevisionId"
                qty = item.get("quantity", 1)
                if not isinstance(qty, int) or qty < 1:
                    return None, "Quantity must be a positive integer"
                bom_items.append(BomItem(hardwareRevisionId=hr_id, quantity=qty))

        return cls(
            version=version,
            status=status,
            releaseNotes=release_notes.strip() if release_notes else None,
            bom=bom_items,
        ), None


@dataclass
class AssemblyRevisionUpdateRequest:
    version: Optional[str] = None
    status: Optional[str] = None
    releaseNotes: Optional[str] = None
    bom: Optional[List[BomItem]] = None
    _has_release_notes: bool = False
    _has_bom: bool = False

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["AssemblyRevisionUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"

        version = data.get("version")
        if version is not None:
            version = version.strip()
        status = data.get("status")
        if status is not None:
            status = status.strip()
            if status not in ("ACTIVE", "DEPRECATED", "EOL"):
                return None, "Status must be ACTIVE, DEPRECATED, or EOL"
        release_notes = data.get("releaseNotes")
        has_release_notes = "releaseNotes" in data
        has_bom = "bom" in data
        bom_raw = data.get("bom")
        bom_items: Optional[List[BomItem]] = None

        if has_bom and bom_raw is not None:
            if not isinstance(bom_raw, list):
                return None, "BOM must be an array"
            bom_items = []
            for item in bom_raw:
                hr_id = item.get("hardwareRevisionId")
                if not hr_id:
                    return None, "Each BOM item must have hardwareRevisionId"
                qty = item.get("quantity", 1)
                if not isinstance(qty, int) or qty < 1:
                    return None, "Quantity must be a positive integer"
                bom_items.append(BomItem(hardwareRevisionId=hr_id, quantity=qty))

        if version is None and status is None and not has_release_notes and not has_bom:
            return None, "No fields to update"

        return cls(
            version=version,
            status=status,
            releaseNotes=release_notes.strip() if release_notes else release_notes,
            bom=bom_items,
            _has_release_notes=has_release_notes,
            _has_bom=has_bom,
        ), None

    def to_update_data(self) -> Dict[str, Any]:
        update_data: Dict[str, Any] = {}
        if self.version is not None:
            update_data["version"] = self.version
        if self.status is not None:
            update_data["status"] = self.status
        if self._has_release_notes:
            update_data["releaseNotes"] = self.releaseNotes
        return update_data
