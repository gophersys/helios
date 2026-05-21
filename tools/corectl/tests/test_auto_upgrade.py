"""Tests for ``corectl.auto_upgrade``.

The auto-upgrade path mutates the user's environment (``pip install``)
and re-execs the process, so every test stubs those out aggressively
and uses ``tmp_path`` as a fake ``~/.corectl`` so the real cache file
is never touched.
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from corectl import auto_upgrade as au


# ────────────────────────────────────────────────────────────────────────
# Fixtures
# ────────────────────────────────────────────────────────────────────────


@pytest.fixture
def fake_home(tmp_path, monkeypatch):
    """Redirect ``Path.home()`` to a tmp dir for the duration of the test.

    The module reads/writes ``Path.home() / '.corectl' / '.upgrade_cache.json'``
    on every call; tests must not be allowed to splat on the real one.
    """
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


@pytest.fixture
def cache_file(fake_home):
    return fake_home / ".corectl" / ".upgrade_cache.json"


@pytest.fixture(autouse=True)
def stub_config(monkeypatch):
    """Pin the api_url + tls_verify resolution so PyPI URL derivation works."""
    monkeypatch.setattr(au, "_pypi_index_url", lambda url: "https://pypi.example/simple/corectl/")
    # Keep ``_pip_index_url`` real so we still exercise the strip-trailing
    # path; it falls back to "" on a malformed URL.


def _set_installed_version(monkeypatch, v: str):
    monkeypatch.setattr(au, "__version__", v)


def _stub_fetch(monkeypatch, value):
    """Make ``_fetch_latest_version`` return ``value`` without hitting the network."""
    monkeypatch.setattr(au, "_fetch_latest_version", lambda *_a, **_kw: value)


def _stub_writable_site(monkeypatch, writable: bool = True):
    monkeypatch.setattr(au, "_site_packages_writable", lambda: writable)


# ────────────────────────────────────────────────────────────────────────
# Opt-out / non-interactive early returns
# ────────────────────────────────────────────────────────────────────────


def test_skips_when_opt_out_env_set(fake_home, monkeypatch):
    """``opt_out=True`` short-circuits before any PyPI call."""
    fetched = MagicMock()
    monkeypatch.setattr(au, "_fetch_latest_version", fetched)

    au.maybe_auto_upgrade(interactive=True, opt_out=True)

    assert not fetched.called
    # And no cache file was created.
    assert not (fake_home / ".corectl" / ".upgrade_cache.json").exists()


def test_skips_when_non_interactive(fake_home, monkeypatch):
    """No auto-upgrade in CI / scripts / pipes — interactive=False short-circuits."""
    fetched = MagicMock()
    monkeypatch.setattr(au, "_fetch_latest_version", fetched)

    au.maybe_auto_upgrade(interactive=False, opt_out=False)

    assert not fetched.called
    assert not (fake_home / ".corectl" / ".upgrade_cache.json").exists()


# ────────────────────────────────────────────────────────────────────────
# Throttle window
# ────────────────────────────────────────────────────────────────────────


def test_skips_when_within_throttle_window(fake_home, cache_file, monkeypatch):
    """A recent ``last_check_at`` keeps us from probing PyPI again."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    recent = datetime.now(timezone.utc) - timedelta(hours=1)
    cache_file.write_text(json.dumps({
        "last_check_at": recent.isoformat(timespec="seconds"),
        "last_seen_latest": "0.11.0",
        "last_attempt_at": recent.isoformat(timespec="seconds"),
        "last_attempt_outcome": "noop",
    }))

    fetched = MagicMock()
    monkeypatch.setattr(au, "_fetch_latest_version", fetched)
    monkeypatch.setattr(au, "CHECK_INTERVAL", 6)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert not fetched.called


def test_probes_when_outside_throttle_window(fake_home, cache_file, monkeypatch):
    """Stale ``last_check_at`` re-enables the PyPI probe."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    stale = datetime.now(timezone.utc) - timedelta(hours=24)
    cache_file.write_text(json.dumps({
        "last_check_at": stale.isoformat(timespec="seconds"),
        "last_seen_latest": "0.11.0",
    }))

    fetched = MagicMock(return_value="0.11.0")
    monkeypatch.setattr(au, "_fetch_latest_version", fetched)
    _set_installed_version(monkeypatch, "0.11.0")
    _stub_writable_site(monkeypatch)
    monkeypatch.setattr(au, "CHECK_INTERVAL", 6)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert fetched.called


# ────────────────────────────────────────────────────────────────────────
# Noop / upgrade decision
# ────────────────────────────────────────────────────────────────────────


def test_noop_when_installed_equals_latest(fake_home, cache_file, monkeypatch):
    """``__version__ == latest`` should not invoke pip."""
    _set_installed_version(monkeypatch, "0.11.0")
    _stub_fetch(monkeypatch, "0.11.0")
    _stub_writable_site(monkeypatch)

    popen = MagicMock()
    monkeypatch.setattr(au.subprocess, "run", popen)
    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert not popen.called
    assert not execv.called
    # noop is recorded in the cache so the throttle clock starts.
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "noop"
    assert data["last_seen_latest"] == "0.11.0"


def test_upgrades_when_latest_is_newer(fake_home, cache_file, monkeypatch, capsys):
    """Newer PyPI version → run pip → re-exec the process."""
    _set_installed_version(monkeypatch, "0.11.0")
    _stub_fetch(monkeypatch, "0.12.0")
    _stub_writable_site(monkeypatch)

    pip_result = MagicMock(returncode=0, stdout="", stderr="")
    sp_run = MagicMock(return_value=pip_result)
    monkeypatch.setattr(au.subprocess, "run", sp_run)

    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    # pip was invoked with the expected pinned upgrade command shape.
    assert sp_run.called
    cmd = sp_run.call_args[0][0]
    assert "pip" in cmd
    assert "install" in cmd
    assert "--upgrade" in cmd
    assert "--extra-index-url" in cmd
    assert "corectl==0.12.0" in cmd

    # And we attempted to re-exec.
    assert execv.called

    # Cache records the upgrade.
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "upgraded"
    assert data["last_seen_latest"] == "0.12.0"


def test_failsoft_when_pip_install_fails(fake_home, cache_file, monkeypatch, capsys):
    """Non-zero pip exit → yellow warning, swallow, cache the failure."""
    _set_installed_version(monkeypatch, "0.11.0")
    _stub_fetch(monkeypatch, "0.12.0")
    _stub_writable_site(monkeypatch)

    pip_result = MagicMock(returncode=1, stdout="", stderr="ERROR: boom")
    monkeypatch.setattr(au.subprocess, "run", MagicMock(return_value=pip_result))

    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    # Must not raise.
    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    captured = capsys.readouterr()
    assert "failed" in captured.err.lower()
    # Did not re-exec.
    assert not execv.called
    # Failure was cached so we don't keep retrying.
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "failed"


def test_handles_pypi_unreachable_gracefully(fake_home, cache_file, monkeypatch, capsys):
    """``_fetch_latest_version`` returning None → no crash, throttle still set."""
    _set_installed_version(monkeypatch, "0.11.0")
    _stub_fetch(monkeypatch, None)
    _stub_writable_site(monkeypatch)

    sp_run = MagicMock()
    monkeypatch.setattr(au.subprocess, "run", sp_run)
    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert not sp_run.called
    assert not execv.called
    # Throttle is set so we don't retry on every command.
    data = json.loads(cache_file.read_text())
    assert "last_check_at" in data
    assert data["last_attempt_outcome"] == "skipped"


def test_handles_pypi_request_exception_gracefully(monkeypatch):
    """``_fetch_latest_version`` itself swallows requests' Exception subclasses."""
    import requests as _requests
    boom = MagicMock(side_effect=_requests.exceptions.ConnectionError("nope"))
    monkeypatch.setattr("requests.get", boom)

    # Direct call into the fetch helper — should not raise.
    out = au._fetch_latest_version("https://pypi.example/simple/corectl/", True)
    assert out is None


# ────────────────────────────────────────────────────────────────────────
# Cache writes / reads
# ────────────────────────────────────────────────────────────────────────


def test_writes_throttle_cache(fake_home, cache_file, monkeypatch):
    """A successful no-op writes the four diagnostic fields."""
    _set_installed_version(monkeypatch, "0.11.0")
    _stub_fetch(monkeypatch, "0.11.0")
    _stub_writable_site(monkeypatch)
    monkeypatch.setattr(au.subprocess, "run", MagicMock())
    monkeypatch.setattr(au.os, "execv", MagicMock())

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert cache_file.exists()
    data = json.loads(cache_file.read_text())
    assert set(data.keys()) >= {
        "last_check_at",
        "last_seen_latest",
        "last_attempt_at",
        "last_attempt_outcome",
    }
    # ISO format with timezone — parseable round-trip.
    assert datetime.fromisoformat(data["last_check_at"]).tzinfo is not None


def test_respects_existing_throttle_cache(fake_home, cache_file, monkeypatch):
    """An existing fresh cache short-circuits — no PyPI call, no pip, no execv."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    recent = datetime.now(timezone.utc) - timedelta(minutes=10)
    cache_file.write_text(json.dumps({
        "last_check_at": recent.isoformat(timespec="seconds"),
        "last_seen_latest": "0.12.0",
        "last_attempt_at": recent.isoformat(timespec="seconds"),
        "last_attempt_outcome": "failed",
    }))

    fetched = MagicMock()
    monkeypatch.setattr(au, "_fetch_latest_version", fetched)
    sp_run = MagicMock()
    monkeypatch.setattr(au.subprocess, "run", sp_run)
    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)
    monkeypatch.setattr(au, "CHECK_INTERVAL", 6)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert not fetched.called
    assert not sp_run.called
    assert not execv.called
    # And the cache content is untouched (a within-window call must not
    # overwrite the prior diagnostic record).
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "failed"


def test_skips_when_site_packages_readonly(fake_home, cache_file, monkeypatch, capsys):
    """Read-only site-packages → one-time notice, no pip call."""
    _set_installed_version(monkeypatch, "0.11.0")
    _stub_fetch(monkeypatch, "0.12.0")
    _stub_writable_site(monkeypatch, writable=False)

    sp_run = MagicMock()
    monkeypatch.setattr(au.subprocess, "run", sp_run)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert not sp_run.called
    out = capsys.readouterr().err
    assert "outdated" in out.lower()
    assert "writable" in out.lower()
    # Throttle the notice — we don't want it on every invocation.
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "skipped"


# ────────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────────


def test_semver_tuple_orders_intuitively():
    t = au._semver_tuple
    assert t("0.10.0") < t("0.11.0")
    assert t("0.11.0") < t("0.11.1")
    assert t("0.11.0") < t("1.0.0")
    # Pre-release strips off the suffix — we don't want to nag dev builds.
    assert t("0.12.0rc1") == t("0.12.0")


def test_pip_index_url_strips_per_package_path():
    # _pip_index_url converts the API URL into a pip-friendly simple index root.
    assert au._pip_index_url("https://concord.example.com").endswith("/simple/")
    assert "pypi.concord.example.com" in au._pip_index_url("https://concord.example.com")


def test_parse_iso_accepts_both_string_and_float():
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    assert au._parse_iso(now_iso) is not None
    assert au._parse_iso(1234567890.5) == 1234567890.5
    assert au._parse_iso(None) is None
    assert au._parse_iso("not-a-date") is None
