"""``corectl auth`` — login / status / logout for the CLI session.

Login is a Claude-Code-style device-code flow: the CLI requests a short
user code, prints a verification URL, and polls until a human approves
the session in the browser. No more pasting API keys.

Service-account auth (CI runners, build servers) lives elsewhere — pass
``CONCORD_API_KEY`` in the environment or use ``--service-account`` on
the command directly. There is no human-facing API-key paste path.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Optional

import click
import requests

from ..config import (
    DEFAULT_API_URL,
    clear_session,
    get_api_url,
    get_session,
    get_tls_verify,
    save_config,
    store_session,
)


@click.group()
def auth():
    """Manage your corectl session."""


# ─── login ─────────────────────────────────────────────────────────────


@auth.command()
@click.option(
    "--url",
    default=None,
    help=(
        "Concord API URL. Defaults to $CONCORD_API_URL → saved config → "
        f"{DEFAULT_API_URL}."
    ),
)
@click.option(
    "--no-browser",
    is_flag=True,
    help="Don't try to open the browser automatically.",
)
@click.pass_context
def login(ctx, url: Optional[str], no_browser: bool):
    """Authenticate by approving a session in your browser."""
    config = ctx.obj["config"]

    # If --url was passed, persist it now so subsequent reads (and the
    # poll loop below) all see the same backend.
    if url:
        config["api_url"] = url.rstrip("/")
        save_config(config)
    base_url = get_api_url(config)
    tls = get_tls_verify(config)

    # ── Step 1: ask the backend for a code pair.
    try:
        resp = requests.post(
            f"{base_url}/v2/auth/session/code",
            json={},
            headers={
                "Content-Type": "application/json",
                "User-Agent": _user_agent(),
            },
            timeout=10,
            verify=tls,
        )
    except requests.RequestException as e:
        click.echo(f"Cannot reach Concord at {base_url}: {e}", err=True)
        raise SystemExit(1)

    if resp.status_code != 201:
        click.echo(f"Failed to start login ({resp.status_code}): {resp.text[:200]}", err=True)
        raise SystemExit(1)

    data = (resp.json().get("data") or {})
    user_code = data["user_code"]
    device_code = data["device_code"]
    verify_uri = data["verification_uri"]
    interval = max(1, int(data.get("interval", 5)))
    expires_in = int(data.get("expires_in", 600))

    click.echo("")
    click.echo(f"  Open: {verify_uri}")
    click.echo(f"  Code: {user_code}")
    click.echo("")
    click.echo(f"Waiting for approval (expires in {expires_in // 60} min)…")

    if not no_browser:
        _try_open_browser(verify_uri)

    # ── Step 2: poll until approved/denied/expired.
    deadline = time.monotonic() + expires_in
    while time.monotonic() < deadline:
        time.sleep(interval)
        try:
            poll = requests.post(
                f"{base_url}/v2/auth/session/poll",
                json={"device_code": device_code},
                headers={"Content-Type": "application/json"},
                timeout=10,
                verify=tls,
            )
        except requests.RequestException as e:
            click.echo(f"\nNetwork error while polling: {e}", err=True)
            raise SystemExit(1)

        if poll.status_code != 200:
            click.echo(f"\nPoll failed ({poll.status_code}): {poll.text[:200]}", err=True)
            raise SystemExit(1)

        body = (poll.json().get("data") or {})

        if body.get("status") == "pending":
            continue
        if body.get("status") == "slow_down":
            interval += 5
            continue
        if body.get("status") in ("expired", "denied"):
            click.echo(f"\nLogin {body['status']}. Run `corectl auth login` to try again.", err=True)
            raise SystemExit(1)
        if "access_token" in body:
            # Approved! Persist + greet.
            from datetime import timedelta as _td
            exp = datetime.now(timezone.utc) + _td(seconds=int(body.get("expires_in", 0)))
            store_session(
                config,
                access_token=body["access_token"],
                refresh_token=body["refresh_token"],
                expires_at=exp.isoformat(),
                user_email=_extract_email(body["access_token"]),
            )
            email = config.get("user_email") or "your account"
            click.echo(f"\nAuthenticated as {email}")
            return

    click.echo("\nLogin timed out waiting for approval.", err=True)
    raise SystemExit(1)


# ─── status ────────────────────────────────────────────────────────────


@auth.command()
@click.pass_context
def status(ctx):
    """Show the active session — who you are, where you point, when it expires."""
    config = ctx.obj["config"]
    base_url = get_api_url(config)
    session = get_session(config)

    click.echo(f"API URL:  {base_url}")

    if not session:
        click.echo("Status:   not authenticated  (run: corectl auth login)")
        return

    click.echo(f"Email:    {session.get('user_email') or 'unknown'}")
    exp = session.get("expires_at")
    if exp:
        try:
            exp_dt = datetime.fromisoformat(exp)
            remaining = exp_dt - datetime.now(timezone.utc)
            mins = int(remaining.total_seconds() // 60)
            click.echo(f"Token:    expires in {mins} min" if mins > 0 else "Token:    expired (will auto-refresh)")
        except ValueError:
            click.echo(f"Token:    expires {exp}")
    click.echo("Refresh:  present (rotates on next API call)")


# ─── logout ────────────────────────────────────────────────────────────


@auth.command()
@click.pass_context
def logout(ctx):
    """Revoke the local session and forget the tokens."""
    config = ctx.obj["config"]
    session = get_session(config)
    if not session:
        click.echo("Already logged out.")
        return

    base_url = get_api_url(config)
    tls = get_tls_verify(config)
    try:
        requests.post(
            f"{base_url}/v2/auth/session/revoke",
            json={"refresh_token": session["refresh_token"]},
            headers={"Content-Type": "application/json"},
            timeout=10,
            verify=tls,
        )
    except requests.RequestException:
        # Best-effort. If the backend is unreachable we still wipe local
        # state so the credentials aren't sitting on disk.
        pass

    clear_session(config)
    click.echo("Logged out.")


# ─── helpers ───────────────────────────────────────────────────────────


def _try_open_browser(uri: str) -> None:
    """Open the verification URI in the user's default browser, silently."""
    try:
        import webbrowser
        webbrowser.open(uri)
    except Exception:
        pass


def _user_agent() -> str:
    """Identify the CLI to the backend so the approval UI can show it.

    Uses the package version when available so server-side audit logs
    can correlate "approved corectl 1.4.2" with a release.
    """
    try:
        from .. import __version__
    except ImportError:
        __version__ = "unknown"
    import platform
    return f"corectl/{__version__} ({platform.system().lower()})"


def _extract_email(access_token: str) -> Optional[str]:
    """Best-effort: pull the ``email`` claim out of the JWT for display.

    We don't validate the signature here — this is purely for the
    "Authenticated as alice@…" line. If decoding fails, the status
    command falls back to "unknown".
    """
    try:
        import base64
        import json
        # JWT = header.payload.signature; payload is base64url JSON.
        parts = access_token.split(".")
        if len(parts) < 2:
            return None
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload).decode("utf-8"))
        return claims.get("email")
    except Exception:
        return None
