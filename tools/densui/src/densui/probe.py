"""densui.probe — render a page headlessly and measure its true geometry.

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
import re
import shutil
import subprocess
import tempfile

_PROBE_JS = (pathlib.Path(__file__).parent / "probe.js").read_text()

_CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
]


class ProbeError(RuntimeError):
    pass


def find_chrome() -> str:
    env = os.environ.get("DENSUI_CHROME")
    if env:
        if pathlib.Path(env).exists():
            return env
        raise ProbeError(f"DENSUI_CHROME={env} does not exist")
    for cand in _CHROME_CANDIDATES:
        if cand.startswith("/"):
            if pathlib.Path(cand).exists():
                return cand
        else:
            hit = shutil.which(cand)
            if hit:
                return hit
    raise ProbeError(
        "no Chrome/Chromium found — the probe cannot run, so it fails; "
        "set DENSUI_CHROME")


def collect(page: str | pathlib.Path, *, root: str, containers: dict[str, str],
            parts: dict[str, str], text_kinds: set[str] | None = None,
            owner_attr: str = "data-addr", root_width: float | None = None,
            window: str = "1600,900", extra_js: str = "") -> dict:
    page = pathlib.Path(page)
    if not page.exists():
        raise ProbeError(f"page not found: {page}")
    cfg = {"root": root, "containers": containers, "parts": parts,
           "textKinds": sorted(text_kinds or []), "ownerAttr": owner_attr,
           "rootWidth": root_width}
    call = f"densuiProbe({json.dumps(cfg)});"
    inject = (f"<script>{extra_js}</script>" if extra_js else "") + \
        "<script>" + _PROBE_JS + "\n" + call + "</script>"
    with tempfile.NamedTemporaryFile("w", suffix=".html", dir=page.parent,
                                     delete=False) as tf:
        tf.write(page.read_text() + inject)
        tmp = pathlib.Path(tf.name)
    try:
        run = subprocess.run(
            [find_chrome(), "--headless=new", "--disable-gpu", "--mute-audio",
             "--no-sandbox", f"--window-size={window}",
             "--virtual-time-budget=6000", "--dump-dom", f"file://{tmp}"],
            capture_output=True, text=True, check=False)
        hits = re.findall(r'<pre id="densui-probe">(.*?)</pre>', run.stdout, re.DOTALL)
        match = hits[-1] if hits else None
        if not match:
            raise ProbeError(
                f"probe produced no output (chrome rc={run.returncode}; "
                f"stderr tail: {run.stderr[-300:]!r})")
        return json.loads(html.unescape(match))
    finally:
        tmp.unlink(missing_ok=True)
