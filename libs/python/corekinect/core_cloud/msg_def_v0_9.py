import base64
import logging
import struct
from abc import ABC
from dataclasses import dataclass, fields, replace
from datetime import datetime
from datetime import timezone
from time import time, sleep
from typing import ClassVar, List, Optional, Sequence, Type, Any, Dict, Tuple

from typing_extensions import Self

from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from corekinect.core_cloud.db_orm_v0_9 import (
    DownlinkMessagesTbl,
    JumpTrack1CMsgTbl,
    JumpTrackHipsSensorDataMsgTbl,
    NetSocketNetworkStatusMessageTbl,
    JumpTrackHardwareFailureV2MsgTbl,
    JumpTrackBootMessageTbl,
    JumpTrackGndConfigV2MsgTbl,
)
from corekinect.utils import Serializable
from corekinect.utils.bits.ops import get_bits
from corekinect.utils.encoding.numbers import int_to_padded_hex
from corekinect.utils.units.length import meters_to_feet, feet_to_meters
from corekinect.utils.units.temp import celsius_to_fahrenheit


@dataclass(frozen=True, slots=True)
class MsgBase(Serializable, ABC):
    """
    Base class for ORM/message mapping and DB querying for DEV_0_9 (MySQL).
    **MUST KEEP** API parity with the v1.0, at least outside facing

    Attributes:
        device_id (int): The unique identifier for the device.
        time_received (datetime): The time when the message was received by the server.
        time_of_record (datetime): The time when the record was created in the database.
        checkin_id (int): The unique identifier for the check-in associated with this message.

    Class variables:
        orm_model (ClassVar[Type[Any]]): The ORM model class associated with this message type.
        orm_field_map (ClassVar[Dict[str, str]]): Mapping of message fields to ORM model fields.
        device_time_fields (ClassVar[Sequence[str] | str]): Fields used for device time calculations.
        interface_type_map (Dict[int, str]): Mapping of interface types to their string representations.
        message_uid_map (Dict[int, str]): Mapping of message UIDs to their string representations.

    Methods:
        device_id_str: Returns the device ID as a zero-padded hex string.
        _convert_orm_obj_to_msg: Converts an ORM object to a message instance.
        _device_time_sqlexpr: Returns the SQL expression for device time based on class definition.
        _query_records: Queries records for a given device ID with optional filters and ordering.
        last: Gets the last record for a given device ID.
        since_server_time: Queries records since a specific server time.
        since_device_time: Queries records since a specific device time.
        since_record_id: Queries records since a specific record ID.
    """

    # Universal-ish fields for 0.9 (present in all five tables below)
    device_id: int = None
    time_received: datetime = None
    time_of_record: datetime = None
    checkin_id: int = None

    orm_model: ClassVar[Type[Any]] = None
    orm_field_map: ClassVar[Dict[str, str]] = {
        "device_id": "DeviceId",
        "time_received": "TimeReceived",
        "time_of_record": "TimeReceived",
        "time_of_config": "TimeOfConfig",
        "timestamp": "TimeOfConfig",
        "checkin_id": "CheckinId",
        "nonce_received": "NonceReceived",
        "account_id": "AccountId",
    }
    device_time_fields: ClassVar[Sequence[str] | str] = ()

    interface_type_map = {
        3: "Iridium",
        2: "LoRa",
        1: "Cellular",
        0: "RPMA",
    }

    message_uid_map = {
        501: "Ack V1",
        502: "Time Request",
        503: "Time Response",
        504: "Firmware Update",
        505: "Firmware Update Response",
        506: "Firmware Update Reset",
        507: "Network Status",
        508: "Network Status V2",
        509: "Network Status V3",
        510: "Firmware Update Prepare",
        511: "Firmware Update V2",
        512: "Network Status V4",
        513: "Boot",
        514: "Firmware V2",
        515: "Reboot V1",
        516: "Emergency Mode Config V2",
        517: "Ground Mode Config",
        518: "Fall Config",
        519: "Fall Event",
        520: "Position V4",
        521: "Hardware Failure V2",
        522: "LoRa Config",
        523: "Position V5",
        524: "GPS Config",
        525: "Emergency Position",
        526: "Emergency Event Response",
        527: "BLE Position",
        528: "BLE Beacon Config",
        529: "BLE Session Key",
        530: "Garmin Biometric Data",
        531: "U-blox Aiding Request",
        532: "U-blox Ephemeris Aiding",
        533: "U-blox Time Aiding",
        534: "HIPS Sensor Data",
        535: "HIPS Config",
        536: "SIM Config",
        537: "Socket Server Config",
        538: "Ground Mode Config V2",
        539: "Modem Config",
        540: "Manufacturing Test",
        541: "Scratchpad",
        542: "Ack V2",
        543: "Reboot V2",
        544: "Firmware V3",
        545: "Firmware Update V3",
        546: "Firmware Update Response V2",
        547: "Firmware Update Reset V2",
        548: "Boot V2",
        549: "Comms Coprocessor HW Failure",
        550: "Socket Server Configuration V2",
        551: "Modem Config V2",
        552: "Sigma5 HW Failure",
        553: "Iridium Config",
        554: "Iridium Status",
        555: "User Notification",
        556: "Position V6",
        557: "Biometric Data",
        558: "Biometric Config",
    }

    @property
    def device_id_str(self) -> str:
        """Returns the device ID as a zero-padded hex string."""
        return int_to_padded_hex(self.device_id).upper()

    @classmethod
    def _convert_orm_obj_to_msg(cls, orm_obj):
        """Convert ORM object to message instance."""
        if orm_obj is None:
            return None

        kwargs = {}
        for f in fields(cls):
            orm_attr = cls.orm_field_map.get(f.name, f.name)
            kwargs[f.name] = getattr(orm_obj, orm_attr, None)

        return cls(**kwargs)

    @classmethod
    def _device_time_sqlexpr(cls):
        """Return the SQL expression for device time based on class definition."""
        if not cls.device_time_fields:
            raise AttributeError(f"{cls.__name__} must define device_time_fields")
        # CoreCloudDBInterface handles either a str field or a list/tuple of fields.
        return CoreCloudDBInterface.device_time_expr(cls.orm_model, cls.device_time_fields)

    @classmethod
    def _query_records(cls, dut_id: int, extra_filters: list | None = None, order_by=None, first: bool = False):
        """Query records for a given device ID with optional filters and ordering."""
        with CoreCloudDBInterface(db_env="DEV_0_9") as db:
            model = cls.orm_model
            query = db.query(model).filter(model.DeviceId == dut_id)

            if extra_filters:
                for filt in extra_filters:
                    query = query.filter(filt)

            if order_by is not None:
                query = query.order_by(order_by)

            if first:
                result = query.first()
                return cls._convert_orm_obj_to_msg(result) if result else None
            results = query.all()
            return [cls._convert_orm_obj_to_msg(r) for r in results]

    # Public

    @classmethod
    def last(cls, dut_id: int) -> Self | None:
        """
        Get the last record for a given device ID.

        Parameters:
            dut_id (int): The device ID to query.

        Returns:
            TMsg: The last message received by the server for the DUT.
        """
        if getattr(cls.orm_model, "CheckinId", None) is not None:
            return cls._query_records(dut_id, order_by=cls.orm_model.CheckinId.desc(), first=True)
        else:
            return cls._query_records(dut_id, first=True)

    @classmethod
    def since_server_time(
        cls, dut_id: int, start_time: datetime, end_time: datetime | None = None
    ) -> List[Self] | None:
        """
        Query records since, not including, a specific server time. Optionally, up to, and including, an end server time.

        Parameters:
            dut_id (int): The device ID to query.
            start_time (datetime): The device start time for the query. Must be timezone-aware.
            end_time (datetime, optional): The device end time for the query. Defaults to None. Must be timezone-aware.

        Returns:
            List[TMsg]: A list of messages received by the server for the DUT since the specified time.
        """
        # Convert all time to UTC
        filters = [cls.orm_model.TimeReceived > start_time.astimezone(timezone.utc)]
        if end_time is not None:
            filters.append(cls.orm_model.TimeReceived <= end_time.astimezone(timezone.utc))
        return cls._query_records(dut_id, extra_filters=filters)

    @classmethod
    def since_device_time(
        cls, dut_id: int, start_time: datetime, end_time: Optional[datetime] = None
    ) -> List[Self] | None:
        """
        Query records since, not including, a specific device time. Optionally, up to, and including, an end device time.

        Parameters:
            dut_id (int): The device ID to query.
            start_time (datetime): The device start time for the query. Must be timezone-aware.
            end_time (datetime, optional): The device end time for the query. Defaults to None. Must be timezone-aware.

        Returns:
            List[TMsg]: A list of messages received by the server for the DUT since the specified device time.
        """
        dev_time_field = cls._device_time_sqlexpr()
        filters = [dev_time_field > start_time.astimezone(timezone.utc)]
        if end_time is not None:
            filters.append(dev_time_field <= end_time.astimezone(timezone.utc))
        return cls._query_records(dut_id, extra_filters=filters)

    @classmethod
    def since_record_id(cls, dut_id: int, start_record_id: int, end_record_id: int | None = None) -> List[Self] | None:
        """
        Query records since, not including, a specific record ID. Optionally, up to, and including, an end record ID.

        Parameters:
            dut_id (int): The device ID to query.
            start_record_id (int): The starting record ID for the query.
            end_record_id (int, optional): The ending record ID for the query. Defaults to None.

        Returns:
            List[TMsg]: A list of messages received by the server for the DUT since the specified record ID.
        """
        filters = [cls.orm_model.CheckinId > start_record_id]
        if end_record_id is not None:
            filters.append(cls.orm_model.CheckinId <= end_record_id)
        return cls._query_records(dut_id, extra_filters=filters)


@dataclass(frozen=True, slots=True)
class ConfMsgBase(MsgBase):
    message_id: int = None
    timestamp: int = None

    # Derived encodings
    hex_message: str = None
    base10_message: int = None
    base64_message: str = None
    hex_message_no_timestamp: str = None
    base10_message_no_timestamp: int = None
    base64_message_no_timestamp: str = None

    # Numeric ranges by struct code for fancy auto testing
    _STRUCT_CODE_RANGES = {
        # unsigned
        "B": (0, 0xFF),
        "H": (0, 0xFFFF),
        "I": (0, 0xFFFFFFFF),
        "Q": (0, 0xFFFFFFFFFFFFFFFF),
        # signed
        "b": (-0x80, 0x7F),
        "h": (-0x8000, 0x7FFF),
        "i": (-0x80000000, 0x7FFFFFFF),
        "q": (-0x8000000000000000, 0x7FFFFFFFFFFFFFFF),
    }
    # don't check but still accept
    _STRUCT_FLOAT_CODES = {"f", "d"}
    # ignore Endianness ans alignment chars in format string
    _STRUCT_PREFIX = set("@=<>!")

    def __post_init__(self) -> None:
        self._ensure_header_defaults()

        # Add current time if not already defined
        if "timestamp" in type(self).packed_struct and self.timestamp is None:
            object.__setattr__(self, "timestamp", int(datetime.now(timezone.utc).timestamp()))

        # make sure stuff is encoded
        if self._ready_to_pack():
            self._regenerate()

    # public
    def send(
        self,
        device_id: int,
        *,
        timeout: int = 180,
        device_type_id: int = 9,
        account_id: int = 21,
    ) -> None:
        """
        Insert a downlink config message and wait for it to appear in DownlinkMessagesTbl.
        Always takes `device_id` explicitly. Stamps current UTC timestamp unless disabled.
        """
        log = logging.getLogger("send_config_msg")
        if not log.handlers:
            logging.basicConfig(level=logging.INFO)

        # make sure the timestamp is valid
        if "timestamp" in type(self).packed_struct and self.timestamp is None:
            object.__setattr__(self, "timestamp", int(datetime.now(timezone.utc).timestamp()))

        # Build payload now
        self._ensure_header_defaults()
        if not self._ready_to_pack():
            missing = [
                f
                for f in type(self).packed_struct
                if f not in ("message_id", "message_length", "timestamp") and getattr(self, f, None) is None
            ]
            raise ValueError(f"Missing required fields for packing: {missing}")
        self._regenerate()
        msg = self.base64_message
        if not msg:
            raise ValueError("No message to send (empty base64 string)")

        # Get last downlink id for this device
        last_id = 0
        with CoreCloudDBInterface(db_env="DEV_0_9") as db:
            last = (
                db.query(DownlinkMessagesTbl)
                .filter(DownlinkMessagesTbl.DeviceId == device_id)
                .order_by(DownlinkMessagesTbl.DownlinkMessageId.desc())
                .first()
            )
            if last is not None:
                last_id = last.DownlinkMessageId

        log.debug(f"Sending config message to DeviceId: {hex(device_id)}, msg={msg!r}")

        # Insert message
        row = DownlinkMessagesTbl(
            DeviceId=device_id,
            DeviceTypeId=device_type_id,
            TimeQueued=datetime.utcnow(),  # naive UTC per schema
            NonceSent=b"0",
            IsAcked=False,
            IsNaked=False,
            Message=msg,
            AccountId=account_id,
        )
        with CoreCloudDBInterface(db_env="DEV_0_9") as db:
            db.add(row)
            db.commit()

        # check for it to populate
        end_time = time() + timeout
        found = False
        new_row = None
        while not found and time() < end_time:
            with CoreCloudDBInterface(db_env="DEV_0_9") as db:
                candidates = (
                    db.query(DownlinkMessagesTbl)
                    .filter(
                        DownlinkMessagesTbl.DeviceId == device_id,
                        DownlinkMessagesTbl.DownlinkMessageId > last_id,
                    )
                    .order_by(DownlinkMessagesTbl.DownlinkMessageId.desc())
                    .all()
                )
                for nm in candidates:
                    if nm.Message == msg:
                        new_row = nm
                        found = True
                        break
            if not found:
                sleep(1)

        log.debug(f"Last DownlinkMessageId: {last_id}")
        log.debug(f"New DownlinkMessageId: {getattr(new_row, 'DownlinkMessageId', None)}")
        log.debug(f"end_time={end_time}, now={time()}")
        log.debug(f"downlink_message_queued={found}")

        assert time() < end_time, "DownlinkMessagesTbl was not updated."
        assert found, "Message did not appear in the DownlinkMessagesTbl."

    def to_bytes(self, *, zero_timestamp: bool = False) -> bytes:
        self._ensure_header_defaults()
        self._validate_fields()
        return self._pack(zero_timestamp=zero_timestamp)

    @classmethod
    def from_base64(cls: Type["ConfMsgBase"], b64: str) -> "ConfMsgBase":
        """
        Create instance from a base64-encoded payload, even if subclass has required fields.
        We bypass __init__ and populate fields via unpack.
        """
        obj = object.__new__(cls)  # bypass __init__ (required fields)
        # Initialize dataclass-managed attributes to defaults the cheap way:
        # Not strictly necessary for frozen dataclasses since we set everything below.
        cls.__init__.__doc__  # touch attribute to silence linters about bypass (no-op)
        # Now unpack into the object
        ConfMsgBase._unpack_into_self(obj, b64)  # call base method explicitly
        return obj

    def with_updates(self, **changes) -> "ConfMsgBase":
        return replace(self, **changes)

    def set_timestamp_now(self) -> "ConfMsgBase":
        object.__setattr__(self, "timestamp", int(datetime.now(timezone.utc).timestamp()))
        return self

    # subclass stubs
    def _encode_flags(self) -> None:
        return

    def _decode_flags(self) -> None:
        return

    # private
    def _ready_to_pack(self) -> bool:
        for fname in type(self).packed_struct:
            if fname in ("message_id", "message_length", "timestamp"):
                continue
            if getattr(self, fname, None) is None:
                return False
        return True

    def _regenerate(self) -> None:
        self._encode_flags()
        self._validate_fields()
        packed = self._pack(zero_timestamp=False)
        self._set_encodings_from_bytes(packed, no_ts=False)
        if "timestamp" in type(self).packed_struct:
            packed_no_ts = self._pack(zero_timestamp=True)
            self._set_encodings_from_bytes(packed_no_ts, no_ts=True)
        self._decode_flags()

    def _ensure_header_defaults(self) -> None:
        # verify subclass constants
        if not getattr(type(self), "packed_format", None):
            raise ValueError(f"{type(self).__name__}: packed_format must be set (ClassVar)")
        if not getattr(type(self), "packed_struct", None):
            raise ValueError(f"{type(self).__name__}: packed_struct must be set (ClassVar)")
        if not getattr(type(self), "message_length", None):
            raise ValueError(f"{type(self).__name__}: message_length must be set (ClassVar)")
        if not getattr(type(self), "uid", None):
            raise ValueError(f"{type(self).__name__}: uid must be set (ClassVar)")

        if tuple(type(self).packed_struct[:2]) != ("message_id", "message_length"):
            raise ValueError(f"{type(self).__name__}: packed_struct must start with ('message_id','message_length')")
        if self.message_id is None:
            object.__setattr__(self, "message_id", int(type(self).uid))

    def _pack(self, *, zero_timestamp: bool) -> bytes:
        args = []
        for fname in type(self).packed_struct:
            if fname == "message_id":
                v = self.message_id
            elif fname == "message_length":
                v = int(type(self).message_length)
            else:
                v = getattr(self, fname, None)
                if v is None:
                    raise ValueError(f"{type(self).__name__}: field '{fname}' must be set before packing")
                if zero_timestamp and fname == "timestamp":
                    v = 0
            args.append(v)
        try:
            return struct.pack(type(self).packed_format, *args)
        except struct.error as e:
            raise ValueError(f"{type(self).__name__}: struct.pack failed: {e}") from e

    def _set_encodings_from_bytes(self, packed: bytes, *, no_ts: bool) -> None:
        self._check_packed_header(packed)
        hex_str = packed.hex()
        base10 = int(hex_str, 16)
        b64 = base64.b64encode(packed).decode("utf-8")
        if no_ts:
            object.__setattr__(self, "hex_message_no_timestamp", hex_str)
            object.__setattr__(self, "base10_message_no_timestamp", base10)
            object.__setattr__(self, "base64_message_no_timestamp", b64)
        else:
            object.__setattr__(self, "hex_message", hex_str)
            object.__setattr__(self, "base10_message", base10)
            object.__setattr__(self, "base64_message", b64)

    def _check_packed_header(self, packed: bytes) -> None:
        if len(packed) < 3:
            raise ValueError("Packed data too short to contain header")
        msg_id = packed[0]
        msg_len = struct.unpack_from(">H", packed, 1)[0]
        if msg_id != int(self.message_id):
            raise ValueError(f"Got message ID {msg_id:#x}, expected {int(self.message_id):#x}")
        if (len(packed) - 3) != int(type(self).message_length):
            raise ValueError(
                f"Incorrect packed length: got {len(packed)-3}, expected {int(type(self).message_length)}"
            )

    def _unpack_into_self(self, base64_message: str) -> None:
        try:
            packed = base64.b64decode(base64_message)
        except Exception as e:
            raise ValueError(f"Invalid base64 for {type(self).__name__}: {e}") from e
        self._ensure_header_defaults()
        self._check_packed_header(packed)
        try:
            values = struct.unpack(type(self).packed_format, packed)
        except struct.error as e:
            raise ValueError(f"{type(self).__name__}: struct.unpack failed: {e}") from e
        for i, fname in enumerate(type(self).packed_struct):
            object.__setattr__(self, fname, values[i])
        self._decode_flags()
        self._set_encodings_from_bytes(packed, no_ts=False)
        if "timestamp" in type(self).packed_struct:
            packed_no_ts = self._pack(zero_timestamp=True)
            self._set_encodings_from_bytes(packed_no_ts, no_ts=True)

    def _expand_format_codes(self, fmt: str) -> list[str]:
        """
        Expand a struct format string to a flat list of element codes, e.g.
          '> B H I' -> ['B','H','I']
          '>2H B'   -> ['H','H','B']
        """
        s = fmt.replace(" ", "")
        i = 0
        out: list[str] = []
        # strip endianness / alignment prefix chars anywhere
        s = "".join(ch for ch in s if ch not in self._STRUCT_PREFIX)
        n = len(s)
        while i < n:
            # gather repeat count digits
            j = i
            while j < n and s[j].isdigit():
                j += 1
            count = int(s[i:j]) if j > i else 1
            if j >= n:
                raise ValueError(f"Bad struct format: {fmt!r}")
            code = s[j]
            i = j + 1
            # 's' and 'p' can have a width (e.g., '16s'); here we don't support them
            if code in {"s", "p"}:
                raise ValueError(f"Unsupported struct code in config packing: {code!r}")
            # 'x' is pad bytes: no field should correspond to them
            if code == "x":
                out.extend(["x"] * count)
            else:
                out.extend([code] * count)
        return out

    def _validate_range(value: int, lo: int, hi: int, name: str) -> None:
        if not (lo <= int(value) <= hi):
            raise ValueError(f"{name} must be between {lo} and {hi} (got {value})")

    def _validate_fields(self) -> None:
        codes = self._expand_format_codes(type(self).packed_format)
        names = list(type(self).packed_struct)

        # Ensure 1:1 mapping
        if len(codes) != len(names):
            raise ValueError(
                f"{type(self).__name__}: packed_format expands to {len(codes)} elements "
                f"but packed_struct has {len(names)}"
            )

        for fname, code in zip(names, codes):
            if code == "x":
                # pad byte(s) must not appear in packed_struct
                raise ValueError(f"{type(self).__name__}: packed_struct includes field for pad byte: {fname!r}")

            # resolve attribute (instance or class var)
            value = getattr(self, fname, None)

            # timestamp policy: by the time we validate, it must be set if present
            if value is None:
                raise ValueError(f"{type(self).__name__}: field '{fname}' must be set before packing")

            # numeric-range validation
            if code in self._STRUCT_CODE_RANGES:
                lo, hi = self._STRUCT_CODE_RANGES[code]
                ivalue = int(value)
                if not (lo <= ivalue <= hi):
                    raise ValueError(f"{fname} must be between {lo} and {hi} (got {value})")
                continue

            # float validation (type only)
            if code in self._STRUCT_FLOAT_CODES:
                if not isinstance(value, (int, float)):
                    raise ValueError(f"{fname} must be a number for struct code '{code}' (got {type(value).__name__})")
                continue

            raise ValueError(f"{type(self).__name__}: unsupported struct code '{code}' for field '{fname}'")


# UID 548
@dataclass(frozen=True, slots=True)
class BootMsgV2(MsgBase):
    """
    UID-548: Boot Message V2

    Attributes:
        from_device (bool): Indicates if the message is from the device.
        nonce_received (int): Nonce received from the device.
        boot_reason (int): Reason for the boot.
        number_of_exceptions (int): Number of exceptions encountered during boot.
        time_of_boot (datetime): Timestamp of when the device booted.
        account_id (int): Account ID associated with the device.

    """

    from_device: bool = None
    nonce_received: int = None
    boot_reason: int = None
    number_of_exceptions: int = None
    time_of_boot: datetime = None
    account_id: int = None

    __type__ = "UID_548"
    orm_model = JumpTrackBootMessageTbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "from_device": "FromDevice",
        "nonce_received": "NonceReceived",
        "boot_reason": "BootReason",
        "number_of_exceptions": "NumberOfExceptions",
        "time_of_boot": "TimeOfBoot",
        "account_id": "AccountId",
    }
    device_time_fields = "TimeOfBoot"

    uid: int = 0x11
    mcu_type_bits = (7, 7)
    fw_triggered_bits = (6, 6)
    boot_reason_bits = (0, 5)

    mcu_type_map = {0: "nrf9160", 1: "nrf52840"}
    fw_triggered_map = {0: "Soft reset", 1: "FW-triggered reset"}
    boot_reason_map = {
        0: "Normal boot",
        1: "Reboot due to exception",
        2: "Reboot due to completing FUOTA",
        3: "Reboot due to being placed on charger",
        4: "Reboot due to error",
        5: "Reboot due to receiving valid reboot message",
        6: "Reboot due to watchdog timer expiration",
        7: "Reboot due to user button sequence",
    }

    @property
    def flag_mcu(self) -> int:
        """(int) Coprocessor type flag.
        0 - nrf9160, 1 - nrf52840.
        """
        return int(get_bits(self.boot_reason or 0, *self.mcu_type_bits))

    @property
    def triggered_by(self) -> bool:
        """(bool) Indicates if the boot was triggered by firmware.
        True if the boot was triggered by firmware, False if it was a soft reset.
        """
        return bool(get_bits(self.boot_reason or 0, *self.fw_triggered_bits))

    @property
    def boot_reason_code(self) -> int:
        """(int) Boot reason code.
        Returns an integer representing the boot reason.
        0 - Normal boot, 1 - Reboot due to exception, etc.
        """
        return int(get_bits(self.boot_reason or 0, *self.boot_reason_bits))

    @property
    def coprocessor_str(self) -> str:
        """(str) Returns a string representation of the coprocessor type."""
        return self.mcu_type_map.get(self.flag_mcu, f"Unknown: {self.flag_mcu}")

    @property
    def fw_triggered_str(self) -> str:
        """(str) Returns a string representation of the firmware-triggered boot status."""
        return self.fw_triggered_map.get(int(self.triggered_by), f"Unknown: {self.triggered_by}")

    @property
    def boot_reason_str(self) -> str:
        """(str) Returns a string representation of the boot reason."""
        return self.boot_reason_map.get(self.boot_reason_code, f"Unknown: {self.boot_reason_code}")


# UID 556
@dataclass(frozen=True, slots=True)
class PositionMsgV6(MsgBase):
    flags: int = None
    is_valid_gps_fix: bool = None
    is_gps_indoors: bool = None
    is_in_motion: bool = None
    update_reason: int = None
    latitude: float = None
    longitude: float = None
    ttf: int = None
    horizontal_accuracy: int = None
    gps_altitude: int = None
    interface_type: int = None
    pressure_altitude: int = None
    ground_speed: int = None
    heading: int = None
    time_of_fix: datetime = None
    batt_voltage: int = None
    batt_percent: int = None
    air_pressure_inhg: float = None
    temperature: float = None
    avg_force: float = None
    max_force: float = None
    fix_type: int = None
    num_sat: int = None
    psm_state: int = None
    pdop: int = None
    bms_temp: int = None
    gps_vert_accuracy: int = None
    emergency_event_id: int = None
    account_id: int = None

    __type__ = "UID_556"
    orm_model = JumpTrack1CMsgTbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "flags": "Flags",
        "is_valid_gps_fix": "IsValidGpsFix",
        "is_gps_indoors": "IsGpsIndoors",
        "is_in_motion": "IsInMotion",
        "update_reason": "UpdateReason",
        "latitude": "Latitude",
        "longitude": "Longitude",
        "interface_type": "DataSource",
        "ttf": "Ttf",
        "horizontal_accuracy": "Accuracy",
        "gps_altitude": "AltitudeGps",
        "pressure_altitude": "AltitudeCalculated",
        "ground_speed": "GroundSpeed",
        "heading": "Heading",
        "time_of_fix": "TimeOfFix",
        "batt_voltage": "BatteryVoltage",
        "batt_percent": "BatteryPercentage",
        "air_pressure_inhg": "AirPressureInHg",
        "temperature": "Temperature",
        "avg_force": "AverageForce",
        "max_force": "MaxForce",
        "fix_type": "FixType",
        "num_sat": "NumSatellites",
        "psm_state": "PsmState",
        "pdop": "Pdop",
        "bms_temp": "BmsTemp",
        "gps_vert_accuracy": "GpsVertAccuracy",
        "emergency_event_id": "EmergencyEventId",
        "account_id": "AccountId",
    }
    device_time_fields = "TimeOfFix"

    uid: int = 556
    message_length: int = None
    packed_format: str = None
    packed_struct: List[str] = None

    # Flag bits
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
    def on_charger(self) -> bool:
        return bool(get_bits(self.flags, *self.on_charger_bits))

    @property
    def used_aiding(self) -> bool:
        return bool(get_bits(self.flags, *self.aiding_data_used_bits))

    # Decode flags
    @property
    def flags_reserved_31_28(self) -> int:
        return int(get_bits(self.flags, *self.reserved_31_28_bits))

    @property
    def flags_aiding_data_used(self) -> bool:
        return bool(get_bits(self.flags, *self.aiding_data_used_bits))

    @property
    def flags_on_charger(self) -> bool:
        return bool(get_bits(self.flags, *self.on_charger_bits))

    @property
    def flags_fix_type(self) -> int:
        return int(get_bits(self.flags, *self.fix_type_bits))

    @property
    def flags_num_of_satellites(self) -> int:
        return int(get_bits(self.flags, *self.num_of_satellites_bits))

    @property
    def flags_confirmed_time_available(self) -> bool:
        return bool(get_bits(self.flags, *self.confirmed_time_available_bits))

    @property
    def flags_confirmed_time(self) -> bool:
        return bool(get_bits(self.flags, *self.confirmed_time_bits))

    @property
    def flags_confirmed_date(self) -> bool:
        return bool(get_bits(self.flags, *self.confirmed_date_bits))

    @property
    def flags_valid_time(self) -> bool:
        return bool(get_bits(self.flags, *self.valid_time_bits))

    @property
    def flags_valid_date(self) -> bool:
        return bool(get_bits(self.flags, *self.valid_date_bits))

    @property
    def flags_gnss_fix_ok(self) -> bool:
        return bool(get_bits(self.flags, *self.gnss_fix_ok_bits))

    @property
    def flags_gnss_fix_valid(self) -> bool:
        return bool(get_bits(self.flags, *self.gnss_fix_valid_bits))

    @property
    def flags_psm_state(self) -> int:
        return int(get_bits(self.flags, *self.psm_state_bits))

    @property
    def flags_reserved_7_5(self) -> int:
        return int(get_bits(self.flags, *self.reserved_7_5_bits))

    @property
    def flags_update_reason(self) -> int:
        return int(get_bits(self.flags, *self.update_reason_bits))

    @property
    def flags_in_motion(self) -> bool:
        return bool(get_bits(self.flags, *self.in_motion_bits))

    @property
    def update_reason_str(self) -> str:
        return self.update_reason_map.get(self.flags_update_reason, f"Unknown: {self.flags_update_reason}")

    @property
    def fix_type_str(self) -> str:
        return self.fix_type_map.get(self.flags_fix_type, f"Unknown Failure: {self.flags_fix_type}")

    @property
    def psm_state_str(self) -> str:
        return self.psm_state_map.get(self.flags_psm_state, f"Unknown Failure: {self.flags_psm_state}")

    @property
    def pressure_altitude_feet(self):
        return self.pressure_altitude

    @property
    def pressure_altitude_meters(self):
        return feet_to_meters(self.pressure_altitude) if self.pressure_altitude is not None else None

    @property
    def gps_altitude_feet(self):
        return meters_to_feet(self.gps_altitude) if self.gps_altitude is not None else None

    @property
    def gps_altitude_meters(self):
        return self.gps_altitude

    @property
    def temperature_celsius(self):
        return self.temperature

    @property
    def temperature_fahrenheit(self):
        return celsius_to_fahrenheit(float(self.temperature)) if self.temperature is not None else None


# UID 534
@dataclass(frozen=True, slots=True)
class HipsDataMsg(MsgBase):
    from_device: bool = None
    nonce_received: int = None
    time_of_measurement: datetime = None
    group_code: int = None
    source_user_id: int = None
    heat_strain_index: float = None
    heart_rate: int = None
    estimated_core_temperature: float = None
    skin_temperature: float = None
    nii: int = None
    risk: int = None
    heart_rate_confidence: int = None
    hips_battery_life: int = None
    account_id: int = None

    __type__ = "UID_534"
    orm_model = JumpTrackHipsSensorDataMsgTbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "from_device": "FromDevice",
        "nonce_received": "NonceReceived",
        "time_of_measurement": "TimeOfMeasurement",
        "group_code": "GroupCode",
        "source_user_id": "SourceUserId",
        "heat_strain_index": "HsiDataValue",
        "heart_rate": "HrDataValue",
        "estimated_core_temperature": "EstimatedCoreTemp",
        "skin_temperature": "SkinTemp",
        "nii": "NII",
        "risk": "Risk",
        "heart_rate_confidence": "Confidence",
        "hips_battery_life": "HipsBatteryLife",
        "account_id": "AccountId",
    }
    device_time_fields = "TimeOfMeasurement"


@dataclass(frozen=True, slots=True)
class BiometricDataMsg(HipsDataMsg):
    """DEV_0_9 has no dedicated 557; reuse HIPS sensor data."""

    __type__ = "UID_557"


# UID 512
@dataclass(frozen=True, slots=True)
class NetworkStatusMsgV4(MsgBase):
    from_device: bool = None
    nonce_received: int = None
    flags: int = None
    lte_connected: bool = None
    socket_connected: bool = None
    send_success: bool = None
    wireless_technology: int = None
    active_sim_slot: int = None
    early_socket_disconnect: bool = None
    dnssec_resolved: bool = None
    time_spent: int = None
    time_of_connection: datetime = None
    rsrq: float = None
    rsrp: float = None
    bytes_sent: int = None
    bytes_received: int = None
    band: int = None
    energy_estimate: int = None
    network_id: int = None
    account_id: int = None

    __type__ = "UID_512"
    orm_model = NetSocketNetworkStatusMessageTbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "from_device": "FromDevice",
        "nonce_received": "NonceReceived",
        "flags": "Flags",
        "lte_connected": "LteConnected",
        "socket_connected": "SocketConnected",
        "send_success": "SendSuccess",
        "wireless_technology": "WirelessTechnology",
        "active_sim_slot": "ActiveSimSlot",
        "early_socket_disconnect": "EarlySocketDisconnect",
        "dnssec_resolved": "DnssecResolved",
        "time_spent": "TimeSpent",
        "time_of_connection": "TimeOfConnection",
        "rsrq": "RSRQ",
        "rsrp": "RSRP",
        "bytes_sent": "NumberOfBytesSent",
        "bytes_received": "NumberOfBytesReceived",
        "band": "Band",
        "energy_estimate": "EnergyEstimate",
        "network_id": "NetworkId",
        "account_id": "AccountId",
    }
    device_time_fields = "TimeOfConnection"

    wireless_technology_map = {
        0: "LTE Cat-M",
        1: "NB-IOT",
    }

    @property
    def wireless_technology_str(self) -> str:
        return self.wireless_technology_map.get(self.wireless_technology, f"Unknown: {self.wireless_technology}")


# UID 521
@dataclass(frozen=True, slots=True)
class HardwareFailureV2Msg(MsgBase):
    from_device: bool = None
    nonce_received: int = None
    failure_time: datetime = None

    acc_failures: int = None
    alt_failures: int = None
    gps_failures: int = None
    sx1262_failures: int = None
    ipc_failures: int = None
    bms_failures: int = None
    ext_flash_failure: int = None
    sec_element_failure: int = None

    # ORM booleans (some rows have these pre-decoded)
    is_acc_com_failure: bool = None
    is_alt_com_failure: bool = None
    is_alt_int_failure: bool = None
    is_gps_com_failure: bool = None
    is_gps_crystal_failure: bool = None
    is_sx1262_com_failure: bool = None
    is_sx1262_pll_failure: bool = None
    is_ipc_com_failure: bool = None
    is_bms_com_failure: bool = None
    is_ext_flash_com_failure: bool = None
    is_sec_element_com_failure: bool = None

    account_id: int = None

    __type__ = "UID_521"
    orm_model = JumpTrackHardwareFailureV2MsgTbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "from_device": "FromDevice",
        "nonce_received": "NonceReceived",
        "failure_time": "FailureTime",
        "acc_failures": "AccFailures",
        "is_acc_com_failure": "IsAccComFailure",
        "alt_failures": "AltFailures",
        "is_alt_com_failure": "IsAltComFailure",
        "is_alt_int_failure": "IsAltIntFailure",
        "gps_failures": "GpsFailures",
        "is_gps_com_failure": "IsGpsComFailure",
        "is_gps_crystal_failure": "IsGpsCrystalFailure",
        "sx1262_failures": "Sx1262Failures",
        "is_sx1262_com_failure": "IsSx1262ComFailure",
        "is_sx1262_pll_failure": "IsSx1262PllFailure",
        "ipc_failures": "IpcFailures",
        "is_ipc_com_failure": "IsIpcComFailure",
        "bms_failures": "BmsFailures",
        "is_bms_com_failure": "IsBmsComFailure",
        "ext_flash_failure": "ExtFlashFailure",
        "is_ext_flash_com_failure": "IsExtFlashComFailure",
        "sec_element_failure": "SecElementFailure",
        "is_sec_element_com_failure": "IsSecElementComFailure",
        "account_id": "AccountId",
    }
    device_time_fields = "FailureTime"

    uid = 521
    # Only define meaningful bits -> reason strings (no reserved entries)
    map_acc_failures = {
        7: "Communications failure",
    }
    map_alt_failures = {
        7: "Communications failure",
        6: "Altimeter interrupt failure",
    }
    map_gps_failures = {
        7: "Communications failure",
        6: "Crystal failure",
        5: "PVT failure",
        4: "Voltage backup failure",
    }
    map_lora_failures = {
        7: "Communications failure",
        6: "Failed PLL lock",
    }
    map_ipc_failures = {
        7: "Communications failure",
    }
    map_bms_failures = {
        7: "Communications failure",
    }
    map_ext_flash_failures = {
        7: "Communications failure",
    }
    map_sec_element_failures = {
        7: "Communications failure",
    }

    @property
    def acc_failure_reason(self):
        return self.map_acc_failures.get(self.acc_failures, f"Unknown: {self.acc_failures}")

    @property
    def alt_failure_reason(self):
        return self.map_alt_failures.get(self.alt_failures, f"Unknown: {self.alt_failures}")

    @property
    def gps_failure_reason(self):
        return self.map_gps_failures.get(self.gps_failures, f"Unknown: {self.gps_failures}")

    @property
    def sx1262_failure_reason(self):
        return self.map_lora_failures.get(self.sx1262_failures, f"Unknown: {self.sx1262_failures}")

    @property
    def ipc_failure_reason(self):
        return self.map_ipc_failures.get(self.ipc_failures, f"Unknown: {self.ipc_failures}")

    @property
    def bms_failure_reason(self):
        return self.map_bms_failures.get(self.bms_failures, f"Unknown: {self.bms_failures}")

    @property
    def ext_flash_failure_reason(self):
        return self.map_ext_flash_failures.get(self.ext_flash_failure, f"Unknown: {self.ext_flash_failure}")

    @property
    def sec_element_failure_reason(self):
        return self.map_sec_element_failures.get(self.sec_element_failure, f"Unknown: {self.sec_element_failure}")


@dataclass(frozen=True, slots=True)
class GroundConfigV2(ConfMsgBase):
    """
    Configuration message for version 2 of ground mode behavior (UID 538).

    Attributes:
        gps_heartbeat_period_minutes (int): Period in minutes for GPS heartbeats.
        continuous_motion_period_seconds (int): Period in seconds for continuous motion detection.
        stop_motion_timeout_seconds (int): Timeout in seconds to enter stop-motion state.
        heartbeat_acquisition_timeout_seconds (int): Timeout in seconds for heartbeat GPS acquisition.
        motion_acquisition_timeout_seconds (int): Timeout in seconds for motion GPS acquisition.
        motion_acceleration_threshold (int): Threshold for motion acceleration detection.
        motion_acceleration_duration (int): Duration in seconds for motion acceleration detection.
        start_motion_window_start_seconds (int): Start of the window in seconds for starting motion detection.
        start_motion_window_end_seconds (int): End of the window in seconds for starting motion detection.
        motion_acquisition_on_time_seconds (int): GPS on time in seconds for continuous motion acquisition.
        motion_initial_acquisition_on_time_seconds (int): GPS on time for initial motion acquisition.

    Raises:
        ValueError: If any of the parameters are out of the allowed range.
        AssertionError: If the message is not properly packed or decoded.

    """

    gps_heartbeat_period_minutes: int = None
    continuous_motion_period_seconds: int = None
    stop_motion_timeout_seconds: int = None
    heartbeat_acquisition_timeout_seconds: int = None
    motion_acquisition_timeout_seconds: int = None
    motion_acceleration_threshold: int = None
    motion_acceleration_duration: int = None
    start_motion_window_start_seconds: int = None
    start_motion_window_end_seconds: int = None
    motion_acquisition_on_time_seconds: int = None
    motion_initial_acquisition_on_time_seconds: int = None

    reserved: ClassVar[int] = 0

    __type__: ClassVar[str] = "UID_538"
    orm_model = JumpTrackGndConfigV2MsgTbl
    orm_field_map: ClassVar[Dict[str, str]] = {
        "gps_heartbeat_period_minutes": "GpsHeartbeatPeriod",
        "continuous_motion_period_seconds": "ContMotionPeriod",
        "stop_motion_timeout_seconds": "MotionStopTimeout",
        "heartbeat_acquisition_timeout_seconds": "HeartbeatAcqTimeout",
        "motion_acquisition_timeout_seconds": "MotionAcqTimeout",
        "motion_acceleration_threshold": "MotionThreshold",
        "motion_acceleration_duration": "MotionDuration",
        "start_motion_window_start_seconds": "StartMotionWindowStart",
        "start_motion_window_end_seconds": "StartMotionWindowEnd",
        "motion_acquisition_on_time_seconds": "MotionAcqOnTime",
        "motion_initial_acquisition_on_time_seconds": "MotionInitAcqOnTime",
        "reserved": "Reserved",
    }
    uid: ClassVar[int] = 0x36  # override for 0.9
    message_length: ClassVar[int] = 0x15
    packed_format: ClassVar[str] = "> B H I H H B B B B B B B B B I"
    packed_struct: ClassVar[Tuple[str, ...]] = (
        "message_id",  # 1 byte
        "message_length",  # 2 bytes
        "timestamp",  # 4 bytes
        "gps_heartbeat_period_minutes",  # 2 bytes
        "continuous_motion_period_seconds",  # 2 bytes
        "stop_motion_timeout_seconds",  # 1 byte
        "heartbeat_acquisition_timeout_seconds",  # 1 byte
        "motion_acquisition_timeout_seconds",  # 1 byte
        "motion_acceleration_threshold",  # 1 byte
        "motion_acceleration_duration",  # 1 byte
        "start_motion_window_start_seconds",  # 1 byte
        "start_motion_window_end_seconds",  # 1 byte
        "motion_acquisition_on_time_seconds",  # 1 byte
        "motion_initial_acquisition_on_time_seconds",  # 1 byte
        "reserved",  # 4 bytes
    )

    def _encode_flags(self) -> None:
        return

    def _decode_flags(self) -> None:
        return


if __name__ == "__main__":
    device_id = 0x70B3D584C01E0FF8

    conf = GroundConfigV2(
        gps_heartbeat_period_minutes=1,
        continuous_motion_period_seconds=30,
        stop_motion_timeout_seconds=60,
        heartbeat_acquisition_timeout_seconds=60,
        motion_acquisition_timeout_seconds=60,
        motion_acceleration_threshold=4,
        motion_acceleration_duration=4,
        start_motion_window_start_seconds=3,
        start_motion_window_end_seconds=30,
        motion_acquisition_on_time_seconds=30,
        motion_initial_acquisition_on_time_seconds=60,
    )

    bootmsg = BootMsgV2.last(device_id)
    if bootmsg:
        bootmsg.boot_

    # conf.send(device_id)
    # exit()

    curr_gnd = GroundConfigV2.last(device_id)

    last_boot = BootMsgV2.last(device_id)
    print("BOOT last:", last_boot.device_id_str if last_boot else None)

    last_pos = PositionMsgV6.last(device_id)
    print("POS  last:", last_pos.device_id_str if last_pos else None)

    last_bio = BiometricDataMsg.last(device_id)
    print("BIO  last:", last_bio.device_id_str if last_bio else None)

    last_net = NetworkStatusMsgV4.last(device_id)
    print("NET  last:", last_net.device_id_str if last_net else None)

    last_hf = HardwareFailureV2Msg.last(device_id)
    print("HF   last:", last_hf.device_id_str if last_hf else None)
