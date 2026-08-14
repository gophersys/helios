"""The probe's chrome runner: CDP wait-for-pre, deadline-loud, centralized.

History, because each rule here was paid for: the fleet's geometry gate
failed three ways on the same page — a crashpad orphan holding pipe-captured
output (hang), a second uncentralized spawn (hang again), then chrome's
new-headless quiescence never triggering on font-heavy pages (hang, and once
SIGABRT). The common cause was chrome deciding when measurement ends. The
runner is now CDP: the page signals completion by inserting a <pre>, we poll
for it over the debugger with our own deadline, chrome's output goes to
DEVNULL and the process is killed in run_scenario's finally. These tests run
REAL chrome — a fake cannot serve a debugger, and the failures this guards
were all environment-real.
"""

import pathlib
import time

import pytest

from densui import probe


def test_wait_for_pre_returns_content(tmp_path):
    page = tmp_path / "page.html"
    page.write_text(
        "<html><body><script>"
        "setTimeout(function(){"
        "var p=document.createElement('pre');p.id='done';"
        "p.textContent=JSON.stringify({ok:1});document.body.appendChild(p);"
        "},300);"
        "</script></body></html>"
    )
    out = probe.wait_for_pre(page, "done", deadline_ms=15000)
    assert out == '{"ok":1}'


def test_missed_deadline_is_a_named_failure(tmp_path):
    """A page that never signals completion must raise ProbeError promptly —
    a bounded, named diagnosis, never a hung gate (nor a generic timeout)."""
    page = tmp_path / "page.html"
    page.write_text("<html><body>never signals</body></html>")
    t0 = time.monotonic()
    with pytest.raises(probe.ProbeError, match="did not appear"):
        probe.wait_for_pre(page, "done", deadline_ms=2000)
    assert time.monotonic() - t0 < 20


def test_chrome_measurement_is_centralized():
    """No file may reach for chrome's DOM-dumping mode again.

    The quiescence hang shipped precisely because measurement chrome was
    spawned in more than one place with more than one idiom. The banned
    string is assembled to avoid matching this test itself.
    """
    banned = "--dump" + "-dom"
    repo = pathlib.Path(__file__).resolve().parents[3]
    offenders = []
    for f in repo.rglob("*.py"):
        if ".venv" in f.parts or f.name == pathlib.Path(__file__).name:
            continue
        if banned in f.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(f.relative_to(repo)))
    for f in repo.rglob("*.js"):
        if ".venv" in f.parts or "node_modules" in f.parts:
            continue
        if banned in f.read_text(encoding="utf-8", errors="ignore"):
            offenders.append(str(f.relative_to(repo)))
    assert not offenders, f"chrome DOM-dump spawns outside the CDP runner: {offenders}"
