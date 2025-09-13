import os
from pathlib import Path
from typing import Any, List, Optional, Type, Union, get_args, get_origin

from dotenv import find_dotenv, load_dotenv


class EnvConfig:
    """
    Base class that loads environment variables into annotated attributes.
    - Honors Optional[...] and class-level defaults.
    - Uses ENV_PREFIX (e.g., "DB_", "SSH_") for env variable names.
    - Converts bool/int/float/List[...] and Path types.
    - Auto-loads .env like the old version (ENV_FILE_PATH/ENV_FILE_NAME supported).
    """

    ENV_PREFIX: str = ""

    def __init__(self, namespace: Optional[str] = None, *, auto_load_env: bool = True) -> None:
        if auto_load_env:
            self._load_env_file()
        self._initialize_from_env(namespace)

    def _load_env_file(self) -> None:
        env_file_path = os.getenv("ENV_FILE_PATH")
        env_file_name = os.getenv("ENV_FILE_NAME")

        loaded = False
        if env_file_path and env_file_name:
            env_file = os.path.join(env_file_path, env_file_name)
            if os.path.exists(env_file):
                if os.path.isfile(env_file):
                    loaded = load_dotenv(env_file)
                else:
                    raise EnvironmentError(f"{env_file} is not a file.")
            else:
                raise EnvironmentError(f"{env_file} does not exist.")
        else:
            # Prefer a local .env if present
            if os.path.exists(".env") and os.path.isfile(".env"):
                loaded = load_dotenv(".env")
            else:
                # Fallback: search up the tree
                found = find_dotenv(usecwd=True)
                if found:
                    loaded = load_dotenv(found)

        if not loaded:
            raise (RuntimeError(f"Environment variable file not found."))

    @staticmethod
    def _is_optional(t) -> bool:
        return get_origin(t) is Union and type(None) in get_args(t)

    @staticmethod
    def _unwrap_optional(t):
        if get_origin(t) is Union:
            args = tuple(a for a in get_args(t) if a is not type(None))
            return args[0] if args else Any
        return t

    @staticmethod
    def _parse_bool(value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _expand_path(value: str) -> str:
        return str(Path(os.path.expanduser(os.path.expandvars(value))).resolve())

    @classmethod
    def _convert_value(cls, value: str, expected_type: Type[Any]) -> Any:
        base = cls._unwrap_optional(expected_type)
        origin = get_origin(base)

        if origin in (list, List):
            inner = get_args(base)[0] if get_args(base) else str
            parts = [p.strip() for p in value.split(",") if p.strip() != ""]
            return [cls._convert_value(p, inner) for p in parts]

        if base is Path:
            return Path(cls._expand_path(value))

        if base is bool:
            return cls._parse_bool(value)
        if base is int:
            return int(value)
        if base is float:
            return float(value)
        if base is str or base is Any:
            return value

        return base(value)

    def _initialize_from_env(self, namespace: Optional[str] = None) -> None:
        ns_prefix = (namespace.rstrip("_") + "_").upper() if namespace else None
        annotations = getattr(self.__class__, "__annotations__", {})

        for attr_name, expected_type in annotations.items():
            base_key = f"{self.ENV_PREFIX}{attr_name}".upper()

            raw = os.getenv(ns_prefix + base_key) if ns_prefix else None
            if raw is None or raw == "":
                raw = os.getenv(base_key)

            has_default = hasattr(self.__class__, attr_name)
            default_val = getattr(self.__class__, attr_name) if has_default else None

            if raw is None or raw == "":
                if has_default:
                    setattr(self, attr_name, default_val)
                    continue
                if self._is_optional(expected_type):
                    setattr(self, attr_name, None)
                    continue
                raise EnvironmentError(f"Environment variable '{base_key}' not found.")
            else:
                try:
                    converted = self._convert_value(raw, expected_type)
                except Exception as e:
                    raise TypeError(f"Could not convert env '{base_key}'='{raw}' to {expected_type}: {e}") from e
                setattr(self, attr_name, converted)

    def __str__(self) -> str:
        lines = []
        for name in getattr(self.__class__, "__annotations__", {}):
            lines.append(f"{name}: {getattr(self, name, None)}")
        return "\n".join(lines)
