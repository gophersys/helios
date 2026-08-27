"""Backward-compatibility tests for ``corekinect.fixture`` shim.

Older test apps and validation scripts ``import corekinect.fixture``.
After the rename to ``corekinect.testbed``, the platform keeps the
old import path as a thin shim that re-exports the new symbols and
emits a single :class:`DeprecationWarning` so users see the cue to
migrate without their code breaking.
"""

from __future__ import annotations

import importlib
import sys
import warnings

import pytest


@pytest.fixture(autouse=True)
def _reset_module_cache():
    """Each test imports corekinect.fixture fresh so the warning fires."""
    for mod in list(sys.modules):
        if mod == "corekinect.fixture" or mod.startswith("corekinect.fixture."):
            sys.modules.pop(mod, None)
    yield


def test_corekinect_fixture_import_still_works():
    """``import corekinect.fixture`` produces a usable module that
    re-exports the public ``TestBed`` surface.
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # we test the warning below
        fixture_mod = importlib.import_module("corekinect.fixture")

    # The full TestBed API should be available on the shim.
    assert hasattr(fixture_mod, "TestBed")
    assert hasattr(fixture_mod, "ADC")
    assert hasattr(fixture_mod, "GPIO")
    assert hasattr(fixture_mod, "Power")

    # And it must be the SAME object as the canonical export — we are
    # rebinding the namespace, not duplicating it.
    import corekinect.testbed
    assert fixture_mod.TestBed is corekinect.testbed.TestBed


def test_corekinect_fixture_import_emits_deprecation_warning():
    """Importing the shim must fire exactly one DeprecationWarning."""
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always")
        importlib.import_module("corekinect.fixture")

    deprecation_msgs = [
        str(w.message) for w in captured
        if issubclass(w.category, DeprecationWarning)
    ]
    assert deprecation_msgs, "expected a DeprecationWarning on import"
    joined = " ".join(deprecation_msgs).lower()
    assert "testbed" in joined, f"warning should point at the new name: {deprecation_msgs}"
