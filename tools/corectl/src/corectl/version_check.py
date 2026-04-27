"""Background version check — print an upgrade notice when a newer corectl is published.

Hits the internal PyPI's ``simple/corectl/`` index once per 24h, caches the
result on disk, and prints a single-line notice on the next ``corectl`` run
when a newer version is available. Does NOT auto-pip-install — interrupting
a command mid-flight to upgrade the binary in place is a worse failure mode
than running a slightly stale CLI for one more day.

Behavior is best-effort: any failure (no network, malformed index, missing
``packaging`` lib) silently no-ops. The check never blocks command execution.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from . import __version__

_CACHE_FILE = Path(os.path.expanduser("~/.config/corectl/last-version-check.json"))
_CACHE_TTL_S = 24 * 60 * 60  # one day
_REQUEST_TIMEOUT_S = 2.0     # never make the user wait

# PyPI ``simple/`` index paths the wheel filename pattern.
# Wheel filename grammar (PEP 427): ``{name}-{version}(-{build})?-{python}-{abi}-{platform}.whl``
_WHEEL_VERSION_RE = re.compile(r"corectl-(\d+(?:\.\d+){1,2}(?:[ab]\d+|rc\d+|\.post\d+|\.dev\d+)?)-")


def _pypi_index_url(api_url: str) -> Optional[str]:
    """Derive the internal PyPI ``simple/corectl/`` URL from the API URL.

    Concord's ingress serves PyPI at the ``pypi.`` subdomain alongside the
    main API host (e.g. ``concord.ad.corekinect.com`` →
    ``pypi.concord.ad.corekinect.com``). When the api_url is empty or
    malformed we return None and silently skip the check.
    """
    try:
        parsed = urlparse(api_url)
        if not parsed.scheme or not parsed.hostname:
            return None
        return f"{parsed.scheme}://pypi.{parsed.hostname}/simple/corectl/"
    except Exception:
        return None


def _read_cache() -> dict:
    try:
        return json.loads(_CACHE_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _write_cache(data: dict) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(json.dumps(data))
    except OSError:
        # Read-only home dir, no permissions, etc — silently skip.
        pass


def _semver_tuple(v: str) -> tuple:
    """Parse a version into a comparable tuple. ``packaging`` not required."""
    # Strip trailing dev/rc/post suffixes — we only care about the numeric core
    # for the "is newer" check. A pre-release suffix sorts as an upgrade past
    # the matching public release, which is the conservative choice (don't
    # nag the user if they're on a dev build).
    core = re.match(r"(\d+(?:\.\d+)*)", v)
    if not core:
        return ()
    return tuple(int(p) for p in core.group(1).split("."))


def _fetch_latest_version(index_url: str, verify) -> Optional[str]:
    """Fetch the highest version from PyPI's simple index. Returns None on any error."""
    try:
        import requests  # local import — version check is opt-out / best-effort
    except ImportError:
        return None
    try:
        resp = requests.get(index_url, timeout=_REQUEST_TIMEOUT_S, verify=verify)
        if resp.status_code != 200:
            return None
        versions = sorted(set(_WHEEL_VERSION_RE.findall(resp.text)), key=_semver_tuple)
        return versions[-1] if versions else None
    except Exception:
        return None


def maybe_print_upgrade_notice(api_url: str, verify) -> None:
    """Print a one-line upgrade notice on stderr if a newer corectl is available.

    Uses a 24h on-disk cache to avoid hammering the index. Errors are
    silently swallowed — this is a courtesy notice, never a blocker.
    """
    cache = _read_cache()
    now = time.time()

    last_check = cache.get("last_check_at", 0)
    cached_latest = cache.get("latest_version")

    if now - last_check < _CACHE_TTL_S and cached_latest is not None:
        latest = cached_latest
    else:
        index = _pypi_index_url(api_url)
        if index is None:
            return
        latest = _fetch_latest_version(index, verify)
        if latest is None:
            # Cache the failure so we don't retry on every command.
            _write_cache({"last_check_at": now, "latest_version": cached_latest})
            return
        _write_cache({"last_check_at": now, "latest_version": latest})

    if _semver_tuple(latest) > _semver_tuple(__version__):
        # Use stderr so a piped ``corectl test versions | jq`` invocation
        # isn't corrupted. ANSI colour is intentional — most terminals see
        # it, and the upgrade hint is meant to be eye-catching.
        try:
            parsed = urlparse(api_url)
            installer = (
                f"{parsed.scheme}://{parsed.hostname}/corectl/install.sh"
                if parsed.scheme and parsed.hostname
                else None
            )
        except Exception:
            installer = None
        msg = (
            f"\033[33mcorectl {latest} available (you have {__version__})"
            + (f" — curl -fsSL {installer} | bash" if installer else "")
            + "\033[0m"
        )
        print(msg, file=sys.stderr)
