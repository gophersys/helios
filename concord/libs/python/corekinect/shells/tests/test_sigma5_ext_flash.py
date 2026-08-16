"""Unit tests for Sigma5AppShell.{write,read,erase}_ext_flash helpers.

The helpers wrap the Sigma5 nRF52840 manufacturing-shell commands
``write_ext_flash``, ``read_ext_flash``, and ``erase_ext_flash``
defined in firmware at ``sigma5_mfg_fw/src/app/sensor_handler.c``.

Tests mock ``ShellCommander.send`` so we exercise the *wrapper* logic
— command formatting, hex-dump parsing, error propagation — without
needing real UART / MTIB / hardware. The firmware response formats
are reproduced verbatim from the C source so this file also acts as
a regression spec for the wire protocol the helper assumes.
"""

from __future__ import annotations

from typing import List, Optional, Tuple
from unittest.mock import patch

import pytest

from corekinect.shells.sigma5 import Sigma5AppShell


# ── Helpers ──────────────────────────────────────────────


class _FakeSend:
    """Replacement for ``ShellCommander.send`` that captures the command
    and returns a scripted response.

    Each call records the ``command`` string in ``self.calls`` and pops
    the next ``(lines, err)`` tuple from ``self.responses``.
    """

    def __init__(self, responses: List[Tuple[List[str], Optional[str]]]):
        self.responses = list(responses)
        self.calls: List[str] = []

    def __call__(self, command, success_patterns=None, timeout_s=30.0):
        self.calls.append(command)
        if not self.responses:
            raise AssertionError(
                f"FakeSend ran out of responses; got call: {command!r}"
            )
        return self.responses.pop(0)


def _make_shell(send_responses):
    """Build a Sigma5AppShell with a stubbed mtib + patched ``send``."""
    shell = Sigma5AppShell(mtib=object())  # mtib never touched in unit tests
    fake = _FakeSend(send_responses)
    shell._cmd.send = fake  # type: ignore[assignment]
    return shell, fake


# ── write_ext_flash ──────────────────────────────────────


def test_write_ext_flash_sends_base64_of_bytes_input():
    """bytes input must be base64-encoded before being sent."""
    shell, fake = _make_shell([
        (["Writing 2 bytes to address: 0x0"], None),
    ])

    ok, err = shell.write_ext_flash(0x0, b"\xa5\x5a")

    assert err is None
    assert ok is True
    assert fake.calls == ["write_ext_flash 0x00000000 pVo="]


def test_write_ext_flash_accepts_already_base64_string():
    """A string input is assumed to be already base64-encoded and
    passed through unchanged. Preserves the legacy contract used by
    older callers."""
    shell, fake = _make_shell([
        (["Writing 2 bytes to address: 0x10"], None),
    ])

    ok, err = shell.write_ext_flash(0x10, "pVo=")

    assert err is None
    assert ok is True
    assert fake.calls == ["write_ext_flash 0x00000010 pVo="]


def test_write_ext_flash_parses_writing_success_line():
    """The firmware emits ``Writing %d bytes to address: 0x%x`` on
    success — the helper returns True when that line is present."""
    shell, _ = _make_shell([
        (
            [
                "Writing 8 bytes to address: 0x0",
                "00000000: a5 5a ff 01 02 03 fe ed 00 00 00 00 00 00 00 00 |.Z..............|",
            ],
            None,
        ),
    ])

    ok, err = shell.write_ext_flash(0x0, b"\xa5\x5a\xff\x01\x02\x03\xfe\xed")
    assert err is None
    assert ok is True


def test_write_ext_flash_propagates_send_error():
    """When the underlying send() returns an error, the helper returns
    (False, err) without raising."""
    shell, _ = _make_shell([
        ([], "Timeout (15s) stream=alive rx=128B"),
    ])

    ok, err = shell.write_ext_flash(0x0, b"\xa5\x5a")
    assert ok is False
    assert err is not None and "Timeout" in err


# ── read_ext_flash ───────────────────────────────────────


def test_read_ext_flash_sends_address_and_length():
    """Command shape: ``read_ext_flash 0x<8> <n>``."""
    shell, fake = _make_shell([
        (
            [
                "Reading 8 bytes from address: 0x0",
                "00000000: a5 5a ff 01 02 03 fe ed                          |.Z......        |",
            ],
            None,
        ),
    ])

    data, err = shell.read_ext_flash(0x0, 8)
    assert err is None
    assert data == b"\xa5\x5a\xff\x01\x02\x03\xfe\xed"
    assert fake.calls == ["read_ext_flash 0x00000000 8"]


def test_read_ext_flash_truncates_to_requested_length():
    """The firmware always emits 16-byte rows even when fewer were
    requested. The helper must slice the returned bytes down to
    ``num_bytes``."""
    shell, _ = _make_shell([
        (
            [
                "Reading 4 bytes from address: 0x100",
                "00000000: a5 5a ff 01 00 00 00 00 00 00 00 00 00 00 00 00 |.Z..............|",
            ],
            None,
        ),
    ])

    data, err = shell.read_ext_flash(0x100, 4)
    assert err is None
    assert data == b"\xa5\x5a\xff\x01"
    assert len(data) == 4


def test_read_ext_flash_returns_error_on_flash_read_failed():
    """Firmware error: ``Flash read failed. <strerror>``."""
    shell, _ = _make_shell([
        (
            [
                "Reading 8 bytes from address: 0x0",
                "Flash read failed. Invalid argument",
            ],
            None,
        ),
    ])

    data, err = shell.read_ext_flash(0x0, 8)
    assert data is None
    assert err is not None
    assert "Flash read failed" in err


def test_read_ext_flash_returns_error_on_too_many_bytes():
    """Firmware bounds-check error (typo ``ablt`` preserved)."""
    shell, _ = _make_shell([
        (
            [
                "Number of bytes (128) must be ablt to fit in 64 bytes",
            ],
            None,
        ),
    ])

    data, err = shell.read_ext_flash(0x0, 128)
    assert data is None
    assert err is not None
    assert "must be ablt to fit in 64 bytes" in err


def test_read_ext_flash_propagates_send_error():
    """An underlying send() error surfaces as (None, err)."""
    shell, _ = _make_shell([
        ([], "Timeout (15s) stream=alive rx=0B"),
    ])

    data, err = shell.read_ext_flash(0x0, 8)
    assert data is None
    assert err is not None and "Timeout" in err


# ── erase_ext_flash ──────────────────────────────────────


def test_erase_ext_flash_sends_correct_command():
    shell, fake = _make_shell([
        (["Erasing flash. 2048 pages, 4096 bytes per page. Chip size 8388608 bytes"], None),
    ])

    ok, err = shell.erase_ext_flash()
    assert err is None
    assert ok is True
    assert fake.calls == ["erase_ext_flash"]


def test_erase_ext_flash_returns_error_on_flash_erase_failed():
    shell, _ = _make_shell([
        (
            [
                "Erasing flash. 2048 pages, 4096 bytes per page. Chip size 8388608 bytes",
                "Flash erase failed. Invalid argument",
            ],
            None,
        ),
    ])

    ok, err = shell.erase_ext_flash()
    assert ok is False
    assert err is not None
    assert "Flash erase failed" in err


def test_erase_ext_flash_propagates_send_error():
    shell, _ = _make_shell([
        ([], "Timeout (30s) stream=alive rx=0B"),
    ])

    ok, err = shell.erase_ext_flash()
    assert ok is False
    assert err is not None and "Timeout" in err
