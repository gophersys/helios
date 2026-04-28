"""Declarative resource types for fixtures.

Each type is split in two:

* A frozen ``dataclass`` declaration the fixture class lists at the
  class level (immutable schema — what the fixture *is*).
* A ``Bound*`` runtime accessor created when the fixture is
  instantiated against a real MTIB client (what the test code
  actually calls).

The split keeps two things easy:

1. Static analysis / AST extraction can read the class-level
   declarations without instantiating the fixture (the backend
   uploads-and-extracts path uses this).
2. Test code never sees raw MTIB channel numbers — it goes through
   ``fixture.adcs["battery"].read_v()``, where the divider math and
   error mapping live in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, Optional, Tuple

from corekinect.fixture import topology


class FixtureValidationError(ValueError):
    """Raised when a fixture declaration has an out-of-range channel/pin."""


class FixtureIOError(RuntimeError):
    """Raised when an MTIB RPC fails inside a bound accessor.

    Tests should catch this at the test boundary; fixture-level
    helpers should let it propagate so the failure attributes
    correctly to the operation that triggered it.
    """


# ── ADC ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ADC:
    """An MTIB ADC channel routed to a DUT-side voltage rail.

    ``divider`` is the *external* voltage divider ratio sitting between
    the rail and the MTIB's signal-conditioning input; ``read_v()``
    multiplies the raw MTIB reading by this so test code receives
    true rail volts. Default 1.0 means "no external divider".
    """

    channel: int
    signal: str = ""
    divider: float = 1.0
    description: str = ""

    def __post_init__(self) -> None:
        if self.channel not in topology.ADC_CHANNELS:
            raise FixtureValidationError(
                f"ADC channel {self.channel} out of range. "
                f"Valid: {topology.ADC_CHANNELS}"
            )
        if self.divider <= 0:
            raise FixtureValidationError(
                f"ADC divider must be > 0 (got {self.divider})"
            )


class BoundADC:
    """Runtime accessor for an ADC declaration."""

    __slots__ = ("_decl", "_mtib")

    def __init__(self, decl: ADC, mtib: Any) -> None:
        self._decl = decl
        self._mtib = mtib

    @property
    def channel(self) -> int:
        return self._decl.channel

    @property
    def signal(self) -> str:
        return self._decl.signal

    @property
    def divider(self) -> float:
        return self._decl.divider

    def read_v(self) -> float:
        """Read the rail voltage in volts (after divider correction)."""
        v, err = self._mtib.AdcRead(self._decl.channel)
        if err:
            raise FixtureIOError(
                f"ADC ch{self._decl.channel} ({self._decl.signal}): {err}"
            )
        if v is None:
            raise FixtureIOError(
                f"ADC ch{self._decl.channel} ({self._decl.signal}): no reading"
            )
        return v * self._decl.divider


# ── GPIO ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class GPIO:
    """An MTIB GPIO pin wired to a DUT signal.

    Direction and resistor are NOT declared here — those are runtime
    state set by the test (``config(direction=..., pull=...)``). The
    declaration only fixes which physical pin is which DUT-side
    signal and what role it plays.
    """

    pin: int
    role: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if self.pin not in topology.GPIO_PINS:
            raise FixtureValidationError(
                f"GPIO pin {self.pin} out of range. Valid: {topology.GPIO_PINS}"
            )


class BoundGPIO:
    """Runtime accessor for a GPIO declaration."""

    __slots__ = ("_decl", "_mtib")

    def __init__(self, decl: GPIO, mtib: Any) -> None:
        self._decl = decl
        self._mtib = mtib

    @property
    def pin(self) -> int:
        return self._decl.pin

    @property
    def role(self) -> str:
        return self._decl.role

    def config(
        self,
        direction: str = "output",
        pull: str = "none",
    ) -> "BoundGPIO":
        """Set the pin direction and pull resistor.

        ``direction`` is ``"input"`` or ``"output"``. ``pull`` is one
        of ``"up"``, ``"down"``, ``"none"``. Returns ``self`` so
        callers can chain (``gpio.config().set_low()``).
        """
        # Imported lazily so the fixture lib doesn't drag the gRPC
        # client into its top-level imports.
        from corekinect.mtib_client.v1.client.types import (
            GpioDirection,
            GpioResistorConfig,
        )

        dir_map = {
            "input": GpioDirection.INPUT,
            "output": GpioDirection.OUTPUT,
        }
        pull_map = {
            "up": GpioResistorConfig.PULL_UP,
            "down": GpioResistorConfig.PULL_DOWN,
            "none": GpioResistorConfig.NONE,
        }
        if direction not in dir_map:
            raise FixtureValidationError(
                f"direction must be one of {list(dir_map)}; got {direction!r}"
            )
        if pull not in pull_map:
            raise FixtureValidationError(
                f"pull must be one of {list(pull_map)}; got {pull!r}"
            )
        err = self._mtib.GpioConfig(
            gpio=self._decl.pin,
            direction=dir_map[direction],
            resistor=pull_map[pull],
        )
        if err:
            raise FixtureIOError(
                f"GPIO {self._decl.pin} ({self._decl.role}) config: {err}"
            )
        return self

    def set_high(self) -> None:
        err = self._mtib.GpioWrite(gpio=self._decl.pin, state=True)
        if err:
            raise FixtureIOError(
                f"GPIO {self._decl.pin} ({self._decl.role}) set_high: {err}"
            )

    def set_low(self) -> None:
        err = self._mtib.GpioWrite(gpio=self._decl.pin, state=False)
        if err:
            raise FixtureIOError(
                f"GPIO {self._decl.pin} ({self._decl.role}) set_low: {err}"
            )

    def read(self) -> bool:
        state, err = self._mtib.GpioRead(gpio=self._decl.pin)
        if err:
            raise FixtureIOError(
                f"GPIO {self._decl.pin} ({self._decl.role}) read: {err}"
            )
        return bool(state)


# ── UART ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class UART:
    """A DUT-side UART wired to one of the MTIB's two UART ports."""

    port: int
    target: str = ""
    baud: int = 115200
    role: str = ""

    def __post_init__(self) -> None:
        if self.port not in topology.UART_PORTS:
            raise FixtureValidationError(
                f"UART port {self.port} out of range. "
                f"Valid: {topology.UART_PORTS}"
            )
        if self.baud <= 0:
            raise FixtureValidationError(f"UART baud must be > 0 (got {self.baud})")


class BoundUART:
    """Runtime accessor for a UART declaration.

    UART streaming is bidirectional and request-driven (see the
    ``UartStream`` notes in the MTIB hardware rules). The bound
    accessor keeps the declaration around but defers stream
    construction to the caller — tests typically wrap the raw stream
    with the higher-level demuxer in ``corekinect.test.uart_demuxer``.
    """

    __slots__ = ("_decl", "_mtib")

    def __init__(self, decl: UART, mtib: Any) -> None:
        self._decl = decl
        self._mtib = mtib

    @property
    def port(self) -> int:
        return self._decl.port

    @property
    def target(self) -> str:
        return self._decl.target

    @property
    def baud(self) -> int:
        return self._decl.baud

    def stream(self, request_iterator: Iterator[Any]) -> Iterator[Any]:
        """Open a bidirectional UART stream.

        Pass-through to the MTIB client's ``UartStream``; ``target``
        resolution is the caller's job because the client uses the
        proto ``HostType`` enum directly.
        """
        # The mapping from declarative ``target`` strings to proto
        # ``HostType`` values lives in :mod:`corekinect.fixture.base`
        # to keep import cycles out of this file.
        return self._mtib.UartStream(
            target=_target_to_host_type(self._decl.target),
            request_iterator=request_iterator,
        )


def _target_to_host_type(target: str) -> Any:
    """Map a fixture-declared ``target`` string to the proto enum.

    Defined here (private) so :class:`BoundUART` can call it without
    a circular import. The acceptable values follow the existing
    ``HostType`` enum names.
    """
    from corekinect.mtib_client.v1.client.types import HostType

    table = {
        "nrf52840": HostType.HOST_TYPE_NRF52840,
        "nrf9151": HostType.HOST_TYPE_NRF9151,
        "nrf9160": HostType.HOST_TYPE_NRF9160_MODEM,
    }
    key = target.strip().lower()
    if key not in table:
        raise FixtureValidationError(
            f"Unknown UART target {target!r}. Valid: {sorted(table)}"
        )
    return table[key]


# ── J-Link ──────────────────────────────────────────────────────


@dataclass(frozen=True)
class JLink:
    """A J-Link programmer addressed by chip family.

    The fixture declares which chip family this J-Link talks to —
    ``NRF52``, ``NRF91``, etc. — and the MTIB server resolves to
    whichever physical probe is connected via ``ListProgrammers``.
    The fixture (and the test code) never sees a probe SNR. Swap
    a J-Link, no fixture change required.
    """

    family: str
    role: str = ""

    def __post_init__(self) -> None:
        fam = self.family.strip().upper()
        if fam not in topology.KNOWN_JLINK_FAMILIES:
            raise FixtureValidationError(
                f"Unknown J-Link family {self.family!r}. "
                f"Valid: {topology.KNOWN_JLINK_FAMILIES}"
            )
        # Frozen dataclass — bypass to normalise.
        object.__setattr__(self, "family", fam)


class BoundJLink:
    """Runtime accessor for a J-Link declaration."""

    __slots__ = ("_decl", "_mtib")

    def __init__(self, decl: JLink, mtib: Any) -> None:
        self._decl = decl
        self._mtib = mtib

    @property
    def family(self) -> str:
        return self._decl.family

    def _resolve_host(self) -> Any:
        """Return the proto ``HostType`` for this family.

        Called before every flash/erase. The server-side
        ``_find_programmer`` then resolves the host type to whichever
        physical probe is registered for it via ``_assign_jlinks``,
        so the test never sees an SNR.
        """
        from corekinect.mtib_client.v1.client.types import HostType

        family_to_host = {
            "NRF52": HostType.HOST_TYPE_NRF52840,
            "NRF53": HostType.HOST_TYPE_NRF5340,
            "NRF91": HostType.HOST_TYPE_NRF9151,
        }
        host = family_to_host.get(self._decl.family)
        if host is None:
            raise FixtureValidationError(
                f"J-Link family {self._decl.family} has no host type mapping. "
                f"Add it to BoundJLink._resolve_host."
            )
        return host

    def erase(self, recover: bool = True) -> None:
        """Erase the target's flash. ``recover=True`` clears APPROTECT.

        Mandatory after every nRF52/91 flash per the repersonalization
        workflow — the test framework's ``flash()`` calls this for
        you, but you can invoke it standalone if a test needs a
        clean device without immediately reflashing.
        """
        host = self._resolve_host()
        err = self._mtib.EraseFlash(target=host, recover=recover)
        if err:
            raise FixtureIOError(
                f"J-Link {self._decl.family} erase (recover={recover}): {err}"
            )

    def flash(self, firmware_path: str, recover: bool = True) -> int:
        """Flash a hex/CFW file to the device. Returns elapsed ms.

        Three-step server-side flow:

        1. ``UploadFwFile`` streams the file to the MTIB and tags it
           with the resolved ``HostType``.
        2. ``ListFwFiles`` finds the freshly-uploaded ``FwFileInfo``
           record by name (the only stable handle the proto exposes).
        3. ``FlashFwFile`` runs ``nrfjprog`` against the probe the
           server resolved for this family.

        ``recover=True`` is forwarded to ``FlashFwFile`` so the
        server runs ``--recover`` before flashing — required after
        APPROTECT on the nRF52/91 family.
        """
        import os

        host = self._resolve_host()
        file_name = os.path.basename(firmware_path)

        err = self._mtib.UploadFwFile(file_path=firmware_path, target=host)
        if err:
            raise FixtureIOError(
                f"J-Link {self._decl.family} upload {firmware_path}: {err}"
            )

        files, err = self._mtib.ListFwFiles()
        if err:
            raise FixtureIOError(
                f"J-Link {self._decl.family} list-after-upload: {err}"
            )
        file_info = next(
            (f for f in (files or []) if f.name == file_name and f.target == host),
            None,
        )
        if file_info is None:
            raise FixtureIOError(
                f"J-Link {self._decl.family}: uploaded {file_name} not "
                f"visible in ListFwFiles — server lost the file"
            )

        time_ms, err = self._mtib.FlashFwFile(file_info=file_info, recover=recover)
        if err:
            raise FixtureIOError(
                f"J-Link {self._decl.family} flash {firmware_path}: {err}"
            )
        return time_ms or 0


# ── Power ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class Power:
    """A DUT-side power rail driven by the MTIB.

    ``rail`` matches the MTIB's internal name (``DUT_PWR`` or
    ``DUT_CHG``). The MTIB resolves this to a power channel index
    server-side; client passes the channel via ``PowerEnable``.
    """

    rail: str
    role: str = ""

    def __post_init__(self) -> None:
        rail = self.rail.strip().upper()
        if rail not in topology.POWER_RAILS:
            raise FixtureValidationError(
                f"Unknown power rail {self.rail!r}. "
                f"Valid: {topology.POWER_RAILS}"
            )
        object.__setattr__(self, "rail", rail)


class BoundPower:
    """Runtime accessor for a power rail."""

    __slots__ = ("_decl", "_mtib")

    def __init__(self, decl: Power, mtib: Any) -> None:
        self._decl = decl
        self._mtib = mtib

    @property
    def rail(self) -> str:
        return self._decl.rail

    @property
    def channel(self) -> int:
        return topology.POWER_RAIL_CHANNEL[self._decl.rail]

    def enable(self, voltage_v: float) -> None:
        """Enable the rail at the given voltage."""
        if voltage_v <= 0:
            raise FixtureValidationError(
                f"voltage_v must be > 0 (got {voltage_v})"
            )
        err = self._mtib.PowerEnable(channel=self.channel, voltage_v=voltage_v)
        if err:
            raise FixtureIOError(
                f"Power {self._decl.rail} enable @ {voltage_v}V: {err}"
            )

    def disable(self) -> None:
        err = self._mtib.PowerDisable(channel=self.channel)
        if err:
            raise FixtureIOError(
                f"Power {self._decl.rail} disable: {err}"
            )

    def read(self) -> Tuple[float, float]:
        """Return ``(voltage_v, current_ma)`` for the rail."""
        result, err = self._mtib.PowerRead(channel=self.channel)
        if err:
            raise FixtureIOError(
                f"Power {self._decl.rail} read: {err}"
            )
        return float(result.voltage_v), float(result.current_ma)


# ── I2C / SPI (declarative-only for now) ────────────────────────


@dataclass(frozen=True)
class I2C:
    """An I2C bus exposed to the DUT.

    The MTIB exposes a single I2C bus today; declaring it makes the
    fixture self-describing for AST extraction. There's no runtime
    accessor yet — DUT-side I2C transactions go through the DUT's
    own firmware in test scenarios.
    """

    port: int = 1
    role: str = ""

    def __post_init__(self) -> None:
        if self.port not in topology.I2C_PORTS:
            raise FixtureValidationError(
                f"I2C port {self.port} out of range. "
                f"Valid: {topology.I2C_PORTS}"
            )


@dataclass(frozen=True)
class SPI:
    """A SPI bus exposed to the DUT (CLK/MISO/MOSI; CS internal to DUT)."""

    port: int = 1
    role: str = ""

    def __post_init__(self) -> None:
        if self.port not in topology.SPI_PORTS:
            raise FixtureValidationError(
                f"SPI port {self.port} out of range. "
                f"Valid: {topology.SPI_PORTS}"
            )


# ── Resource map containers ─────────────────────────────────────


class _ResourceMap:
    """Read-only dict-like wrapper around a ``{name: BoundX}`` map.

    Exposes the runtime accessors keyed by the fixture's logical
    names. Indexing a missing key gives a ``KeyError`` with the list
    of available names so the operator immediately sees what was
    declared.
    """

    __slots__ = ("_items", "_kind")

    def __init__(self, items: Dict[str, Any], kind: str) -> None:
        self._items = items
        self._kind = kind

    def __getitem__(self, key: str) -> Any:
        try:
            return self._items[key]
        except KeyError:
            raise KeyError(
                f"{self._kind} {key!r} not declared on this fixture. "
                f"Available: {sorted(self._items)}"
            ) from None

    def __contains__(self, key: str) -> bool:
        return key in self._items

    def __iter__(self) -> Iterator[str]:
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def keys(self):
        return self._items.keys()

    def values(self):
        return self._items.values()

    def items(self):
        return self._items.items()
