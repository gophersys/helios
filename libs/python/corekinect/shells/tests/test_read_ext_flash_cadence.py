"""Regression tests for the read_ext_flash UART-cadence parser race.

What this exercises
-------------------
``CommsCoprocShell.read_ext_flash`` and ``Sigma5AppShell.read_ext_flash``
both call ``ShellCommander.send()`` with success_patterns that include
``"Reading"`` and ``"bytes from address"``. Those patterns match the
firmware's *prologue* line (``Reading 8 bytes from address: 0x0``)
which is printed BEFORE the underlying ``flash_read()`` SPI transaction
runs. On the comms processor (nRF9151 under LTE modem load) the SPI
read can take many seconds — significantly longer than the 3 s
fallback that ``send()`` uses once a success pattern has matched.

The visible failure mode (run cmpnbxt5y on panel 0AW2):

  - test_08 (app side, fast SPI): PASSED on all 5 slots
  - test_13 (comms side, slow SPI): FAILED on all 5 slots, ``data=None``

Captured UART showed the prologue line in the buffer but no hex-dump
line — ``send()`` had returned 3 s after the prologue, before the
firmware emitted the actual data.

The tests below DO NOT mock ``send()``. They mock the layer below
(``BufferedUartStream``) and drive the REAL ``ShellCommander.send()``
loop on a worker thread, feeding bytes into the fake stream with a
controlled cadence that mirrors the production failure. The fix
(drop the prologue from success_patterns; wait for the prompt or
an explicit terminal line) is verified against the same fixture.

If a regression ever drops the read parser back into a premature-
success pattern, ``test_read_handles_slow_hex_dump_after_prologue``
fails RED again — without needing a real comms board.
"""

from __future__ import annotations

import threading
import time
from typing import List, Optional

import pytest

from corekinect.shells.comms_coproc import CommsCoprocShell
from corekinect.shells.sigma5 import Sigma5AppShell


# ── Fake BufferedUartStream ──────────────────────────────


class FakeStream:
    """A test double for ``BufferedUartStream``.

    Exposes the surface ``ShellCommander.send()`` reads:
    ``check_alive`` / ``clear`` / ``write`` / ``get_text`` /
    ``_data_event`` / ``is_alive`` / ``last_error`` / ``rx_bytes``.

    A scenario script is a list of ``(delay_s, text_to_append)`` pairs.
    A background thread plays the script after a write() arrives — i.e.
    the device "responds" after the command goes out. The cadence
    mirrors what a real shell does, and ``send()`` runs unchanged
    against this fixture.
    """

    def __init__(self, scenario: List[tuple]):
        self._scenario = list(scenario)
        self._buffer = ""
        self._lock = threading.Lock()
        self._data_event = threading.Event()
        self._writes: List[bytes] = []
        self._player: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self.is_alive = True
        self.last_error: Optional[str] = None
        self.rx_bytes = 0

    # ── ShellCommander.send() surface ────────────────

    def check_alive(self) -> Optional[str]:
        return None

    def clear(self) -> None:
        with self._lock:
            self._buffer = ""
        self._data_event.clear()

    def write(self, data: bytes) -> None:
        # ShellCommander.send() writes "\r<command>\r".
        # On the FIRST write, start the playback thread that simulates
        # the device's response.
        self._writes.append(data)
        if self._player is None:
            self._player = threading.Thread(
                target=self._play, daemon=True, name="fake-stream-player"
            )
            self._player.start()

    def get_text(self) -> str:
        with self._lock:
            return self._buffer

    # ── Internal playback ────────────────────────────

    def _play(self) -> None:
        # Echo the command first (real Zephyr shell echoes the input
        # before responding). The echo line is what ShellCommander.send()
        # waits for in its "echo_seen" check.
        first_write = self._writes[0].decode("utf-8", errors="ignore")
        # The wire format is ``\r<cmd>\r`` — strip leading \r so the
        # echo line looks natural.
        echo = first_write.strip("\r")
        self._append(f"{echo}\r\n")
        for delay_s, chunk in self._scenario:
            if self._stop.wait(delay_s):
                return
            self._append(chunk)

    def _append(self, chunk: str) -> None:
        with self._lock:
            self._buffer += chunk
            self.rx_bytes += len(chunk)
        self._data_event.set()


def _attach(stream: FakeStream, shell) -> None:
    """Wire a fake stream into a shell's ShellCommander.

    ``Sigma5AppShell`` and ``CommsCoprocShell`` both hold a
    ``ShellCommander`` at ``self._cmd``; the commander reads its UART
    via ``self._stream``. Swapping ``_stream`` is the smallest possible
    surface — the rest of ``send()`` runs unchanged.
    """
    shell._cmd._stream = stream  # type: ignore[attr-defined]


# ── Scenarios ────────────────────────────────────────────


def _hex_row(prefix: str = "00000000", data_hex: str = "a5 5a ff 01 02 03 fe ed") -> str:
    """Build a firmware-shape hex-dump row.

    Format mirrors ``shell_hexdump``:
        ``00000000: a5 5a ff 01 02 03 fe ed                          |.Z......        |``
    """
    return f"{prefix}: {data_hex}                          |.Z......        |\r\n"


# ── The cadence-race regression ──────────────────────────


def test_read_handles_slow_hex_dump_after_prologue():
    """Comms side: firmware prints ``Reading N bytes from address:``
    immediately, then takes several seconds (SPI under modem load)
    before printing the hex-dump. The parser must keep listening
    until the actual data line arrives, not bail 3 s after the
    prologue.

    Cadence (matches captured UART from run cmpnbxt5y on panel 0AW2):

        t=0.10s   "Reading 8 bytes from address: 0x0\\r\\n"
        t=4.00s   "00000000: a5 5a ff 01 02 03 fe ed ...\\r\\n"
        t=4.05s   "Mfg shell: "

    With the broken success_patterns (``"Reading"`` matches at 0.10 s,
    3 s fallback fires at 3.10 s) ``send()`` returns BEFORE the 4 s
    hex-dump line, the parser sees no hex line, and read_ext_flash
    returns ``(None, "Failed to parse hex data from: ...")``.

    The fix is in the success_patterns / send() loop, not in this
    test — this test SHOULD PASS once the fix lands.
    """
    scenario = [
        (0.10, "Reading 8 bytes from address: 0x0\r\n"),
        (3.90, _hex_row()),  # arrives well after the 3 s fallback would have fired
        (0.05, "Mfg shell: "),
    ]
    stream = FakeStream(scenario)
    shell = CommsCoprocShell(mtib=object())
    _attach(stream, shell)

    data, err = shell.read_ext_flash(0x0, 8, timeout_s=15.0)

    assert err is None, (
        f"read_ext_flash bailed before the slow hex-dump arrived. "
        f"err={err!r} — the success_patterns probably still trip on the "
        f"prologue line instead of waiting for the actual data."
    )
    assert data == b"\xa5\x5a\xff\x01\x02\x03\xfe\xed", (
        f"got {data!r}, expected the 8-byte pattern"
    )


def test_read_sigma5_app_side_handles_same_cadence():
    """Same race exists in ``Sigma5AppShell.read_ext_flash`` — the
    app processor responds faster in practice, but the parser is
    structurally identical and must not regress.
    """
    scenario = [
        (0.10, "Reading 8 bytes from address: 0x0\r\n"),
        (3.90, _hex_row()),
        (0.05, "Mfg shell: "),
    ]
    stream = FakeStream(scenario)
    shell = Sigma5AppShell(mtib=object())
    _attach(stream, shell)

    data, err = shell.read_ext_flash(0x0, 8, timeout_s=15.0)

    assert err is None, f"sigma5 app read_ext_flash bailed early. err={err!r}"
    assert data == b"\xa5\x5a\xff\x01\x02\x03\xfe\xed"


def test_read_returns_error_on_flash_read_failed_line():
    """Negative path — firmware emits ``Flash read failed.`` instead
    of a hex-dump. The parser must surface that as an error, not
    return ``(None, "Failed to parse hex data")``.
    """
    scenario = [
        (0.10, "Reading 8 bytes from address: 0x0\r\n"),
        (0.10, "Flash read failed. Invalid argument\r\n"),
        (0.10, "Mfg shell: "),
    ]
    stream = FakeStream(scenario)
    shell = CommsCoprocShell(mtib=object())
    _attach(stream, shell)

    data, err = shell.read_ext_flash(0x0, 8, timeout_s=5.0)

    assert data is None
    assert err is not None and "Flash read failed" in err, (
        f"expected a 'Flash read failed' error, got {err!r}"
    )


def test_read_truncates_16byte_row_to_num_bytes():
    """The firmware's ``shell_hexdump(buf, num_bytes)`` always renders
    in 16-byte rows; if the caller asked for 8 bytes, the back half
    of the row is the buffer tail, not real flash content.
    """
    scenario = [
        (0.05, "Reading 8 bytes from address: 0x0\r\n"),
        (
            0.05,
            "00000000: a5 5a ff 01 02 03 fe ed 11 11 11 11 11 11 11 11 |.Z..............|\r\n",
        ),
        (0.05, "Mfg shell: "),
    ]
    stream = FakeStream(scenario)
    shell = CommsCoprocShell(mtib=object())
    _attach(stream, shell)

    data, err = shell.read_ext_flash(0x0, 8, timeout_s=5.0)

    assert err is None
    assert data == b"\xa5\x5a\xff\x01\x02\x03\xfe\xed", (
        f"parser returned the trailing buffer bytes — got {data!r}"
    )
    assert len(data) == 8


def test_read_strips_offset_column_so_address_bytes_dont_leak_into_data():
    """The ``00000000:`` offset prefix must be stripped before the
    hex-pair scan, or the parser prepends the 4 offset bytes to the
    caller's data and returns 12 bytes when 8 were asked for.
    """
    scenario = [
        (0.05, "Reading 8 bytes from address: 0x100\r\n"),
        (
            0.05,
            "00000100: de ad be ef 11 22 33 44 00 00 00 00 00 00 00 00 |....\"3D........|\r\n",
        ),
        (0.05, "Mfg shell: "),
    ]
    stream = FakeStream(scenario)
    shell = CommsCoprocShell(mtib=object())
    _attach(stream, shell)

    data, err = shell.read_ext_flash(0x100, 8, timeout_s=5.0)

    assert err is None
    assert data == b"\xde\xad\xbe\xef\x11\x22\x33\x44"
