from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class DeploymentCreateRequest:
    name: str
    fixtureId: str
    config: Optional[dict] = None
    version: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["DeploymentCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        name = (data.get("name") or "").strip()
        fixture_id = (data.get("fixtureId") or "").strip()
        if not name:
            return None, "Name is required"
        if not fixture_id:
            return None, "Fixture ID is required"
        config = data.get("config")
        version = data.get("version")
        return cls(
            name=name,
            fixtureId=fixture_id,
            config=config,
            version=version.strip() if version else None,
        ), None
