"""Backward-compatibility tests for the ``fixture:`` → ``testbed:`` rename.

The platform's canonical key is now ``testbed:``. Projects scaffolded
before the rename still ship ``fixture:`` and we keep them working for
one minor version with a deprecation warning. Two contracts here:

* A manifest with only ``fixture:`` (no ``testbed:``) validates as if
  ``fixture:`` had been spelled ``testbed:``.
* The validator emits a warning so the operator knows to rename.
"""

from __future__ import annotations

import pytest

from corekinect.manifest.schema import validate_manifest


_BASE_MANIFEST = {
    "schema": "1.0",
    "package": {
        "type": "validation",
        "version": "0.1.0",
        "framework": ">=0.10.0",
    },
    "product": {
        "slug": "alpha",
        "board": "alpha_b0",
        "device": {"type_id": 1, "variant_id": 1},
    },
    "stages": {
        "smoke": {
            "directory": "tests/smoke",
            "timeout_s": 300,
        },
    },
}


def _with_testbed_key():
    """Canonical manifest — ``testbed:`` only."""
    return {
        **_BASE_MANIFEST,
        "testbed": {
            "module": "testbeds.alpha_b0.testbed:AlphaB0TestBed",
        },
    }


def _with_fixture_key():
    """Legacy manifest — ``fixture:`` only."""
    return {
        **_BASE_MANIFEST,
        "fixture": {
            "module": "testbeds.alpha_b0.testbed:AlphaB0TestBed",
        },
    }


def test_canonical_testbed_key_validates_clean():
    """Sanity: the canonical key still validates without warnings about
    the deprecation. (Other warnings — e.g., zero device ids — may
    appear and are tolerated.)
    """
    res = validate_manifest(_with_testbed_key())
    assert res.valid, [str(e) for e in res.errors]
    assert all("deprecated" not in str(w).lower() for w in res.warnings)


def test_legacy_fixture_key_validates_with_deprecation_warning():
    """``fixture:`` is still accepted but produces a deprecation warning."""
    res = validate_manifest(_with_fixture_key())
    assert res.valid, [str(e) for e in res.errors]
    # The warning must mention deprecation and the new key.
    joined = " ".join(str(w) for w in res.warnings).lower()
    assert "deprecated" in joined, f"no deprecation warning surfaced: {res.warnings}"
    assert "testbed" in joined, f"warning does not point at the new key: {res.warnings}"


def test_manifest_with_neither_key_still_fails():
    """Without ``testbed:`` or ``fixture:`` validation fails — we don't
    silently widen the contract.
    """
    res = validate_manifest(_BASE_MANIFEST)
    assert not res.valid
