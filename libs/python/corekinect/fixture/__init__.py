"""Typed fixture-definition library.

A test app declares its DUT-side wiring in a Python class that
subclasses :class:`Fixture` and lists the MTIB resources it uses by
their physical channel/pin numbers. The class is the single source
of truth for how this product's fixture talks to its DUT.

Public API:

* :class:`Fixture` — base class. Subclass per ``<board_revision>``.
* :class:`ADC`, :class:`GPIO`, :class:`UART`, :class:`JLink`,
  :class:`Power`, :class:`I2C`, :class:`SPI` — declarative wrappers.
* :exc:`FixtureValidationError` — raised on malformed declarations.
* :exc:`FixtureIOError` — raised on MTIB RPC failures.
* :mod:`corekinect.fixture.topology` — fixed MTIB pin/channel limits.
"""

from corekinect.fixture.types import (
    ADC,
    GPIO,
    UART,
    JLink,
    Power,
    I2C,
    SPI,
    BoundADC,
    BoundGPIO,
    BoundUART,
    BoundJLink,
    BoundPower,
    FixtureValidationError,
    FixtureIOError,
)
from corekinect.fixture.base import Fixture

__all__ = [
    "Fixture",
    "ADC",
    "GPIO",
    "UART",
    "JLink",
    "Power",
    "I2C",
    "SPI",
    "BoundADC",
    "BoundGPIO",
    "BoundUART",
    "BoundJLink",
    "BoundPower",
    "FixtureValidationError",
    "FixtureIOError",
]
