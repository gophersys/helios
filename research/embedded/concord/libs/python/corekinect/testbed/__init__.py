"""Typed fixture-definition library.

A test app declares its DUT-side wiring in a Python class that
subclasses :class:`TestBed` and lists the MTIB resources it uses by
their physical channel/pin numbers. The class is the single source
of truth for how this product's fixture talks to its DUT.

Public API:

* :class:`TestBed` — base class. Subclass per ``<board_revision>``.
* :class:`ADC`, :class:`GPIO`, :class:`UART`, :class:`JLink`,
  :class:`Power`, :class:`I2C`, :class:`SPI` — declarative wrappers.
* :exc:`TestBedValidationError` — raised on malformed declarations.
* :exc:`TestBedIOError` — raised on MTIB RPC failures.
* :mod:`corekinect.testbed.topology` — fixed MTIB pin/channel limits.
"""

from corekinect.testbed.types import (
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
    TestBedValidationError,
    TestBedIOError,
)
from corekinect.testbed.base import TestBed

__all__ = [
    "TestBed",
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
    "TestBedValidationError",
    "TestBedIOError",
]
