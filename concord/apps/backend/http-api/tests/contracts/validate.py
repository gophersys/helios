"""
Response shape validator for Concord API contract tests.

Validates that API responses have the correct structure (field presence and
types) without asserting exact values. This documents the API contract and
catches serializer regressions before they reach clients.

Usage::

    from tests.contracts.validate import assert_response_shape

    PRODUCT_SHAPE = {
        "id": str,
        "name": str,
        "slug": (str, type(None)),  # nullable
        "active": bool,
    }

    def test_get_product(authed_client, mock_db):
        ...
        assert_response_shape(resp.get_json()["data"], PRODUCT_SHAPE)

Shape grammar:
  - ``str``, ``int``, ``bool``, ``dict``, ``list`` — exact type match
  - ``(str, type(None))`` — union / nullable
  - ``{"nested": str}`` — nested object (recursive)
  - ``[{"id": str}]`` — list where every element matches the inner shape
"""

from typing import Any


class ShapeError(AssertionError):
    """Raised when a response field does not match the expected shape."""


def assert_response_shape(
    data: Any,
    shape: Any,
    path: str = "",
) -> None:
    """Recursively assert that *data* conforms to *shape*.

    Parameters
    ----------
    data:
        The actual value (usually a parsed JSON object).
    shape:
        The expected shape descriptor (see module docstring).
    path:
        Dot-joined path used in error messages (e.g. ``"boardRevision.version"``).
    """
    _check(data, shape, path or "<root>")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _check(data: Any, shape: Any, path: str) -> None:
    """Dispatch to the appropriate checker based on shape type."""
    if isinstance(shape, dict):
        _check_dict(data, shape, path)
    elif isinstance(shape, list):
        _check_list(data, shape, path)
    elif isinstance(shape, tuple):
        _check_union(data, shape, path)
    elif isinstance(shape, type):
        _check_type(data, shape, path)
    else:
        raise TypeError(f"Unknown shape descriptor at '{path}': {shape!r}")


def _check_type(data: Any, expected_type: type, path: str) -> None:
    """Assert that data is an instance of expected_type."""
    if not isinstance(data, expected_type):
        raise ShapeError(
            f"Field '{path}' expected {expected_type.__name__}, "
            f"got {type(data).__name__} (value={data!r})"
        )


def _check_union(data: Any, types: tuple, path: str) -> None:
    """Assert that data is an instance of any type in the tuple."""
    if not isinstance(data, types):
        type_names = " | ".join(t.__name__ for t in types)
        raise ShapeError(
            f"Field '{path}' expected {type_names}, "
            f"got {type(data).__name__} (value={data!r})"
        )


def _check_dict(data: Any, shape: dict, path: str) -> None:
    """Assert that data is a dict with all keys defined in shape."""
    if not isinstance(data, dict):
        raise ShapeError(
            f"Field '{path}' expected dict, got {type(data).__name__} (value={data!r})"
        )
    for key, sub_shape in shape.items():
        child_path = f"{path}.{key}" if path != "<root>" else key
        if key not in data:
            raise ShapeError(f"Field '{child_path}' is missing from response")
        _check(data[key], sub_shape, child_path)


def _check_list(data: Any, shape: list, path: str) -> None:
    """Assert that data is a list; if shape has one element, apply it to each item."""
    if not isinstance(data, list):
        raise ShapeError(
            f"Field '{path}' expected list, got {type(data).__name__} (value={data!r})"
        )
    if shape:
        item_shape = shape[0]
        for i, item in enumerate(data):
            _check(item, item_shape, f"{path}[{i}]")


# ---------------------------------------------------------------------------
# Convenience: unwrap the standard ApiResponse envelope
# ---------------------------------------------------------------------------

def assert_envelope(response_json: dict) -> Any:
    """Assert the standard ``{"data": ..., "errors": [...]}`` envelope is present.

    Returns the inner *data* value so tests can chain shape assertions.
    """
    assert "data" in response_json, "Response missing 'data' key"
    assert "errors" in response_json, "Response missing 'errors' key"
    assert isinstance(response_json["errors"], list), "'errors' must be a list"
    return response_json["data"]
