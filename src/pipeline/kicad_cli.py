"""Single source of truth for locating the kicad-cli binary.

Every consumer previously did::

    KICAD_CLI = shutil.which("kicad-cli") or "/usr/bin/kicad-cli"

which is dishonest: when KiCad is not installed the fallback is a path that
does not exist, so the failure surfaces much later as a bare
``FileNotFoundError: '/usr/bin/kicad-cli'`` from deep inside subprocess. That
turned "KiCad is missing" into 58 apparently-unrelated test failures.

Resolution is by PATH only — per the project decision in CLAUDE.md, the
toolchain is whatever ``kicad-cli`` PATH points at (KiCad 10 in CI and in the
devcontainer), never a hardcoded location.
"""

from __future__ import annotations

import shutil
import subprocess


def find_kicad_cli() -> str | None:
    """Absolute path to kicad-cli, or None when it is not installed."""
    return shutil.which("kicad-cli")


def require_kicad_cli() -> str:
    """Absolute path to kicad-cli, raising a diagnosable error if absent.

    Raises FileNotFoundError specifically, not a bare RuntimeError: callers
    such as manufacturing.export_* degrade gracefully behind ``except OSError``
    (FileNotFoundError is an OSError subclass), and that is exactly the error
    subprocess raised before this module existed. Changing the type here would
    silently turn "KiCad is absent" from a handled condition into an escaping
    exception several layers up.
    """
    path = find_kicad_cli()
    if path is None:
        raise FileNotFoundError(
            "kicad-cli not found on PATH. Install KiCad 10 (see docs/ci.md), "
            "use the devcontainer, or run inside ghcr.io/gophersys/research-hardware-ci."
        )
    return path


def kicad_cli_version() -> str | None:
    """Version string reported by kicad-cli, or None when unavailable.

    Never raises: callers use this for capability reporting and skip logic,
    where a broken install should read the same as a missing one.
    """
    path = find_kicad_cli()
    if path is None:
        return None
    try:
        out = subprocess.run([path, "version"], capture_output=True, text=True,
                             timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        return None
    return out.stdout.strip() or None
