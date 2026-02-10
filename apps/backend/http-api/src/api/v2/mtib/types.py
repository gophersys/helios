from dataclasses import dataclass
from typing import List, Optional, Tuple


@dataclass
class AppIdMapping:
    """Structure for AppId to JLINK mapping"""

    jlink: int
    appId: int


@dataclass
class MtibRegisterRequest:
    """Request structure for registering a MTIB"""

    name: str
    hostname: str
    mtibType: str
    features: List[str]
    appIds: List[AppIdMapping]

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["MtibRegisterRequest"], Optional[str]]:
        """Parse JSON data into request object with validation"""
        if not data:
            return None, "Request body must contain JSON data"

        name = (data.get("name") or "").strip()
        if not name:
            return None, "Field 'name' is required"

        # Validate name starts with "verdin-"
        if not name.startswith("verdin-"):
            return None, "MTIB name must start with 'verdin-'"

        hostname = (data.get("hostname") or "").strip()
        if not hostname:
            return None, "Field 'hostname' is required"

        mtib_type = (data.get("mtibType") or "").strip()
        if not mtib_type:
            return None, "Field 'mtibType' is required"

        # Validate mtib type
        if mtib_type not in ["validation", "manufacturing"]:
            return None, "mtibType must be either 'validation' or 'manufacturing'"

        features = data.get("features", [])
        if not isinstance(features, list):
            return None, "Field 'features' must be a list"

        # Validate features
        valid_features = ["joulescope", "motion"]
        for feature in features:
            if feature.lower() not in valid_features:
                return None, f"Invalid feature '{feature}'. Valid features are: {', '.join(valid_features)}"

        app_ids = data.get("appIds", [])
        if not isinstance(app_ids, list):
            return None, "Field 'appIds' must be a list"

        # Validate appId mappings
        app_id_mappings = []
        for mapping in app_ids:
            if not isinstance(mapping, dict):
                return None, "Each appId mapping must be an object"

            jlink = mapping.get("jlink")
            app_id = mapping.get("appId")

            if jlink is None or not isinstance(jlink, int):
                return None, "Each appId mapping must have a valid 'jlink' number"

            if app_id is None or not isinstance(app_id, int):
                return None, "Each appId mapping must have a valid 'appId' number"

            app_id_mappings.append(AppIdMapping(jlink=jlink, appId=app_id))

        return cls(name=name, hostname=hostname, mtibType=mtib_type, features=features, appIds=app_id_mappings), None


@dataclass
class MtibUnregisterRequest:
    """Request structure for unregistering a MTIB"""

    hostname: str

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["MtibUnregisterRequest"], Optional[str]]:
        """Parse JSON data into request object with validation"""
        if not data:
            return None, "Request body must contain JSON data"

        hostname = (data.get("hostname") or "").strip()
        if not hostname:
            return None, "Field 'hostname' is required"

        return cls(hostname=hostname), None


@dataclass
class MtibResponse:
    """Response structure for MTIB data"""

    hostname: str
    name: str
    type: str
    features: List[str]

    @classmethod
    def from_mtib(cls, mtib) -> "MtibResponse":
        return cls(
            hostname=mtib.id,
            name=mtib.name,
            type=mtib.type.lower(),
            features=[feature.lower() for feature in mtib.features],
        )
