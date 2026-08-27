"""``corectl update`` — self-upgrade corectl + corekinect from the Concord pypi.

The two ship in lockstep ``major.minor`` (see ``concord-release`` skill), so
upgrading one without the other is always a mistake. This command pins them
together by piping through the same install.sh that the home page advertises:

    curl -fsSL https://<concord-host>/corectl/install.sh | bash

That script lives in ``apps/frontend/app/static/corectl/install.sh`` and is
the single source of truth for what installs land on a user's machine.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Literal
from urllib.parse import urlparse

import click

from ..config import get_api_url, load_config


InstallContext = Literal["pipx", "uv", "pip"]


def detect_install_context() -> InstallContext:
    """Classify how the current corectl was installed.

    Honours PEP 668 by routing pipx / uv installs to their own
    upgrade flows instead of a bare ``pip install --user --upgrade``
    that fails on externally-managed Python distributions.

    Returns one of ``"pipx"``, ``"uv"``, or ``"pip"``. The bare-pip
    case lands on the curl-bash install.sh path, which is itself
    expected to thread the right flags through to the runtime
    installer (--user, --break-system-packages, etc.).
    """
    exe = (sys.executable or "").lower()
    if "/pipx/" in exe or "pipx/venvs" in exe or os.environ.get("PIPX_HOME"):
        return "pipx"
    if "/uv/" in exe or os.environ.get("UV_CACHE_DIR") or os.environ.get("UV_TOOL_DIR"):
        return "uv"
    return "pip"


def upgrade_command_for(context: InstallContext, *, install_url: str = "") -> str:
    """Return the shell command appropriate for ``context``.

    For ``pipx`` / ``uv`` this is a one-shot tool-upgrade. For ``pip``
    it falls back to the curl-bash install.sh — the install script is
    the single source of truth for what a fresh install looks like,
    and we want the upgrade flow to land in the same place.
    """
    if context == "pipx":
        return "pipx upgrade corectl"
    if context == "uv":
        return "uv tool upgrade corectl"
    if install_url:
        return f"curl -fsSL {install_url} | bash"
    return "pip install --user --upgrade corectl corekinect"


@click.command()
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Print the install command without running it.",
)
def update(dry_run: bool) -> None:
    """Upgrade corectl + corekinect to the latest published lockstep version."""
    config = load_config()
    api_url = get_api_url(config)
    if not api_url:
        click.echo(
            "Error: no api_url configured. Run `corectl auth login --url <url>` first.",
            err=True,
        )
        sys.exit(1)

    parsed = urlparse(api_url)
    if not parsed.scheme or not parsed.hostname:
        click.echo(f"Error: malformed api_url: {api_url!r}", err=True)
        sys.exit(1)

    install_url = f"{parsed.scheme}://{parsed.hostname}/corectl/install.sh"

    # Honour PEP 668: route pipx / uv installs through their own tool
    # commands instead of a bare pip that would fail on externally-
    # managed Python. The install.sh fallback is the single source of
    # truth for fresh installs, so the pip context lands there too.
    context = detect_install_context()
    if context == "pip" and not shutil.which("bash"):
        click.echo(
            "Error: bash is required to run the installer.\n"
            f"Manual fallback:\n"
            f"  pip install --user --upgrade --index-url "
            f"{parsed.scheme}://pypi.{parsed.hostname}/simple/ corectl corekinect",
            err=True,
        )
        sys.exit(1)

    cmd = upgrade_command_for(context, install_url=install_url)
    if dry_run:
        click.echo(cmd)
        return

    click.echo(f"# install context: {context}")
    click.echo(f"$ {cmd}")
    rc = subprocess.call(cmd, shell=True)

    # For pipx / uv, the wheel comes from the public PyPI index by
    # default — operators who serve a private corekinect wheel
    # alongside corectl need to inject it. We can't do that for them
    # here, but we leave a breadcrumb so the next operator who hits a
    # version mismatch finds the answer.
    if rc == 0 and context in ("pipx", "uv"):
        click.echo(
            f"\nNote: {context} upgraded corectl. If corekinect lockstep is required, "
            f"run `{context} inject corectl corekinect` (pipx) or "
            f"reinstall via `{cmd}` after publishing the matching wheel."
        )
    sys.exit(rc)
