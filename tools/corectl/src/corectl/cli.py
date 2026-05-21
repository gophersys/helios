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
import sys

import click

from . import __version__
from .config import load_config
from .commands import auth, budgets, runs, test, update as update_cmd


def _argv_opt_out() -> bool:
    """Detect ``--no-auto-upgrade`` / ``--no-version-check`` in argv pre-parse.

    The auto-upgrade path runs *before* Click parses arguments because a
    successful upgrade re-execs the process — if Click parsed first, the
    subcommand would already be dispatched. We mirror Click's own
    boolean-flag matching here for the handful of opt-out flags.
    """
    for tok in sys.argv[1:]:
        if tok in ("--no-auto-upgrade", "--no-version-check"):
            return True
    return False


# Run the upgrade attempt before Click does anything else. The function
# is fail-soft — any error path returns silently, the original command
# continues unchanged. On a successful upgrade it ``os.execv``s and
# never returns.
try:
    from .auto_upgrade import maybe_auto_upgrade as _maybe_auto_upgrade

    _maybe_auto_upgrade(
        interactive=sys.stdin.isatty(),
        opt_out=(
            os.environ.get("CONCORD_NO_AUTO_UPGRADE") == "1"
            or _argv_opt_out()
        ),
    )
except Exception:
    pass


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name="corectl")
@click.option(
    "--insecure",
    is_flag=True,
    default=False,
    help="Skip TLS certificate verification for this run. Sets CONCORD_VERIFY_SSL=false. "
         "Use when the host doesn't trust the Concord internal CA (WSL, foreign network).",
)
@click.option(
    "--no-version-check",
    is_flag=True,
    default=False,
    envvar="CORECTL_SKIP_VERSION_CHECK",
    help="Skip the daily upgrade-availability check on internal pypi.",
)
@click.option(
    "--no-auto-upgrade",
    is_flag=True,
    default=False,
    envvar="CONCORD_NO_AUTO_UPGRADE",
    help="Skip the in-place self-upgrade on launch. Implied by --no-version-check. "
         "Auto-upgrade is throttled to once per 6h and never runs in non-interactive "
         "shells regardless of this flag.",
)
@click.pass_context
def main(ctx, insecure, no_version_check, no_auto_upgrade):
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

    # Best-effort upgrade-available notice. Cached 24h on disk; errors
    # never block the command. Skipped via --no-version-check or
    # CORECTL_SKIP_VERSION_CHECK=1 so CI runs stay quiet. The notice is
    # the courtesy "you should upgrade" hint — the real auto-upgrade
    # ran before Click parsed argv (see top of this file).
    if not no_version_check:
        try:
            from .config import get_api_url, get_tls_verify
            from .version_check import maybe_print_upgrade_notice
            maybe_print_upgrade_notice(
                api_url=get_api_url(ctx.obj["config"]),
                verify=get_tls_verify(ctx.obj["config"]),
            )
        except Exception:
            pass

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
main.add_command(test.claim, "claim")
main.add_command(test.unclaim, "unclaim")
main.add_command(test.status, "status")
main.add_command(update_cmd.update, "update")


if __name__ == "__main__":
    main()
