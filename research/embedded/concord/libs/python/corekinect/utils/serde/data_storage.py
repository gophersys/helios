import json
from dataclasses import asdict, dataclass, fields, is_dataclass, MISSING
from datetime import datetime
from typing import (
    Any,
    Dict,
    List,
    Type,
    TypeVar,
    get_args,
    get_origin,
    Union,
)

T = TypeVar("T", bound="DataStorageObject")


@dataclass(frozen=True)
class DataStorageObject:
    """
    Generic reusable storage base class.

    Features:
    - to_dict / from_dict
    - marshal (JSON) / unmarshal
    - csv_headers / to_csv_row / from_csv_row
    - Handles:
        * datetime <-> ISO8601 strings
        * Optional[T]
        * list[T]
        * dict[str, T]
        * Nested dataclasses / DataStorageObject subclasses
    """

    # --------------------|  Private Utils  |--------------------

    @staticmethod
    def _strip_optional(annot: Any) -> tuple[Any, bool]:
        """Return (inner_type, is_optional)."""
        origin = get_origin(annot)
        if origin is Union:
            args = get_args(annot)
            non_none = [a for a in args if a is not type(None)]
            if len(non_none) == 1:
                return non_none[0], True
        return annot, False

    @staticmethod
    def _serialize_value(value: Any) -> Any:
        """Serialize a Python value into JSON/CSV-friendly form."""
        if isinstance(value, datetime):
            return value.isoformat()

        # Nested dataclasses / DataStorageObject
        if is_dataclass(value):
            # Assuming they have to_dict if they subclass us,
            # but dataclasses.asdict would also work in simple cases.
            if isinstance(value, DataStorageObject):
                return value.to_dict()
            return asdict(value)

        # Lists and dicts – recurse
        if isinstance(value, list):
            return [DataStorageObject._serialize_value(v) for v in value]

        if isinstance(value, dict):
            return {k: DataStorageObject._serialize_value(v) for k, v in value.items()}

        # Everything else: primitive types (int, float, str, bool, None, etc.)
        return value

    @staticmethod
    def _deserialize_value(annot: Any, value: Any) -> Any:
        """Deserialize JSON/CSV value into the annotated Python type."""
        # Handle Optional[T]
        inner, is_optional = DataStorageObject._strip_optional(annot)
        if is_optional:
            if value is None or value == "":
                return None
            annot = inner

        origin = get_origin(annot)
        args = get_args(annot)

        # datetime from ISO string
        if annot is datetime:
            if isinstance(value, datetime):
                return value
            if isinstance(value, str):
                return datetime.fromisoformat(value)
            raise TypeError(f"Cannot convert {value!r} to datetime")

        # list[T]
        if origin is list and args:
            elem_type = args[0]
            if not isinstance(value, list):
                # Allow CSV string encoding (e.g. JSON string)
                if isinstance(value, str):
                    value = json.loads(value)
            return [DataStorageObject._deserialize_value(elem_type, v) for v in value]

        # dict[str, T]
        if origin is dict and args and len(args) == 2:
            key_type, val_type = args
            if key_type is not str:
                raise TypeError("Only dict[str, T] supported generically")
            if not isinstance(value, dict):
                if isinstance(value, str):
                    value = json.loads(value)
            return {str(k): DataStorageObject._deserialize_value(val_type, v) for k, v in value.items()}

        # Nested dataclasses / DataStorageObject
        if isinstance(annot, type) and is_dataclass(annot):
            if isinstance(value, annot):
                return value
            if isinstance(value, dict):
                if issubclass(annot, DataStorageObject):
                    return annot.from_dict(value)
                return annot(**value)

        # Primitive types: int, float, bool, str
        if annot in (int, float, bool, str):
            if isinstance(value, annot):
                return value

            if isinstance(value, str):
                v = value.strip()
                if annot is bool:
                    if v.lower() in ("true", "1", "yes", "y", "on"):
                        return True
                    if v.lower() in ("false", "0", "no", "n", "off"):
                        return False
                    raise ValueError(f"Cannot interpret {value!r} as bool")
                try:
                    return annot(v)  # int(v) / float(v) / str(v)
                except Exception as exc:
                    raise TypeError(f"Cannot convert {value!r} to {annot}") from exc

            # Last resort: try to cast
            try:
                return annot(value)
            except Exception as exc:
                raise TypeError(f"Cannot convert {value!r} to {annot}") from exc

        # Fallback: just return as-is
        return value

    # --------------------|  Dict Conversion  |--------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize this object to a plain dictionary."""
        out: Dict[str, Any] = {}
        for f in fields(self):
            v = getattr(self, f.name)
            out[f.name] = self._serialize_value(v)
        return out

    @classmethod
    def from_dict(cls: Type[T], data: Dict[str, Any]) -> T:
        """Deserialize a dictionary into this dataclass type."""
        kwargs: Dict[str, Any] = {}

        for f in fields(cls):
            if f.name in data:
                raw = data[f.name]
            else:
                # Respect dataclass defaults if not present
                if f.default is not MISSING or f.default_factory is not MISSING:  # type: ignore[attr-defined]
                    continue
                raise ValueError(f"Missing field {f.name} for {cls.__name__}")

            value = cls._deserialize_value(f.type, raw)
            kwargs[f.name] = value

        return cls(**kwargs)

    # --------------------|  JSON  |--------------------

    def marshal(self) -> str:
        """Serialize this object to a JSON string."""
        return json.dumps(self.to_dict())

    @classmethod
    def unmarshal(cls: Type[T], s: str) -> T:
        """Deserialize a JSON string into this dataclass type."""
        return cls.from_dict(json.loads(s))

    # --------------------|  CSV  |--------------------
    @classmethod
    def csv_headers(cls) -> List[str]:
        """Return the CSV column headers in field order."""
        return [f.name for f in fields(cls)]

    def to_csv_row(self) -> List[Any]:
        """
        Generic CSV row:
        - datetime -> ISO string
        - list/dict/nested objects -> JSON string
        - primitives -> as-is
        """
        row: List[Any] = []

        for f in fields(self):
            v = getattr(self, f.name)
            serialized = self._serialize_value(v)

            # For complex types, store as JSON string to keep row flat
            if isinstance(serialized, (list, dict)):
                row.append(json.dumps(serialized))
            else:
                row.append(serialized)

        return row

    @classmethod
    def from_csv_row(cls: Type[T], row: List[Any]) -> T:
        """
        CSV row must be in field order.
        Values may be native Python types or strings.
        """
        kwargs: Dict[str, Any] = {}

        for f, raw in zip(fields(cls), row):
            value = cls._deserialize_value(f.type, raw)
            kwargs[f.name] = value

        return cls(**kwargs)
