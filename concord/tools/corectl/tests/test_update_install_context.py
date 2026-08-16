"""Tests for the install-context detection used by ``corectl update``.

PEP 668 makes a bare ``pip install --user --upgrade corectl`` fail on
externally-managed Python distributions, so ``corectl update`` has to
route through whichever installer the operator chose — ``pipx``, ``uv``,
or a curl-bash fall-back to the install.sh path.

The dedicated helper ``detect_install_context()`` looks at
``sys.executable`` and a few environment variables, classifies the
install, and returns the upgrade command. These tests pin its
behaviour so subsequent install layouts don't silently regress to bare
pip.
"""

from __future__ import annotations

import pytest

from corectl.commands import update as update_mod


def test_detect_pipx_via_pipx_home_env(monkeypatch):
    """PIPX_HOME env var → pipx upgrade."""
    monkeypatch.setattr(update_mod.sys, "executable", "/usr/bin/python3")
    monkeypatch.setenv("PIPX_HOME", "/home/user/.local/pipx")
    monkeypatch.delenv("UV_CACHE_DIR", raising=False)
    assert update_mod.detect_install_context() == "pipx"


def test_detect_pipx_via_pipx_path(monkeypatch):
    """sys.executable inside a pipx venv → pipx upgrade."""
    monkeypatch.setattr(
        update_mod.sys, "executable",
        "/home/user/.local/pipx/venvs/corectl/bin/python",
    )
    monkeypatch.delenv("PIPX_HOME", raising=False)
    monkeypatch.delenv("UV_CACHE_DIR", raising=False)
    assert update_mod.detect_install_context() == "pipx"


def test_detect_uv_via_uv_cache_dir(monkeypatch):
    """UV_CACHE_DIR set → uv tool upgrade."""
    monkeypatch.setattr(update_mod.sys, "executable", "/usr/bin/python3")
    monkeypatch.delenv("PIPX_HOME", raising=False)
    monkeypatch.setenv("UV_CACHE_DIR", "/home/user/.cache/uv")
    assert update_mod.detect_install_context() == "uv"


def test_detect_falls_back_to_pip_for_unknown_layout(monkeypatch):
    """Plain pip install → 'pip' (curl-bash install.sh)."""
    monkeypatch.setattr(update_mod.sys, "executable", "/usr/bin/python3")
    monkeypatch.delenv("PIPX_HOME", raising=False)
    monkeypatch.delenv("UV_CACHE_DIR", raising=False)
    assert update_mod.detect_install_context() == "pip"


def test_upgrade_command_for_pipx_uses_pipx_upgrade():
    assert update_mod.upgrade_command_for("pipx") == "pipx upgrade corectl"


def test_upgrade_command_for_uv_uses_uv_tool_upgrade():
    assert update_mod.upgrade_command_for("uv") == "uv tool upgrade corectl"


def test_upgrade_command_for_pip_uses_install_sh(monkeypatch):
    cmd = update_mod.upgrade_command_for("pip", install_url="https://x.example/install.sh")
    # The fallback runs the same install.sh used by `curl | bash`.
    assert "install.sh" in cmd
    assert "https://x.example/install.sh" in cmd
