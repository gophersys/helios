from dataclasses import is_dataclass
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    Callable,
    Annotated,
    Optional,
    get_args,
    get_origin,
)

BoolParser = Callable[[str], bool]
PathExpander = Callable[[str], str]

from corekinect.utils import Logger


def unwrap_annotated(tp: Any) -> tuple[Any, list[Any]]:
    """
    If tp is Annotated[T, m1, m2, ...], return (T, [m1, m2, ...]).
    Otherwise return (tp, []).
    """
    if get_origin(tp) is Annotated:
        base, *meta = get_args(tp)
        return base, list(meta)
    return tp, []


def unwrap_optional(tp: Any) -> Any:
    """
    If tp is Optional[T] or Union[T, None], return T.
    Otherwise return tp.
    """
    origin = get_origin(tp)
    args = get_args(tp)

    # Optional[T] is just Union[T, NoneType]
    if origin is Optional:
        return args[0] if args else Any
    if origin is getattr(__import__("typing"), "Union", None):
        non_none = [a for a in args if a is not type(None)]  # noqa: E721
        if len(non_none) == 1:
            return non_none[0]
    return tp


def convert_str_to_type(
    value: str | None,
    expected_type: Any,
    *,
    empty_is_none: bool = True,
    bool_parser: BoolParser | None = None,
    path_expander: PathExpander | None = None,
) -> Any:
    """General-purpose string -> typed value converter."""
    log = Logger(log_name=convert_str_to_type.__name__)

    if value is None:
        return None
    value = value.strip()

    if value == "" and empty_is_none:
        return None

    # Unwrap Annotated and Optional
    base, _meta = unwrap_annotated(expected_type)
    base = unwrap_optional(base)
    origin = get_origin(base)

    # --------------------|  Containers  |--------------------
    if origin in (
        list,
        list.__class__,
    ):
        inner = get_args(base)[0] if get_args(base) else str
        parts = [p.strip() for p in value.split(",") if p.strip() != ""]
        return [
            convert_str_to_type(
                p, inner, empty_is_none=empty_is_none, bool_parser=bool_parser, path_expander=path_expander
            )
            for p in parts
        ]

    # --------------------|  Special types  |--------------------
    if base is Path:
        if path_expander:
            value = path_expander(value)
        return Path(value)

    if base is bool:
        if bool_parser:
            return bool_parser(value)
        return value.lower() in {"1", "true", "t", "yes", "y", "on"}

    if base is int:
        return int(value)

    if base is float:
        return float(value)

    if base is str or base is Any:
        return value

    if base is datetime:
        return datetime.fromisoformat(value)

    # Dataclasses or other custom types that accept a single string
    if is_dataclass(base):
        log.warning(f"{base=} conversion may not be what we want... Making {value=} a {base=}")
        return base(value)

    log.warning(f"We fell through, making {value=} a {base=}")
    return base(value)
