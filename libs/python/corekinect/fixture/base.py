"""``Fixture`` base class — typed accessor surface for tests.

A test app subclasses :class:`Fixture` once per hardware revision and
declares its DUT-side wiring via class-level dicts of declarative
types from :mod:`corekinect.fixture.types`. At runtime the subclass
is instantiated with an :class:`MtibV1Client`, which binds each
declaration to a runtime accessor.

::

    # fixtures/alpha_b0/fixture.py — in the test app
    from corekinect.fixture import Fixture, ADC, GPIO, UART, JLink, Power

    class AlphaB0Fixture(Fixture):
        name = "alpha_b0-fixture"
        revision = "1.0"
        battery_installed = False
        boot_settle_s = 3

        adcs = {
            "battery": ADC(channel=1, signal="VBAT"),
            "reg_3v3": ADC(channel=7, signal="REG_3V3"),
        }
        gpios = {
            "boot_app":   GPIO(pin=0, role="LOW = nRF52 boots"),
            "boot_comms": GPIO(pin=1, role="LOW = nRF91 boots"),
        }
        uarts = {
            "app":   UART(port=1, target="nrf52840"),
            "comms": UART(port=2, target="nrf9151"),
        }
        jlinks = {
            "app":   JLink(family="NRF52"),
            "comms": JLink(family="NRF91"),
        }
        power = {
            "dut":     Power(rail="DUT_PWR"),
            "charger": Power(rail="DUT_CHG"),
        }

The ``concord.yaml`` manifest points at the fixture module via
``fixture.module: fixtures.alpha_b0.fixture:AlphaB0Fixture``. The
backend AST-extracts ``name``/``revision`` (and the resource map
summaries) at upload time without instantiating the class.
"""

from __future__ import annotations

from typing import Any, ClassVar, Dict, Optional

from corekinect.fixture.types import (
    ADC,
    GPIO,
    UART,
    JLink,
    Power,
    BoundADC,
    BoundGPIO,
    BoundUART,
    BoundJLink,
    BoundPower,
    FixtureValidationError,
    _ResourceMap,
)


class Fixture:
    """Base class for product-specific fixture wiring.

    Subclass and declare ``name``, ``revision``, and the resource
    maps (``adcs``, ``gpios``, ``uarts``, ``jlinks``, ``power``).
    Constants like ``battery_installed`` and ``boot_settle_s`` go on
    the class as plain attributes — they're behavior knobs, not pin
    mappings.
    """

    # ── Required identity (subclass MUST set these) ──
    name: ClassVar[str] = ""
    revision: ClassVar[str] = ""

    # ── Resource maps (subclass overrides as needed) ──
    adcs: ClassVar[Dict[str, ADC]] = {}
    gpios: ClassVar[Dict[str, GPIO]] = {}
    uarts: ClassVar[Dict[str, UART]] = {}
    jlinks: ClassVar[Dict[str, JLink]] = {}
    power: ClassVar[Dict[str, Power]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate the fixture declaration at class-definition time.

        Catches mistakes like missing ``name``/``revision``,
        empty ``adcs`` map alongside ``read`` calls in tests, and
        type mismatches in the resource maps. Validation here means
        the test app's import-time error message points at the
        fixture module, not at some downstream test failure.
        """
        super().__init_subclass__(**kwargs)
        if not cls.name:
            raise FixtureValidationError(
                f"{cls.__name__}: class attribute ``name`` is required"
            )
        if not cls.revision:
            raise FixtureValidationError(
                f"{cls.__name__}: class attribute ``revision`` is required"
            )

        for attr, expected_type in (
            ("adcs", ADC),
            ("gpios", GPIO),
            ("uarts", UART),
            ("jlinks", JLink),
            ("power", Power),
        ):
            value = getattr(cls, attr, {})
            if not isinstance(value, dict):
                raise FixtureValidationError(
                    f"{cls.__name__}.{attr} must be a dict, got "
                    f"{type(value).__name__}"
                )
            for key, decl in value.items():
                if not isinstance(key, str) or not key:
                    raise FixtureValidationError(
                        f"{cls.__name__}.{attr}: keys must be non-empty "
                        f"strings, got {key!r}"
                    )
                if not isinstance(decl, expected_type):
                    raise FixtureValidationError(
                        f"{cls.__name__}.{attr}[{key!r}]: expected "
                        f"{expected_type.__name__}, got "
                        f"{type(decl).__name__}"
                    )

    def __init__(self, mtib: Optional[Any] = None) -> None:
        """Bind the class-level declarations to a live MTIB client.

        ``mtib`` is optional only for tooling that needs to inspect
        the declarations without an MTIB attached (e.g. dry-run
        documentation generators). Test code always passes an
        ``MtibV1Client`` instance.
        """
        self._mtib = mtib
        cls = type(self)
        if mtib is None:
            # Bind to None — accessors will raise on use, declaration
            # introspection still works via .keys() / iteration.
            self.adcs = _ResourceMap(
                {k: BoundADC(d, mtib) for k, d in cls.adcs.items()}, "ADC",
            )
            self.gpios = _ResourceMap(
                {k: BoundGPIO(d, mtib) for k, d in cls.gpios.items()}, "GPIO",
            )
            self.uarts = _ResourceMap(
                {k: BoundUART(d, mtib) for k, d in cls.uarts.items()}, "UART",
            )
            self.jlinks = _ResourceMap(
                {k: BoundJLink(d, mtib) for k, d in cls.jlinks.items()}, "JLink",
            )
            self.power = _ResourceMap(
                {k: BoundPower(d, mtib) for k, d in cls.power.items()}, "Power",
            )
            return

        self.adcs = _ResourceMap(
            {k: BoundADC(d, mtib) for k, d in cls.adcs.items()}, "ADC",
        )
        self.gpios = _ResourceMap(
            {k: BoundGPIO(d, mtib) for k, d in cls.gpios.items()}, "GPIO",
        )
        self.uarts = _ResourceMap(
            {k: BoundUART(d, mtib) for k, d in cls.uarts.items()}, "UART",
        )
        self.jlinks = _ResourceMap(
            {k: BoundJLink(d, mtib) for k, d in cls.jlinks.items()}, "JLink",
        )
        self.power = _ResourceMap(
            {k: BoundPower(d, mtib) for k, d in cls.power.items()}, "Power",
        )

    @property
    def mtib(self) -> Any:
        """Underlying MTIB client. Tests should prefer the typed accessors."""
        return self._mtib

    def summary(self) -> Dict[str, Any]:
        """Machine-readable description of the fixture's wiring.

        Used by the backend's AST extractor to populate the
        ``FixtureDesign.profileTemplate`` JSON for the UI. Captures
        the mapping shape but not the live MTIB state.
        """
        cls = type(self)
        return {
            "name": cls.name,
            "revision": cls.revision,
            "adcs": {
                k: {
                    "channel": d.channel,
                    "signal": d.signal,
                    "divider": d.divider,
                    "description": d.description,
                }
                for k, d in cls.adcs.items()
            },
            "gpios": {
                k: {
                    "pin": d.pin,
                    "role": d.role,
                    "description": d.description,
                }
                for k, d in cls.gpios.items()
            },
            "uarts": {
                k: {
                    "port": d.port,
                    "target": d.target,
                    "baud": d.baud,
                    "role": d.role,
                }
                for k, d in cls.uarts.items()
            },
            "jlinks": {
                k: {"family": d.family, "role": d.role}
                for k, d in cls.jlinks.items()
            },
            "power": {
                k: {"rail": d.rail, "role": d.role}
                for k, d in cls.power.items()
            },
        }
