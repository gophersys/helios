"""P2.1 — autoconf must FAIL LOUDLY on malformed manifests.

The v0.12.0 -> 0.12.3 silent-skew incident's silence amplifier #1 was
``corekinect.test.autoconf.pytest_configure`` swallowing every
``Exception`` from ``load_manifest`` into a ``warnings.warn`` + early
return. A real exception (KeyError on a missing config key after the
fixture->testbed rename, a schema-validation failure, etc.) turned
into a soft no-op that left tests skipping with "fixture not found"
— invisible to the operator and tabulated as
``total>0, passed=0, failed=0, errors=0`` in the dashboard.

This file pins the contract going forward:

  - Manifest genuinely absent (no concord.yaml in tree)
        → autoconf is a silent no-op (pytest collection succeeds with
          warnings only). LEGITIMATE — single-file test scripts.

  - Manifest exists but YAML is malformed (yaml.YAMLError)
        → autoconf RAISES, pytest collection hard-fails. The operator
          sees the YAML parse error in the runner pod logs and can fix
          the manifest.

  - Manifest exists, parses, but a required top-level key is missing
    (KeyError / ValueError inside Manifest.from_dict)
        → autoconf RAISES. The old behaviour warned and no-op'd; the
          new behaviour propagates.

  - Manifest exists and parses, but its ``package.type`` is empty
    (the "v1 / pre-rename" shape — what triggered the original
    incident)
        → autoconf RAISES. The old behaviour also warned and no-op'd
          on this branch — now it must raise.

The control case (no manifest → no-op) is intentionally on the
permissive side: a contributor running a standalone unit test in
``libs/python/corekinect/`` without a concord.yaml in cwd is still
allowed to import ``corekinect.test.autoconf`` and have it do
nothing. That is the ONLY no-op path.

Tests run via ``pytester`` so the behaviour under test is the real
``pytest_configure`` hook, not a stub.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

pytest_plugins = ["pytester"]


# ────────────────────────────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────────────────────────────


def _write_conftest(pytester: pytest.Pytester) -> None:
    """Wire autoconf into the inner pytester run via pytest_plugins."""
    pytester.makepyfile(
        conftest=textwrap.dedent(
            """
            pytest_plugins = ["corekinect.test.autoconf"]
            """
        )
    )


def _write_trivial_test(pytester: pytest.Pytester) -> None:
    """A single trivial test that doesn't depend on any autoconf fixture.

    Used to confirm that a NO-manifest run still passes (autoconf is a
    silent no-op there) and to confirm that a manifest-load FAILURE
    hard-stops collection (so the trivial test never even runs).
    """
    pytester.makepyfile(
        test_trivial=textwrap.dedent(
            """
            def test_nothing():
                assert True
            """
        )
    )


# ────────────────────────────────────────────────────────────────────────
# Tests
# ────────────────────────────────────────────────────────────────────────


def test_no_manifest_is_silent_noop(pytester: pytest.Pytester) -> None:
    """No concord.yaml in tree → autoconf is a silent no-op.

    The trivial test must run and pass. Autoconf must not emit any
    user-visible error (warnings are fine; failures are not).
    """
    _write_conftest(pytester)
    _write_trivial_test(pytester)

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
    # No surprise errors during collection.
    stdout = result.stdout.str()
    assert "ERROR" not in stdout.splitlines()[-5:][-1].upper() or "passed" in stdout, (
        f"No-manifest case must not produce a collection error:\n{stdout}"
    )


def test_malformed_yaml_propagates(pytester: pytest.Pytester) -> None:
    """concord.yaml present but YAML is invalid → autoconf must RAISE.

    `load_manifest` raises ``yaml.YAMLError`` (or a subclass) for
    syntactically-broken files. autoconf must propagate that — pytest
    must hard-fail collection rather than warn-and-no-op.
    """
    _write_conftest(pytester)
    _write_trivial_test(pytester)
    # Indentation-broken YAML: a mapping key with no value after the colon
    # plus a list-with-mapping-value that's malformed.
    pytester.makefile(
        ".yaml",
        concord=textwrap.dedent(
            """
            package:
              type: validation
              version: "0.1.0"
              framework: ">=0.9.0"
            product:
              this is not valid yaml
                : at all
            """
        ).strip(),
    )

    result = pytester.runpytest("-v")
    # Either the run errors out at collection, or the inner pytest exits
    # non-zero. The contract is "do NOT silently pass."
    assert result.ret != 0, (
        f"Malformed YAML must NOT pass silently. Got ret={result.ret}\n"
        f"stdout=\n{result.stdout.str()}\nstderr=\n{result.stderr.str()}"
    )
    combined = result.stdout.str() + result.stderr.str()
    # The error must mention the manifest or YAML so the operator can
    # fix the right thing.
    assert (
        "yaml" in combined.lower()
        or "manifest" in combined.lower()
        or "concord.yaml" in combined.lower()
    ), (
        f"Failure must point at the manifest/YAML:\n{combined}"
    )


def test_missing_required_key_propagates(pytester: pytest.Pytester) -> None:
    """concord.yaml parses but has no `package` block at all.

    The pre-rename shape: a v1 manifest that doesn't even have a
    `package:` key. Old autoconf warned + no-op'd; new autoconf must
    refuse to start the run.
    """
    _write_conftest(pytester)
    _write_trivial_test(pytester)
    # Valid YAML, valid mapping at root, but missing the entire
    # `package:` section — the schema requires it.
    pytester.makefile(
        ".yaml",
        concord=textwrap.dedent(
            """
            schema: "1.0"
            product:
              slug: legacy
              board: legacy_b0
            """
        ).strip(),
    )

    result = pytester.runpytest("-v")
    assert result.ret != 0, (
        f"Missing required `package:` must NOT pass silently. ret={result.ret}\n"
        f"stdout=\n{result.stdout.str()}\nstderr=\n{result.stderr.str()}"
    )


def test_empty_package_type_propagates(pytester: pytest.Pytester) -> None:
    """Manifest parses but `package.type` is empty.

    The exact shape that the original incident saw: the v1 manifest's
    ``fixture:`` block survived but the new ``package.type`` field was
    blank, so ``manifest.package.type`` was a falsy empty string.
    Old autoconf warned + no-op'd here too; new autoconf must raise.
    """
    _write_conftest(pytester)
    _write_trivial_test(pytester)
    pytester.makefile(
        ".yaml",
        concord=textwrap.dedent(
            """
            schema: "1.0"
            package:
              type: ""
              version: "0.1.0"
              framework: ">=0.9.0"
            product:
              slug: legacy
              board: legacy_b0
            """
        ).strip(),
    )

    result = pytester.runpytest("-v")
    assert result.ret != 0, (
        f"Empty package.type (v1 shape) must NOT pass silently. ret={result.ret}\n"
        f"stdout=\n{result.stdout.str()}\nstderr=\n{result.stderr.str()}"
    )


def test_valid_manifest_proceeds(pytester: pytest.Pytester) -> None:
    """Sanity: a minimal-but-valid concord.yaml lets the trivial test run."""
    _write_conftest(pytester)
    _write_trivial_test(pytester)
    pytester.makefile(
        ".yaml",
        concord=textwrap.dedent(
            """
            schema: "1.0"
            package:
              type: validation
              version: "0.1.0"
              framework: ">=0.9.0"
            product:
              slug: legacy
              board: legacy_b0
              device:
                type_id: 1
                variant_id: 1
            testbed:
              module: testbeds.legacy.testbed:LegacyTestBed
              multi_slot: false
            """
        ).strip(),
    )

    result = pytester.runpytest("-v")
    result.assert_outcomes(passed=1)
