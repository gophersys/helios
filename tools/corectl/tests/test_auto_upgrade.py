"""Tests for ``corectl.auto_upgrade``.

The auto-upgrade path mutates the user's environment (``pip install``)
and re-execs the process, so every test stubs those out aggressively
and uses ``tmp_path`` as a fake ``~/.corectl`` so the real cache file
is never touched.

The module keeps ``corectl`` and ``corekinect`` in lockstep — every
test that exercises the upgrade path covers both packages explicitly
so a future single-package regression is caught at the unit level.
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
    """Redirect ``Path.home()`` to a tmp dir for the duration of the test."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    return tmp_path


@pytest.fixture
def cache_file(fake_home):
    return fake_home / ".corectl" / ".upgrade_cache.json"


@pytest.fixture(autouse=True)
def stub_pypi_url(monkeypatch):
    """Pin the per-package PyPI URL derivation so tests don't need a real api_url."""
    monkeypatch.setattr(
        au,
        "_pypi_index_url",
        lambda url, pkg="corectl": f"https://pypi.example/simple/{pkg}/",
    )


@pytest.fixture(autouse=True)
def stub_not_editable(monkeypatch):
    """Default tests to non-editable installs. Editable-specific tests override."""
    monkeypatch.setattr(au, "_is_editable_install", lambda pkg: False)


def _set_installed_versions(monkeypatch, *, corectl: str, corekinect: str):
    """Pin both packages' installed versions for the duration of one test."""
    monkeypatch.setattr(au, "__version__", corectl)
    monkeypatch.setattr(
        au,
        "_installed_version",
        lambda pkg: corectl if pkg == "corectl" else corekinect,
    )


def _stub_fetch_latest(monkeypatch, mapping):
    """Stub ``_fetch_latest_version`` to return per-package latest from ``mapping``.

    ``mapping`` is ``{"corectl": "0.12.0", "corekinect": "0.12.0"}`` or
    similar. Pass ``None`` for a package to simulate PyPI unreachable for
    that package specifically.
    """
    def _fetch(index_url, pkg, verify):
        return mapping.get(pkg)
    monkeypatch.setattr(au, "_fetch_latest_version", _fetch)


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
        "last_seen_latest": {"corectl": "0.11.0", "corekinect": "0.11.0"},
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
        "last_seen_latest": {"corectl": "0.11.0", "corekinect": "0.11.0"},
    }))

    _set_installed_versions(monkeypatch, corectl="0.11.0", corekinect="0.11.0")
    fetched = MagicMock(return_value="0.11.0")
    monkeypatch.setattr(au, "_fetch_latest_version", fetched)
    _stub_writable_site(monkeypatch)
    monkeypatch.setattr(au, "CHECK_INTERVAL", 6)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert fetched.called


# ────────────────────────────────────────────────────────────────────────
# Noop / upgrade decision
# ────────────────────────────────────────────────────────────────────────


def test_noop_when_both_packages_current(fake_home, cache_file, monkeypatch):
    """Both packages == latest → no pip, no execv, throttle starts."""
    _set_installed_versions(monkeypatch, corectl="0.11.0", corekinect="0.11.0")
    _stub_fetch_latest(monkeypatch, {"corectl": "0.11.0", "corekinect": "0.11.0"})
    _stub_writable_site(monkeypatch)

    sp_run = MagicMock()
    monkeypatch.setattr(au.subprocess, "run", sp_run)
    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert not sp_run.called
    assert not execv.called
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "noop"
    assert data["last_seen_latest"]["corectl"] == "0.11.0"
    assert data["last_seen_latest"]["corekinect"] == "0.11.0"


def test_upgrades_both_when_corectl_outdated(fake_home, cache_file, monkeypatch):
    """corectl behind → pip pulls BOTH to the published lockstep target."""
    _set_installed_versions(monkeypatch, corectl="0.11.0", corekinect="0.11.0")
    _stub_fetch_latest(monkeypatch, {"corectl": "0.12.0", "corekinect": "0.12.0"})
    _stub_writable_site(monkeypatch)

    pip_result = MagicMock(returncode=0, stdout="", stderr="")
    sp_run = MagicMock(return_value=pip_result)
    monkeypatch.setattr(au.subprocess, "run", sp_run)
    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert sp_run.called
    cmd = sp_run.call_args[0][0]
    assert "pip" in cmd and "install" in cmd and "--upgrade" in cmd
    assert "--extra-index-url" in cmd
    assert "corectl==0.12.0" in cmd
    assert "corekinect==0.12.0" in cmd
    assert execv.called

    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "upgraded"


def test_upgrades_both_when_corekinect_outdated(fake_home, cache_file, monkeypatch):
    """corekinect behind (the common drift case) → pip pulls BOTH forward."""
    _set_installed_versions(monkeypatch, corectl="0.11.0", corekinect="0.10.5")
    _stub_fetch_latest(monkeypatch, {"corectl": "0.11.0", "corekinect": "0.11.0"})
    _stub_writable_site(monkeypatch)

    pip_result = MagicMock(returncode=0, stdout="", stderr="")
    sp_run = MagicMock(return_value=pip_result)
    monkeypatch.setattr(au.subprocess, "run", sp_run)
    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert sp_run.called
    cmd = sp_run.call_args[0][0]
    # Both packages on the pip command line.
    assert "corectl==0.11.0" in cmd
    assert "corekinect==0.11.0" in cmd

    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "upgraded"


def test_upgrades_when_corekinect_missing_entirely(fake_home, monkeypatch):
    """corekinect not installed at all → upgrade path installs it."""
    monkeypatch.setattr(au, "__version__", "0.11.0")
    monkeypatch.setattr(
        au,
        "_installed_version",
        lambda pkg: "0.11.0" if pkg == "corectl" else None,
    )
    _stub_fetch_latest(monkeypatch, {"corectl": "0.11.0", "corekinect": "0.11.0"})
    _stub_writable_site(monkeypatch)

    pip_result = MagicMock(returncode=0, stdout="", stderr="")
    sp_run = MagicMock(return_value=pip_result)
    monkeypatch.setattr(au.subprocess, "run", sp_run)
    monkeypatch.setattr(au.os, "execv", MagicMock())

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert sp_run.called
    cmd = sp_run.call_args[0][0]
    assert "corekinect==0.11.0" in cmd


# ────────────────────────────────────────────────────────────────────────
# Editable installs — never clobber a dev's source tree
# ────────────────────────────────────────────────────────────────────────


def test_skips_when_corectl_is_editable(fake_home, cache_file, monkeypatch):
    """``pip install -e tools/corectl`` → auto-upgrade must NOT replace it."""
    _set_installed_versions(monkeypatch, corectl="0.11.0", corekinect="0.11.0")
    _stub_fetch_latest(monkeypatch, {"corectl": "0.12.0", "corekinect": "0.12.0"})
    _stub_writable_site(monkeypatch)
    monkeypatch.setattr(au, "_is_editable_install", lambda pkg: pkg == "corectl")

    sp_run = MagicMock()
    monkeypatch.setattr(au.subprocess, "run", sp_run)
    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    # Critical: no pip, no execv. The dev's editable corectl stays intact.
    assert not sp_run.called
    assert not execv.called
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "skipped_editable"


def test_skips_when_corekinect_is_editable(fake_home, cache_file, monkeypatch):
    """``pip install -e libs/python`` → auto-upgrade must NOT replace it
    even if only corectl is the one with a newer version available."""
    _set_installed_versions(monkeypatch, corectl="0.11.0", corekinect="0.11.0")
    _stub_fetch_latest(monkeypatch, {"corectl": "0.12.0", "corekinect": "0.11.0"})
    _stub_writable_site(monkeypatch)
    monkeypatch.setattr(au, "_is_editable_install", lambda pkg: pkg == "corekinect")

    sp_run = MagicMock()
    monkeypatch.setattr(au.subprocess, "run", sp_run)
    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert not sp_run.called
    assert not execv.called
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "skipped_editable"


# ────────────────────────────────────────────────────────────────────────
# Failure modes
# ────────────────────────────────────────────────────────────────────────


def test_failsoft_when_pip_install_fails(fake_home, cache_file, monkeypatch, capsys):
    """Non-zero pip exit → yellow warning, swallow, cache the failure."""
    _set_installed_versions(monkeypatch, corectl="0.11.0", corekinect="0.11.0")
    _stub_fetch_latest(monkeypatch, {"corectl": "0.12.0", "corekinect": "0.12.0"})
    _stub_writable_site(monkeypatch)

    pip_result = MagicMock(returncode=1, stdout="", stderr="ERROR: boom")
    monkeypatch.setattr(au.subprocess, "run", MagicMock(return_value=pip_result))

    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    captured = capsys.readouterr()
    assert "failed" in captured.err.lower()
    assert not execv.called
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "failed"


def test_handles_pypi_unreachable_for_either_package(fake_home, cache_file, monkeypatch):
    """PyPI returning None for ONE package → bail entirely (lockstep contract)."""
    _set_installed_versions(monkeypatch, corectl="0.11.0", corekinect="0.11.0")
    # corectl probe succeeds, corekinect probe fails — must NOT upgrade just one.
    _stub_fetch_latest(monkeypatch, {"corectl": "0.12.0", "corekinect": None})
    _stub_writable_site(monkeypatch)

    sp_run = MagicMock()
    monkeypatch.setattr(au.subprocess, "run", sp_run)
    execv = MagicMock()
    monkeypatch.setattr(au.os, "execv", execv)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert not sp_run.called
    assert not execv.called
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "skipped"


def test_handles_pypi_request_exception_gracefully(monkeypatch):
    """``_fetch_latest_version`` itself swallows requests' Exception subclasses."""
    import requests as _requests
    boom = MagicMock(side_effect=_requests.exceptions.ConnectionError("nope"))
    monkeypatch.setattr("requests.get", boom)

    out = au._fetch_latest_version(
        "https://pypi.example/simple/corectl/", "corectl", True
    )
    assert out is None


def test_skips_when_site_packages_readonly(fake_home, cache_file, monkeypatch, capsys):
    """Read-only site-packages → one-time notice, no pip call."""
    _set_installed_versions(monkeypatch, corectl="0.11.0", corekinect="0.11.0")
    _stub_fetch_latest(monkeypatch, {"corectl": "0.12.0", "corekinect": "0.12.0"})
    _stub_writable_site(monkeypatch, writable=False)

    sp_run = MagicMock()
    monkeypatch.setattr(au.subprocess, "run", sp_run)

    au.maybe_auto_upgrade(interactive=True, opt_out=False)

    assert not sp_run.called
    out = capsys.readouterr().err
    assert "outdated" in out.lower()
    assert "writable" in out.lower()
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "skipped"


# ────────────────────────────────────────────────────────────────────────
# Cache shape
# ────────────────────────────────────────────────────────────────────────


def test_writes_throttle_cache(fake_home, cache_file, monkeypatch):
    """A successful no-op writes the four diagnostic fields."""
    _set_installed_versions(monkeypatch, corectl="0.11.0", corekinect="0.11.0")
    _stub_fetch_latest(monkeypatch, {"corectl": "0.11.0", "corekinect": "0.11.0"})
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
    # ``last_seen_latest`` is now a per-package dict, not a bare string.
    assert isinstance(data["last_seen_latest"], dict)
    assert "corectl" in data["last_seen_latest"]
    assert "corekinect" in data["last_seen_latest"]
    assert datetime.fromisoformat(data["last_check_at"]).tzinfo is not None


def test_respects_existing_throttle_cache(fake_home, cache_file, monkeypatch):
    """An existing fresh cache short-circuits — no PyPI call, no pip, no execv."""
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    recent = datetime.now(timezone.utc) - timedelta(minutes=10)
    cache_file.write_text(json.dumps({
        "last_check_at": recent.isoformat(timespec="seconds"),
        "last_seen_latest": {"corectl": "0.12.0", "corekinect": "0.12.0"},
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
    data = json.loads(cache_file.read_text())
    assert data["last_attempt_outcome"] == "failed"


# ────────────────────────────────────────────────────────────────────────
# Internal helpers
# ────────────────────────────────────────────────────────────────────────


def test_semver_tuple_orders_intuitively():
    t = au._semver_tuple
    assert t("0.10.0") < t("0.11.0")
    assert t("0.11.0") < t("0.11.1")
    assert t("0.11.0") < t("1.0.0")
    assert t("0.12.0rc1") == t("0.12.0")


def test_pip_index_url_strips_per_package_path():
    assert au._pip_index_url("https://concord.example.com").endswith("/simple/")
    assert "pypi.concord.example.com" in au._pip_index_url("https://concord.example.com")


def test_pypi_index_url_takes_package_name():
    """``_pypi_index_url`` builds per-package URLs so both managed packages
    can be probed from the same internal index."""
    # The autouse stub replaces the real one in this test module — call
    # the real function directly via importlib to verify its signature.
    import importlib, corectl.auto_upgrade as real_mod
    importlib.reload(real_mod)
    # NOTE: reloading would defeat the autouse stub for this test only.
    # Use the underlying function via getattr on the reloaded module.
    url_corectl = real_mod._pypi_index_url(
        "https://concord.example.com", "corectl"
    )
    url_corekinect = real_mod._pypi_index_url(
        "https://concord.example.com", "corekinect"
    )
    assert url_corectl.endswith("/simple/corectl/")
    assert url_corekinect.endswith("/simple/corekinect/")
    # Reload again so subsequent tests see a clean module — pytest's
    # fixture teardown restores monkeypatch state, but the import cache
    # still holds the reloaded module.
    importlib.reload(real_mod)


def test_parse_iso_accepts_both_string_and_float():
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    assert au._parse_iso(now_iso) is not None
    assert au._parse_iso(1234567890.5) == 1234567890.5
    assert au._parse_iso(None) is None
    assert au._parse_iso("not-a-date") is None


def test_installed_version_returns_module_version_for_corectl(monkeypatch):
    """The ``corectl`` lookup short-circuits to ``__version__`` to avoid
    importlib.metadata overhead on every launch."""
    monkeypatch.setattr(au, "__version__", "0.99.0")
    assert au._installed_version("corectl") == "0.99.0"


def test_installed_version_returns_none_for_uninstalled_package():
    """Asking about a package that isn't installed yields None."""
    assert au._installed_version("this-package-does-not-exist-xyz123") is None
