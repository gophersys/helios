import json
from typing import Any, Dict, Type, TypeVar

T = TypeVar("T")


class Serializable:
    _class_map = {}

    def __init_subclass__(cls, **kwargs):
        """Automatically register subclasses."""
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "__type__"):
            Serializable._class_map[cls.__type__] = cls

    def _stringify_keys(cls, d):
        if isinstance(d, dict):
            return {str(k): cls._stringify_keys(v) for k, v in d.items()}
        if isinstance(d, list):
            return [cls._stringify_keys(i) for i in d]
        return d

    def _intify_keys(cls, d):
        if isinstance(d, dict):
            return {int(k) if k.isdigit() else k: cls._intify_keys(v) for k, v in d.items()}
        if isinstance(d, list):
            return [cls._intify_keys(i) for i in d]
        return d

    def to_dict(self) -> Dict[str, Any]:
        """Convert the object to a dictionary."""
        data = {
            key: (
                value.to_dict()
                if isinstance(value, Serializable)
                else (
                    [v.to_dict() if isinstance(v, Serializable) else v for v in value]
                    if isinstance(value, list)
                    else value
                )
            )
            for key, value in self.__dict__.items()
        }
        data["type"] = self.__class__.__type__  # Add the type field for serialization
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Any:
        """Resolve the correct class and deserialize."""
        class_type = data.get("type")
        if not class_type or class_type not in cls._class_map:
            raise TypeError(f"Unknown type '{class_type}' for deserialization.")
        target_cls = cls._class_map[class_type]
        return target_cls(
            **{
                key: (
                    [Serializable.from_dict(v) if isinstance(v, dict) and "type" in v else v for v in value]
                    if isinstance(value, list)
                    else Serializable.from_dict(value) if isinstance(value, dict) and "type" in value else value
                )
                for key, value in data.items()
                if key != "type"
            }
        )

    def marshall(self) -> str:
        """Convert the object to a JSON string."""
        return json.dumps(self.to_dict(), indent=2)

    @classmethod
    def unmarshall(cls: Type[T], json_str: str) -> T:
        """Reconstruct the object from a JSON string."""
        data = json.loads(json_str)
        return cls.from_dict(data)
