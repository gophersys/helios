"""corectl auth — authentication commands.

Usage:
    corectl auth login --url http://localhost:9001 --token ck_ci_admin_...
    corectl auth status
    corectl auth logout
"""

import click

from ..config import get_api_url, get_api_token, save_config
from ..api import ConcordAPI


@click.group()
def auth():
    """Manage authentication with Concord API."""
    pass


@auth.command()
@click.option("--url", prompt="Concord API URL", default="http://localhost:9001",
              help="Concord HTTP API base URL")
@click.option("--token", prompt="API Token", hide_input=True,
              help="Concord API key (ck_ci_admin_... or ck_run_...)")
@click.pass_context
def login(ctx, url: str, token: str):
    """Authenticate with a Concord API instance."""
    # Verify the token works
    api = ConcordAPI(url, token)
    if not api.health_check():
        click.echo(f"Cannot reach Concord API at {url}", err=True)
        raise SystemExit(1)

    # Save to config
    config = ctx.obj["config"]
    config["api_url"] = url
    config["api_token"] = token
    save_config(config)

    click.echo(f"Authenticated with {url}")


@auth.command()
@click.pass_context
def status(ctx):
    """Show current authentication status."""
    config = ctx.obj["config"]
    url = get_api_url(config)
    token = get_api_token(config)

    if not token:
        click.echo("Not authenticated. Run: corectl auth login")
        return

    api = ConcordAPI(url, token)
    reachable = api.health_check()

    click.echo(f"API URL:  {url}")
    click.echo(f"Token:    {token[:15]}...")
    click.echo(f"Status:   {'Connected' if reachable else 'Unreachable'}")


@auth.command()
@click.pass_context
def logout(ctx):
    """Clear stored authentication."""
    config = ctx.obj["config"]
    config.pop("api_token", None)
    save_config(config)
    click.echo("Logged out")
