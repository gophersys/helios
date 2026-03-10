"""Request/response types for FixtureDesign endpoints."""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class FixtureDesignCreateRequest:
    """POST /v2/validation/designs - Create a new fixture design."""

    name: str
    product: str
    revision: str
    capabilities: List[str]
    profile_template: Dict[str, Any]
    schematic_url: Optional[str] = None
    bom_url: Optional[str] = None
    assembly_guide: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FixtureDesignCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body required"

        name = (data.get("name") or "").strip()
        if not name:
            return None, "name is required"

        product = (data.get("product") or "").strip().lower()
        if not product:
            return None, "product is required"

        revision = (data.get("revision") or "").strip()
        if not revision:
            return None, "revision is required"

        capabilities = data.get("capabilities", [])
        if not isinstance(capabilities, list):
            return None, "capabilities must be an array"

        profile_template = data.get("profileTemplate", {})
        if not isinstance(profile_template, dict):
            return None, "profileTemplate must be an object"

        return cls(
            name=name,
            product=product,
            revision=revision,
            capabilities=[str(c).strip() for c in capabilities],
            profile_template=profile_template,
            schematic_url=data.get("schematicUrl"),
            bom_url=data.get("bomUrl"),
            assembly_guide=data.get("assemblyGuide"),
            notes=data.get("notes"),
        ), None


@dataclass
class FixtureDesignUpdateRequest:
    """PATCH /v2/validation/designs/<id> - Update a fixture design."""

    _has_name: bool = False
    _has_capabilities: bool = False
    _has_profile_template: bool = False
    _has_schematic_url: bool = False
    _has_bom_url: bool = False
    _has_assembly_guide: bool = False
    _has_notes: bool = False

    name: Optional[str] = None
    capabilities: Optional[List[str]] = None
    profile_template: Optional[Dict[str, Any]] = None
    schematic_url: Optional[str] = None
    bom_url: Optional[str] = None
    assembly_guide: Optional[str] = None
    notes: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["FixtureDesignUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body required"

        inst = cls()

        if "name" in data:
            inst._has_name = True
            inst.name = (data["name"] or "").strip() or None

        if "capabilities" in data:
            inst._has_capabilities = True
            caps = data["capabilities"]
            if caps is not None and not isinstance(caps, list):
                return None, "capabilities must be an array"
            inst.capabilities = [str(c).strip() for c in caps] if caps else []

        if "profileTemplate" in data:
            inst._has_profile_template = True
            tpl = data["profileTemplate"]
            if tpl is not None and not isinstance(tpl, dict):
                return None, "profileTemplate must be an object"
            inst.profile_template = tpl

        if "schematicUrl" in data:
            inst._has_schematic_url = True
            inst.schematic_url = data["schematicUrl"]

        if "bomUrl" in data:
            inst._has_bom_url = True
            inst.bom_url = data["bomUrl"]

        if "assemblyGuide" in data:
            inst._has_assembly_guide = True
            inst.assembly_guide = data["assemblyGuide"]

        if "notes" in data:
            inst._has_notes = True
            inst.notes = data["notes"]

        return inst, None

    def to_update_data(self) -> Dict[str, Any]:
        """Return dict of fields to update in DB."""
        data = {}
        if self._has_name and self.name:
            data["name"] = self.name
        if self._has_capabilities:
            data["capabilities"] = self.capabilities
        if self._has_profile_template:
            data["profileTemplate"] = self.profile_template
        if self._has_schematic_url:
            data["schematicUrl"] = self.schematic_url
        if self._has_bom_url:
            data["bomUrl"] = self.bom_url
        if self._has_assembly_guide:
            data["assemblyGuide"] = self.assembly_guide
        if self._has_notes:
            data["notes"] = self.notes
        return data
