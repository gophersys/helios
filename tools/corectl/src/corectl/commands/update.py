"""``corectl update`` — self-upgrade corectl + corekinect from the Concord pypi.

The two ship in lockstep ``major.minor`` (see ``concord-release`` skill), so
upgrading one without the other is always a mistake. This command pins them
together by piping through the same install.sh that the home page advertises:

    curl -fsSL https://<concord-host>/corectl/install.sh | bash

That script lives in ``apps/frontend/app/static/corectl/install.sh`` and is
the single source of truth for what installs land on a user's machine.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from urllib.parse import urlparse

import click

from ..config import get_api_url, load_config


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

    # Prefer the install.sh path so the upgrade flow is identical to a
    # fresh install — single source of truth.
    if not shutil.which("bash"):
        click.echo(
            "Error: bash is required to run the installer.\n"
            f"Manual fallback:\n"
            f"  pip install --user --upgrade --index-url "
            f"{parsed.scheme}://pypi.{parsed.hostname}/simple/ corectl corekinect",
            err=True,
        )
        sys.exit(1)

    cmd = f"curl -fsSL {install_url} | bash"
    if dry_run:
        click.echo(cmd)
        return

    click.echo(f"$ {cmd}")
    rc = subprocess.call(cmd, shell=True)
    sys.exit(rc)
