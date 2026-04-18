"""HTTP harness for E2E tests that drive the Concord manufacturing API.

Thin, typed wrappers around the handful of API calls the E2E suite
needs:

  * create a manufacturing session, wait for runner READY
  * trigger a run (standalone or panel) with a QR code + SNRs
  * poll a run until it finishes (COMPLETED / FAILED / CANCELLED)
  * end a session and release the fixture

All requests carry the admin API key and raise
:class:`HarnessError` with the response body on any non-2xx status so
the caller sees what the server actually returned.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import requests


class HarnessError(RuntimeError):
    """Non-2xx API response."""


@dataclass(frozen=True)
class SessionInfo:
    id: str
    runner_status: Optional[str]
    runner_deployment_name: Optional[str]


@dataclass(frozen=True)
class RunInfo:
    id: str
    status: str
    panel_identifier: Optional[str]
    target_count: int
    completed_count: int
    passed_count: int
    failed_count: int
    duration_ms: Optional[int]
    targets: List[Dict[str, Any]]


class ApiHarness:
    """Minimal wrapper around the subset of /v2/manufacturing used by E2E tests."""

    def __init__(self, base_url: str, api_key: str, timeout_s: float = 30.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout_s = timeout_s
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"ApiKey {api_key}",
            "Content-Type": "application/json",
        })

    # ── internals ────────────────────────────────────────────────────

    def _call(self, method: str, path: str, json: Optional[dict] = None) -> dict:
        url = f"{self.base_url}{path}"
        resp = self._session.request(method, url, json=json, timeout=self.timeout_s)
        if resp.status_code >= 400:
            raise HarnessError(f"{method} {path} → {resp.status_code}: {resp.text[:500]}")
        if not resp.text.strip():
            return {}
        return resp.json()

    # ── sessions ─────────────────────────────────────────────────────

    def create_session(
        self, *, product_id: str, fixture_id: str, asset_set_id: str,
    ) -> SessionInfo:
        body = self._call("POST", "/v2/manufacturing/sessions", json={
            "productId": product_id,
            "fixtureId": fixture_id,
            "assetSetId": asset_set_id,
        })
        data = body["data"]
        return SessionInfo(
            id=data["id"],
            runner_status=data.get("runnerStatus"),
            runner_deployment_name=data.get("runnerDeploymentName"),
        )

    def get_session(self, session_id: str) -> Dict[str, Any]:
        return self._call("GET", f"/v2/manufacturing/sessions/{session_id}")["data"]

    def wait_for_runner_ready(
        self, session_id: str, *, timeout_s: float = 180.0, poll_s: float = 2.0,
    ) -> None:
        deadline = time.monotonic() + timeout_s
        last_status: Optional[str] = None
        while time.monotonic() < deadline:
            s = self.get_session(session_id)
            status = s.get("runnerStatus")
            if status != last_status:
                last_status = status
            if status in ("READY", "RUNNING"):
                return
            if status == "ERROR":
                raise HarnessError(
                    f"runner deployment reported ERROR for session {session_id}"
                )
            time.sleep(poll_s)
        raise HarnessError(
            f"runner did not reach READY within {timeout_s}s (last status={last_status})"
        )

    def end_session(self, session_id: str) -> None:
        self._call("POST", f"/v2/manufacturing/sessions/{session_id}/end")

    # ── runs ─────────────────────────────────────────────────────────

    def trigger_run(
        self, *, session_id: str, qr_code: str, run_type: str = "panel",
    ) -> str:
        body = self._call(
            "POST",
            f"/v2/manufacturing/sessions/{session_id}/runs",
            json={"qrCode": qr_code, "runType": run_type},
        )
        return body["data"]["id"]

    def get_run(self, run_id: str) -> RunInfo:
        data = self._call("GET", f"/v2/runs/{run_id}")["data"]
        return RunInfo(
            id=data["id"],
            status=data["status"],
            panel_identifier=data.get("panelIdentifier"),
            target_count=data.get("targetCount", 0),
            completed_count=data.get("completedCount", 0),
            passed_count=data.get("passedCount", 0),
            failed_count=data.get("failedCount", 0),
            duration_ms=data.get("durationMs"),
            targets=data.get("targets", []) or [],
        )

    def wait_for_run(
        self,
        run_id: str,
        *,
        timeout_s: float = 1800.0,
        poll_s: float = 5.0,
    ) -> RunInfo:
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            run = self.get_run(run_id)
            if run.status in ("COMPLETED", "FAILED", "CANCELLED"):
                return run
            time.sleep(poll_s)
        raise HarnessError(f"run {run_id} did not terminate within {timeout_s}s")
