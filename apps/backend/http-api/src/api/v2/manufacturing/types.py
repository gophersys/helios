"""Request types for manufacturing endpoints."""

from dataclasses import dataclass, field
from typing import Optional, Tuple


@dataclass
class ManufacturingConfigCreateRequest:
    boardRevisionId: str
    stages: list
    enabled: bool = False
    firmwareSource: str = "latest_build"
    firmwareSetId: Optional[str] = None
    personalizationConfig: Optional[dict] = None
    passCriteria: Optional[dict] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ManufacturingConfigCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        board_rev_id = (data.get("boardRevisionId") or "").strip()
        if not board_rev_id:
            return None, "boardRevisionId is required"
        stages = data.get("stages")
        if stages is None:
            return None, "stages is required"
        return cls(
            boardRevisionId=board_rev_id,
            stages=stages,
            enabled=bool(data.get("enabled", False)),
            firmwareSource=data.get("firmwareSource", "latest_build"),
            firmwareSetId=data.get("firmwareSetId"),
            personalizationConfig=data.get("personalizationConfig"),
            passCriteria=data.get("passCriteria"),
        ), None


@dataclass
class ManufacturingConfigUpdateRequest:
    _has_enabled: bool = False
    enabled: Optional[bool] = None
    stages: Optional[list] = None
    firmwareSource: Optional[str] = None
    firmwareSetId: Optional[str] = None
    personalizationConfig: Optional[dict] = None
    passCriteria: Optional[dict] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ManufacturingConfigUpdateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        req = cls()
        if "enabled" in data:
            req._has_enabled = True
            req.enabled = bool(data["enabled"])
        if "stages" in data:
            req.stages = data["stages"]
        if "firmwareSource" in data:
            req.firmwareSource = data["firmwareSource"]
        if "firmwareSetId" in data:
            req.firmwareSetId = data["firmwareSetId"]
        if "personalizationConfig" in data:
            req.personalizationConfig = data["personalizationConfig"]
        if "passCriteria" in data:
            req.passCriteria = data["passCriteria"]
        return req, None

    def to_update_data(self) -> dict:
        from database import Json
        d = {}
        if self._has_enabled:
            d["enabled"] = self.enabled
        if self.stages is not None:
            d["stages"] = Json(self.stages)
        if self.firmwareSource is not None:
            d["firmwareSource"] = self.firmwareSource
        if self.firmwareSetId is not None:
            d["firmwareSetId"] = self.firmwareSetId
        if self.personalizationConfig is not None:
            d["personalizationConfig"] = Json(self.personalizationConfig)
        if self.passCriteria is not None:
            d["passCriteria"] = Json(self.passCriteria)
        return d


@dataclass
class SessionCreateRequest:
    productId: str
    fixtureId: str
    config: Optional[dict] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["SessionCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        product_id = (data.get("productId") or "").strip()
        if not product_id:
            return None, "productId is required"
        fixture_id = (data.get("fixtureId") or "").strip()
        if not fixture_id:
            return None, "fixtureId is required"
        return cls(
            productId=product_id,
            fixtureId=fixture_id,
            config=data.get("config"),
        ), None


@dataclass
class PanelCreateRequest:
    qrCode: str
    unitCount: int

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["PanelCreateRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        qr_code = (data.get("qrCode") or "").strip()
        if not qr_code:
            return None, "qrCode is required"
        unit_count = data.get("unitCount")
        if unit_count is None or not isinstance(unit_count, int) or unit_count < 1:
            return None, "unitCount must be a positive integer"
        return cls(qrCode=qr_code, unitCount=unit_count), None


# Reporter callback types

@dataclass
class ReportPanelStartRequest:
    qrCode: str
    unitCount: int

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportPanelStartRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        qr_code = (data.get("qrCode") or "").strip()
        if not qr_code:
            return None, "qrCode is required"
        unit_count = data.get("unitCount")
        if unit_count is None or not isinstance(unit_count, int) or unit_count < 1:
            return None, "unitCount must be a positive integer"
        return cls(qrCode=qr_code, unitCount=unit_count), None


@dataclass
class ReportUnitStartRequest:
    panelId: str
    slotIndex: int
    slotId: str
    serialNumber: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportUnitStartRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        panel_id = (data.get("panelId") or "").strip()
        if not panel_id:
            return None, "panelId is required"
        slot_index = data.get("slotIndex")
        if slot_index is None or not isinstance(slot_index, int):
            return None, "slotIndex must be an integer"
        slot_id = (data.get("slotId") or "").strip()
        if not slot_id:
            return None, "slotId is required"
        return cls(
            panelId=panel_id,
            slotIndex=slot_index,
            slotId=slot_id,
            serialNumber=data.get("serialNumber"),
        ), None


VALID_UNIT_STATUSES = {"PASSED", "FAILED", "ERROR"}


@dataclass
class ReportStageResultRequest:
    unitId: str
    stageName: str
    status: str
    durationMs: Optional[int] = None
    measurements: Optional[dict] = None
    errorMessage: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportStageResultRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        unit_id = (data.get("unitId") or "").strip()
        if not unit_id:
            return None, "unitId is required"
        stage_name = (data.get("stageName") or "").strip()
        if not stage_name:
            return None, "stageName is required"
        status = (data.get("status") or "").strip()
        if not status:
            return None, "status is required"
        return cls(
            unitId=unit_id,
            stageName=stage_name,
            status=status,
            durationMs=data.get("durationMs"),
            measurements=data.get("measurements"),
            errorMessage=data.get("errorMessage"),
        ), None


@dataclass
class ReportUnitResultRequest:
    unitId: str
    status: str
    serialNumber: Optional[str] = None
    durationMs: Optional[int] = None
    errorMessage: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportUnitResultRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        unit_id = (data.get("unitId") or "").strip()
        if not unit_id:
            return None, "unitId is required"
        status = (data.get("status") or "").strip()
        if not status:
            return None, "status is required"
        if status not in VALID_UNIT_STATUSES:
            return None, f"status must be one of: {', '.join(sorted(VALID_UNIT_STATUSES))}"
        return cls(
            unitId=unit_id,
            status=status,
            serialNumber=data.get("serialNumber"),
            durationMs=data.get("durationMs"),
            errorMessage=data.get("errorMessage"),
        ), None


VALID_PANEL_STATUSES = {"PASSED", "FAILED", "CANCELLED"}


@dataclass
class ReportPanelCompleteRequest:
    panelId: str
    status: str
    passedUnits: int = 0
    failedUnits: int = 0
    durationMs: Optional[int] = None

    @classmethod
    def from_json(cls, data: dict) -> Tuple[Optional["ReportPanelCompleteRequest"], Optional[str]]:
        if not data:
            return None, "Request body must contain JSON data"
        panel_id = (data.get("panelId") or "").strip()
        if not panel_id:
            return None, "panelId is required"
        status = (data.get("status") or "").strip()
        if not status:
            return None, "status is required"
        if status not in VALID_PANEL_STATUSES:
            return None, f"status must be one of: {', '.join(sorted(VALID_PANEL_STATUSES))}"
        return cls(
            panelId=panel_id,
            status=status,
            passedUnits=data.get("passedUnits", 0),
            failedUnits=data.get("failedUnits", 0),
            durationMs=data.get("durationMs"),
        ), None
