"""densui.drive — gesture-level verification over CDP.

Launches headless Chrome with a debugging port, opens the page, and runs a
scenario (clicks, drags, wheel, eval) through drive.js (node's built-in
WebSocket — no new Python dependencies). Replaces the founding session's
ad-hoc CDP scripts. Eyes doctrine: gestures verify BEHAVIOUR; geometry is
still proved by the battery, never by looking.
"""

from __future__ import annotations

import json
import pathlib
import socket
import subprocess
import time
import urllib.request

from densui.probe import ProbeError, find_chrome

DRIVE_JS = pathlib.Path(__file__).parent / "drive.js"


class DriveError(RuntimeError):
    pass


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def run_scenario(
    page: str | pathlib.Path,
    scenario: list[dict],
    window: str = "1600,900",
    timeout_s: float = 20.0,
) -> list:
    """Returns the scenario's results list; raises DriveError on any failure —
    a gesture that cannot run is a failure, not a pass."""
    page = pathlib.Path(page).resolve()
    if not page.exists():
        raise DriveError(f"page not found: {page}")
    port = _free_port()
    chrome = subprocess.Popen(
        [
            find_chrome(),
            "--headless=new",
            "--disable-gpu",
            "--mute-audio",
            "--no-sandbox",
            f"--window-size={window}",
            f"--remote-debugging-port={port}",
            f"file://{page}",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + timeout_s
        ws_url = None
        while time.time() < deadline and ws_url is None:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/json") as fh:
                    tabs = json.load(fh)
                for tab in tabs:
                    if tab.get("type") == "page" and str(page.name) in tab.get("url", ""):
                        ws_url = tab["webSocketDebuggerUrl"]
            except OSError:
                time.sleep(0.2)
        if ws_url is None:
            raise DriveError("could not reach Chrome's debugger")
        run = subprocess.run(
            ["node", str(DRIVE_JS), ws_url, json.dumps(scenario)],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            check=False,
        )
        if run.returncode != 0:
            raise DriveError(f"scenario failed: {run.stderr.strip() or run.stdout.strip()}")
        return json.loads(run.stdout)["results"]
    except ProbeError as exc:
        raise DriveError(str(exc)) from exc
    finally:
        chrome.terminate()
        chrome.wait(timeout=5)
