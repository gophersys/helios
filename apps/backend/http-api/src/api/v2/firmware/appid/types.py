# Standard includes
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

# 3rd party includes
from flask import request

# -------------------------------------------------
#                                        Base Types
# -------------------------------------------------


@dataclass
class FirmwareAppIDBase:
    """Base class for firmware appid data"""

    appId: int
    name: str
    chipset: str
    target: str
    notes: Optional[str] = None


# -------------------------------------------------
#                                      Input Types
# -------------------------------------------------


@dataclass
class FirmwareAppIDCreateRequest:
    """Request structure for creating a firmware appid"""

    appId: int
    name: str
    chipset: str
    target: str
    notes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple["FirmwareAppIDCreateRequest", Optional[str]]:
        """Parse JSON data into request object with validation"""
        if not data:
            return None, "Request body must contain JSON data"

        app_id = data.get("appId")
        if not app_id:
            return None, "Field 'appId' is required"

        name = data.get("name")
        if not name:
            return None, "Field 'name' is required"

        chipset = data.get("chipset")
        if not chipset:
            return None, "Field 'chipset' is required"

        target = data.get("target")
        if not target:
            return None, "Field 'target' is required"

        notes = data.get("notes")  # Optional field

        return cls(appId=app_id, name=name, chipset=chipset, target=target, notes=notes), None


@dataclass
class FirmwareAppIDUpdateRequest:
    """Request structure for updating a firmware appid"""

    name: Optional[str] = None
    chipset: Optional[str] = None
    target: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple["FirmwareAppIDUpdateRequest", Optional[str]]:
        """Parse JSON data into request object with validation"""
        if not data:
            return None, "Request body must contain JSON data"

        # All fields are optional for updates
        return (
            cls(
                name=data.get("name"),
                chipset=data.get("chipset"),
                target=data.get("target"),
                notes=data.get("notes"),
            ),
            None,
        )


@dataclass
class FirmwareAppIDListQuery:
    """Query parameters for listing firmware appids"""

    chipset: Optional[str] = None
    target: Optional[str] = None
    limit: Optional[int] = None
    offset: int = 0

    @classmethod
    def from_request(cls) -> "FirmwareAppIDListQuery":
        """Parse query parameters from Flask request"""
        return cls(
            chipset=request.args.get("chipset"),
            target=request.args.get("target"),
            limit=request.args.get("limit", type=int),
            offset=request.args.get("offset", type=int, default=0),
        )


# -------------------------------------------------
#                                     Output Types
# -------------------------------------------------


@dataclass
class FirmwareAppIDResponse:
    """Response structure for firmware appid data"""

    appId: int
    name: str
    chipset: str
    target: str
    notes: Optional[str]
    createdAt: str
    updatedAt: str

    @classmethod
    def from_appid(cls, appid) -> "FirmwareAppIDResponse":
        """Create response from Prisma AppId model"""
        return cls(
            appId=appid.appId,
            name=appid.name,
            chipset=appid.chipset,
            target=appid.target,
            notes=appid.notes,
            createdAt=appid.createdAt.isoformat(),
            updatedAt=appid.updatedAt.isoformat(),
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON response"""
        return {
            "appId": self.appId,
            "name": self.name,
            "chipset": self.chipset,
            "target": self.target,
            "notes": self.notes,
            "createdAt": self.createdAt,
            "updatedAt": self.updatedAt,
        }


# -------------------------------------------------
#                                   Helper Functions
# -------------------------------------------------


def build_where_clause(query: FirmwareAppIDListQuery) -> Dict[str, Any]:
    """Build Prisma where clause from query parameters"""
    where_clause = {}
    if query.chipset:
        where_clause["chipset"] = query.chipset
    if query.target:
        where_clause["target"] = query.target
    return where_clause


def build_update_data(update_request: FirmwareAppIDUpdateRequest) -> Dict[str, Any]:
    """Build update data dictionary from update request"""
    update_data = {}
    if update_request.name is not None:
        update_data["name"] = update_request.name
    if update_request.chipset is not None:
        update_data["chipset"] = update_request.chipset
    if update_request.target is not None:
        update_data["target"] = update_request.target
    if update_request.notes is not None:
        update_data["notes"] = update_request.notes
    return update_data
