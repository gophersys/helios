"""corectl budgets — data-driven ``@pytest.mark.timeout`` budgets.

Every manufacturing / validation test in a Concord package should
declare an explicit ``@pytest.mark.timeout(N)`` marker. Choosing ``N``
by gut is error-prone: set it too tight and good runs flake, too loose
and a single hung slot drags the whole panel's wall clock.

``corectl budgets suggest`` pulls the last ``--runs`` executions of a
product's stage from the HTTP API, groups the per-test durations
across every slot, and emits a table plus drop-in decorator lines
using a simple budget rule: ``ceil(max + 5, 5)`` — the observed
maximum rounded up to the next 5-second boundary with a 5-second
safety margin.

Example
-------

::

    $ corectl budgets suggest --product alpha --stage fw_flash --runs 50

    test_01_power_on                          n=40 p50=4.2s p95=5.8s max=6.1s → @pytest.mark.timeout(15)
    test_02_flash_app                         n=40 p50=42.1s p95=51.9s max=54.3s → @pytest.mark.timeout(60)
    ...

    Tip: paste the suggested markers above the test functions and
    re-run ``corectl test validate`` to confirm.

The suggestions are intentionally conservative — they match the
format used throughout ``apps/manufacturing/alpha/tests/`` so the
reader can copy them verbatim.
"""

from __future__ import annotations

import math
import re
from collections import defaultdict
from statistics import median
from typing import Any, Dict, Iterable, List, Optional, Tuple

import click

from ..api import AuthError, ConcordAPI
from ..config import get_service_account_key, save_config
from .runs import _unwrap  # same envelope peeler used by `corectl runs`


# ────────────────────────────────────────────────────────────────────────
# Budget rule
# ────────────────────────────────────────────────────────────────────────


_MARGIN_S = 5.0
_ROUND_S = 5.0
_MIN_BUDGET_S = 10.0


def _suggest_budget_s(max_ms: float) -> int:
    """Round ``max_ms + 5s`` up to the next 5-second boundary.

    Mirrors the hand-authored budgets used across the Alpha tests. A
    hard floor of 10 s covers trivially fast tests whose ``max`` is a
    handful of milliseconds — we don't want a 5 s ceiling there.
    """
    max_s = max_ms / 1000.0
    target = max(max_s + _MARGIN_S, _MIN_BUDGET_S)
    return int(math.ceil(target / _ROUND_S) * _ROUND_S)


def _percentile(values: List[float], q: float) -> float:
    """Nearest-rank percentile. Returns 0.0 on empty input."""
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(math.ceil(q * len(ordered))) - 1))
    return ordered[idx]


_SLOT_PARAM_RE = re.compile(r"\[slot-\d+\]$")


def _strip_slot_suffix(test_name: str) -> str:
    """``test_01_boot[slot-3]`` → ``test_01_boot``.

    Parametrised test names carry a trailing ``[slot-N]`` under the
    parallel runner; the suggested budget is the same for all slots
    so we group across them.
    """
    return _SLOT_PARAM_RE.sub("", test_name or "")


# ────────────────────────────────────────────────────────────────────────
# API glue
# ────────────────────────────────────────────────────────────────────────


def _client(ctx: click.Context) -> ConcordAPI:
    config = ctx.obj["config"]
    try:
        return ConcordAPI.from_config(
            config,
            save_callback=save_config,
            service_account_key=get_service_account_key(config),
        )
    except AuthError as e:
        click.echo(str(e), err=True)
        raise SystemExit(1)


def _fetch_product_runs(
    api: ConcordAPI,
    *,
    product_slug: str,
    limit: int,
) -> List[Dict[str, Any]]:
    """Return up to ``limit`` recent runs for the given product slug.

    The HTTP API accepts ``productSlug`` as a filter; we ask for all
    terminal states (PASSED, FAILED) because both produce useful
    timing data — a FAILED run still measures real hardware latency
    for the tests that did execute.
    """
    resp = api.get(
        "/v2/runs",
        params={
            "productSlug": product_slug,
            "limit": str(limit),
        },
    )
    resp.raise_for_status()
    payload = _unwrap(resp.json())
    return payload if isinstance(payload, list) else []


def _fetch_run_detail(api: ConcordAPI, run_id: str) -> Dict[str, Any]:
    resp = api.get(f"/v2/runs/{run_id}")
    resp.raise_for_status()
    return _unwrap(resp.json())


# ────────────────────────────────────────────────────────────────────────
# Aggregation
# ────────────────────────────────────────────────────────────────────────


def _collect_durations(
    run_details: Iterable[Dict[str, Any]],
    *,
    module_prefix: Optional[str],
) -> Dict[str, List[float]]:
    """Group test-execution durations by test name (slot suffix stripped).

    Only PASSED / FAILED executions are counted — ERROR and SKIPPED
    durations don't reflect real runtime of the test body. If
    ``module_prefix`` is given, only executions whose module matches
    are kept (lets the caller scope suggestions to one stage).
    """
    buckets: Dict[str, List[float]] = defaultdict(list)
    for run in run_details:
        for target in run.get("targets") or []:
            for execution in target.get("executions") or []:
                if module_prefix and execution.get("module") != module_prefix:
                    continue
                status = (execution.get("status") or "").upper()
                if status not in {"PASSED", "FAILED"}:
                    continue
                duration = execution.get("durationMs")
                if not isinstance(duration, (int, float)) or duration <= 0:
                    continue
                name = _strip_slot_suffix(execution.get("name") or "")
                if name:
                    buckets[name].append(float(duration))
    return buckets


def _resolve_stage_module(
    api: ConcordAPI, product_slug: str, stage_name: str,
) -> Optional[str]:
    """Look up the module filename for ``stage_name`` from the product's manifest.

    Returns the bare module (e.g. ``test_01_electrical``) or ``None``
    when the lookup fails. The caller can still suggest budgets
    across every stage by omitting the filter.
    """
    resp = api.get(f"/v2/products/slug/{product_slug}/test-packages")
    if resp.status_code != 200:
        return None
    payload = _unwrap(resp.json())
    packages = payload if isinstance(payload, list) else []
    for pkg in packages:
        manifest = pkg.get("manifest") or {}
        stages = manifest.get("stages") or {}
        cfg = stages.get(stage_name)
        if isinstance(cfg, dict) and cfg.get("module"):
            return cfg["module"]
    return None


# ────────────────────────────────────────────────────────────────────────
# CLI
# ────────────────────────────────────────────────────────────────────────


@click.group()
def budgets() -> None:
    """Suggest ``@pytest.mark.timeout`` budgets from real run data."""


@budgets.command("suggest")
@click.option("--product", required=True, help="Product slug (e.g. alpha)")
@click.option("--stage", default=None, help="Restrict to one stage (e.g. fw_flash)")
@click.option("--runs", "run_limit", default=30, show_default=True, type=int,
              help="How many recent runs to scan")
@click.option("--module", "module_override", default=None,
              help="Override stage→module lookup (e.g. test_01_electrical)")
@click.pass_context
def budgets_suggest(
    ctx: click.Context,
    product: str,
    stage: Optional[str],
    run_limit: int,
    module_override: Optional[str],
) -> None:
    """Print suggested per-test timeout budgets from recent runs."""
    api = _client(ctx)

    module_filter: Optional[str] = module_override
    if stage and not module_filter:
        module_filter = _resolve_stage_module(api, product, stage)
        if not module_filter:
            click.echo(click.style(
                f"warning: couldn't resolve stage {stage!r} → module from "
                f"the product's manifest; suggestions will span every "
                f"stage. Pass --module to restrict manually.",
                fg="yellow",
            ), err=True)

    summary_runs = _fetch_product_runs(api, product_slug=product, limit=run_limit)
    if not summary_runs:
        raise click.ClickException(f"No runs found for product {product!r}")

    run_details: List[Dict[str, Any]] = []
    with click.progressbar(summary_runs, label="Fetching run details") as bar:
        for summary in bar:
            rid = summary.get("id")
            if rid:
                run_details.append(_fetch_run_detail(api, rid))

    buckets = _collect_durations(run_details, module_prefix=module_filter)
    if not buckets:
        raise click.ClickException(
            "No PASSED/FAILED executions in the scanned runs — "
            "can't suggest budgets. Try a larger --runs value "
            "or drop --stage to widen the filter."
        )

    click.echo()
    header = f"{'test':<42} {'n':>3}  {'p50':>6}  {'p95':>6}  {'max':>6}   suggestion"
    click.echo(click.style(header, bold=True))
    click.echo("-" * len(header))

    for name in sorted(buckets):
        values = buckets[name]
        p50 = median(values)
        p95 = _percentile(values, 0.95)
        mx = max(values)
        budget = _suggest_budget_s(mx)
        click.echo(
            f"{name:<42} {len(values):>3}  "
            f"{p50/1000:>5.1f}s  {p95/1000:>5.1f}s  {mx/1000:>5.1f}s   "
            f"@pytest.mark.timeout({budget})  "
            f"# observed p95={p95/1000:.0f}s, max={mx/1000:.0f}s"
        )

    click.echo()
    click.echo(click.style(
        "Rule: budget = ceil(max + 5 s, 5 s), floor = 10 s.",
        dim=True,
    ))
