from abc import ABC
from dataclasses import dataclass
from dataclasses import fields
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Type, ClassVar, Literal, Mapping

from typing_extensions import Self
from requests import Response
import logging

from corekinect.core_cloud.db_interface import CoreCloudDBInterface
from corekinect.core_cloud.api_interface import CoreCloudRestInterface
from corekinect.core_cloud.db_orm_v1_0 import (
    Devicemessagestbl,
    Messagesbiometricdatatbl,
    Messagesboottbl,
    Messagescommshwfailtbl,
    Messagesnetworkstatusv4tbl,
    Messagespositionv5tbl,
    Messagesalphahwfailtbl,
    Messagessigma5hwfailtbl,
    Configgpstbl,
    Configgroundtbl,
    Messagesscratchpadtbl,
)
from corekinect.utils import Logger
from corekinect.utils import Serializable
from corekinect.utils.bits.ops import extract_bits
from corekinect.utils.encoding.numbers import int_to_padded_hex
from corekinect.utils.encoding.byte_str import base64_to_str
from corekinect.utils.units.length import meters_to_feet, feet_to_meters
from corekinect.utils.units.temp import celsius_to_fahrenheit


# ----------------------------------------  Message Base
@dataclass(frozen=True, slots=True)
class MsgBase(Serializable, ABC):
    """
    Base class for ORM/message mapping and DB querying.

    Attributes:
        device_id (int): Unique identifier for the device.
        interface_type (int): Type of interface used by the device.
        time_of_record (datetime): Timestamp of when the message was recorded.
        device_message_id (int): Unique identifier for the message.

    Class variables:
        device_time_fields (ClassVar[Sequence[str]]): Fields used for device time.
        orm_model (ClassVar[Type[Any]]): ORM model class for database interaction.
        orm_field_map (ClassVar[Dict[str, str]]): Mapping of class fields to ORM fields.
        interface_type_map (Dict[int, str]): Mapping of interface type codes to human-readable strings.
        message_uid_map (Dict[int, str]): Mapping of message UID codes to human-readable names.

    Methods:
        _get_reason_from_mapping(value: Optional[int], mapping: Dict[int, str]) -> str:
            Get the reason string from a bit mask value.
        _convert_orm_obj_to_msg(orm_obj):
            Convert ORM object to message instance.
        _query_records(dut_id: int, extra_filters: list = None, order_by=None, first: bool = False, *, env="VAL_1_0"):
            Query records from the database and return message instances.
        last(dut_id, *, env="VAL_1_0"):
            Get the last message for a device.
        since_server_time(dut_id: int, start_time: datetime, end_time: datetime = None, *, env="VAL_1_0"):
            Get messages since a specific server time.
        since_device_time(dut_id: int, start_time: datetime, end_time: Optional[datetime] = None, *, env="VAL_1_0"):
            Get messages since a specific device time.
        since_record_id(dut_id: int, start_record_id: int, end_record_id: int = None, *, env="VAL_1_0"):
            Get messages since a specific record ID.


    """

    # universal fields every message has
    device_id: int = None
    interface_type: int = None
    time_of_record: datetime = None
    device_message_id: int = None

    # class-level (not in __init__)
    device_time_fields: ClassVar[Sequence[str]] = ()
    orm_model: ClassVar[Type[Any]] = None
    orm_field_map: ClassVar[Dict[str, str]] = {
        "device_id": "deviceid",
        "interface_type": "interfacetype",
        "time_of_record": "timeofrecord",
        "device_message_id": "messageid",
    }

    uid: int = None
    message_length: int = None
    packed_format: str = None
    packed_struct: List[str] = None

    interface_type_map = {
        5: "Iridium",
        4: "RPMA",
        3: "LoRa",
        2: "Cellular",
        1: "Socket Server 0.9",
        0: "Error: Unsupported type: 0",
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
        """Return the device ID as a padded hexadecimal string."""
        return int_to_padded_hex(self.device_id).upper()

    @classmethod
    def _get_reason_from_mapping(cls, value: Optional[int], mapping: Dict[int, str]) -> str:
        """Get the reason string from a bit mask value."""
        if value is None:
            return "No value provided"
        return mapping.get(value, f"Unknown: {value}")

    @classmethod
    def _convert_orm_obj_to_msg(cls, orm_obj):
        """Convert ORM object to message instance."""
        if orm_obj is None:
            return None

        kwargs = {}
        for f in fields(cls):
            orm_field = cls.orm_field_map.get(f.name, f.name)  # fallback: same name
            kwargs[f.name] = getattr(orm_obj, orm_field, None)

        return cls(**kwargs)

    @classmethod
    def _query_records(
        cls,
        dut_ids: int | Sequence[int],
        extra_filters: list = None,
        order_by=None,
        reverse_order: bool = False,
        first: bool = False,
        *,
        env="VAL_1_0",
    ) -> List[Self]:
        """
        Query records from the database and return message instances.

        Args:
            dut_id (int): Device ID to filter records.
            extra_filters (list): Additional filters to apply to the query.
            order_by (Any): SQLAlchemy order_by clause to sort results.
            first (bool): If True, return the first result only; otherwise, return all results.
            env (str): Database environment to use for the query.

        Returns:
            Self | List[Self]: A single message instance if `first` is True, or a list of message instances.

        """
        # Handle IDs
        is_multi = not isinstance(dut_ids, int)
        if is_multi:
            # Convert to list once, in case it's a generator
            dut_ids = list(dut_ids)
            if not dut_ids:
                return []  # nothing to query
            if first:
                raise ValueError(
                    "`first=True` with multiple device IDs is ambiguous; use single ID or a multi helper."
                )

        with CoreCloudDBInterface(env=env) as db:
            # Use class's ORM model
            model = cls.orm_model
            query = db.query(model)

            if is_multi:
                query = query.filter(model.deviceid.in_(dut_ids))
            else:
                query = query.filter(model.deviceid == dut_ids)

            if extra_filters:
                for filt in extra_filters:
                    query = query.filter(filt)

            if order_by is not None:
                if reverse_order:
                    query = query.order_by(order_by.desc())
                else:
                    query = query.order_by(order_by)

            if first and not is_multi:
                result = query.first()
                return cls._convert_orm_obj_to_msg(result) if result else None

            results = query.all()
            return [cls._convert_orm_obj_to_msg(r) for r in results]

    # ----------------------------------------  Single-device

    @classmethod
    def last(cls, dut_id, *, env="VAL_1_0") -> Optional[Self]:
        """
        Get the last record for a given device ID.

        Args:
            dut_id (int): Device ID to filter records.`
            env (str): Database environment to use for the query.

        Returns:
            Optional[Self]: The last message instance for the device, or None if no records found.
        """
        return cls._query_records(dut_id, order_by=cls.orm_model.recordid.desc(), first=True, env=env)

    @classmethod
    def since_server_time(
        cls, dut_id: int, start_time: datetime, end_time: datetime = None, *, env="VAL_1_0"
    ) -> List[Self]:
        """
        Query records since, not including, a specific server time. Optionally, up to, and including, an end server time.

        Args:
            dut_id (int): Device ID to filter records.
            start_time (datetime): Start time for filtering records.
            end_time (datetime, optional): End time for filtering records. Defaults to None.
            env (str): Database environment to use for the query.

        Returns:
            List[Self]: A list of message instances since the specified start time, optionally up to the end time.
        """
        filters = [cls.orm_model.timeofrecord > start_time]
        if end_time is not None:
            filters.append(cls.orm_model.timeofrecord <= end_time)
        return cls._query_records(dut_id, extra_filters=filters, env=env)

    @classmethod
    def since_device_time(
        cls, dut_id: int, start_time: datetime, end_time: Optional[datetime] = None, *, env="VAL_1_0"
    ) -> List[Self]:
        """
        Query records since, not including, a specific device time. Optionally, up to, and including, an end device time.

        Args:
            dut_id (int): Device ID to filter records.
            start_time (datetime): Start time for filtering records.
            end_time (datetime, optional): End time for filtering records. Defaults to None.
            env (str): Database environment to use for the query.

        Returns:
            List[Self]: A list of message instances since the specified device time, optionally up to the end time.
        """
        if not cls.device_time_fields:
            raise AttributeError(f"{cls.__name__} must define device_time_fields")
        dev_time_field = CoreCloudDBInterface.device_time_expr(cls.orm_model, cls.device_time_fields)
        filters = [dev_time_field > start_time]
        if end_time is not None:
            filters.append(dev_time_field <= end_time)

        return cls._query_records(dut_id, extra_filters=filters, order_by=dev_time_field, env=env)

    @classmethod
    def since_record_id(
        cls, dut_id: int, start_record_id: int, end_record_id: int = None, *, db_env="VAL_1_0"
    ) -> List[Self]:
        """
        Query records since, not including, a specific record ID. Optionally, up to, and including, an end record ID.

        Args:
            dut_id (int): Device ID to filter records.
            start_record_id (int): Start record ID for filtering records.
            end_record_id (int, optional): End record ID for filtering records. Defaults to None.
            db_env (str): Database environment to use for the query.

        Returns:
            List[Self]: A list of message instances since the specified record ID, optionally up to the end record ID.
        """
        filters = [cls.orm_model.recordid > start_record_id]
        if end_record_id is not None:
            filters.append(cls.orm_model.recordid <= end_record_id)
        return cls._query_records(dut_id, extra_filters=filters, env=db_env)

    # ----------------------------------------  Multi-device

    @classmethod
    def since_server_time_multi(
        cls,
        dut_ids: Sequence[int],
        start_time: datetime,
        end_time: datetime | None = None,
        *,
        env: str = "VAL_1_0",
    ) -> List[Self]:
        """Query records for multiple devices since a server-side timestamp."""
        if not dut_ids:
            return []
        filters = [cls.orm_model.timeofrecord > start_time]
        if end_time is not None:
            filters.append(cls.orm_model.timeofrecord <= end_time)
        return cls._query_records(dut_ids, extra_filters=filters, env=env)

    @classmethod
    def since_device_time_multi(
        cls,
        dut_ids: Sequence[int],
        start_time: datetime,
        end_time: datetime | None = None,
        *,
        env: str = "VAL_1_0",
    ) -> List[Self]:
        """Query records for multiple devices since a device-side timestamp."""
        if not dut_ids:
            return []
        if not cls.device_time_fields:
            raise AttributeError(f"{cls.__name__} must define device_time_fields")

        dev_time_field = CoreCloudDBInterface.device_time_expr(cls.orm_model, cls.device_time_fields)
        filters = [dev_time_field > start_time]
        if end_time is not None:
            filters.append(dev_time_field <= end_time)

        return cls._query_records(
            dut_ids,
            extra_filters=filters,
            order_by=dev_time_field,
            env=env,
        )

    @classmethod
    def since_record_id_multi(
        cls,
        dut_ids: Sequence[int],
        start_record_id: int,
        end_record_id: int | None = None,
        *,
        env: str = "VAL_1_0",
    ) -> List[Self]:
        """Query records for multiple devices since a given record ID."""
        if not dut_ids:
            return []
        filters = [cls.orm_model.recordid > start_record_id]
        if end_record_id is not None:
            filters.append(cls.orm_model.recordid <= end_record_id)

        return cls._query_records(dut_ids, extra_filters=filters, env=env)


# ----------------------------------------  Config Base
class ConfMsgBase(MsgBase):
    """
    Base for REST-backed configuration messages.

    Subclasses should define:
      - api_set_endpoint: ClassVar[tuple[str, str]]  e.g. ("PUT", "/System/Devices/Configurations/Gps")
      - api_search_endpoint: ClassVar[tuple[str, str]] | None
      - api_field_map: ClassVar[Dict[str, str]]   # dataclass_attr -> API field name
      - api_types: ClassVar[Dict[str, type]]      # API field name -> expected type (for coercion/validation)
    """

    # Defaults (override in subclasses)
    api_set_endpoint: ClassVar[Optional[tuple[str, str]]] = None
    api_search_endpoint: ClassVar[Optional[tuple[str, str]]] = None
    api_field_map: ClassVar[Dict[str, str]] = {}
    api_types: ClassVar[Dict[str, type]] = {}

    @staticmethod
    def _device_id_to_hex_str(dev_id: int | str) -> str:
        """
        Convert device id to an uppercase hex string without '0x'.
        Pads to 16 chars by default (common for DevEUI), but leaves longer as-is.
        """
        if isinstance(dev_id, int):
            s = format(dev_id, "X")
        else:
            s = str(dev_id).strip()
            if s.lower().startswith("0x"):
                s = s[2:]
        s = s.upper()
        if len(s) < 16:
            s = s.rjust(16, "0")
        return s

    @classmethod
    def _to_api_key(cls, attr_name: str) -> str:
        """Map dataclass attribute to API field name."""
        return cls.api_field_map.get(attr_name, attr_name)

    @classmethod
    def _from_api_key(cls, api_key: str) -> str:
        """Map API field name back to dataclass attribute name (best-effort)."""
        inv = {v: k for k, v in cls.api_field_map.items()}
        return inv.get(api_key, api_key)

    def missing_fields(self) -> list[str]:
        """
        Return dataclass field names that are part of api_field_map but currently None.
        """
        missing: list[str] = []
        for attr in self.api_field_map.keys():
            if getattr(self, attr, None) is None:
                missing.append(attr)
        return missing

    def _validate_for_send(self) -> None:
        """Validate all required fields are set before sending to the API."""
        miss = self.missing_fields()
        if miss:
            raise ValueError(f"{type(self).__name__}: missing required fields: {miss}")

        # Type sanity (best-effort): coerce/validate against api_types
        for attr, api_name in self.api_field_map.items():
            if api_name not in self.api_types:
                continue
            expected = self.api_types[api_name]
            val = getattr(self, attr, None)
            if val is None:
                continue
            try:
                # allow bool/int interop where sensible
                if expected is bool:
                    _ = bool(val)
                elif expected is int:
                    _ = int(val)
                elif expected is str:
                    _ = str(val)
                else:
                    # accept as-is for other types
                    _ = val
            except Exception as e:
                raise TypeError(
                    f"{type(self).__name__}: field {attr!r} (API {api_name!r}) "
                    f"cannot be coerced to {expected.__name__}: {e}"
                ) from e

    def to_api_payload(self, *, device_id: Optional[int | str] = None) -> Dict[str, Any]:
        """
        Build the API payload dict from this instance.

        deviceId handling:
          - If device_id is provided, it takes precedence.
          - Else, if self.device_id is set, it's used.
          - Produces uppercase hex string (padded to 16 chars by default).
        """
        self._validate_for_send()

        if device_id is None:
            if self.device_id is None:
                raise ValueError(f"{type(self).__name__}: device_id is required for API payload")
            device_id = self.device_id

        payload: Dict[str, Any] = {"deviceIds": [self._device_id_to_hex_str(device_id)]}

        # Map dataclass attributes to API names
        for attr, api_name in self.api_field_map.items():
            val = getattr(self, attr, None)
            if api_name in type(self).api_types:
                t = type(self).api_types[api_name]
                try:
                    if t is bool:
                        val = bool(val)
                    elif t is int:
                        val = int(val)
                    elif t is str:
                        val = str(val)
                except Exception:
                    # _validate_for_send should already catch coercion problems
                    pass
            payload[api_name] = val

        return payload

    @classmethod
    def from_api_payload(cls, payload: Mapping[str, Any], *, include_device_id: bool = True) -> "ConfMsgBase":
        """
        Create an instance from an API JSON dict. Unknown fields are ignored.
        """
        kwargs: Dict[str, Any] = {}
        if include_device_id:
            dev = payload.get("deviceId")
            if dev is not None:
                try:
                    # try to parse hex to int for internal consistency
                    kwargs["device_id"] = int(str(dev), 16)
                except Exception:
                    kwargs["device_id"] = None

        for api_name, val in payload.items():
            attr = cls._from_api_key(api_name)
            if attr in cls.__dataclass_fields__:  # type: ignore[attr-defined]
                kwargs[attr] = val
        return cls(**kwargs)  # type: ignore[arg-type]

    def send(
        self,
        *,
        device_id: Optional[int | str] = None,
        env_namespace: Optional[Literal["VAL_1_0", "DEV_1_0", "DEV_0_9"]] = "DEV_1_0",
        client: Optional["CoreCloudRestInterface"] = None,
        timeout: Optional[float] = None,
        headers: Optional[Mapping[str, str]] = None,
        raise_for_status: bool = False,
    ) -> Response:
        """
        Send this config to the REST endpoint defined by `api_set_endpoint`.
        """
        log = Logger(Logger.Config(console_log_level=logging.DEBUG))
        if not type(self).api_set_endpoint:
            raise NotImplementedError(f"{type(self).__name__}: api_set_endpoint is not defined")

        method, path = type(self).api_set_endpoint
        payload = self.to_api_payload(device_id=f"{device_id:X}")
        resp = None

        if client is not None:
            resp = client.request(method, path, json=payload, timeout=timeout, headers=headers)
        else:
            with CoreCloudRestInterface(env_namespace=env_namespace) as api:
                log.debug(f"Sending {method} {path} using {env_namespace!r}")
                resp = api.request(method, path, json=payload, timeout=timeout, headers=headers)

        log.debug(f"{resp.status_code}: {resp.text}")
        if raise_for_status:
            resp.raise_for_status()
        return resp

    @classmethod
    def search_via_rest(
        cls,
        criteria: Mapping[str, Any],
        *,
        env_namespace: Optional[Literal["VAL_1_0", "DEV_1_0", "DEV_0_9"]] = "DEV_1_0",
        client: Optional["CoreCloudRestInterface"] = None,
        timeout: Optional[float] = None,
        headers: Optional[Mapping[str, str]] = None,
        map_field_names: bool = True,
    ) -> Response | None:
        """
        POST search criteria to the configured search endpoint. If map_field_names=True,
        field keys provided as dataclass names will be mapped to API names automatically.
        """
        if not cls.api_search_endpoint:
            raise NotImplementedError(f"{cls.__name__}: api_search_endpoint is not defined")

        method, path = cls.api_search_endpoint

        body: Dict[str, Any] = {}
        for k, v in criteria.items():
            api_key = cls._to_api_key(k) if map_field_names else k
            body[api_key] = v

        if client is not None:
            return client.request(method, path, json=body, timeout=timeout, headers=headers)

        with CoreCloudRestInterface(env_namespace=env_namespace) as api:
            return api.request(method, path, json=body, timeout=timeout, headers=headers)


# ----------------------------------------  None-message reference tables
@dataclass(frozen=True, slots=True)
class DeviceMessageLog(MsgBase):
    """
    Represents a device message log entry.

    Attributes:
        record_id (int): Unique identifier for the record.
        is_uplink (bool): Indicates if the message is an uplink.
        interface_type (int): Type of interface used by the device.
        time_of_record (datetime): Timestamp of when the message was recorded.
        device_id (int): Unique identifier for the device.
        account_id (int): Unique identifier for the account.
        message_id (int): Unique identifier for the message.
        message_uid (int): Unique identifier for the message UID.

    Class variables:
        __type__ (str): Type identifier for the message.
        orm_model (Type[Any]): ORM model class for database interaction.
        orm_field_map (Dict[str, str]): Mapping of class fields to ORM fields.

    Properties:
        message_name (str): Returns the name of the message based on its UID.
        interface_str (str): Returns a string representation of the interface type.

    Methods:
        last(dut_id, *, env="VAL_1_0"):
            Get the last message for a device.
        since_server_time(dut_id: int, start_time: datetime, end_time: datetime = None, *, env="VAL_1_0"):
            Get messages since a specific server time.
        since_device_time(dut_id: int, start_time: datetime, end_time: Optional[datetime] = None, *, env="VAL_1_0"):
            Get messages since a specific device time.
        since_record_id(dut_id: int, start_record_id: int, end_record_id: int = None, *, env="VAL_1_0"):
            Get messages since a specific record ID.
    """

    record_id: int = None
    is_uplink: bool = None
    interface_type: int = None
    time_of_record: datetime = None
    device_id: int = None
    account_id: int = None
    message_id: int = None
    message_uid: int = None

    # Non-ORM fields
    __type__ = "DMT"
    orm_model = Devicemessagestbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "record_id": "recordid",
        "is_uplink": "isuplink",
        "interface_type": "interfacetype",
        "time_of_record": "timeofrecord",
        "device_id": "deviceid",
        "account_id": "accountid",
        "message_id": "messageid",
        "message_uid": "messageuid",
    }

    @property
    def message_name(self) -> str:
        """Return the name of the message based on its UID."""
        return self.message_uid_map.get(self.message_uid, f"Unknown UID: {self.message_uid}")

    @property
    def interface_str(self) -> str:
        """Return a string representation of the interface type."""
        return self._get_reason_from_mapping(self.interface_type, self.interface_type_map)


# ----------------------------------------  Message Definitions


# [501] Ack V1; TODO: Needs to be implemented...
class AckMsgV1:
    """Ack V1."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[501] Ack Message V1 not supported at this time")


# [502] Time Request; TODO: Needs to be implemented...
class TimeRequestMsgV1:
    """Time Request."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[502] Time Request Message V1 not supported at this time")


# [503] Time Response; TODO: Needs to be implemented...
class TimeResponseMsgV1:
    """Time Response."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[503] Time Response Message V1 not supported at this time")


# [504] Firmware Update; TODO: Needs to be implemented...
class FirmwareUpdateMsgV1:
    """Firmware Update."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[504] Firmware Update Message V1 not supported at this time")


# [505] Firmware Update Response; TODO: Needs to be implemented...
class FirmwareUpdateResponseMsgV1:
    """Firmware Update Response."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[505] Firmware Update Response Message V1 not supported at this time")


# [506] Firmware Update Reset; TODO: Needs to be implemented...
class FirmwareUpdateResetMsgV1:
    """Firmware Update Reset."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[506] Firmware Update Reset Message V1 not supported at this time")


# [507] Network Status; TODO: Needs to be implemented...
class NetworkStatusMsgV1:
    """Network Status."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[507] Network Status Message V1 not supported at this time")


# [508] Network Status V2; TODO: Needs to be implemented...
class NetworkStatusMsgV2:
    """Network Status V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[508] Network Status Message V2 not supported at this time")


# [509] Network Status V3; TODO: Needs to be implemented...
class NetworkStatusMsgV3:
    """Network Status V3."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[509] Network Status Message V3 not supported at this time")


# [510] Firmware Update Prepare; TODO: Needs to be implemented...
class FirmwareUpdatePrepareMsgV1:
    """Firmware Update Prepare."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[510] Firmware Update Prepare Message V1 not supported at this time")


# [511] Firmware Update V2; TODO: Needs to be implemented...
class FirmwareUpdateMsgV2:
    """Firmware Update V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[511] Firmware Update Message V2 not supported at this time")


# [512] Network Status V4
@dataclass(frozen=True, slots=True)
class NetworkStatusMsgV4(MsgBase):
    """CoreCloud message type."""
    record_id: int = None
    time_of_connection: datetime = None
    did_lte_conn: bool = None
    did_sock_conn: bool = None
    send_success: bool = None
    used_nb_iot: bool = None
    did_use_sim1: bool = None
    did_socket_disconnect_early: bool = None
    did_use_dns_sec: bool = None
    flags: int = None
    time_spent: int = None
    rsrq: float = None
    rsrp: float = None
    bytes_sent: int = None
    bytes_received: int = None
    band: int = None
    energy_estimate: int = None
    network_id: int = None

    # Non-ORM fields
    __type__ = "UID_512"
    orm_model = Messagesnetworkstatusv4tbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "record_id": "recordid",
        "time_of_connection": "timeofconnection",
        "did_lte_conn": "didlteconn",
        "did_sock_conn": "didsockconn",
        "send_success": "sendsuccess",
        "used_nb_iot": "usednbiot",
        "did_use_sim1": "didusesim1",
        "did_socket_disconnect_early": "didsocketdisconnectearly",
        "did_use_dns_sec": "didusednssec",
        "flags": "flags",
        "time_spent": "timespent",
        "rsrq": "rsrq",
        "rsrp": "rsrp",
        "bytes_sent": "bytessent",
        "bytes_received": "bytesreceived",
        "band": "band",
        "energy_estimate": "energyestimate",
        "network_id": "networkid",
    }
    device_time_fields = "timeofconnection"

    uid: int = 512
    message_length: int = None
    packed_format: str = None
    packed_struct: List[str] = None

    # Flag bits
    flags_lte_connected_bits = (7, 7)
    flags_socket_connected_bits = (6, 6)
    flags_send_success_bits = (5, 5)
    flags_wireless_technology_bits = (4, 4)
    flags_active_sim_slot_bits = (3, 3)
    flags_early_socket_disconnect_bits = (2, 2)
    flags_dnssec_resolved_bits = (1, 1)
    flags_reserved_bits = (0, 0)

    wireless_technology_map = {
        0: "LTE Cat-M",
        1: "NB-IOT",
    }

    @property
    def flags_lte_connected(self) -> bool:
        """Perform flags lte connected."""
        return extract_bits(self.flags, self.flags_lte_connected_bits, cast=bool, default=None)

    @property
    def flags_socket_connected(self) -> bool:
        """Perform flags socket connected."""
        return extract_bits(self.flags, self.flags_socket_connected_bits, cast=bool, default=None)

    @property
    def flags_send_success(self) -> bool:
        """Perform flags send success."""
        return extract_bits(self.flags, self.flags_send_success_bits, cast=bool, default=None)

    @property
    def flags_wireless_technology(self) -> int:
        """Perform flags wireless technology."""
        return extract_bits(self.flags, self.flags_wireless_technology_bits, cast=int, default=None)

    @property
    def flags_active_sim_slot(self) -> int:
        """Perform flags active sim slot."""
        return extract_bits(self.flags, self.flags_active_sim_slot_bits, cast=int, default=None)

    @property
    def flags_early_socket_disconnect(self) -> bool:
        """Perform flags early socket disconnect."""
        return extract_bits(self.flags, self.flags_early_socket_disconnect_bits, cast=bool, default=None)

    @property
    def flags_dnssec_resolved(self) -> bool:
        """Perform flags dnssec resolved."""
        return extract_bits(self.flags, self.flags_dnssec_resolved_bits, cast=bool, default=None)

    @property
    def flags_reserved(self) -> int:
        """Perform flags reserved."""
        return extract_bits(self.flags, self.flags_reserved_bits, cast=int, default=None)

    @property
    def wireless_technology_str(self):
        """Perform wireless technology str."""
        return self._get_reason_from_mapping(self.flags_wireless_technology, self.wireless_technology_map)


# [513] Boot Message V1; TODO: Needs to be implemented...
class BootMsgV1:
    """Boot Message V1."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[513] Boot Message V1 not supported at this time")


# [514] Firmware V2; TODO: Needs to be implemented...
class FirmwareMsgV2:
    """Firmware V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[514] Firmware Message V2 not supported at this time")


# [515] Reboot V1; TODO: Needs to be implemented...
class RebootMsgV1:
    """Reboot V1."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[515] Reboot Message V1 not supported at this time")


# [516] Emergency Mode Config V2; TODO: Needs to be implemented...
class EmergencyModeConfigMsgV2:
    """Emergency Mode Config V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[516] Emergency Mode Config Message V2 not supported at this time")


# [517] Ground Mode Config; TODO: Needs to be implemented...
class GroundModeConfigMsgV1:
    """Ground Mode Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[517] Ground Mode Config Message V1 not supported at this time")


# [518] Fall Config; TODO: Needs to be implemented...
class FallConfigMsgV1:
    """Fall Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[518] Fall Config Message V1 not supported at this time")


# [519] Fall Event; TODO: Needs to be implemented...
class FallEventMsgV1:
    """Fall Event."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[519] Fall Event Message V1 not supported at this time")


# [520] Position V4; TODO: Needs to be implemented...
class PositionMsgV4:
    """Position V4."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[520] Position Message V4 not supported at this time")


# [521] Hardware Failure V2; TODO: Needs to be implemented...
class HardwareFailureMsgV2:
    """Hardware Failure V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[521] Hardware Failure Message V2 not supported at this time")


# [522] LoRa Config; TODO: Needs to be implemented...
class LoRaConfigMsgV1:
    """LoRa Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[522] LoRa Config Message V1 not supported at this time")


# [523] Position V5; TODO: Needs to be implemented...
class PositionMsgV5:
    """Position V5."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[523] Position Message V5 not supported at this time")


# [524] GPS Config; TODO: Needs to be implemented...
@dataclass(frozen=True, slots=True)
class GPSConfMsg(ConfMsgBase):
    """CoreCloud message type."""
    is_psm_enabled: bool = None
    is_aiding_enabled: bool = None
    gnss_update_freq: int = None
    target_fix_accuracy: int = None
    target_fix_pdop: int = None

    __type__: ClassVar[str] = "UID_524"
    orm_model = Configgpstbl
    orm_field_map: ClassVar[Dict[str, str]] = {
        **ConfMsgBase.orm_field_map,
        "is_psm_enabled": "ispsmenabled",
        "is_aiding_enabled": "aidingenabled",
        "gnss_update_freq": "gnssupdatefreq",
        "target_fix_accuracy": "targetfixaccuracy",
        "target_fix_pdop": "targetfixpdop",
    }

    api_set_endpoint: ClassVar[tuple[str, str]] = ("PUT", "/System/Devices/Configurations/Gps")

    api_field_map: ClassVar[Dict[str, str]] = {
        "is_aiding_enabled": "isAidingEnabled",
        "is_psm_enabled": "isPsmEnabled",
        "gnss_update_freq": "gnssUpdateFrequency",
        "target_fix_accuracy": "targetFixAccuracyMeters",
        "target_fix_pdop": "targetFixPdopTenths",
    }

    # API field -> expected type (for coercion/validation)
    api_types: ClassVar[Dict[str, type]] = {
        "deviceId": str,  # injected by to_api_payload
        "isAidingEnabled": bool,
        "isPsmEnabled": bool,
        "gnssUpdateFrequency": int,
        "targetFixAccuracyMeters": int,
        "targetFixPdopTenths": int,
    }

    # Optional message metadata (unused for REST)
    uid = 524
    message_length = None
    packed_format = None
    packed_struct = None

    def _extra_validate(self) -> None:
        """Perform message-specific field validation beyond the base checks."""
        if self.gnss_update_freq is not None and self.gnss_update_freq < 0:
            raise ValueError("gnss_update_freq must be >= 0")
        if self.target_fix_accuracy is not None and self.target_fix_accuracy <= 0:
            raise ValueError("target_fix_accuracy must be > 0")
        if self.target_fix_pdop is not None and self.target_fix_pdop <= 0:
            raise ValueError("target_fix_pdop must be > 0")

    def _validate_for_send(self) -> None:
        """Validate all required fields are set before sending to the API."""
        super(type(self), self)._validate_for_send()
        self._extra_validate()


# [525] Emergency Position; TODO: Needs to be implemented...
class EmergencyPositionMsgV1:
    """Emergency Position."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[525] Emergency Position Message V1 not supported at this time")


# [526] Emergency Event Response; TODO: Needs to be implemented...
class EmergencyEventResponseMsgV1:
    """Emergency Event Response."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[526] Emergency Event Response Message V1 not supported at this time")


# [527] BLE Position; TODO: Needs to be implemented...
class BLEPositionMsgV1:
    """BLE Position."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[527] BLE Position Message V1 not supported at this time")


# [528] BLE Beacon Config; TODO: Needs to be implemented...
class BLEBeaconConfigMsgV1:
    """BLE Beacon Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[528] BLE Beacon Config Message V1 not supported at this time")


# [529] BLE Session Key; TODO: Needs to be implemented...
class BLESessionKeyMsgV1:
    """BLE Session Key."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[529] BLE Session Key Message V1 not supported at this time")


# [530] Garmin Biometric Data; TODO: Needs to be implemented...
class GarminBiometricDataMsgV1:
    """Garmin Biometric Data."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[530] Garmin Biometric Data Message V1 not supported at this time")


# [531] U-blox Aiding Request; TODO: Needs to be implemented...
class UBloxAidingRequestMsgV1:
    """U-blox Aiding Request."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[531] U-blox Aiding Request Message V1 not supported at this time")


# [532] U-blox Ephemeris Aiding; TODO: Needs to be implemented...
class UBloxEphemerisAidingMsgV1:
    """U-blox Ephemeris Aiding."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[532] U-blox Ephemeris Aiding Message V1 not supported at this time")


# [533] U-blox Time Aiding; TODO: Needs to be implemented...
class UBloxTimeAidingMsgV1:
    """U-blox Time Aiding."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[533] U-blox Time Aiding Message V1 not supported at this time")


# [534] HIPS Sensor Data; TODO: Needs to be implemented...
class HIPSSensorDataMsgV1:
    """HIPS Sensor Data."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[534] HIPS Sensor Data Message V1 not supported at this time")


# [535] HIPS Config; TODO: Needs to be implemented...
class HIPSSensorConfigMsgV1:
    """HIPS Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[535] HIPS Config Message V1 not supported at this time")


# [536] SIM Config; TODO: Needs to be implemented...
class SIMConfigMsgV1:
    """SIM Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[536] SIM Config Message V1 not supported at this time")


# [537] Socket Server Config; TODO: Needs to be implemented...
class SocketServerConfigMsgV1:
    """Socket Server Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[537] Socket Server Config Message V1 not supported at this time")


# [538] Ground Mode Config V2; TODO: Needs to be implemented...
@dataclass(frozen=True, slots=True)
class GroundModeConfigV2(ConfMsgBase):
    """CoreCloud message type."""
    gps_heartbeat_period_minutes: int = None
    continuous_motion_period_seconds: int = None
    stop_motion_timeout_seconds: int = None
    heartbeat_acquisition_timeout_seconds: int = None
    stop_motion_acquisition_timeout_seconds: int = None
    motion_acceleration_threshold: int = None
    motion_acceleration_duration: int = None
    start_motion_window_start_seconds: int = None
    start_motion_window_end_seconds: int = None
    motion_acquisition_on_time_seconds: int = None
    motion_initial_acquisition_on_time_seconds: int = None

    __type__: ClassVar[str] = "UID_538"
    orm_model = Configgroundtbl

    api_set_endpoint: ClassVar[tuple[str, str]] = ("PUT", "/System/Devices/Configurations/GroundModeV2")

    api_field_map: ClassVar[Dict[str, str]] = {
        "gps_heartbeat_period_minutes": "gpsHeartbeatPeriod",
        "continuous_motion_period_seconds": "continuousMotionPeriod",
        "stop_motion_timeout_seconds": "stopMotionTimeout",
        "heartbeat_acquisition_timeout_seconds": "heartbeatAcquisitionTimeout",
        "stop_motion_acquisition_timeout_seconds": "motionAcquisitionTimeout",
        "motion_acceleration_threshold": "xlrMotionThreshold",
        "motion_acceleration_duration": "xlrMotionDuration",
        "start_motion_window_start_seconds": "startMotionWindowStart",
        "start_motion_window_end_seconds": "startMotionWindowEnd",
        "motion_acquisition_on_time_seconds": "motionAcquisitionOnTime",
        "motion_initial_acquisition_on_time_seconds": "motionInitialAcquisitionOnTime",
    }

    api_types: ClassVar[Dict[str, type]] = {
        "gpsHeartbeatPeriod": int,
        "continuousMotionPeriod": int,
        "stopMotionTimeout": int,
        "heartbeatAcquisitionTimeout": int,
        "motionAcquisitionTimeout": int,
        "motionAccelerationThreshold": int,
        "motionAccelerationDuration": int,
        "startMotionWindowStart": int,
        "startMotionWindowEnd": int,
    }

    uid = 538
    message_length = None
    packed_format = None
    packed_struct = None

    def _extra_validate(self) -> None:
        """Perform message-specific field validation beyond the base checks."""
        if self.gps_heartbeat_period_minutes is not None and self.gps_heartbeat_period_minutes < 0:
            raise ValueError("gps_heartbeat_period_minutes must be >= 0")
        if self.continuous_motion_period_seconds is not None and self.continuous_motion_period_seconds < 0:
            raise ValueError("continuous_motion_period_seconds must be >= 0")
        if self.stop_motion_timeout_seconds is not None and self.stop_motion_timeout_seconds < 0:
            raise ValueError("stop_motion_timeout_seconds must be >= 0")
        if self.heartbeat_acquisition_timeout_seconds is not None and self.heartbeat_acquisition_timeout_seconds < 0:
            raise ValueError("heartbeat_acquisition_timeout_seconds must be >= 0")
        if (
            self.stop_motion_acquisition_timeout_seconds is not None
            and self.stop_motion_acquisition_timeout_seconds < 0
        ):
            raise ValueError("motion_acquisition_timeout_seconds must be >= 0")
        if self.motion_acceleration_threshold is not None and self.motion_acceleration_threshold < 0:
            raise ValueError("motion_acceleration_threshold must be >= 0")
        if self.motion_acceleration_duration is not None and self.motion_acceleration_duration < 0:
            raise ValueError("motion_acceleration_duration must be >= 0")
        if self.start_motion_window_start_seconds is not None and self.start_motion_window_start_seconds < 0:
            raise ValueError("start_motion_window_start_seconds must be >= 0")
        if self.start_motion_window_end_seconds is not None and self.start_motion_window_end_seconds < 0:
            raise ValueError("start_motion_window_end_seconds must be >= 0")
        if self.motion_acquisition_on_time_seconds is not None and self.motion_acquisition_on_time_seconds < 0:
            raise ValueError("motion_acquisition_on_time_seconds must be >= 0")
        if (
            self.motion_initial_acquisition_on_time_seconds is not None
            and self.motion_initial_acquisition_on_time_seconds < 0
        ):
            raise ValueError("motion_initial_acquisition_on_time_seconds must be >= 0")

    def _validate_for_send(self) -> None:
        """Validate all required fields are set before sending to the API."""
        super(type(self), self)._validate_for_send()
        self._extra_validate()


# [539] Modem Config; TODO: Needs to be implemented...
class ModemConfigMsgV1:
    """Modem Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[539] Modem Config Message V1 not supported at this time")


# [540] Manufacturing Test; TODO: Needs to be implemented...
class ManufacturingTestMsgV1:
    """Manufacturing Test."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[540] Manufacturing Test Message V1 not supported at this time")


# [541] Scratchpad
@dataclass(frozen=True, slots=True)
class ScratchpadMsg(MsgBase):
    """CoreCloud message type."""
    payload_b64: str = None

    uid: int = 541
    __type__ = "UID_541"
    orm_model = Messagesscratchpadtbl
    orm_field_map = {"payload_b64": "payload"}

    @property
    def payload_as_string(self) -> str:
        """Perform payload as string."""
        return base64_to_str(self.payload_b64)


# [542] Ack V2; TODO: Needs to be implemented...
class AckMsgV2:
    """Ack V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[542] Ack Message V2 not supported at this time")


# [543] Reboot V2; TODO: Needs to be implemented...
class RebootMsgV2:
    """Reboot V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[543] Reboot Message V2 not supported at this time")


# [544] Firmware V3; TODO: Needs to be implemented...
class FirmwareMsgV3:
    """Firmware V3."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[544] Firmware Message V3 not supported at this time")


# [545] Firmware Update V3; TODO: Needs to be implemented...
class FirmwareUpdateMsgV3:
    """Firmware Update V3."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[545] Firmware Update Message V3 not supported at this time")


# [546] Firmware Update Response V2; TODO: Needs to be implemented...
class FirmwareUpdateResponseMsgV2:
    """Firmware Update Response V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[546] Firmware Update Response Message V2 not supported at this time")


# [547] Firmware Update Reset V2; TODO: Needs to be implemented...
class FirmwareUpdateResetMsgV2:
    """Firmware Update Reset V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[547] Firmware Update Reset Message V2 not supported at this time")


# [548] Boot V2
@dataclass(frozen=True, slots=True)
class BootMsgV2(MsgBase):
    """CoreCloud message type."""
    record_id: int = None
    time_of_boot: datetime = None
    flags: int = None
    # chip_id: int = None
    # boot_reason: int = None
    num_exceptions: int = None

    # Non-ORM fields
    __type__ = "UID_548"
    orm_model = Messagesboottbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "record_id": "recordid",
        "time_of_boot": "timeofboot",
        "flags": "flags",
        # "chip_id": "chipid",
        # "boot_reason": "bootreason",
        "num_exceptions": "numexceptions",
    }
    device_time_fields = "timeofboot"

    uid: int = 548
    message_length: int = None
    packed_format: str = None
    packed_struct: List[str] = None

    # Flag bits
    mcu_type_bits = (6, 7)
    fw_triggered_bits = (5, 5)
    boot_reason_bits = (0, 4)

    # Maps
    mcu_type_map = {
        0: "Comms Core",
        1: "App Core",
    }

    fw_triggered_map = {
        0: "Soft reset",
        1: "FW-triggered reset",
    }

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
        """Perform flag mcu."""
        return extract_bits(self.flags, self.mcu_type_bits, cast=int, default=None)

    @property
    def triggered_by(self) -> bool:
        """Perform triggered by."""
        return extract_bits(self.flags, self.fw_triggered_bits, cast=bool, default=None)

    @property
    def boot_reason(self) -> int:
        """Perform boot reason."""
        return extract_bits(self.flags, self.boot_reason_bits, cast=int, default=None)

    @property
    def coprocessor_str(self) -> str:
        """Perform coprocessor str."""
        return self._get_reason_from_mapping(self.flag_mcu, self.mcu_type_map)

    @property
    def fw_triggered_str(self) -> str:
        """Perform fw triggered str."""
        return self._get_reason_from_mapping(self.triggered_by, self.fw_triggered_map)

    @property
    def boot_reason_str(self) -> str:
        """Perform boot reason str."""
        return self._get_reason_from_mapping(self.boot_reason, self.boot_reason_map)


# [549] Comms Coprocessor HW Failure
@dataclass(frozen=True, slots=True)
class CommsHwFailureMsg(MsgBase):
    """CoreCloud message type."""
    record_id: int = None
    time_of_event: datetime = None
    sim_fails: int = None
    lora_fails: int = None
    ipc_fails: int = None
    ext_flash_fails: int = None
    sec_elem_fails: int = None
    sat_modem_fails: int = None

    # Non-ORM fields
    __type__ = "UID_549"
    orm_model = Messagescommshwfailtbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "record_id": "recordid",
        "time_of_event": "timeofevent",
        "sim_fails": "simfails",
        "lora_fails": "sx1262fails",
        "ipc_fails": "ipcfails",
        "ext_flash_fails": "extflashfails",
        "sec_elem_fails": "secelemfails",
        "sat_modem_fails": "satmodemfails",
    }
    device_time_fields = "timeofevent"

    uid = 549
    message_length: int = None
    packed_format: str = None
    packed_struct: List[str] = None

    map_sim_fails = {
        7: "SIM slot 0 failure",
        6: "SIM slot 1 failure",
    }

    map_lora_fails = {
        7: "Communications failure",
        6: "Failed PLL lock",
    }

    map_ipc_fails = {
        7: "Communications failure",
    }

    map_ext_flash_fails = {
        7: "Communications failure",
    }

    map_sec_elem_fails = {
        7: "Communications failure",
    }

    map_sat_modem_fails = {
        7: "Communications failure",
    }

    @property
    def sim_failure_reason(self):
        """Perform sim failure reason."""
        return self._get_reason_from_mapping(self.sim_fails, self.map_sim_fails)

    @property
    def lora_failure_reason(self):
        """Perform lora failure reason."""
        return self._get_reason_from_mapping(self.lora_fails, self.map_lora_fails)

    @property
    def ipc_failure_reason(self):
        """Perform ipc failure reason."""
        return self._get_reason_from_mapping(self.ipc_fails, self.map_ipc_fails)

    @property
    def ext_flash_failure_reason(self):
        """Perform ext flash failure reason."""
        return self._get_reason_from_mapping(self.ext_flash_fails, self.map_ext_flash_fails)

    @property
    def sec_elem_failure_reason(self):
        """Perform sec elem failure reason."""
        return self._get_reason_from_mapping(self.sec_elem_fails, self.map_sec_elem_fails)

    @property
    def sat_modem_failure_reason(self):
        """Perform sat modem failure reason."""
        return self._get_reason_from_mapping(self.sat_modem_fails, self.map_sat_modem_fails)


# [550] Socket Server Configuration V2; TODO: Needs to be implemented...
class SocketServerConfigMsgV2:
    """Socket Server Configuration V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[550] Socket Server Configuration Message V2 not supported at this time")


# [551] Modem Config V2; TODO: Needs to be implemented...
class ModemConfigMsgV2:
    """Modem Config V2."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[551] Modem Config Message V2 not supported at this time")


# [552] Sigma5 HW Failure
@dataclass(frozen=True, slots=True)
class Sigma5HwFailureMsg(MsgBase):
    """CoreCloud message type."""
    xlr_fails: int = None
    alt_fails: int = None
    gps_fails: int = None
    bms_fails: int = None
    ext_flash_fails: int = None

    __type__ = "UID_552"
    orm_model = Messagessigma5hwfailtbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "time_of_event": "timeofevent",
        "xlr_fails": "xlrfails",
        "alt_fails": "altfails",
        "gps_fails": "gpsfails",
        "bms_fails": "bmsfails",
        "ext_flash_fails": "extflashfails",
    }
    device_time_fields = "timeofevent"

    uid: int = 552
    message_length: int = None
    packed_format: str = None
    packed_struct: List[str] = None

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

    @property
    def xlr_failure_reason(self) -> str:
        """Perform xlr failure reason."""
        return self._get_reason_from_mapping(self.xlr_fails, self.map_xlr_fails)

    @property
    def alt_failure_reason(self) -> str:
        """Perform alt failure reason."""
        return self._get_reason_from_mapping(self.alt_fails, self.map_alt_fails)

    @property
    def gps_failure_reason(self) -> str:
        """Perform gps failure reason."""
        return self._get_reason_from_mapping(self.gps_fails, self.map_gps_fails)

    @property
    def bms_failure_reason(self) -> str:
        """Perform bms failure reason."""
        return self._get_reason_from_mapping(self.bms_fails, self.map_bms_fails)

    @property
    def ext_flash_failure_reason(self) -> str:
        """Perform ext flash failure reason."""
        return self._get_reason_from_mapping(self.ext_flash_fails, self.map_ext_flash_fails)


# [553] Iridium Config; TODO: Needs to be implemented...
class IridiumConfigMsgV1:
    """Iridium Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[553] Iridium Config Message V1 not supported at this time")


# [554] Iridium Status; TODO: Needs to be implemented...
class IridiumStatusMsgV1:
    """Iridium Status."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[554] Iridium Status Message V1 not supported at this time")


# [555] User Notification
class UserNotificationMsgV1:
    """User Notification."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[555] User Notification Message V1 not supported at this time")


# [556] Position V6
@dataclass(frozen=True, slots=True)
class PositionMsgV6(MsgBase):
    """
    UID-558: Position Message V6

    Attributes:
        device_id (int): Unique identifier for the device.
        interface_type (int): Type of interface used by the device.
        time_of_record (datetime): Timestamp of when the message was recorded.
        device_message_id (int): Unique identifier for the message.
        record_id (int): Unique identifier for the record.
        flags (int): Bitmask containing various flags.
        is_in_motion (bool): Indicates if the device is in motion.
        gnss_fix_valid (bool): Indicates if the GNSS fix is valid.
        gnss_fix_ok (bool): Indicates if the GNSS fix is OK.
        valid_date (bool): Indicates if the date is valid.
        valid_time (bool): Indicates if the time is valid.
        conf_date (bool): Indicates if the date is confirmed.
        conf_time (bool): Indicates if the time is confirmed.
        conf_time_avail (bool): Indicates if the confirmed time is available.
        on_charger (bool): Indicates if the device is on a charger.
        used_aiding (bool): Indicates if aiding data was used.
        update_reason (int): Reason for the update.
        psm_state (int): Power Saving Mode state.
        num_sat (int): Number of satellites used for the fix.
        fix_type (int): Type of GNSS fix.
        latitude (float): Latitude of the device's position.
        longitude (float): Longitude of the device's position.
        gps_on_time (int): Time the GPS was turned on.
        horizontal_accuracy (int): Horizontal accuracy of the position.
        gps_altitude (int): Altitude from GPS.
        pressure_altitude (int): Altitude from pressure sensor.
        time_of_fix (datetime): Timestamp of the fix.
        ground_speed (int): Ground speed of the device.
        heading (int): Heading of the device.
        batt_voltage (int): Battery voltage.
        air_pressure (float): Air pressure at the device's location.
        temperature (float): Temperature at the device's location.
        avg_force (float): Average force applied to the device.
        max_force (float): Maximum force applied to the device.
        batt_percent (int): Battery percentage.
        pdop (int): Position Dilution of Precision.
        bms_temp (int): Battery Management System temperature.
        gps_vert_accuracy (int): Vertical accuracy of the GPS fix.
        emergency_event_id (int): Identifier for any emergency event.

    Properties:
        flags_reserved_31_28 (int): Reserved bits 31-28 from flags.
        flags_aiding_data_used (bool): Indicates if aiding data was used.
        flags_on_charger (bool): Indicates if the device is on a charger.
        flags_fix_type (int): Type of GNSS fix from flags.
        flags_num_of_satellites (int): Number of satellites used for the fix from flags.
        flags_confirmed_time_available (bool): Indicates if confirmed time is available.
        flags_confirmed_time (bool): Indicates if the time is confirmed.
        flags_confirmed_date (bool): Indicates if the date is confirmed.
        flags_valid_time (bool): Indicates if the time is valid.
        flags_valid_date (bool): Indicates if the date is valid.
        flags_gnss_fix_ok (bool): Indicates if the GNSS fix is OK.
        flags_gnss_fix_valid (bool): Indicates if the GNSS fix is valid.
        flags_psm_state (int): Power Saving Mode state from flags.
        flags_reserved_7_5 (int): Reserved bits 7-5 from flags.
        flags_update_reason (int): Reason for the update from flags.
        flags_in_motion (bool): Indicates if the device is in motion.
        update_reason_str (str): Get the update reason as a string.
        fix_type_str (str): Get the fix type as a string.
        psm_state_str (str): Get the PSM state as a string.
        pressure_altitude_feet (int | None): Pressure altitude in feet.
        pressure_altitude_meters (float | None): Pressure altitude in meters.
        gps_altitude_feet (int | None): GPS altitude in feet.
        gps_altitude_meters (int | None): GPS altitude in meters.
        temperature_celsius (float | None): Temperature in Celsius.
        temperature_fahrenheit (float | None): Temperature in Fahrenheit.

    Class variables:
        uid (int): Unique identifier for the message type.
        orm_model (Type[Any]): ORM model class for database interaction.
        orm_field_map (Dict[str, str]): Mapping of class fields to ORM fields.

    Methods:
        last(dut_id, *, env="VAL_1_0"):
            Get the last message for a device.
        since_server_time(dut_id: int, start_time: datetime, end_time: datetime = None, *, env="VAL_1_0"):
            Get messages since a specific server time.
        since_device_time(dut_id: int, start_time: datetime, end_time: Optional[datetime] = None, *, env="VAL_1_0"):
            Get messages since a specific device time.
        since_record_id(dut_id: int, start_record_id: int, end_record_id: int = None, *, env="VAL_1_0"):
            Get messages since a specific record ID.

    """

    record_id: int = None
    flags: int = None
    is_in_motion: bool = None
    gnss_fix_valid: bool = None
    gnss_fix_ok: bool = None
    valid_date: bool = None
    valid_time: bool = None
    conf_date: bool = None
    conf_time: bool = None
    conf_time_avail: bool = None
    on_charger: bool = None
    used_aiding: bool = None
    update_reason: int = None
    psm_state: int = None
    num_sat: int = None
    fix_type: int = None
    latitude: float = None
    longitude: float = None
    gps_on_time: int = None
    horizontal_accuracy: int = None
    gps_altitude: int = None
    pressure_altitude: int = None
    time_of_fix: datetime = None
    ground_speed: int = None
    heading: int = None
    batt_voltage: int = None
    air_pressure: float = None
    temperature: float = None
    avg_force: float = None
    max_force: float = None
    batt_percent: int = None
    pdop: int = None
    bms_temp: int = None
    gps_vert_accuracy: int = None
    emergency_event_id: int = None

    # Non-Data Fields
    __type__ = "UID_556"
    orm_model = Messagespositionv5tbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "record_id": "recordid",
        "flags": "flags",
        "is_in_motion": "isinmotion",
        "gnss_fix_valid": "gnssfixvalid",
        "gnss_fix_ok": "gnssfixok",
        "valid_date": "validdate",
        "valid_time": "validtime",
        "conf_date": "confdate",
        "conf_time": "conftime",
        "conf_time_avail": "conftimeavail",
        "on_charger": "oncharger",
        "used_aiding": "usedaiding",
        "update_reason": "updatereason",
        "psm_state": "psmstate",
        "num_sat": "numsat",
        "fix_type": "fixtype",
        "latitude": "latitude",
        "longitude": "longitude",
        "gps_on_time": "gpsontime",
        "horizontal_accuracy": "horizontalaccuracy",
        "gps_altitude": "gpsaltitude",
        "pressure_altitude": "pressurealtitude",
        "time_of_fix": "timeoffix",
        "ground_speed": "groundspeed",
        "heading": "heading",
        "batt_voltage": "battvoltage",
        "air_pressure": "airpressure",
        "temperature": "temperature",
        "avg_force": "avgforce",
        "max_force": "maxforce",
        "batt_percent": "battpercent",
        "pdop": "pdop",
        "bms_temp": "bmstemp",
        "gps_vert_accuracy": "vertaccuracy",
        "emergency_event_id": "emergencyeventid",
    }
    device_time_fields = "timeoffix"

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
        0: "PSM is not active (device is in continuous mode)",
        1: "PSM Enabled (intermediate state before Acquisition state)",
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

    # Decode flags
    @property
    def flags_reserved_31_28(self) -> int:
        """Return reserved bits 31-28 from flags."""
        return extract_bits(self.flags, self.reserved_31_28_bits, cast=int, default=None)

    @property
    def flags_aiding_data_used(self) -> bool:
        """(bool): Indicates if aiding data was used."""
        return extract_bits(self.flags, self.aiding_data_used_bits, cast=bool, default=None)

    @property
    def flags_on_charger(self) -> bool:
        """(bool): Indicates if the device is on a charger."""
        return extract_bits(self.flags, self.on_charger_bits, cast=bool, default=None)

    @property
    def flags_fix_type(self) -> int:
        """(int): Type of GNSS fix from flags."""
        return extract_bits(self.flags, self.fix_type_bits, cast=int, default=None)

    @property
    def flags_num_of_satellites(self) -> int:
        """(int): Number of satellites used for the fix from flags."""
        return extract_bits(self.flags, self.num_of_satellites_bits, cast=int, default=None)

    @property
    def flags_confirmed_time_available(self) -> bool:
        """(bool): Indicates if confirmed time is available."""
        return extract_bits(self.flags, self.confirmed_time_available_bits, cast=bool, default=None)

    @property
    def flags_confirmed_time(self) -> bool:
        """(bool): Indicates if the time is confirmed."""
        return extract_bits(self.flags, self.confirmed_time_bits, cast=bool, default=None)

    @property
    def flags_confirmed_date(self) -> bool:
        """(bool): Indicates if the date is confirmed."""
        return extract_bits(self.flags, self.confirmed_date_bits, cast=bool, default=None)

    @property
    def flags_valid_time(self) -> bool:
        """(bool): Indicates if the time is valid."""
        return extract_bits(self.flags, self.valid_time_bits, cast=bool, default=None)

    @property
    def flags_valid_date(self) -> bool:
        """(bool): Indicates if the date is valid."""
        return extract_bits(self.flags, self.valid_date_bits, cast=bool, default=None)

    @property
    def flags_gnss_fix_ok(self) -> bool:
        """(bool): Indicates if the GNSS fix is OK."""
        return extract_bits(self.flags, self.gnss_fix_ok_bits, cast=bool, default=None)

    @property
    def flags_gnss_fix_valid(self) -> bool:
        """(bool): Indicates if the GNSS fix is valid."""
        return extract_bits(self.flags, self.gnss_fix_valid_bits, cast=bool, default=None)

    @property
    def flags_psm_state(self) -> int:
        """(int): Power Saving Mode state from flags."""
        return extract_bits(self.flags, self.psm_state_bits, cast=int, default=None)

    @property
    def flags_reserved_7_5(self) -> int:
        """(int): Reserved bits 7-5 from flags."""
        return extract_bits(self.flags, self.reserved_7_5_bits, cast=int, default=None)

    @property
    def flags_update_reason(self) -> int:
        """(int): Reason for the update from flags."""
        return extract_bits(self.flags, self.update_reason_bits, cast=int, default=None)

    @property
    def flags_in_motion(self) -> bool:
        """(bool): Indicates if the device is in motion."""
        return extract_bits(self.flags, self.in_motion_bits, cast=bool, default=None)

    @property
    def update_reason_str(self) -> str:
        """(str): Get the update reason as a string."""
        return self._get_reason_from_mapping(self.flags_update_reason, self.update_reason_map)

    @property
    def fix_type_str(self) -> str:
        """(str): Get the fix type as a string."""
        return self._get_reason_from_mapping(self.flags_fix_type, self.fix_type_map)

    @property
    def psm_state_str(self) -> str:
        """(str): Get the PSM state as a string."""
        return self._get_reason_from_mapping(self.flags_psm_state, self.psm_state_map)

    @property
    def pressure_altitude_feet(self) -> int | None:
        """(int | None): Pressure altitude in feet."""
        return self.pressure_altitude

    @property
    def pressure_altitude_meters(self) -> float | None:
        """(float | None): Pressure altitude in meters."""
        return feet_to_meters(self.pressure_altitude) if self.pressure_altitude is not None else None

    @property
    def gps_altitude_feet(self) -> int | None:
        """(int | None): GPS altitude in feet."""
        return meters_to_feet(self.gps_altitude) if self.gps_altitude is not None else None

    @property
    def gps_altitude_meters(self) -> int | None:
        """(int | None): GPS altitude in meters."""
        return self.gps_altitude

    @property
    def temperature_celsius(self) -> float | None:
        """(float | None): Temperature in Celsius."""
        return self.temperature

    @property
    def temperature_fahrenheit(self) -> float | None:
        """(float | None): Temperature in Fahrenheit."""
        return celsius_to_fahrenheit(self.temperature) if self.temperature is not None else None


# [557] Biometric Data
@dataclass(frozen=True, slots=True)
class BiometricDataMsg(MsgBase):
    """CoreCloud message type."""
    record_id: int = None
    time_of_measurement: datetime = None
    flags: int = None
    air_pressure: int = None
    external_temperature: int = None
    relative_humidity: int = None
    heart_rate: int = None
    heart_rate_confidence: int = None
    spo2: int = None
    spo2_confidence: int = None
    skin_temperature: int = None
    estimated_core_temperature: int = None
    heat_strain_index: int = None
    wobble_index: int = None
    vsm_on_time: int = None
    heat_emergency_event_id: int = None

    # Non-ORM fields
    __type__ = "UID_557"
    orm_model = Messagesbiometricdatatbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "record_id": "recordid",
        "time_of_measurement": "timeofmeasurement",
        "flags": "flags",
        "air_pressure": "airpressure",
        "external_temperature": "externaltemperature",
        "relative_humidity": "relativehumidity",
        "heart_rate": "heartrate",
        "heart_rate_confidence": "heartrateconfidence",
        "spo2": "spo2",
        "spo2_confidence": "spo2confidence",
        "skin_temperature": "skintemperature",
        "estimated_core_temperature": "estimatedcoretemperature",
        "heat_strain_index": "heatstrainindex",
        "wobble_index": "wobbleindex",
        "vsm_on_time": "vsmontime",
        "heat_emergency_event_id": "heatemergencyeventid",
    }
    device_time_fields = "timeofmeasurement"

    uid: int = 557
    message_length: int = None
    packed_format: str = None
    packed_struct: List[str] = None

    # Flag bits
    reserved_7_1 = (1, 7)
    on_body_bits = (0, 0)

    # Decode flags
    @property
    def on_body(self) -> bool:
        """Perform on body."""
        return extract_bits(self.flags, self.on_body_bits, cast=bool, default=None)


# [558] Biometric Config; TODO: Needs to be implemented...
class BiometricConfigMsgV1:
    """Biometric Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[558] Biometric Config Message V1 not supported at this time.")


# [559] Alpha HW Failure
@dataclass(frozen=True, slots=True)
class AlphaHwFailureMsg(MsgBase):
    """CoreCloud message type."""
    record_id: int = None
    time_of_event: datetime = None
    xlr_fails: int = None
    alt_fails: int = None
    gps_fails: int = None
    bms_fails: int = None
    ext_flash_fails: int = None
    ppg_fails: int = None
    imu_fails: int = None
    ir_fails: int = None
    batt_charger_fails: int = None

    # Non-ORM fields
    __type__ = "UID_559"
    orm_model = Messagesalphahwfailtbl
    orm_field_map = {
        **MsgBase.orm_field_map,
        "record_id": "recordid",
        "time_of_event": "timeofevent",
        "xlr_fails": "xlrfails",
        "alt_fails": "altfails",
        "gps_fails": "gpsfails",
        "bms_fails": "bmsfails",
        "ext_flash_fails": "extflashfails",
        "ppg_fails": "ppgfails",
        "imu_fails": "imufails",
        "ir_fails": "irfails",
        "batt_charger_fails": "battchargerfails",
    }
    device_time_fields = "timeofevent"

    uid: int = 559
    message_length: int = None
    packed_format: str = None
    packed_struct: List[str] = None

    map_xlr_fails = {7: "Communications failure"}
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
    map_ppg_fails = {
        7: "Communications failure",
        6: "PSP library failure",
        5: "VSM driver watchdog tripped",
    }
    map_imu_fails = {
        7: "Communications failure",
    }
    map_ir_fails = {
        7: "Communications failure",
    }
    map_batt_charger_fails = {
        7: "Communications failure",
    }

    @property
    def xlr_failure_reason(self) -> str:
        """Perform xlr failure reason."""
        return self._get_reason_from_mapping(self.xlr_fails, self.map_xlr_fails)

    @property
    def alt_failure_reason(self) -> str:
        """Perform alt failure reason."""
        return self._get_reason_from_mapping(self.alt_fails, self.map_alt_fails)

    @property
    def gps_failure_reason(self) -> str:
        """Perform gps failure reason."""
        return self._get_reason_from_mapping(self.gps_fails, self.map_gps_fails)

    @property
    def bms_failure_reason(self) -> str:
        """Perform bms failure reason."""
        return self._get_reason_from_mapping(self.bms_fails, self.map_bms_fails)

    @property
    def ext_flash_failure_reason(self) -> str:
        """Perform ext flash failure reason."""
        return self._get_reason_from_mapping(self.ext_flash_fails, self.map_ext_flash_fails)

    @property
    def ppg_failure_reason(self) -> str:
        """Perform ppg failure reason."""
        return self._get_reason_from_mapping(self.ppg_fails, self.map_ppg_fails)

    @property
    def imu_failure_reason(self) -> str:
        """Perform imu failure reason."""
        return self._get_reason_from_mapping(self.imu_fails, self.map_imu_fails)

    @property
    def ir_failure_reason(self) -> str:
        """Perform ir failure reason."""
        return self._get_reason_from_mapping(self.ir_fails, self.map_ir_fails)

    @property
    def batt_charger_failure_reason(self) -> str:
        """Perform batt charger failure reason."""
        return self._get_reason_from_mapping(self.batt_charger_fails, self.map_batt_charger_fails)


# [560] LoRa Config V2; Needs to be implemented
class LoRaConfigMsgV2:
    """LoRa Config V2; Needs to be implemented."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[560] LoRa Config Message V2 not supported at this time.")


# [561] Binary Image Upload; TODO: Needs to be implemented...
class BinaryImageUploadMsgV1:
    """Binary Image Upload."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[561] Binary Image Upload Message V1 not supported at this time.")


# [562] Drone Mode Config; TODO: Needs to be implemented...
class DroneModeConfigMsgV1:
    """Drone Mode Config."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[562] Drone Mode Config Message V1 not supported at this time.")


# [563] Theta HW Failure; TODO: Needs to be implemented...
class ThetaHwFailureMsgV1:
    """Theta HW Failure."""
    def __init__(self):
        """Perform   init  ."""
        raise NotImplementedError(f"[563] Theta HW Failure Message V1 not supported at this time.")
