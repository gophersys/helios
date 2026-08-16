"""Structured error types + contextual error-message helpers.

Exception hierarchy is re-exported from :mod:`corekinect.errors`:

    from corekinect.test.errors import CloudError, FirmwareError

    raise CloudError("Device not registered in CoreCloud")
    raise FirmwareError("Version mismatch", expected="0.5.2", actual="0.5.1")

Message helpers (this module) format the boilerplate for common
failure modes so every skip/fail message names the variable or file
path at fault instead of leaving the operator to grep:

    from corekinect.test.errors import missing_env_var, bad_testbed_class

    raise HardwareError(missing_env_var("MTIB_ADDRESS", "connect to hardware",
                                        hint="or set MOCK_MODE=1"))
    pytest.skip(missing_env_var("MTIB_HOSTS", "enumerate slots",
                                alternatives=("MTIB_HOST", "FIXTURE_CONFIG_PATH")))
    raise ConfigError(bad_testbed_class(module_ref, cause=exc))
"""

from typing import Iterable, Optional

# Re-export the canonical hierarchy
from corekinect.errors import (  # noqa: F401
    CloudError,
    ConfigError,
    FirmwareError,
    HardwareError,
    TimeoutError,
    ValidationError,
)

__all__ = [
    "CloudError",
    "ConfigError",
    "FirmwareError",
    "HardwareError",
    "TimeoutError",
    "ValidationError",
    "missing_env_var",
    "bad_testbed_class",
]


def missing_env_var(
    name: str,
    purpose: str,
    *,
    alternatives: Iterable[str] = (),
    hint: Optional[str] = None,
) -> str:
    """Format a skip/fail message for an empty environment variable.

    Keeps the variable name out of the log-message f-string so every
    caller says the same thing the same way.

    >>> missing_env_var("MTIB_ADDRESS", "connect to hardware")
    'MTIB_ADDRESS not set — cannot connect to hardware.'
    >>> missing_env_var("MTIB_HOSTS", "enumerate slots",
    ...                 alternatives=("MTIB_HOST", "FIXTURE_CONFIG_PATH"))
    'MTIB_HOSTS not set — cannot enumerate slots. Alternatives: MTIB_HOST, FIXTURE_CONFIG_PATH.'
    >>> missing_env_var("DEVICE_ID", "create context", hint="run `corectl auth login`")
    'DEVICE_ID not set — cannot create context. Hint: run `corectl auth login`.'
    """
    parts = [f"{name} not set — cannot {purpose}."]
    alts = tuple(a for a in alternatives if a)
    if alts:
        parts.append(f"Alternatives: {', '.join(alts)}.")
    if hint:
        parts.append(f"Hint: {hint}.")
    return " ".join(parts)


def bad_testbed_class(module_ref: str, cause: BaseException) -> str:
    """Format an error message for a failed ``fixture.module`` import.

    The ``module:Class`` reference in ``concord.yaml`` may fail for
    several reasons (module missing, class missing, circular import).
    The original exception carries that detail; we surface both so the
    operator sees the manifest reference AND the underlying
    ``ImportError`` / ``AttributeError`` in one message.
    """
    return (
        f"Cannot import fixture class {module_ref!r}: "
        f"{type(cause).__name__}: {cause}"
    )
