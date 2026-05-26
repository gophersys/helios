"""Backward-compat shim for ``corekinect.fixture`` → ``corekinect.testbed``.

The library was renamed from ``fixture`` (overloaded with pytest's
fixture, and ambiguous with Concord's physical ``Fixture`` rows) to
``testbed`` so the DUT-side wiring concept reads cleanly in user code
and platform discussions alike.

This module re-exports every public symbol from
:mod:`corekinect.testbed` and emits a single :class:`DeprecationWarning`
on first import so existing test apps continue to work while the user
gets the cue to update their imports.

Migrate by replacing the old import path:

* Before:  ``from corekinect`` + ``.fixture import TestBed, ADC, GPIO``
* After:   ``from corekinect.testbed import TestBed, ADC, GPIO``

The shim will be removed in the next minor release.
"""

from __future__ import annotations

import warnings

from corekinect.testbed import *  # noqa: F401,F403 — re-export everything
from corekinect.testbed import __all__ as _testbed_all

warnings.warn(
    "`corekinect.fixture` is deprecated — import from `corekinect.testbed` instead. "
    "This compat shim will be removed in the next minor release.",
    DeprecationWarning,
    stacklevel=2,
)

__all__ = list(_testbed_all)
