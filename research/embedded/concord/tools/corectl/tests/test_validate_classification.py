"""Tests for the project-vs-environment split in
``corectl test validate``.

The senior-dev feedback that drove this change: certain validation
checks fail not because the user's project is broken but because their
*local environment* drifted from the platform. Treating those as
project errors blocks uploads for reasons the user can't see at a
glance ("why is my green test app suddenly red?"). Splitting them
into a separate ``Environment`` category that emits warnings (with a
clear upgrade command) keeps the upload pipe open while still telling
the operator what to fix.

These tests focus on the classification — not the wording — so they
stay robust against copy edits.
"""

from __future__ import annotations

import pytest

from corectl.commands import test as test_mod


def test_validation_result_supports_environment_warnings():
    """``ValidationResult.env_warn(...)`` records the message under a
    distinct bucket from project errors and warnings.
    """
    r = test_mod.ValidationResult()
    r.env_warn("framework artifacts drifted from template")
    # Environment warnings must NOT be in the project ``errors`` list —
    # otherwise the validate command exits 1 and uploads are blocked.
    assert "framework artifacts drifted from template" not in r.errors
    # They live in their own bucket so the renderer can group them.
    assert r.env_warnings, "expected env_warnings to capture the message"
    assert "framework artifacts drifted from template" in r.env_warnings


def test_validation_result_passed_ignores_environment_warnings():
    """A project with only environment warnings still passes — uploads
    are allowed even though the local env is degraded.
    """
    r = test_mod.ValidationResult()
    r.env_warn("framework version mismatch")
    r.ok("manifest schema ok")
    assert r.passed is True


def test_validation_result_passed_fails_on_project_errors():
    """Project errors still fail the validation."""
    r = test_mod.ValidationResult()
    r.error("missing concord.yaml")
    assert r.passed is False
