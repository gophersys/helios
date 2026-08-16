"""ui.probe — render a page headlessly and measure its true geometry.

collect() returns {"scale", "containers": [{id, r}], "parts": [{c, kind,
owner, r}]} with rects (x0, y0, x1, y1) in root-relative CSS px. Text kinds
are measured as glyph ink. Fail-loud throughout: a missing Chrome, root, or
probe output raises — a measurement that cannot run is a failure, not a pass.
"""

from __future__ import annotations

import html
import json
import os
import pathlib
import shutil
import tempfile

_PROBE_JS = (pathlib.Path(__file__).parent / "probe.js").read_text()

_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome",
    "google-chrome-stable",
    "chromium",
    "chromium-browser",
]


class ProbeError(RuntimeError):
    pass


def find_chrome() -> str:
    env = os.environ.get("UI_CHROME")
    if env:
        if pathlib.Path(env).exists():
            return env
        raise ProbeError(f"UI_CHROME={env} does not exist")
    for cand in _CHROME_CANDIDATES:
        if cand.startswith("/"):
            if pathlib.Path(cand).exists():
                return cand
        else:
            hit = shutil.which(cand)
            if hit:
                return hit
    raise ProbeError(
        "no Chrome/Chromium found — the probe cannot run, so it fails; set UI_CHROME"
    )


def collect(
    page: str | pathlib.Path,
    *,
    root: str,
    containers: dict[str, str],
    parts: dict[str, str],
    text_kinds: set[str] | None = None,
    owner_attr: str = "data-addr",
    root_width: float | None = None,
    window: str = "1600,900",
    extra_js: str = "",
) -> dict:
    page = pathlib.Path(page)
    if not page.exists():
        raise ProbeError(f"page not found: {page}")
    cfg = {
        "root": root,
        "containers": containers,
        "parts": parts,
        "textKinds": sorted(text_kinds or []),
        "ownerAttr": owner_attr,
        "rootWidth": root_width,
    }
    call = f"uiProbe({json.dumps(cfg)});"
    inject = (
        (f"<script>{extra_js}</script>" if extra_js else "")
        + "<script>"
        + _PROBE_JS
        + "\n"
        + call
        + "</script>"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=page.parent, delete=False) as tf:
        tf.write(page.read_text() + inject)
        tmp = pathlib.Path(tf.name)
    try:
        return json.loads(wait_for_pre(tmp, "ui-probe", window=window))
    finally:
        tmp.unlink(missing_ok=True)


def wait_for_pre(
    page: str | pathlib.Path,
    pre_id: str,
    *,
    window: str = "1600,900",
    deadline_ms: int = 30000,
) -> str:
    """Return the textContent of <pre id=pre_id> once the page inserts it.

    THE ONLY sanctioned way to run chrome for a measurement — a test pins
    that nothing else spawns it. Measurement pages signal completion by
    inserting a <pre>; this asks the page for it over CDP (drive.run_scenario
    launches chrome with output on DEVNULL and kills it afterwards) and WE
    own the deadline. Its predecessor (chrome's DOM-dump mode) depended on chrome's
    quiescence heuristics and, on the fleet with font-heavy pages, hung
    twice (no exit in 400s) and SIGABRTed once — three failure shapes, one
    cause: chrome deciding when measurement ends. Now it never decides
    anything: no pipes to hold (crashpad's orphan trick is moot), no
    quiescence wait, and the browser dies in run_scenario's finally.
    """
    from ui.drive import DriveError, run_scenario

    try:
        results = run_scenario(
            page,
            [{"op": "wait_pre", "id": pre_id, "deadlineMs": deadline_ms}],
            window=window,
            timeout_s=deadline_ms / 1000 + 15,
        )
    except DriveError as exc:
        raise ProbeError(f"probe produced no output: {exc}") from exc
    return html.unescape(results[0])
