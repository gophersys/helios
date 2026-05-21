"""Framework dispatch for the validation runner.

A TestPackage declares which test framework its suite runs under —
``pytest`` (the default, current behaviour) or ``ztest`` (Zephyr's
ztest, captured via UART after MTIB flashes a hex). This module is the
single source of truth that converts that field into:

    * the container ``command`` array the K8s Job spec uses, and
    * the env-var value the runner pod reads to confirm dispatch.

Backward compatibility is non-negotiable. Every test package created
before this dispatch existed has ``framework`` either NULL in the DB
or absent from concord.yaml; those packages must continue to dispatch
to the pytest entrypoint exactly as they did before. ``None`` /
``""`` / missing all collapse to ``PYTEST`` via :func:`normalize_framework`.

Caller surface
--------------

* :func:`normalize_framework` — accepts user input, returns canonical
  ``"PYTEST"`` or ``"ZTEST"``, raises ``ValueError`` on garbage.
* :func:`runner_command_for_framework` — returns a copy of the command
  list for the framework. Mutating the result never affects subsequent
  calls.
* :func:`framework_env_var` — the value to inject under ``TEST_FRAMEWORK``
  in the runner pod env block.

The actual container image is the same for both frameworks today —
``concord-test-runner`` ships entrypoints for both pytest and ztest.
This keeps deploy infrastructure (image promotion, vuln scans, helm
values) on one rail; only the in-container command differs.
"""

from __future__ import annotations

from typing import List, Optional


# Canonical framework constants. These mirror the (forthcoming) Prisma
# ``TestFramework`` enum values; keep in sync.
FRAMEWORK_PYTEST = "PYTEST"
FRAMEWORK_ZTEST = "ZTEST"

# Default for back-compat: pre-dispatch test packages have no framework
# declared, and they must continue to behave as pytest.
DEFAULT_FRAMEWORK = FRAMEWORK_PYTEST

# Allowed values returned from normalize_framework — kept as a tuple
# so error messages can iterate over them.
ALLOWED_FRAMEWORKS = (FRAMEWORK_PYTEST, FRAMEWORK_ZTEST)


# The container ``command`` arrays. These are intentionally immutable
# module-level lists (we return copies in the public API); changing them
# changes the dispatched entrypoint cluster-wide, so they're easy to
# locate in code review.
_PYTEST_RUNNER_COMMAND: List[str] = ["/app/entrypoint.sh"]
_ZTEST_RUNNER_COMMAND: List[str] = [
    "python3", "-m", "corekinect.test.ztest_runner",
]


# Public read-only views (lists, so tests can compare with `==` against
# the same literal shape they would build by hand). Callers should use
# :func:`runner_command_for_framework` which returns a fresh copy.
PYTEST_RUNNER_COMMAND: List[str] = list(_PYTEST_RUNNER_COMMAND)
ZTEST_RUNNER_COMMAND: List[str] = list(_ZTEST_RUNNER_COMMAND)


def normalize_framework(value: Optional[str]) -> str:
    """Canonicalize a framework value coming from concord.yaml or the DB.

    * ``None`` / ``""`` / whitespace → ``DEFAULT_FRAMEWORK`` (pytest).
    * Case-insensitive match against the allowed set.
    * Anything else raises ``ValueError`` with the set of accepted
      values, so the upload handler can surface a 400 with a useful
      message.
    """
    if value is None:
        return DEFAULT_FRAMEWORK
    if not isinstance(value, str):
        raise ValueError(
            f"framework must be a string, got {type(value).__name__}"
        )
    stripped = value.strip()
    if not stripped:
        return DEFAULT_FRAMEWORK
    upper = stripped.upper()
    if upper not in ALLOWED_FRAMEWORKS:
        allowed = ", ".join(f.lower() for f in ALLOWED_FRAMEWORKS)
        raise ValueError(
            f"Unknown framework {value!r} — must be one of: {allowed}"
        )
    return upper


def runner_command_for_framework(value: Optional[str]) -> List[str]:
    """Return the container ``command`` list for the given framework.

    Always returns a fresh copy — callers freely mutate the result
    (appending more args, replacing entries) without affecting the next
    dispatch.
    """
    fw = normalize_framework(value)
    if fw == FRAMEWORK_ZTEST:
        return list(_ZTEST_RUNNER_COMMAND)
    return list(_PYTEST_RUNNER_COMMAND)


def framework_env_var(value: Optional[str]) -> str:
    """Return the canonical ``TEST_FRAMEWORK`` env var value.

    The runner pod uses this to log which framework it expects and (in
    the future) to verify the dispatched command matches what the
    backend intended.
    """
    return normalize_framework(value)
