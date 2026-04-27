"""corectl CLI entry point.

Usage feels natural from a project directory:

    cd alpha-validation/
    corectl validate              # validate this project
    corectl upload                # upload this project
    corectl versions              # list published versions
    corectl run smoke             # run smoke tests
    corectl run regression -m health_check  # run health check

Resource-qualified (when outside a project or managing other resources):

    corectl test validate /path/to/project
    corectl test release <package-id>
    corectl auth login
    corectl auth status
"""

import os

import click

from . import __version__
from .config import load_config
from .commands import auth, budgets, runs, test


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="corectl")
@click.option(
    "--insecure",
    is_flag=True,
    default=False,
    help="Skip TLS certificate verification for this run. Sets CONCORD_VERIFY_SSL=false. "
         "Use when the host doesn't trust the Concord internal CA (WSL, foreign network).",
)
@click.pass_context
def main(ctx, insecure):
    """Concord platform CLI — manage validation, fixtures, and manufacturing."""
    if insecure:
        os.environ["CONCORD_VERIFY_SSL"] = "false"
        # Silence the urllib3 InsecureRequestWarning so output stays clean.
        try:
            import urllib3
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        except Exception:
            pass
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config()
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


# ── Resource groups ──
main.add_command(auth.auth)
main.add_command(budgets.budgets)
main.add_command(runs.runs)
main.add_command(test.test)

# ── Shortcuts (work from project root without typing "test") ──
# These are aliases that delegate to the test subcommands
main.add_command(test.validate, "validate")
main.add_command(test.run, "run")
main.add_command(test.upload, "upload")
main.add_command(test.versions, "versions")
main.add_command(test.package, "package")
main.add_command(test.init, "init")
main.add_command(test.release, "release")
main.add_command(test.sync, "sync")


if __name__ == "__main__":
    main()
