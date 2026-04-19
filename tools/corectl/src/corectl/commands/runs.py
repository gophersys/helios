"""corectl runs — inspect test runs from the command line.

The Concord web UI is the canonical place to watch a run, but the
common operator workflow — "is my last panel green?" / "how long did
the last 5 Alpha runs take?" — doesn't need a browser. These commands
read the HTTP API and print the same data in a terminal-friendly
shape.

Commands
--------

``corectl runs list``
    Last N runs (default 10), newest first.

``corectl runs show <run-id>``
    Full run detail: status, counts, duration, per-target breakdown.

``corectl runs watch <run-id>``
    Poll until the run terminates; print a single re-rendered status
    line every few seconds. Exits non-zero if the run ends FAILED.

All commands talk to the HTTP API using the operator's saved auth
(``corectl auth login``). No direct DB access.
"""

from __future__ import annotations

import sys
import time
from typing import Any, Dict, List, Optional

import click

from ..api import ConcordAPI
from ..config import get_api_url, require_auth


# ────────────────────────────────────────────────────────────────────────
# Low-level API calls
# ────────────────────────────────────────────────────────────────────────


def _client(ctx: click.Context) -> ConcordAPI:
    config = ctx.obj["config"]
    token = require_auth(config)
    return ConcordAPI(get_api_url(config), token)


_ENVELOPE_KEYS = {"data", "errors", "pagination", "meta"}


def _unwrap(body: Any) -> Any:
    """Flatten the API's nested ``{"data": {"data": [...]}}`` envelope.

    List endpoints wrap an extra ``data: {data: [...], pagination: {}}``
    around the payload; detail endpoints use a single ``data: {...}``.
    The outermost envelope also carries an ``errors`` key. Keep peeling
    as long as the only keys we see are envelope bookkeeping.
    """
    while (
        isinstance(body, dict)
        and "data" in body
        and set(body.keys()) <= _ENVELOPE_KEYS
    ):
        body = body["data"]
    return body


def _fetch_runs(api: ConcordAPI, *, limit: int, status: Optional[str]) -> List[Dict[str, Any]]:
    params = {"limit": str(limit)}
    if status:
        params["status"] = status.upper()
    resp = api.get("/v2/runs", params=params)
    resp.raise_for_status()
    payload = _unwrap(resp.json())
    return payload if isinstance(payload, list) else []


def _fetch_run(api: ConcordAPI, run_id: str) -> Dict[str, Any]:
    resp = api.get(f"/v2/runs/{run_id}")
    if resp.status_code == 404:
        raise click.ClickException(f"run {run_id} not found")
    resp.raise_for_status()
    return _unwrap(resp.json())


# ────────────────────────────────────────────────────────────────────────
# Formatting
# ────────────────────────────────────────────────────────────────────────


_STATUS_COLOR = {
    "PASSED":    "green",
    "COMPLETED": "green",
    "FAILED":    "red",
    "ERROR":     "red",
    "CANCELLED": "yellow",
    "ACTIVE":    "cyan",
    "PENDING":   "blue",
    "SKIPPED":   "white",
}


def _paint(status: str) -> str:
    return click.style(status, fg=_STATUS_COLOR.get(status.upper(), "white"))


def _fmt_duration(ms: Optional[int]) -> str:
    if ms is None:
        return "—"
    if ms < 1000:
        return f"{ms}ms"
    s = ms / 1000.0
    if s < 60:
        return f"{s:.1f}s"
    m, s = divmod(s, 60)
    return f"{int(m)}m{int(s):02d}s"


def _fmt_row(run: Dict[str, Any]) -> str:
    rid = run.get("id", "—")
    status = run.get("status", "—")
    total = run.get("targetCount", 0)
    passed = run.get("passedCount", 0)
    failed = run.get("failedCount", 0)
    dur = _fmt_duration(run.get("durationMs"))
    panel = run.get("panelIdentifier") or "—"
    return (
        f"{rid:<28} {_paint(status):<18} "
        f"p={passed:>2} f={failed:>2} /{total:<2} "
        f"dur={dur:<8} panel={panel}"
    )


# ────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────


@click.group()
def runs() -> None:
    """Inspect manufacturing / validation test runs."""


@runs.command("list")
@click.option("--limit", default=10, show_default=True, type=int, help="Max rows")
@click.option("--status", default=None, help="Filter by status (ACTIVE, COMPLETED, FAILED…)")
@click.pass_context
def runs_list(ctx: click.Context, limit: int, status: Optional[str]) -> None:
    """List recent runs (newest first)."""
    api = _client(ctx)
    rows = _fetch_runs(api, limit=limit, status=status)
    if not rows:
        click.echo("No runs matched.")
        return
    for r in rows:
        click.echo(_fmt_row(r))


@runs.command("show")
@click.argument("run_id")
@click.pass_context
def runs_show(ctx: click.Context, run_id: str) -> None:
    """Show a single run in detail, including per-target status."""
    api = _client(ctx)
    run = _fetch_run(api, run_id)

    click.echo(click.style(f"Run {run.get('id')}", bold=True))
    click.echo(f"  Status:    {_paint(run.get('status', '—'))}")
    click.echo(f"  Panel:     {run.get('panelIdentifier') or '—'}")
    click.echo(f"  Duration:  {_fmt_duration(run.get('durationMs'))}")
    click.echo(
        f"  Totals:    "
        f"targets={run.get('targetCount', 0)} "
        f"passed={run.get('passedCount', 0)} "
        f"failed={run.get('failedCount', 0)} "
        f"done={run.get('completedCount', 0)}"
    )
    targets = run.get("targets") or []
    if targets:
        click.echo()
        click.echo(click.style("Targets:", bold=True))
        for t in targets:
            snr = t.get("serialNumber") or "?"
            st = t.get("status", "—")
            tp = t.get("passedCount", 0)
            tf = t.get("failedCount", 0)
            td = _fmt_duration(t.get("durationMs"))
            click.echo(
                f"  slot{t.get('slotIndex', '?'):<2} "
                f"{snr:<8} {_paint(st):<18} "
                f"p={tp:>2} f={tf:>2} dur={td}"
            )


@runs.command("cancel")
@click.argument("run_id")
@click.option("--yes", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def runs_cancel(ctx: click.Context, run_id: str, yes: bool) -> None:
    """Cancel an in-flight run.

    A stuck ACTIVE run blocks its fixture and confuses dashboards; this
    calls the backend's cancel endpoint so the runner pod gets torn
    down and the DB row transitions to CANCELLED. Fails loudly if the
    run is already terminal.
    """
    api = _client(ctx)
    run = _fetch_run(api, run_id)
    status = (run.get("status") or "").upper()
    if status in {"COMPLETED", "FAILED", "CANCELLED", "ERROR"}:
        click.echo(f"run {run_id} is already {status}; nothing to cancel.")
        return
    if not yes:
        click.confirm(
            f"Cancel run {run_id} ({_paint(status)})?",
            abort=True,
        )
    resp = api.post(f"/v2/runs/{run_id}/cancel")
    if resp.status_code >= 400:
        raise click.ClickException(
            f"cancel failed: HTTP {resp.status_code} {resp.text[:200]}"
        )
    click.echo(f"run {run_id} → CANCELLED")


@runs.command("watch")
@click.argument("run_id")
@click.option("--interval", default=5, show_default=True, type=float, help="Poll interval (s)")
@click.option("--timeout", default=1800, show_default=True, type=int, help="Give up after N seconds")
@click.pass_context
def runs_watch(ctx: click.Context, run_id: str, interval: float, timeout: int) -> None:
    """Poll a run until it terminates; exit non-zero on FAILED/ERROR/CANCELLED."""
    api = _client(ctx)
    deadline = time.monotonic() + timeout
    last_line = ""
    while time.monotonic() < deadline:
        run = _fetch_run(api, run_id)
        status = (run.get("status") or "").upper()
        done = run.get("completedCount", 0)
        total = run.get("targetCount", 0)
        passed = run.get("passedCount", 0)
        failed = run.get("failedCount", 0)
        dur = _fmt_duration(run.get("durationMs"))
        line = (
            f"[{_paint(status)}] targets {done}/{total}  "
            f"passed={passed} failed={failed}  dur={dur}"
        )
        if line != last_line:
            click.echo(line)
            last_line = line
        if status in ("COMPLETED", "FAILED", "CANCELLED", "ERROR"):
            if status in ("FAILED", "ERROR", "CANCELLED"):
                sys.exit(1)
            return
        time.sleep(interval)
    raise click.ClickException(f"run {run_id} did not terminate within {timeout}s")
