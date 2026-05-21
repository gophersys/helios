"""Best-effort self-upgrade on launch.

When the internal PyPI publishes a newer ``corectl`` wheel, this module
pip-installs it in place and re-execs the same command so the new code
picks up immediately. The intent is that developers never run a stale
CLI without ever needing to type ``pip install --upgrade`` themselves.

Compared to the lighter ``version_check.maybe_print_upgrade_notice``,
this path actually performs the upgrade. The two coexist:

* ``version_check`` runs unconditionally (24h-cached notice), prints a
  yellow hint, never mutates anything. Safe in CI / scripts / pipes.
* ``maybe_auto_upgrade`` only runs in interactive shells, throttles
  itself to 6h, swallows every error, and re-execs after a successful
  ``pip install`` so the user's command resumes against the new wheel.

Failure modes — all silent / fail-soft:

* Non-interactive caller (CI, pipe) → no-op.
* Opted out via ``--no-auto-upgrade`` or ``CONCORD_NO_AUTO_UPGRADE=1`` → no-op.
* Throttle window not elapsed → no-op.
* PyPI unreachable / index parse failure → cache the attempt, no-op.
* Installed already equals latest → cache, no-op.
* ``pip install`` exits non-zero → yellow warning, cache the failure to
  avoid retrying on every subsequent invocation for the rest of the
  throttle window, continue with the old version.
* Read-only ``site-packages`` (system Python, distro install) → one-time
  yellow notice telling the user to re-install in a writable env, then
  cache so it's not nagged on every command.
"""

from __future__ import annotations

import json
import os
import re
import site
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from . import __version__


# Module-level so tests can monkey-patch a tighter window. Hours.
CHECK_INTERVAL = 6

_REQUEST_TIMEOUT_S = 3.0
_PIP_TIMEOUT_S = 120.0

# Same wheel-filename grammar used by version_check (PEP 427):
#   {name}-{version}(-{build})?-{python}-{abi}-{platform}.whl
_WHEEL_VERSION_RE = re.compile(
    r"corectl-(\d+(?:\.\d+){1,2}(?:[ab]\d+|rc\d+|\.post\d+|\.dev\d+)?)-"
)

_ANSI_YELLOW = "\033[33m"
_ANSI_GREEN = "\033[32m"
_ANSI_RESET = "\033[0m"


def _cache_path() -> Path:
    """Resolve the throttle cache path.

    Computed lazily (not at import time) so tests can monkey-patch
    ``Path.home`` without first having to also reach into this module.
    """
    return Path.home() / ".corectl" / ".upgrade_cache.json"


def _read_cache() -> dict:
    try:
        return json.loads(_cache_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _write_cache(data: dict) -> None:
    try:
        path = _cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data))
    except OSError:
        # Read-only home, no permissions — silently skip. The whole module
        # is best-effort; failing to persist a throttle marker is fine.
        pass


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _semver_tuple(v: str) -> tuple:
    """Comparable tuple for naïve semver comparison.

    Matches ``version_check._semver_tuple``: strips dev/rc/post suffixes
    so a pre-release sorts as an upgrade past the matching public release.
    """
    core = re.match(r"(\d+(?:\.\d+)*)", v)
    if not core:
        return ()
    return tuple(int(p) for p in core.group(1).split("."))


def _pypi_index_url(api_url: str) -> Optional[str]:
    """Derive the internal PyPI ``simple/corectl/`` URL from the API URL.

    Mirrors ``version_check._pypi_index_url`` — Concord's ingress serves
    PyPI at the ``pypi.`` subdomain alongside the main API host. When
    the api_url is empty or malformed we return None and the caller
    silently no-ops.
    """
    try:
        parsed = urlparse(api_url)
        if not parsed.scheme or not parsed.hostname:
            return None
        return f"{parsed.scheme}://pypi.{parsed.hostname}/simple/corectl/"
    except Exception:
        return None


def _fetch_latest_version(index_url: str, verify) -> Optional[str]:
    """Return the highest published version on the internal PyPI, or None.

    Returns None on any error — network, HTTP status, parse failure.
    Callers cache the failure so a broken PyPI doesn't make every
    invocation pause for the request timeout.
    """
    try:
        import requests  # local import — auto-upgrade is opt-out / best-effort
    except ImportError:
        return None
    try:
        resp = requests.get(index_url, timeout=_REQUEST_TIMEOUT_S, verify=verify)
        if resp.status_code != 200:
            return None
        versions = sorted(
            set(_WHEEL_VERSION_RE.findall(resp.text)),
            key=_semver_tuple,
        )
        return versions[-1] if versions else None
    except Exception:
        return None


def _site_packages_writable() -> bool:
    """Probe whether ``pip install`` would have write permission.

    We don't try to predict every pip path — we just check the first
    site-packages directory the current interpreter uses. If that's
    read-only (system Python on macOS / Debian, the read-only WSL Python
    distro layout) ``pip install`` will EACCES regardless of which user
    runs it, so there's no point trying.
    """
    try:
        paths = site.getsitepackages()
    except Exception:
        return True  # err on the side of attempting
    if not paths:
        return True
    return os.access(paths[0], os.W_OK)


def _print_stderr(msg: str) -> None:
    print(msg, file=sys.stderr)


def maybe_auto_upgrade(*, interactive: bool, opt_out: bool) -> None:
    """Upgrade-and-re-exec on launch when a newer corectl is available.

    Parameters
    ----------
    interactive
        ``True`` only when stdin is a TTY. Caller computes this; we
        never auto-upgrade in CI / scripts / non-tty contexts because
        a surprise ``pip install`` mid-pipeline is far worse than
        running a slightly stale CLI for one more day.
    opt_out
        ``True`` when the user passed ``--no-auto-upgrade`` /
        ``CONCORD_NO_AUTO_UPGRADE=1`` / ``--no-version-check``. We
        treat all three identically — the user said "don't touch my
        environment".

    Behaviour summary (see module docstring for the full contract):

    1. Early-return if ``opt_out`` or not ``interactive``.
    2. Throttled to one PyPI probe per ``CHECK_INTERVAL`` hours.
    3. On newer-version-available: print yellow notice, run
       ``pip install --upgrade --extra-index-url <pypi> corectl==<latest>``
       as a subprocess (``sys.executable -m pip``), then on success
       print green notice and ``os.execv(sys.argv[0], sys.argv)`` so
       the new code picks up.
    4. Any failure (pip non-zero, PyPI unreachable, read-only site-
       packages) emits a yellow warning at most once per throttle
       window and the original command continues.
    """
    if opt_out:
        return
    if not interactive:
        return

    cache = _read_cache()
    now = time.time()
    last_check_at = _parse_iso(cache.get("last_check_at"))
    interval_s = max(0, int(CHECK_INTERVAL)) * 3600

    if last_check_at is not None and (now - last_check_at) < interval_s:
        # Still inside the throttle window — don't even hit PyPI.
        return

    # Resolve the PyPI URL via the same config helper the rest of corectl
    # uses. We do this lazily to keep the import surface minimal when
    # the auto-upgrade path is opted out.
    try:
        from .config import get_api_url, get_tls_verify, load_config
    except Exception:
        return

    try:
        config = load_config()
        api_url = get_api_url(config)
        verify = get_tls_verify(config)
    except Exception:
        return

    index_url = _pypi_index_url(api_url)
    if index_url is None:
        return

    latest = _fetch_latest_version(index_url, verify)
    if latest is None:
        # PyPI unreachable / parse failure — mark the throttle so we
        # don't retry on every command for the next CHECK_INTERVAL hours.
        _write_cache(
            {
                "last_check_at": _now_iso(),
                "last_seen_latest": cache.get("last_seen_latest"),
                "last_attempt_at": _now_iso(),
                "last_attempt_outcome": "skipped",
            }
        )
        return

    if _semver_tuple(latest) <= _semver_tuple(__version__):
        # Already current. Record the no-op so the throttle clock starts.
        _write_cache(
            {
                "last_check_at": _now_iso(),
                "last_seen_latest": latest,
                "last_attempt_at": _now_iso(),
                "last_attempt_outcome": "noop",
            }
        )
        return

    # We're going to attempt an upgrade. First make sure the install
    # would even succeed — a system Python with read-only site-packages
    # will EACCES on every command, and we don't want the user to see
    # that error every single time. Print a one-time notice and bail.
    if not _site_packages_writable():
        _print_stderr(
            f"{_ANSI_YELLOW}corectl {__version__} is outdated (latest: {latest}); "
            f"re-install in a writable env to enable auto-upgrade.{_ANSI_RESET}"
        )
        _write_cache(
            {
                "last_check_at": _now_iso(),
                "last_seen_latest": latest,
                "last_attempt_at": _now_iso(),
                "last_attempt_outcome": "skipped",
            }
        )
        return

    _print_stderr(
        f"{_ANSI_YELLOW}Upgrading corectl {__version__} → {latest}...{_ANSI_RESET}"
    )

    # PEP 503 names the index URL; pip wants ``--extra-index-url`` so we
    # don't disable the public PyPI fallback (corekinect's deps live
    # there). The pinned ``corectl==<latest>`` request is what forces
    # pip to land exactly on the wheel we just saw on the index.
    pip_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--extra-index-url",
        _pip_index_url(api_url),
        f"corectl=={latest}",
    ]

    try:
        result = subprocess.run(
            pip_cmd,
            timeout=_PIP_TIMEOUT_S,
            capture_output=True,
            text=True,
        )
        rc = result.returncode
    except Exception:
        rc = 1
        result = None  # type: ignore[assignment]

    if rc != 0:
        _print_stderr(
            f"{_ANSI_YELLOW}corectl auto-upgrade to {latest} failed "
            f"(pip exit {rc}); continuing with {__version__}.{_ANSI_RESET}"
        )
        # Record the failure so we don't keep retrying on every command
        # for the next CHECK_INTERVAL hours.
        _write_cache(
            {
                "last_check_at": _now_iso(),
                "last_seen_latest": latest,
                "last_attempt_at": _now_iso(),
                "last_attempt_outcome": "failed",
            }
        )
        return

    _write_cache(
        {
            "last_check_at": _now_iso(),
            "last_seen_latest": latest,
            "last_attempt_at": _now_iso(),
            "last_attempt_outcome": "upgraded",
        }
    )

    _print_stderr(
        f"{_ANSI_GREEN}Upgrade complete. Re-running...{_ANSI_RESET}"
    )

    # Re-exec the same command so the new wheel's code path takes over.
    # ``argv[0]`` is the absolute path to the corectl entry-point script;
    # if it isn't (running as ``python -m corectl``, etc.) ``execv``
    # raises ``FileNotFoundError`` and the original command continues
    # naturally on the upgraded interpreter at the next invocation.
    try:
        os.execv(sys.argv[0], sys.argv)
    except OSError:
        return


def _pip_index_url(api_url: str) -> str:
    """Strip the trailing ``corectl/`` from the simple index for pip.

    pip's ``--extra-index-url`` wants the root of the simple index,
    not a per-package directory. ``_pypi_index_url`` produces the
    per-package URL because that's what the HTTP probe needs.
    """
    try:
        parsed = urlparse(api_url)
        if parsed.scheme and parsed.hostname:
            return f"{parsed.scheme}://pypi.{parsed.hostname}/simple/"
    except Exception:
        pass
    return ""


def _parse_iso(value) -> Optional[float]:
    """Parse the ``last_check_at`` value back into a unix timestamp.

    Accepts ISO-8601 strings (the format we write) and floats (legacy /
    test convenience). Returns None if unparseable so the throttle
    treats the cache as "never checked".
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value).timestamp()
        except ValueError:
            return None
    return None
