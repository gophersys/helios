from dataclasses import dataclass
from typing import Annotated, Optional, ClassVar, Any

from ..unified_core.conf_message_base import ConfigMessageBase
from ..unified_core.api_map import api_translation
from ..unified_core.db_map import db_translation
from ..unified_core.message_base import MessageBase
from ..unified_core.message_codec import MessageCodec

from corekinect.core_cloud.db_orm_v1_0 import Configgroundtbl as v1_Configgroundtbl


@dataclass(frozen=True, slots=True)
class GroundModeConfigV2(ConfigMessageBase, MessageBase, MessageCodec):
    """
    Ground Mode Config V2:
      * READ: MessageBase.get_* (DB)
      * SEND: ConfigMessageBase.send_via_api() with explicit api_translation per field
      * BINARY: BinarySerializable for base64 payloads (v0.9 etc.) via binary_layout()
    """

    __type__: ClassVar[str] = "UID_538"
    UID: ClassVar[int] = 0x36  # v0.9 uses 0x36
    api_set_endpoint: ClassVar[tuple[str, str]] = ("PUT", "/System/Devices/Configurations/GroundModeV2")

    # ORM bindings for both schemas
    _orm_model_v1 = v1_Configgroundtbl

    # Header-ish fields used by packing
    message_id: int = UID
    message_length: int = 0
    timestamp: int = 0
    reserved: int = 0

    gps_heartbeat_period_minutes: Annotated[
        Optional[int],
        db_translation(V1_0="gpsheartbeatperiod", V0_9="GpsHeartbeatPeriod"),
        api_translation(api="gpsHeartbeatPeriod", coerce=int),
    ] = None
    continuous_motion_period_seconds: Annotated[
        Optional[int],
        db_translation(V1_0="continuousmotionperiod", V0_9="ContMotionPeriod"),
        api_translation(api="continuousMotionPeriod", coerce=int),
    ] = None
    stop_motion_timeout_seconds: Annotated[
        Optional[int],
        db_translation(V1_0="stopmotiontimeout", V0_9="MotionStopTimeout"),
        api_translation(api="stopMotionTimeout", coerce=int),
    ] = None
    heartbeat_acquisition_timeout_seconds: Annotated[
        Optional[int],
        db_translation(V1_0="heartbeatacquisitiontimeout", V0_9="HeartbeatAcqTimeout"),
        api_translation(api="heartbeatAcquisitionTimeout", coerce=int),
    ] = None
    stop_motion_acquisition_timeout_seconds: Annotated[
        Optional[int],
        db_translation(V1_0="motionacquisitiontimeout", V0_9="MotionAcqTimeout"),
        api_translation(api="motionAcquisitionTimeout", coerce=int),
    ] = None
    motion_acceleration_threshold: Annotated[
        Optional[int],
        db_translation(V1_0="xlrmotionthreshold", V0_9="MotionThreshold"),
        api_translation(api="xlrMotionThreshold", coerce=int),
    ] = None
    motion_acceleration_duration: Annotated[
        Optional[int],
        db_translation(V1_0="xlrmotionduration", V0_9="MotionDuration"),
        api_translation(api="xlrMotionDuration", coerce=int),
    ] = None
    start_motion_window_start_seconds: Annotated[
        Optional[int],
        db_translation(V1_0="startmotionwindowstart", V0_9="StartMotionWindowStart"),
        api_translation(api="startMotionWindowStart", coerce=int),
    ] = None
    start_motion_window_end_seconds: Annotated[
        Optional[int],
        db_translation(V1_0="startmotionwindowend", V0_9="StartMotionWindowEnd"),
        api_translation(api="startMotionWindowEnd", coerce=int),
    ] = None
    motion_acquisition_on_time_seconds: Annotated[
        Optional[int],
        db_translation(V1_0="motionacquisitionontime", V0_9="MotionAcqOnTime"),
        api_translation(api="motionAcquisitionOnTime", coerce=int),
    ] = None
    motion_initial_acquisition_on_time_seconds: Annotated[
        Optional[int],
        db_translation(V1_0="motioninitialacquisitionontime", V0_9="MotionInitAcqOnTime"),
        api_translation(api="motionInitialAcquisitionOnTime", coerce=int),
    ] = None

    @classmethod
    def binary_layout(cls):
        # Using the exact spec you posted (v0.9 variant)
        # (name, struct_code) order matters
        return [
            ("message_id", "B"),
            ("message_length", "H"),
            ("timestamp", "I"),
            ("gps_heartbeat_period_minutes", "H"),
            ("continuous_motion_period_seconds", "H"),
            ("stop_motion_timeout_seconds", "B"),
            ("heartbeat_acquisition_timeout_seconds", "B"),
            ("stop_motion_acquisition_timeout_seconds", "B"),
            ("motion_acceleration_threshold", "B"),
            ("motion_acceleration_duration", "B"),
            ("start_motion_window_start_seconds", "B"),
            ("start_motion_window_end_seconds", "B"),
            ("motion_acquisition_on_time_seconds", "B"),
            ("motion_initial_acquisition_on_time_seconds", "B"),
            ("reserved", "I"),
        ]

    def pack_items(self):
        return [
            ("B", self.message_id),
            ("H", 0),
            ("I", self.timestamp),
            ("H", self.gps_heartbeat_period_minutes),
            ("H", self.continuous_motion_period_seconds),
            ("B", self.stop_motion_timeout_seconds),
            ("B", self.heartbeat_acquisition_timeout_seconds),
            ("B", self.stop_motion_acquisition_timeout_seconds),
            ("B", self.motion_acceleration_threshold),
            ("B", self.motion_acceleration_duration),
            ("B", self.start_motion_window_start_seconds),
            ("B", self.start_motion_window_end_seconds),
            ("B", self.motion_acquisition_on_time_seconds),
            ("B", self.motion_initial_acquisition_on_time_seconds),
            ("I", self.reserved),
        ]
