import pytest

from ..src.version_checker import is_version_supported


# Test cases that should return True
@pytest.mark.parametrize(
    "full_version,supported_versions",
    [
        ("1.2.3", "1.x"),
        ("1.2.3", "1.X"),
        ("1.2.3", "1.2"),
        ("1.2.3", "1.2.3"),
        ("1.2.3", "1.2.x"),
        ("1.2.3", "1.2.X"),
        ("2.0.0", ["1.x", "2.0"]),
        ("1.2.3", ["1.2", "1.3"]),
        ("1.2.3", "1"),
    ],
)
def test_is_version_supported_true(full_version, supported_versions):
    assert is_version_supported(full_version, supported_versions) == True


# Test cases that should return False
@pytest.mark.parametrize(
    "full_version,supported_versions",
    [
        ("1.2.3", "1.2.4"),
        ("2.1.0", ["1.x", "2.0"]),
        ("1.2.3", "1.3"),
        ("1.2.3", ["1.3", "1.4"]),
        ("1.2.3", []),
        ("1.2.3", None),
        ("1.2.3", "2"),
    ],
)
def test_is_version_supported_false(full_version, supported_versions):
    assert is_version_supported(full_version, supported_versions) == False


# Test cases that should raise ValueError
@pytest.mark.parametrize(
    "full_version,supported_versions,expected_exception,expected_message",
    [
        ("invalid.version", "1.x", ValueError, r"Invalid full version: invalid\.version"),
        ("1.2.3", "invalid.version", ValueError, r"Invalid supported version: invalid\.version"),
    ],
)
def test_is_version_supported_exceptions(full_version, supported_versions, expected_exception, expected_message):
    with pytest.raises(expected_exception, match=expected_message):
        is_version_supported(full_version, supported_versions)
