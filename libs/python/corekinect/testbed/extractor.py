"""AST-only extractor for fixture metadata.

The backend uploads-and-extracts path needs to read fixture metadata
out of a Python module *without* executing the test app's code. We
walk the AST, find the unique class that subclasses ``TestBed``, and
read its class-level constants and resource maps as literals.

Failure modes that get rejected here (each raises
:exc:`TestBedExtractionError` with a specific message):

* No class subclassing ``TestBed`` in the source.
* More than one ``TestBed`` subclass in a single module.
* ``name`` or ``revision`` missing or non-literal-string.
* A resource value like ``ADC(channel=99)`` with an out-of-range
  channel.
* A resource value that's not one of the known declarative types.
* Anything that requires evaluating arbitrary code (variables,
  imports, list comprehensions in resource maps, etc.).

The returned dict is shaped to match :func:`TestBed.summary` so the
backend can drop it directly into ``TestBedDesign.profileTemplate``.
"""

from __future__ import annotations

import ast
from typing import Any, Dict, List, Optional, Tuple

from corekinect.testbed import topology


class TestBedExtractionError(ValueError):
    __test__ = False  # not a pytest test class
    """A fixture module's AST violates the extraction contract."""


# Resource-type names the extractor recognises and how to read their
# arguments. Each entry maps the type name to a parser that returns
# the summary dict for one declaration. Adding a new declarative type
# means: add it here, add the binding in
# :mod:`corekinect.testbed.types`, add a topology limit if needed.
_KNOWN_RESOURCE_TYPES = {"ADC", "GPIO", "UART", "JLink", "Power", "I2C", "SPI"}


def extract_testbed(source: str, *, source_path: str = "<fixture>") -> Dict[str, Any]:
    """Extract a fixture's metadata from its Python source.

    ``source_path`` is included in error messages to help operators
    locate the offending module.
    """
    try:
        tree = ast.parse(source, filename=source_path)
    except SyntaxError as e:
        raise TestBedExtractionError(
            f"{source_path}: syntax error: {e.msg} (line {e.lineno})"
        ) from None

    testbed_classes = [
        node for node in tree.body
        if isinstance(node, ast.ClassDef) and _has_fixture_base(node)
    ]
    if not testbed_classes:
        raise TestBedExtractionError(
            f"{source_path}: no class subclassing TestBed found"
        )
    if len(testbed_classes) > 1:
        names = [c.name for c in testbed_classes]
        raise TestBedExtractionError(
            f"{source_path}: expected exactly one TestBed subclass, found "
            f"{len(testbed_classes)}: {names}"
        )

    cls = testbed_classes[0]
    constants = _collect_class_assigns(cls)

    name = _require_string_literal(constants, "name", cls, source_path)
    revision = _require_string_literal(constants, "revision", cls, source_path)

    return {
        "name": name,
        "revision": revision,
        "class_name": cls.name,
        "adcs": _extract_resource_map(constants, "adcs", "ADC", _parse_adc, source_path),
        "gpios": _extract_resource_map(constants, "gpios", "GPIO", _parse_gpio, source_path),
        "uarts": _extract_resource_map(constants, "uarts", "UART", _parse_uart, source_path),
        "jlinks": _extract_resource_map(constants, "jlinks", "JLink", _parse_jlink, source_path),
        "power": _extract_resource_map(constants, "power", "Power", _parse_power, source_path),
    }


# ── Helpers ─────────────────────────────────────────────────────


def _has_fixture_base(cls: ast.ClassDef) -> bool:
    """Does ``cls`` list ``TestBed`` (any import alias) as a base?"""
    for base in cls.bases:
        # ``class Foo(TestBed):``
        if isinstance(base, ast.Name) and base.id == "TestBed":
            return True
        # ``class Foo(corekinect.testbed.TestBed):``
        if isinstance(base, ast.Attribute) and base.attr == "TestBed":
            return True
    return False


def _collect_class_assigns(cls: ast.ClassDef) -> Dict[str, ast.AST]:
    """Return ``{attr_name: value_node}`` for top-level class assigns.

    Only handles plain ``name = expr`` and ``name: type = expr``
    forms. Nested logic, methods, and conditional assigns are
    ignored — they can't be extracted statically anyway.
    """
    result: Dict[str, ast.AST] = {}
    for stmt in cls.body:
        if isinstance(stmt, ast.Assign):
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = stmt.value
        elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            if stmt.value is not None:
                result[stmt.target.id] = stmt.value
    return result


def _require_string_literal(
    constants: Dict[str, ast.AST],
    attr: str,
    cls: ast.ClassDef,
    source_path: str,
) -> str:
    node = constants.get(attr)
    if node is None:
        raise TestBedExtractionError(
            f"{source_path}: class {cls.name} missing required attribute "
            f"``{attr}`` (must be a string literal)"
        )
    if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
        raise TestBedExtractionError(
            f"{source_path}: class {cls.name}.{attr} must be a string "
            f"literal, got {type(node).__name__}"
        )
    if not node.value:
        raise TestBedExtractionError(
            f"{source_path}: class {cls.name}.{attr} must be a non-empty "
            f"string"
        )
    return node.value


def _extract_resource_map(
    constants: Dict[str, ast.AST],
    attr: str,
    expected_type: str,
    parser,
    source_path: str,
) -> Dict[str, Any]:
    """Walk ``cls.<attr>`` (a dict literal) into ``{key: parser(call_node)}``."""
    node = constants.get(attr)
    if node is None:
        return {}
    if not isinstance(node, ast.Dict):
        raise TestBedExtractionError(
            f"{source_path}: ``{attr}`` must be a dict literal"
        )

    result: Dict[str, Any] = {}
    for key_node, val_node in zip(node.keys, node.values):
        if not isinstance(key_node, ast.Constant) or not isinstance(key_node.value, str):
            raise TestBedExtractionError(
                f"{source_path}: ``{attr}`` keys must be string literals"
            )
        key = key_node.value
        if not key:
            raise TestBedExtractionError(
                f"{source_path}: ``{attr}`` has an empty-string key"
            )
        if not isinstance(val_node, ast.Call):
            raise TestBedExtractionError(
                f"{source_path}: ``{attr}[{key!r}]`` must be a call to "
                f"{expected_type}(...)"
            )
        type_name = _call_type_name(val_node)
        if type_name != expected_type:
            raise TestBedExtractionError(
                f"{source_path}: ``{attr}[{key!r}]`` expected "
                f"{expected_type}(...), got {type_name}(...)"
            )
        result[key] = parser(val_node, attr, key, source_path)
    return result


def _call_type_name(call: ast.Call) -> str:
    """Return the name part of a call (``ADC(...)`` → ``"ADC"``)."""
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return ""


def _kwargs(call: ast.Call) -> Dict[str, ast.AST]:
    """Return the ``kw=value`` arguments as a name→AST dict."""
    return {kw.arg: kw.value for kw in call.keywords if kw.arg is not None}


def _const(node: Optional[ast.AST]) -> Any:
    """Resolve a literal node to its Python value, or ``None``."""
    if node is None:
        return None
    if isinstance(node, ast.Constant):
        return node.value
    # Negative numeric literal: ``-1`` parses to UnaryOp(USub, Constant).
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        if isinstance(node.operand, ast.Constant) and isinstance(
            node.operand.value, (int, float)
        ):
            return -node.operand.value
    return None


def _require_int(
    kwargs: Dict[str, ast.AST],
    name: str,
    where: str,
    source_path: str,
) -> int:
    val = _const(kwargs.get(name))
    if not isinstance(val, int):
        raise TestBedExtractionError(
            f"{source_path}: {where}: ``{name}`` must be an integer literal"
        )
    return val


def _optional_string(
    kwargs: Dict[str, ast.AST],
    name: str,
    default: str = "",
) -> str:
    val = _const(kwargs.get(name))
    if val is None:
        return default
    if not isinstance(val, str):
        return default
    return val


def _optional_float(
    kwargs: Dict[str, ast.AST],
    name: str,
    default: float = 1.0,
) -> float:
    val = _const(kwargs.get(name))
    if val is None:
        return default
    if isinstance(val, (int, float)):
        return float(val)
    return default


def _optional_int(
    kwargs: Dict[str, ast.AST],
    name: str,
    default: int,
) -> int:
    val = _const(kwargs.get(name))
    if isinstance(val, int):
        return val
    return default


# ── Per-type parsers ────────────────────────────────────────────


def _parse_adc(call: ast.Call, attr: str, key: str, source_path: str) -> Dict[str, Any]:
    where = f"{attr}[{key!r}]"
    kw = _kwargs(call)
    channel = _require_int(kw, "channel", where, source_path)
    if channel not in topology.ADC_CHANNELS:
        raise TestBedExtractionError(
            f"{source_path}: {where}: ADC channel {channel} out of range. "
            f"Valid: {topology.ADC_CHANNELS}"
        )
    divider = _optional_float(kw, "divider", 1.0)
    if divider <= 0:
        raise TestBedExtractionError(
            f"{source_path}: {where}: divider must be > 0, got {divider}"
        )
    return {
        "channel": channel,
        "signal": _optional_string(kw, "signal"),
        "divider": divider,
        "description": _optional_string(kw, "description"),
    }


def _parse_gpio(call: ast.Call, attr: str, key: str, source_path: str) -> Dict[str, Any]:
    where = f"{attr}[{key!r}]"
    kw = _kwargs(call)
    pin = _require_int(kw, "pin", where, source_path)
    if pin not in topology.GPIO_PINS:
        raise TestBedExtractionError(
            f"{source_path}: {where}: GPIO pin {pin} out of range. "
            f"Valid: {topology.GPIO_PINS}"
        )
    return {
        "pin": pin,
        "role": _optional_string(kw, "role"),
        "description": _optional_string(kw, "description"),
    }


def _parse_uart(call: ast.Call, attr: str, key: str, source_path: str) -> Dict[str, Any]:
    where = f"{attr}[{key!r}]"
    kw = _kwargs(call)
    port = _require_int(kw, "port", where, source_path)
    if port not in topology.UART_PORTS:
        raise TestBedExtractionError(
            f"{source_path}: {where}: UART port {port} out of range. "
            f"Valid: {topology.UART_PORTS}"
        )
    baud = _optional_int(kw, "baud", 115200)
    if baud <= 0:
        raise TestBedExtractionError(
            f"{source_path}: {where}: baud must be > 0, got {baud}"
        )
    return {
        "port": port,
        "target": _optional_string(kw, "target"),
        "baud": baud,
        "role": _optional_string(kw, "role"),
    }


def _parse_jlink(call: ast.Call, attr: str, key: str, source_path: str) -> Dict[str, Any]:
    where = f"{attr}[{key!r}]"
    kw = _kwargs(call)
    family_node = kw.get("family")
    if family_node is None:
        raise TestBedExtractionError(
            f"{source_path}: {where}: ``family`` is required"
        )
    family_val = _const(family_node)
    if not isinstance(family_val, str) or not family_val:
        raise TestBedExtractionError(
            f"{source_path}: {where}: ``family`` must be a non-empty string"
        )
    family = family_val.strip().upper()
    if family not in topology.KNOWN_JLINK_FAMILIES:
        raise TestBedExtractionError(
            f"{source_path}: {where}: unknown J-Link family {family_val!r}. "
            f"Valid: {topology.KNOWN_JLINK_FAMILIES}"
        )
    return {"family": family, "role": _optional_string(kw, "role")}


def _parse_power(call: ast.Call, attr: str, key: str, source_path: str) -> Dict[str, Any]:
    where = f"{attr}[{key!r}]"
    kw = _kwargs(call)
    rail_node = kw.get("rail")
    if rail_node is None:
        raise TestBedExtractionError(
            f"{source_path}: {where}: ``rail`` is required"
        )
    rail_val = _const(rail_node)
    if not isinstance(rail_val, str) or not rail_val:
        raise TestBedExtractionError(
            f"{source_path}: {where}: ``rail`` must be a non-empty string"
        )
    rail = rail_val.strip().upper()
    if rail not in topology.POWER_RAILS:
        raise TestBedExtractionError(
            f"{source_path}: {where}: unknown power rail {rail_val!r}. "
            f"Valid: {topology.POWER_RAILS}"
        )
    return {"rail": rail, "role": _optional_string(kw, "role")}
