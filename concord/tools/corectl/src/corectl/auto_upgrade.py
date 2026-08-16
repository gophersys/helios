"""Best-effort self-upgrade on launch.

When the internal PyPI publishes a newer ``corectl`` or ``corekinect``
wheel, this module pip-installs them in place and re-execs the same
command so the new code picks up immediately. The intent is that
developers never run a stale CLI/SDK without ever needing to type
``pip install --upgrade`` themselves.

The two packages are upgraded together (atomic) per the lockstep
``major.minor`` policy: corectl and corekinect always ship matching
minors and either being behind is a problem we want to fix in one
shot rather than have one stale + one current.

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
* Installed already equals latest for both packages → cache, no-op.
* Either package is editable-installed (``pip install -e``) → skip the
  upgrade entirely. Editable installs are dev source checkouts; pip
  ``--upgrade`` would replace them with a downloaded wheel and silently
  break the dev's working tree. We never do that.
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
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from . import __version__


# Module-level so tests can monkey-patch a tighter window. Hours.
CHECK_INTERVAL = 6

# Packages this module keeps in lockstep. corectl is the CLI; corekinect
# is the test framework / SDK that corectl ships alongside.
MANAGED_PACKAGES: Tuple[str, ...] = ("corectl", "corekinect")

_REQUEST_TIMEOUT_S = 3.0
_PIP_TIMEOUT_S = 120.0

# Wheel filename grammar (PEP 427), parameterized by package name so the
# same regex factory can serve both managed packages:
#   {name}-{version}(-{build})?-{python}-{abi}-{platform}.whl
def _wheel_version_re(pkg: str) -> re.Pattern:
    return re.compile(
        rf"{re.escape(pkg)}-(\d+(?:\.\d+){{1,2}}(?:[ab]\d+|rc\d+|\.post\d+|\.dev\d+)?)-"
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


def _pypi_index_url(api_url: str, pkg: str = "corectl") -> Optional[str]:
    """Derive the internal PyPI ``simple/<pkg>/`` URL from the API URL.

    Mirrors ``version_check._pypi_index_url`` — Concord's ingress serves
    PyPI at the ``pypi.`` subdomain alongside the main API host. When
    the api_url is empty or malformed we return None and the caller
    silently no-ops.
    """
    try:
        parsed = urlparse(api_url)
        if not parsed.scheme or not parsed.hostname:
            return None
        return f"{parsed.scheme}://pypi.{parsed.hostname}/simple/{pkg}/"
    except Exception:
        return None


def _fetch_latest_version(index_url: str, pkg: str, verify) -> Optional[str]:
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
            set(_wheel_version_re(pkg).findall(resp.text)),
            key=_semver_tuple,
        )
        return versions[-1] if versions else None
    except Exception:
        return None


def _installed_version(pkg: str) -> Optional[str]:
    """Return the version of ``pkg`` installed in the current interpreter,
    or None if the package isn't installed at all.

    Used to detect "corekinect is way behind corectl" so we can pull it
    forward without the user noticing the drift.
    """
    if pkg == "corectl":
        # Avoid an importlib round-trip for our own module.
        return __version__
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:
        return None
    try:
        return version(pkg)
    except PackageNotFoundError:
        return None


def _is_editable_install(pkg: str) -> bool:
    """True if ``pkg`` was installed via ``pip install -e``.

    Editable installs point at a source checkout. ``pip install --upgrade``
    would silently replace them with a downloaded wheel — destroying the
    dev's working tree without warning. So whenever EITHER package in the
    lockstep set is editable we skip the auto-upgrade entirely; the dev
    is clearly working on the code locally and we shouldn't surprise
    them. Returns False on any introspection error (we'd rather attempt
    and let pip succeed than skip a legitimate upgrade).
    """
    try:
        from importlib.metadata import PackageNotFoundError, distribution
    except ImportError:
        return False
    try:
        dist = distribution(pkg)
    except PackageNotFoundError:
        # Not installed at all — treat as non-editable so the upgrade
        # path can install it fresh from PyPI.
        return False
    try:
        # PEP 660 / pip editable installs write ``direct_url.json`` with
        # ``dir_info.editable: true``. Older "develop" installs predating
        # PEP 660 leave a ``.egg-link`` file in site-packages; both forms
        # appear in ``dist.files`` so the json probe is the canonical check.
        raw = dist.read_text("direct_url.json")
        if not raw:
            return False
        return bool(json.loads(raw).get("dir_info", {}).get("editable", False))
    except Exception:
        return False


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


def _resolve_targets(
    api_url: str, verify
) -> Optional[Dict[str, Dict[str, Optional[str]]]]:
    """For each managed package, fetch ``installed`` + ``latest`` versions.

    Returns ``{pkg: {"installed": str|None, "latest": str|None}}`` or None
    if PyPI couldn't be reached for ANY of the managed packages — in
    which case the throttle is updated and the caller no-ops. Partial
    success (one reachable, one not) is treated as full failure to keep
    the lockstep contract honest: we never upgrade just one package and
    leave the other behind.
    """
    out: Dict[str, Dict[str, Optional[str]]] = {}
    for pkg in MANAGED_PACKAGES:
        idx = _pypi_index_url(api_url, pkg)
        if idx is None:
            return None
        latest = _fetch_latest_version(idx, pkg, verify)
        if latest is None:
            return None
        out[pkg] = {"installed": _installed_version(pkg), "latest": latest}
    return out


def _needs_upgrade(targets: Dict[str, Dict[str, Optional[str]]]) -> bool:
    """True when ANY managed package is behind its latest published wheel.

    Missing-installed counts as out-of-date so a fresh corectl-only
    install on a machine without corekinect pulls the SDK on next launch.
    """
    for pkg, ver in targets.items():
        installed = ver["installed"]
        latest = ver["latest"]
        if installed is None:
            return True
        if _semver_tuple(latest) > _semver_tuple(installed):
            return True
    return False


def _format_upgrade_summary(
    targets: Dict[str, Dict[str, Optional[str]]],
) -> str:
    parts = []
    for pkg, ver in targets.items():
        installed = ver["installed"] or "(missing)"
        latest = ver["latest"]
        if installed != latest:
            parts.append(f"{pkg} {installed} → {latest}")
    return ", ".join(parts) if parts else "(no diff)"


def maybe_auto_upgrade(*, interactive: bool, opt_out: bool) -> None:
    """Upgrade-and-re-exec on launch when a newer wheel is available.

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
    3. Probes PyPI for the latest published ``corectl`` AND ``corekinect``
       in one round so the upgrade respects the lockstep policy.
    4. On either-out-of-date: print yellow notice, run
       ``pip install --upgrade --extra-index-url <pypi> corectl==<v> corekinect==<v>``
       as a subprocess (``sys.executable -m pip``), then on success
       print green notice and ``os.execv(sys.argv[0], sys.argv)`` so
       the new code picks up.
    5. Any failure (pip non-zero, PyPI unreachable, read-only site-
       packages, editable install) emits a yellow warning at most once
       per throttle window and the original command continues.
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

    targets = _resolve_targets(api_url, verify)
    if targets is None:
        # PyPI unreachable / parse failure for at least one package —
        # cache the attempt so we don't retry on every command for the
        # next CHECK_INTERVAL hours.
        _write_cache(
            {
                "last_check_at": _now_iso(),
                "last_seen_latest": cache.get("last_seen_latest"),
                "last_attempt_at": _now_iso(),
                "last_attempt_outcome": "skipped",
            }
        )
        return

    # Record the freshly-observed latest versions even when there's no
    # work to do — handy when poking at the cache to confirm the probe
    # ran. Per-package values keep the format honest about lockstep.
    seen_latest = {pkg: targets[pkg]["latest"] for pkg in MANAGED_PACKAGES}

    if not _needs_upgrade(targets):
        # Already current on every managed package. Record the no-op so
        # the throttle clock starts.
        _write_cache(
            {
                "last_check_at": _now_iso(),
                "last_seen_latest": seen_latest,
                "last_attempt_at": _now_iso(),
                "last_attempt_outcome": "noop",
            }
        )
        return

    # If EITHER managed package is editable-installed we never auto-
    # upgrade. The dev is working on the source tree; replacing their
    # editable install with a wheel would silently destroy their
    # working changes. Just log it and bail.
    editable = [pkg for pkg in MANAGED_PACKAGES if _is_editable_install(pkg)]
    if editable:
        # No yellow notice — devs in this mode know what they're doing
        # and don't want to be nagged every launch. We still cache so
        # the throttle clock starts and we don't probe PyPI again.
        _write_cache(
            {
                "last_check_at": _now_iso(),
                "last_seen_latest": seen_latest,
                "last_attempt_at": _now_iso(),
                "last_attempt_outcome": "skipped_editable",
            }
        )
        return

    # We're going to attempt an upgrade. First make sure the install
    # would even succeed — a system Python with read-only site-packages
    # will EACCES on every command, and we don't want the user to see
    # that error every single time. Print a one-time notice and bail.
    if not _site_packages_writable():
        diff = _format_upgrade_summary(targets)
        _print_stderr(
            f"{_ANSI_YELLOW}{diff} is outdated; re-install in a writable env "
            f"to enable auto-upgrade.{_ANSI_RESET}"
        )
        _write_cache(
            {
                "last_check_at": _now_iso(),
                "last_seen_latest": seen_latest,
                "last_attempt_at": _now_iso(),
                "last_attempt_outcome": "skipped",
            }
        )
        return

    summary = _format_upgrade_summary(targets)
    _print_stderr(f"{_ANSI_YELLOW}Upgrading {summary}...{_ANSI_RESET}")

    # PEP 503 names the index URL; pip wants ``--extra-index-url`` so we
    # don't disable the public PyPI fallback (transitive deps live
    # there). Pinned ``pkg==<latest>`` per managed package forces pip
    # to land exactly on the wheels we just saw on the index, and
    # passing both in one invocation keeps the upgrade atomic.
    pip_cmd = [
        sys.executable,
        "-m",
        "pip",
        "install",
        "--upgrade",
        "--extra-index-url",
        _pip_index_url(api_url),
    ] + [f"{pkg}=={targets[pkg]['latest']}" for pkg in MANAGED_PACKAGES]

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
            f"{_ANSI_YELLOW}corectl auto-upgrade failed (pip exit {rc}); "
            f"continuing with {summary.split(' →')[0] if summary else __version__}.{_ANSI_RESET}"
        )
        # Record the failure so we don't keep retrying on every command
        # for the next CHECK_INTERVAL hours.
        _write_cache(
            {
                "last_check_at": _now_iso(),
                "last_seen_latest": seen_latest,
                "last_attempt_at": _now_iso(),
                "last_attempt_outcome": "failed",
            }
        )
        return

    _write_cache(
        {
            "last_check_at": _now_iso(),
            "last_seen_latest": seen_latest,
            "last_attempt_at": _now_iso(),
            "last_attempt_outcome": "upgraded",
        }
    )

    _print_stderr(f"{_ANSI_GREEN}Upgrade complete. Re-running...{_ANSI_RESET}")

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
    """Strip the trailing ``<pkg>/`` from the simple index for pip.

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
