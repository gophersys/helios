import pytest

from ..bits.ops import get_bits, set_bits


def test_get_bits_basic():
    """Test get bits basic."""
    assert get_bits(0b1111, 0, 3) == 0b1111  # Correct
    assert get_bits(0b101010, 1, 4) == 0b0101  # Updated expected value to 0b0101 (5)
    assert get_bits(0, 0, 0) == 0
    assert get_bits(255, 8, 15) == 0  # Bits beyond the byte range


def test_get_bits_edge_cases():
    """Test get bits edge cases."""
    assert get_bits(-1, 0, 31) == 0xFFFFFFFF  # Assuming 32-bit representation
    assert get_bits("255", 0, 3) is None  # Invalid type returns None


def test_set_bits_basic():
    """Test set bits basic."""
    # Set bits 0-3 to 0b0000 in 0b1111 -> 0b0000
    assert set_bits(0b1111, 0, 3, 0b0000) == 0b0000
    # Set bits 1-4 to 0b1010 in 0b0000 -> 0b1010
    assert set_bits(0b0000, 1, 4, 0b1010) == 0b10100
    # Overlapping bits
    assert set_bits(0b1100, 2, 5, 0b0011) == 0b001100


def test_set_bits_edge_cases():
    """Test set bits edge cases."""
    # Setting bits beyond the existing bits should work (assuming 32 bits)
    result = set_bits(0, 16, 23, 0xFF)
    assert result == 0x00FF0000
    assert set_bits("255", 0, 3, 0b0000) is None  # Invalid type returns None
    assert set_bits(255, "0", 3, 0b0000) is None  # Invalid type returns None
