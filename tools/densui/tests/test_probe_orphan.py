"""The probe must survive a chrome that leaves fd-holding orphans behind.

google-chrome daemonizes a crashpad handler that inherits stdout/stderr.
With pipe capture, subprocess.run() blocks until that orphan dies — chrome
itself already exited — which hung the fleet's geometry job for 8+ minutes
(run 31763912930: MAIN_CHROME_COUNT=0, crashpad holding 2 pipe fds, python
waiting). Debian chromium disables crashpad, so the defect stayed invisible
until the CI image moved to google-chrome.

The fake chrome here reproduces the shape exactly: valid probe output, then
an orphan holding the output fds for 60s, then exit. Under pipe capture the
collect() below takes ~60s and the elapsed assertion fails; with file
capture it returns in well under a second. The 5s/0.0s A/B for the raw
mechanism is recorded in LOG.md (2026-08-14).
"""

import json
import pathlib
import stat
import time

import pytest

from densui import probe


@pytest.fixture()
def fake_chrome(tmp_path, monkeypatch):
    payload = json.dumps({"scale": 1, "containers": [], "parts": []})
    script = tmp_path / "fake-chrome.sh"
    script.write_text(
        "#!/bin/sh\n"
        f"printf '%s' '<pre id=\"densui-probe\">{payload}</pre>'\n"
        "sleep 60 &\n"
        "exit 0\n"
    )
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("DENSUI_CHROME", str(script))
    return script


def test_collect_returns_despite_fd_holding_orphan(fake_chrome, tmp_path):
    page = tmp_path / "page.html"
    page.write_text("<html><body></body></html>")
    t0 = time.monotonic()
    out = probe.collect(page, root="body", containers={}, parts={})
    elapsed = time.monotonic() - t0
    assert out == {"scale": 1, "containers": [], "parts": []}
    assert elapsed < 20, (
        f"collect took {elapsed:.1f}s — an orphan's fds are blocking the "
        "read again (pipe capture regression)"
    )


def test_orphan_free_failure_still_loud(tmp_path, monkeypatch):
    """A chrome that exits without probe output must still raise, fast."""
    script = tmp_path / "silent-chrome.sh"
    script.write_text("#!/bin/sh\nexit 0\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("DENSUI_CHROME", str(script))
    page = tmp_path / "page.html"
    page.write_text("<html><body></body></html>")
    with pytest.raises(probe.ProbeError, match="no output"):
        probe.collect(page, root="body", containers={}, parts={})

def test_chrome_spawning_is_centralized():
    """Every --dump-dom invocation must go through probe.dump_dom.

    The crashpad hang shipped TWICE because a demo build script carried its
    own pipe-captured chrome spawn that the probe.py fix could not reach.
    The hardened runner is only a fix if it is the only runner.
    """
    repo = pathlib.Path(__file__).resolve().parents[3]
    offenders = []
    for f in repo.rglob("*.py"):
        if ".venv" in f.parts or f.name == "probe.py" or f.name == "test_probe_orphan.py":
            continue
        if "dump-dom" in f.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(f.relative_to(repo)))
    assert not offenders, f"direct chrome spawns outside probe.dump_dom: {offenders}"
