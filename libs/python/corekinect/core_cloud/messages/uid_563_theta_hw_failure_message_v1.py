from dataclasses import dataclass
from datetime import datetime
from typing import Annotated

from corekinect.core_cloud.db_orm_v1_0 import Messagesthetahwfailtbl
from ..unified_core.db_map import db_translation
from ..unified_core.message_base import MessageBase
from ..unified_core.message_codec import MessageCodec


@dataclass(frozen=True, slots=True)
class ThetaHwFailureMessageV1(MessageBase, MessageCodec):
    __type__ = "UID_563"
    UID = 563
    _schema = {"V1_0": Messagesthetahwfailtbl, "V0_9": None}
    _device_time_fields = {"V1_0": "timeofevent", "V0_9": None}

    device_id: Annotated[int, db_translation(V1_0="deviceid", V0_9=None)] = None
    time_of_event: Annotated[datetime, db_translation(V1_0="timeofevent", V0_9=None)] = None
    record_id: Annotated[int, db_translation(V1_0="recordid", V0_9=None)] = None

    xlr_fails: Annotated[int, db_translation(V1_0="xlrfails", V0_9=None)] = None
    alt_fails: Annotated[int, db_translation(V1_0="altfails", V0_9=None)] = None
    gps_fails: Annotated[int, db_translation(V1_0="gpsfails", V0_9=None)] = None
    bms_fails: Annotated[int, db_translation(V1_0="bmsfails", V0_9=None)] = None
    ext_flash_fails: Annotated[int, db_translation(V1_0="extflashfails", V0_9=None)] = None
    batt_charger_fails: Annotated[int, db_translation(V1_0="battchargerfails", V0_9=None)] = None

    message_id: int = UID
    message_length: int = 10
    timestamp: int = 0

    def pack_items(self):
        return [
            ("B", self.message_id),
            ("H", self.message_length),
            ("I", self.timestamp),
            ("B", self.xlr_fails),
            ("B", self.alt_fails),
            ("B", self.gps_fails),
            ("B", self.bms_fails),
            ("B", self.ext_flash_fails),
            ("B", self.batt_charger_fails),
        ]

    map_xlr_fails = {
        7: "Communications failure",
    }
    map_alt_fails = {
        7: "Communications failure",
        6: "Altimeter interrupt failure",
    }
    map_gps_fails = {
        7: "Communications failure",
        6: "Crystal failure",
        5: "PVT failure",
        4: "Voltage Backup failure (VBCKP)",
    }
    map_bms_fails = {
        7: "Communications failure",
    }
    map_ext_flash_fails = {
        7: "Communications failure",
    }
    map_batt_charger_fails = {
        7: "Communications failure",
    }

    @property
    def xlr_failure_reason(self) -> str:
        return self._get_reason_from_mapping(self.xlr_fails, self.map_xlr_fails)

    @property
    def alt_failure_reason(self) -> str:
        return self._get_reason_from_mapping(self.alt_fails, self.map_alt_fails)

    @property
    def gps_failure_reason(self) -> str:
        return self._get_reason_from_mapping(self.gps_fails, self.map_gps_fails)

    @property
    def bms_failure_reason(self) -> str:
        return self._get_reason_from_mapping(self.bms_fails, self.map_bms_fails)

    @property
    def ext_flash_failure_reason(self) -> str:
        return self._get_reason_from_mapping(self.ext_flash_fails, self.map_ext_flash_fails)

    @property
    def batt_charger_failure_reason(self) -> str:
        return self._get_reason_from_mapping(self.batt_charger_fails, self.map_batt_charger_fails)
