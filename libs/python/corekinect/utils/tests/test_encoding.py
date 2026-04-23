import base64

import pytest

from ..encoding.byte_str import bytes_to_base64, hex_to_base64, to_hex
from ..encoding.numbers import hex_to_base10, int_to_padded_bin, int_to_padded_hex
from ..geo.coordinate_encoding import hex_lat_long_to_base_10


def test_to_hex():
    """Test to hex."""
    data = b"\x00\xff"
    assert to_hex(data) == "00ff"
    data = b"hello"
    assert to_hex(data) == "68656c6c6f"


def test_hex_to_base10():
    """Test hex to base10."""
    assert hex_to_base10("0x1a") == 26
    assert hex_to_base10("1a") == 26
    assert hex_to_base10(26) == 26
    with pytest.raises(ValueError):
        hex_to_base10(3.14)  # Invalid type


def test_int_to_padded_hex():
    """Test int to padded hex."""
    assert int_to_padded_hex(26, num_bytes=2) == "001a"
    assert int_to_padded_hex(255, num_bytes=1) == "ff"
    result = int_to_padded_hex(1, num_bytes=4, do_print=True)
    assert result == "00000001"


def test_int_to_padded_bin():
    """Test int to padded bin."""
    assert int_to_padded_bin(5, num_bytes=1) == "00000101"
    assert int_to_padded_bin(255, num_bytes=2) == "0000000011111111"
    result = int_to_padded_bin(3, num_bytes=4, do_print=True)
    assert result == "00000000000000000000000000000011"  # 32-bit string


def test_hex_to_base64():
    """Test hex to base64."""
    hex_str = "48656c6c6f"  # 'Hello'
    assert hex_to_base64(hex_str) == base64.b64encode(b"Hello").decode("utf-8")
    hex_str = "776f726c64"  # 'world'
    assert hex_to_base64(hex_str) == base64.b64encode(b"world").decode("utf-8")


def test_bytes_to_base64():
    """Test bytes to base64."""
    data = b"Hello World"
    assert bytes_to_base64(data) == base64.b64encode(data).decode("utf-8")
    data = b"\x00\xff\x10"
    assert bytes_to_base64(data) == base64.b64encode(data).decode("utf-8")


@pytest.mark.skip(reason="Test not implemented")
def test_hex_lat_long_to_base_10():
    """Test hex lat long to base 10."""
    # test not implemented
    pass
