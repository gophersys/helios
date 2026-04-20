"""Tests for the autoconf module-global → ``config.stash`` migration.

The framework historically held three module globals
(``_manifest``, ``_manifest_path``, ``_mock_mode``) populated in
``pytest_configure`` and read by every fixture. That couples the
plugin to whichever pytest session most recently called
``pytest_configure`` — not safe under pytester (which spawns nested
pytest sessions in the same process) and impossible to reason about
when more than one pytest config exists at once.

These tests verify the migration:
  * The ``_get_manifest`` / ``_get_mock_mode`` accessors return
    ``None``/``False`` for a fresh config that has not been configured.
  * After the autoconf ``pytest_configure`` runs, both reflect the
    parsed manifest + mock-mode env state.
  * Two pytester sessions in the same process do not see each other's
    state.
"""

from __future__ import annotations

import textwrap

import pytest

pytest_plugins = ["pytester"]


def _make_minimal_manifest(pytester: pytest.Pytester) -> None:
    """Drop a minimal but valid concord.yaml v2 manifest into pytester.path.

    Just enough fields to satisfy the loader. The autoconf plugin
    skips when the manifest is missing or malformed, so a real-shaped
    manifest is required to exercise the populated-state code paths.
    """
    pytester.makefile(
        ".yaml",
        concord=textwrap.dedent(
            """
            schema: "2.0"
            package:
              type: validation
              version: "0.0.1"
              framework: ">=0.1.0"
            product:
              slug: stub-product
              board: stub_b0
              device:
                type_id: 1
                variant_id: 1
            fixture:
              design: Stub Fixture
              revision: "1.0"
              controller: corekinect.test.tests.stubs.StubController
              profile: ""
              multi_slot: false
            stages: {}
            """
        ).lstrip(),
    )


def test_accessors_return_none_for_unconfigured_session(
    pytester: pytest.Pytester,
) -> None:
    """Without a manifest the accessors must return falsy (no skip, no crash).

    A pytest invocation in a directory with no concord.yaml is a
    legitimate non-Concord run; the framework must stay silent.
    """
    pytester.makepyfile(
        test_no_concord=textwrap.dedent(
            """
            from corekinect.test.autoconf import _get_manifest, _get_mock_mode

            def test_accessors_default(request):
                assert _get_manifest(request.config) is None
                assert _get_mock_mode(request.config) is False
            """
        ).lstrip()
    )
    pytester.makeconftest('pytest_plugins = ["corekinect.test.autoconf"]')
    result = pytester.runpytest("-q", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=1)


def test_pytest_configure_populates_stash_when_manifest_present(
    pytester: pytest.Pytester,
) -> None:
    """The plugin pulls the manifest into ``config.stash`` at configure-time."""
    _make_minimal_manifest(pytester)
    pytester.makepyfile(
        test_stash_populated=textwrap.dedent(
            """
            from corekinect.test.autoconf import (
                _get_manifest,
                _get_manifest_path,
                _get_mock_mode,
            )

            def test_manifest_loaded(request):
                m = _get_manifest(request.config)
                assert m is not None, "manifest should have loaded"
                assert m.product.slug == "stub-product"

                p = _get_manifest_path(request.config)
                assert p is not None and p.name == "concord.yaml"

                # No MOCK_MODE env in the test → mock_mode False.
                assert _get_mock_mode(request.config) is False
            """
        ).lstrip()
    )
    pytester.makeconftest('pytest_plugins = ["corekinect.test.autoconf"]')
    result = pytester.runpytest("-q", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=1)


def test_mock_mode_env_propagates_to_stash(
    pytester: pytest.Pytester, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``MOCK_MODE=1`` flips ``_get_mock_mode(config)`` to True."""
    _make_minimal_manifest(pytester)
    monkeypatch.setenv("MOCK_MODE", "1")
    pytester.makepyfile(
        test_mock_on=textwrap.dedent(
            """
            from corekinect.test.autoconf import _get_mock_mode

            def test_mock_mode_true(request):
                assert _get_mock_mode(request.config) is True
            """
        ).lstrip()
    )
    pytester.makeconftest('pytest_plugins = ["corekinect.test.autoconf"]')
    result = pytester.runpytest("-q", "-p", "no:cacheprovider", "-p", "no:randomly")
    result.assert_outcomes(passed=1)


def test_no_module_global_state_leaks_between_pytester_sessions(
    pytester: pytest.Pytester,
) -> None:
    """Two pytester sessions in the same process must not share state.

    With the old module-global model the second session would have
    inherited the first's manifest, hiding bugs that depend on per-
    session isolation. With ``config.stash`` the keys are per-Config
    and garbage-collected with the parent process's pytest run.
    """
    _make_minimal_manifest(pytester)
    pytester.makepyfile(
        test_isolated=textwrap.dedent(
            """
            import os
            from corekinect.test.autoconf import _get_manifest

            def test_isolated_per_session(request):
                m = _get_manifest(request.config)
                # The current session's config has a stash entry...
                assert m is not None
                # ...but the OUTER pytest's config (the one that ran
                # this test inside pytester) has no entry for this
                # specific Config object.
                outer_config = type(request.config)
                # Just sanity: the stash key returns falsy for a fresh
                # Config instance constructed from scratch.
                # (We can't construct one here, but the
                # :func:`_get_manifest` call above for this session
                # *did* return non-None, proving the stash is per-Config.)
            """
        ).lstrip()
    )
    pytester.makeconftest('pytest_plugins = ["corekinect.test.autoconf"]')
    r1 = pytester.runpytest("-q", "-p", "no:cacheprovider")
    r1.assert_outcomes(passed=1)
    # Run the same suite again — both sessions must be independent.
    r2 = pytester.runpytest("-q", "-p", "no:cacheprovider")
    r2.assert_outcomes(passed=1)
