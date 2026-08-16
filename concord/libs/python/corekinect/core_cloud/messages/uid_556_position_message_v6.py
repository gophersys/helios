from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Optional

from corekinect.utils.bits.ops import get_bits
from corekinect.utils.units.length import meters_to_feet, feet_to_meters
from corekinect.utils.units.temp import celsius_to_fahrenheit
from ..unified_core.db_map import db_translation
from ..unified_core.message_base import MessageBase
from ..unified_core.message_codec import MessageCodec
from corekinect.core_cloud.db_orm_v1_0 import Messagespositionv5tbl


@dataclass(frozen=True, slots=True)
class PositionMsgV6(MessageBase, MessageCodec):
    """
    Position V6 domain model with literal DB mappings for both schemas (V1_0/V0_9),
    plus convenience bitfield-derived properties.
    """

    __type__ = "UID_556"
    UID = 556
    _schema = {"V1_0": Messagespositionv5tbl}
    _device_time_fields = {"V1_0": "timeoffix", "V0_9": "TimeOfFix"}

    # Base/universal fields
    device_id: Annotated[int, db_translation(V1_0="deviceid", V0_9="DeviceId")] = None
    time_of_record: Annotated[datetime, db_translation(V1_0="timeofrecord", V0_9="TimeReceived")] = None
    record_id: Annotated[int, db_translation(V1_0="recordid", V0_9="CheckinId")] = None

    # Status/flags & booleans
    flags: Annotated[int, db_translation(V1_0="flags", V0_9="Flags")] = None
    is_in_motion: Annotated[bool, db_translation(V1_0="isinmotion", V0_9="IsInMotion")] = None
    gnss_fix_valid: Annotated[bool, db_translation(V1_0="gnssfixvalid", V0_9="IsValidGpsFix")] = None
    gnss_fix_ok: Annotated[bool, db_translation(V1_0="gnssfixok", V0_9="IsValidGpsFix")] = None
    valid_date: Annotated[bool, db_translation(V1_0="validdate", V0_9="IsGpsIndoors")] = None
    valid_time: Annotated[bool, db_translation(V1_0="validtime", V0_9="IsGpsIndoors")] = None
    conf_date: Annotated[bool, db_translation(V1_0="confdate", V0_9="IsGpsIndoors")] = None
    conf_time: Annotated[bool, db_translation(V1_0="conftime", V0_9="IsGpsIndoors")] = None
    conf_time_avail: Annotated[bool, db_translation(V1_0="conftimeavail", V0_9="IsGpsIndoors")] = None
    on_charger: Annotated[bool, db_translation(V1_0="oncharger", V0_9=None)] = None
    used_aiding: Annotated[bool, db_translation(V1_0="usedaiding", V0_9=None)] = None

    # Enums / ints
    update_reason: Annotated[int, db_translation(V1_0="updatereason", V0_9="UpdateReason")] = None
    psm_state: Annotated[int, db_translation(V1_0="psmstate", V0_9="PsmState")] = None
    num_sat: Annotated[int, db_translation(V1_0="numsat", V0_9="NumSatellites")] = None
    fix_type: Annotated[int, db_translation(V1_0="fixtype", V0_9="FixType")] = None

    # Position
    latitude: Annotated[float, db_translation(V1_0="latitude", V0_9="Latitude")] = None
    longitude: Annotated[float, db_translation(V1_0="longitude", V0_9="Longitude")] = None
    gps_on_time: Annotated[int, db_translation(V1_0="gpsontime", V0_9="Ttf")] = None
    horizontal_accuracy: Annotated[int, db_translation(V1_0="horizontalaccuracy", V0_9="Accuracy")] = None
    gps_altitude: Annotated[int, db_translation(V1_0="gpsaltitude", V0_9="AltitudeGps")] = None
    pressure_altitude: Annotated[int, db_translation(V1_0="pressurealtitude", V0_9="AltitudeCalculated")] = None
    time_of_fix: Annotated[datetime, db_translation(V1_0="timeoffix", V0_9="TimeOfFix")] = None
    ground_speed: Annotated[int, db_translation(V1_0="groundspeed", V0_9="GroundSpeed")] = None
    heading: Annotated[int, db_translation(V1_0="heading", V0_9="Heading")] = None

    # Power/telemetry
    batt_voltage: Annotated[int, db_translation(V1_0="battvoltage", V0_9="BatteryVoltage")] = None
    air_pressure_inhg: Annotated[float, db_translation(V1_0="airpressure", V0_9="AirPressureInHg")] = None
    temperature: Annotated[float, db_translation(V1_0="temperature", V0_9="Temperature")] = None
    avg_force: Annotated[float, db_translation(V1_0="avgforce", V0_9="AverageForce")] = None
    max_force: Annotated[float, db_translation(V1_0="maxforce", V0_9="MaxForce")] = None
    batt_percent: Annotated[int, db_translation(V1_0="battpercent", V0_9="BatteryPercentage")] = None
    pdop: Annotated[int, db_translation(V1_0="pdop", V0_9="Pdop")] = None
    bms_temp: Annotated[int, db_translation(V1_0="bmstemp", V0_9="BmsTemp")] = None
    gps_vert_accuracy: Annotated[int, db_translation(V1_0="vertaccuracy", V0_9="GpsVertAccuracy")] = None
    emergency_event_id: Annotated[int, db_translation(V1_0="emergencyeventid", V0_9="EmergencyEventId")] = None

    # Misc
    interface_type: Annotated[int, db_translation(V1_0="interfacetype", V0_9="DataSource")] = None
    account_id: Annotated[int, db_translation(V1_0=None, V0_9="AccountId")] = None

    # --- Bit fields (V6 flags) ---
    reserved_31_28_bits = (28, 31)
    aiding_data_used_bits = (27, 27)
    on_charger_bits = (26, 26)
    fix_type_bits = (23, 25)
    num_of_satellites_bits = (18, 22)
    confirmed_time_available_bits = (17, 17)
    confirmed_time_bits = (16, 16)
    confirmed_date_bits = (15, 15)
    valid_time_bits = (14, 14)
    valid_date_bits = (13, 13)
    gnss_fix_ok_bits = (12, 12)
    gnss_fix_valid_bits = (11, 11)
    psm_state_bits = (8, 10)
    reserved_7_5_bits = (5, 7)
    update_reason_bits = (1, 4)
    in_motion_bits = (0, 0)

    # Maps
    fix_type_map = {
        0: "No Fix",
        1: "Dead Reckoning Only",
        2: "2D Fix",
        3: "3D Fix",
        4: "GNSS + Dead Reckoning Combined",
        5: "Time Only Fix",
    }
    psm_state_map = {
        0: "PSM is not active (continuous mode)",
        1: "PSM Enabled",
        2: "Acquisition",
        3: "Tracking",
        4: "Power Optimized Tracking",
        5: "Inactive",
    }
    update_reason_map = {
        0: "Device Boot/First network join",
        1: "Heartbeat Message",
        2: "Stop Motion Event",
        3: "Emergency",
        4: "Jumping",
        5: "Continuous Motion",
        6: "In Plane",
        7: "Fall",
        8: "Landed",
        9: "Point Of Interest (POI)",
        10: "Forced Check-In",
        15: "Manufacturing Test",
    }

    @property
    def flags_reserved_31_28(self) -> Optional[int]:
        """Flags reserved 31 28."""
        return int(get_bits(self.flags, *self.reserved_31_28_bits)) if self.flags is not None else None

    @property
    def flags_aiding_data_used(self) -> Optional[bool]:
        """Flags aiding data used."""
        return bool(get_bits(self.flags, *self.aiding_data_used_bits)) if self.flags is not None else None

    @property
    def flags_on_charger(self) -> Optional[bool]:
        """Flags on charger."""
        return bool(get_bits(self.flags, *self.on_charger_bits)) if self.flags is not None else None

    @property
    def flags_fix_type(self) -> Optional[int]:
        """Flags fix type."""
        return int(get_bits(self.flags, *self.fix_type_bits)) if self.flags is not None else None

    @property
    def flags_num_of_satellites(self) -> Optional[int]:
        """Flags num of satellites."""
        return int(get_bits(self.flags, *self.num_of_satellites_bits)) if self.flags is not None else None

    @property
    def flags_confirmed_time_available(self) -> Optional[bool]:
        """Flags confirmed time available."""
        return bool(get_bits(self.flags, *self.confirmed_time_available_bits)) if self.flags is not None else None

    @property
    def flags_confirmed_time(self) -> Optional[bool]:
        """Flags confirmed time."""
        return bool(get_bits(self.flags, *self.confirmed_time_bits)) if self.flags is not None else None

    @property
    def flags_confirmed_date(self) -> Optional[bool]:
        """Flags confirmed date."""
        return bool(get_bits(self.flags, *self.confirmed_date_bits)) if self.flags is not None else None

    @property
    def flags_valid_time(self) -> Optional[bool]:
        """Flags valid time."""
        return bool(get_bits(self.flags, *self.valid_time_bits)) if self.flags is not None else None

    @property
    def flags_valid_date(self) -> Optional[bool]:
        """Flags valid date."""
        return bool(get_bits(self.flags, *self.valid_date_bits)) if self.flags is not None else None

    @property
    def flags_gnss_fix_ok(self) -> Optional[bool]:
        """Flags gnss fix ok."""
        return bool(get_bits(self.flags, *self.gnss_fix_ok_bits)) if self.flags is not None else None

    @property
    def flags_gnss_fix_valid(self) -> Optional[bool]:
        """Flags gnss fix valid."""
        return bool(get_bits(self.flags, *self.gnss_fix_valid_bits)) if self.flags is not None else None

    @property
    def flags_psm_state(self) -> Optional[int]:
        """Flags psm state."""
        return int(get_bits(self.flags, *self.psm_state_bits)) if self.flags is not None else None

    @property
    def flags_reserved_7_5(self) -> Optional[int]:
        """Flags reserved 7 5."""
        return int(get_bits(self.flags, *self.reserved_7_5_bits)) if self.flags is not None else None

    @property
    def flags_update_reason(self) -> Optional[int]:
        """Flags update reason."""
        return int(get_bits(self.flags, *self.update_reason_bits)) if self.flags is not None else None

    @property
    def flags_in_motion(self) -> Optional[bool]:
        """Flags in motion."""
        return bool(get_bits(self.flags, *self.in_motion_bits)) if self.flags is not None else None

    @property
    def update_reason_str(self) -> str:
        """Update reason str."""
        v = self.flags_update_reason
        return self.update_reason_map.get(v, f"Unknown: {v}")

    @property
    def fix_type_str(self) -> str:
        """Fix type str."""
        v = self.flags_fix_type
        return self.update_reason_map.get(v, f"Unknown: {v}")

    @property
    def psm_state_str(self) -> str:
        """Psm state str."""
        v = self.flags_psm_state
        return self.update_reason_map.get(v, f"Unknown: {v}")

    @property
    def pressure_altitude_feet(self) -> Optional[int]:
        """Pressure altitude feet."""
        return self.pressure_altitude

    @property
    def pressure_altitude_meters(self) -> Optional[float]:
        """Pressure altitude meters."""
        return feet_to_meters(self.pressure_altitude) if self.pressure_altitude is not None else None

    @property
    def gps_altitude_feet(self) -> Optional[int]:
        """Gps altitude feet."""
        return meters_to_feet(self.gps_altitude) if self.gps_altitude is not None else None

    @property
    def gps_altitude_meters(self) -> Optional[int]:
        """Gps altitude meters."""
        return self.gps_altitude

    @property
    def temperature_celsius(self) -> Optional[float]:
        """Temperature celsius."""
        return self.temperature

    @property
    def temperature_fahrenheit(self) -> Optional[float]:
        """Temperature fahrenheit."""
        return celsius_to_fahrenheit(self.temperature) if self.temperature is not None else None
