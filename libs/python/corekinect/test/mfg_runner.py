"""Persistent manufacturing test runner.

Stays alive for the duration of a ManufacturingSession, receiving panel
assignments via WebSocket and running tests for each. Designed for K8s
Deployment with replicas=1 -- auto-restarts on crash.

Usage:
    python -m corekinect.test.mfg_runner --session-id <id>

Environment:
    CONCORD_API_URL: Backend API base URL
    CONCORD_API_KEY: Ephemeral API key for auth
    CONCORD_SESSION_ID: Manufacturing session ID
    MTIB_HOSTS: Comma-separated MTIB gRPC addresses
    PRODUCT_SLUG: Product slug for test package download
    TEST_PACKAGE_VERSION: Test package version (already downloaded by entrypoint.sh)
"""

import os
import signal
import sys
import threading
import time
import traceback
from typing import Optional

import requests
import socketio

from corekinect.test.runner import TestRunner
from corekinect.test.slot import FixtureContext
from corekinect.utils import Logger

log = Logger(log_name="mfg_runner")

# TLS verification -- can be disabled for local dev with self-signed certs
_TLS_VERIFY = os.environ.get("TLS_VERIFY", "true").lower() in ("1", "true", "yes")


class ManufacturingRunnerLoop:
    """Long-running loop that receives panel assignments via WebSocket.

    Connects to MTIB hardware once at startup, then waits for
    ``manufacturing_run_start`` events on the session's WS room.
    Each event triggers a full TestRunner execution for that panel.
    """

    def __init__(
        self,
        session_id: str,
        api_url: str,
        api_key: str,
        api_host: Optional[str] = None,
    ):
        self.session_id = session_id
        self.api_url = api_url.rstrip("/")
        self.api_key = api_key
        self.api_host = api_host

        self.fixture_ctx: Optional[FixtureContext] = None
        self.sio: Optional[socketio.Client] = None
        self._running_lock = threading.Lock()
        self._current_run_id: Optional[str] = None
        self._current_runner: Optional[TestRunner] = None
        self._shutting_down = False

        # Auth header for HTTP calls
        auth_prefix = "ApiKey" if api_key.startswith("ck_") else "Bearer"
        self._auth_headers = {
            "Authorization": f"{auth_prefix} {api_key}",
            "Content-Type": "application/json",
        }

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self) -> None:
        """Start the persistent runner loop.

        1. Connect to MTIB hardware
        2. Connect to backend WebSocket
        3. Join the manufacturing session room
        4. Send READY heartbeat
        5. Recover any missed/crashed runs
        6. Block on the event loop until session ends
        """
        log.info("=" * 60)
        log.info("ManufacturingRunnerLoop starting")
        log.info("  session_id = %s", self.session_id)
        log.info("  api_url    = %s", self.api_url)
        log.info("=" * 60)

        # Register signal handler for graceful shutdown
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

        # Max lifetime safety net — self-terminate if session was never ended
        max_lifetime_h = int(os.environ.get("RUNNER_MAX_LIFETIME_HOURS", "8"))
        self._start_time = time.monotonic()
        self._max_lifetime_s = max_lifetime_h * 3600
        log.info("  max_lifetime = %dh", max_lifetime_h)

        # 1. Connect MTIB hardware — wait until ALL slots are reachable.
        # Fixtures may be powered off overnight; the runner stays alive and
        # retries until the operator powers them back on.
        mock_mode = os.environ.get("MOCK_MODE", "0") in ("1", "true", "yes")
        log.info("Connecting to MTIB hardware...%s", " (MOCK_MODE)" if mock_mode else "")
        retry_interval = int(os.environ.get("MTIB_RETRY_INTERVAL_S", "60"))
        try:
            self.fixture_ctx = FixtureContext.from_env()
            total = self.fixture_ctx.slot_count
            while not self._shutting_down:
                connected = self.fixture_ctx.connect_available()
                if connected == total:
                    break
                if mock_mode:
                    log.warning("Only %d/%d slots connected (mock mode — continuing)", connected, total)
                    break
                log.warning(
                    "Waiting for hardware: %d/%d slots connected. Retrying in %ds...",
                    connected, total, retry_interval,
                )
                self._send_heartbeat("WAITING")
                time.sleep(retry_interval)
                if time.monotonic() - self._start_time > self._max_lifetime_s:
                    log.error("Max lifetime exceeded while waiting for hardware.")
                    self._send_heartbeat("ERROR")
                    sys.exit(1)
        except Exception as e:
            if mock_mode:
                log.warning("MTIB init failed (mock mode — continuing): %s", e)
                self.fixture_ctx = None
            else:
                log.error("MTIB init failed: %s", e)
                self._send_heartbeat("ERROR")
                sys.exit(1)

        # 2. Connect WebSocket
        self.sio = socketio.Client(
            reconnection=True,
            reconnection_attempts=0,  # infinite
            reconnection_delay=1,
            reconnection_delay_max=30,
            logger=False,
        )
        self._register_ws_handlers()

        ws_url = self.api_url
        ws_auth = {"apiKey": self.api_key}

        log.info("Connecting to WebSocket: %s (namespace=/runs)", ws_url)
        for attempt in range(10):
            try:
                self.sio.connect(
                    ws_url,
                    namespaces=["/runs"],
                    auth=ws_auth,
                    wait_timeout=30,
                )
                break
            except Exception as e:
                delay = min(2 ** attempt, 30)
                log.warning("WebSocket connection failed (attempt %d/10): %s — retrying in %ds", attempt + 1, e, delay)
                time.sleep(delay)
        else:
            log.error("WebSocket connection failed after 10 attempts")
            log.error("Cannot receive panel assignments without WebSocket. Reporting ERROR.")
            self._send_heartbeat("ERROR")
            sys.exit(1)

        # 3. Join session room (only if connected)
        if self.sio and self.sio.connected:
            self.sio.emit(
                "subscribe_mfg_session",
                {"sessionId": self.session_id},
                namespace="/runs",
            )

        # 4. Send initial heartbeat
        self._send_heartbeat("READY")

        # 5. Start periodic heartbeat + lifetime watchdog
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True, name="heartbeat"
        )
        self._heartbeat_thread.start()

        # 6. Recover any pending/crashed runs
        self._recover_pending_runs()

        # 7. Block until disconnected
        log.info("Runner ready -- waiting for panel assignments")
        self.sio.wait()
        log.info("Event loop exited")

    # ------------------------------------------------------------------
    # WebSocket event handlers
    # ------------------------------------------------------------------

    def _register_ws_handlers(self) -> None:
        """Register all WS event handlers on the /runs namespace."""
        sio = self.sio

        @sio.on("connect", namespace="/runs")
        def on_connect():
            log.info("WebSocket connected")
            # Re-join room on reconnect
            sio.emit(
                "subscribe_mfg_session",
                {"sessionId": self.session_id},
                namespace="/runs",
            )
            # Check for panels missed during disconnect
            self._recover_pending_runs()

        @sio.on("disconnect", namespace="/runs")
        def on_disconnect():
            log.warning("WebSocket disconnected -- will auto-reconnect")

        @sio.on("manufacturing_run_start", namespace="/runs")
        def on_manufacturing_run_start(data):
            self._on_manufacturing_run_start(data)

        @sio.on("manufacturing_run_cancelled", namespace="/runs")
        def on_manufacturing_run_cancelled(data):
            self._on_manufacturing_run_cancelled(data)

        @sio.on("manufacturing_session_end", namespace="/runs")
        def on_manufacturing_session_end(data):
            self._on_manufacturing_session_end(data)

        @sio.on("error", namespace="/runs")
        def on_error(data):
            log.error("WS error: %s", data)

    def _on_manufacturing_run_start(self, data: dict) -> None:
        """Handle a new panel assignment from the backend.

        Extracts run_id from the event, configures environment for the
        TestRunner, executes the manufacturing test suite, and reports
        completion.
        """
        run_id = data.get("id")
        panel_id = data.get("panelIdentifier", "unknown")

        if not run_id:
            log.error("manufacturing_run_start event missing 'id': %s", data)
            return

        log.info("=" * 50)
        log.info("Panel assignment: run_id=%s panel=%s", run_id, panel_id)
        log.info("=" * 50)

        with self._running_lock:
            self._current_run_id = run_id

        self._send_heartbeat("RUNNING")

        # Self-heal MTIB connections that may have gone stale (e.g., MTIB
        # servers restarted while the runner was idle). Reconnect before
        # preflight so transient restarts don't fail the panel.
        if self.fixture_ctx:
            try:
                self.fixture_ctx.ensure_all_connected()
            except Exception as e:
                log.warning("ensure_all_connected raised: %s", e)

        # Set environment for TestRunner and reporter
        os.environ["CONCORD_RUN_ID"] = run_id
        os.environ["CONCORD_SESSION_ID"] = run_id

        # Extract target info from the run assignment and set env vars.
        # pytest/autoconf creates a fresh FixtureContext per run that reads
        # SLOT_FILTER, SLOT_SNRS, and SLOT_DEVICE_IDS from the environment.
        targets = data.get("targets", [])
        if targets:
            targets_sorted = sorted(targets, key=lambda t: t.get("slotIndex", 0))

            # SLOT_FILTER: which slot indices to test for this panel
            target_indices = [t.get("slotIndex", 0) for t in targets_sorted]
            os.environ["SLOT_FILTER"] = ",".join(str(i) for i in target_indices)

            # SLOT_SNRS + SLOT_DEVICE_IDS: per-slot DUT identity for this panel
            # These must be comma-separated aligned with MTIB_HOSTS order (all slots),
            # not just the filtered ones. Build a full-width list with blanks for
            # slots not in this run, then FixtureContext.from_env() picks them up.
            mtib_hosts = os.environ.get("MTIB_HOSTS", "")
            total_slots = len([a for a in mtib_hosts.split(",") if a.strip()]) if mtib_hosts else 0
            snrs = [""] * total_slots
            device_ids = [""] * total_slots
            target_ids = [""] * total_slots
            for t in targets_sorted:
                idx = t.get("slotIndex", 0)
                if idx < total_slots:
                    snrs[idx] = t.get("serialNumber") or ""
                    device_ids[idx] = t.get("deviceId") or ""
                    target_ids[idx] = t.get("id") or ""
            os.environ["SLOT_SNRS"] = ",".join(snrs)
            os.environ["SLOT_DEVICE_IDS"] = ",".join(device_ids)
            os.environ["SLOT_TARGET_IDS"] = ",".join(target_ids)

            log.info("Run targets: %s",
                     ", ".join(f"slot-{t.get('slotIndex')}={t.get('serialNumber','?')}"
                               for t in targets_sorted))
        else:
            os.environ.pop("SLOT_FILTER", None)
            os.environ.pop("SLOT_SNRS", None)
            os.environ.pop("SLOT_DEVICE_IDS", None)
            os.environ.pop("SLOT_TARGET_IDS", None)

        try:
            runner = TestRunner(stage="manufacturing", run_id=run_id)
            with self._running_lock:
                self._current_runner = runner
            exit_code = runner.run()
            log.info(
                "Panel %s completed: exit_code=%d",
                panel_id, exit_code,
            )
        except Exception:
            log.error(
                "Panel %s crashed:\n%s", panel_id, traceback.format_exc()
            )
            # Report failure to the API
            self._report_run_failed(run_id, "Runner exception during test execution")
        finally:
            with self._running_lock:
                self._current_run_id = None
                self._current_runner = None
            self._send_heartbeat("READY")

    def _on_manufacturing_run_cancelled(self, data: dict) -> None:
        """Handle cancel event — kill the pytest subprocess if it matches."""
        cancelled_run_id = data.get("runId")
        log.info("Received cancel for run %s", cancelled_run_id)

        with self._running_lock:
            if self._current_run_id != cancelled_run_id:
                log.info("Cancel ignored — run %s is not the current run", cancelled_run_id)
                return
            runner = self._current_runner

        if runner:
            log.info("Killing pytest subprocess for run %s", cancelled_run_id)
            runner.cancel()
        else:
            log.warning("No active TestRunner to cancel for run %s", cancelled_run_id)

    def _on_manufacturing_session_end(self, data: dict) -> None:
        """Handle session end -- graceful shutdown.

        If a test is currently running, sets the shutdown flag so we
        exit after it finishes. Otherwise disconnects immediately.
        """
        log.info("Manufacturing session ended: %s", data.get("id", "?"))
        self._shutting_down = True

        with self._running_lock:
            if self._current_run_id:
                log.info(
                    "Test in progress (run=%s) -- will shut down after completion",
                    self._current_run_id,
                )
                return

        self._shutdown()

    # ------------------------------------------------------------------
    # HTTP helpers
    # ------------------------------------------------------------------

    def _heartbeat_loop(self) -> None:
        """Periodic heartbeat every 30s + lifetime watchdog."""
        while not self._shutting_down:
            time.sleep(30)
            if self._shutting_down:
                break

            # Check max lifetime
            elapsed = time.monotonic() - self._start_time
            if elapsed > self._max_lifetime_s:
                hours = self._max_lifetime_s / 3600
                log.error("Runner exceeded max lifetime (%dh) -- shutting down", hours)
                self._send_heartbeat("ERROR")
                self._shutting_down = True
                self._shutdown()
                return

            # Send periodic heartbeat (READY or RUNNING depending on state)
            with self._running_lock:
                status = "RUNNING" if self._current_run_id else "READY"
            self._send_heartbeat(status)

    def _send_heartbeat(self, status: str) -> None:
        """POST runner heartbeat to the backend.

        Best-effort -- failures are logged but don't interrupt operation.
        """
        url = f"{self.api_url}/v2/manufacturing/sessions/{self.session_id}/runner-heartbeat"
        try:
            resp = requests.post(
                url,
                json={"status": status},
                headers=self._auth_headers,
                timeout=5,
                verify=_TLS_VERIFY,
            )
            if not resp.ok:
                log.warning(
                    "Heartbeat %s failed: %d %s",
                    status, resp.status_code, resp.text[:200],
                )
        except Exception as e:
            log.warning("Heartbeat %s error: %s", status, e)

    def _report_run_failed(self, run_id: str, error_msg: str) -> None:
        """Report a run as FAILED via the reporting API."""
        url = f"{self.api_url}/v2/runs/{run_id}/report/finish"
        try:
            requests.post(
                url,
                json={
                    "status": "FAILED",
                    "errorMessage": error_msg,
                    "stage": "manufacturing",
                    "total": 0,
                    "passed": 0,
                    "failed": 0,
                    "errors": 1,
                },
                headers=self._auth_headers,
                timeout=10,
                verify=_TLS_VERIFY,
            )
        except Exception as e:
            log.warning("Failed to report run %s as FAILED: %s", run_id, e)

    # ------------------------------------------------------------------
    # Crash recovery
    # ------------------------------------------------------------------

    def _recover_pending_runs(self) -> None:
        """Recover from a crash by checking session state on first startup.

        Only runs once (guarded by _recovery_done flag). Skips if a run
        is currently being executed by this runner instance.

        - Runs with status ACTIVE (was running when we crashed) -> mark FAILED
        - Runs with status PENDING (not yet started) -> execute them
        """
        if getattr(self, '_recovery_done', False):
            return
        self._recovery_done = True

        # Don't mark runs as crashed if we're currently executing one
        with self._running_lock:
            if self._current_run_id:
                return

        url = f"{self.api_url}/v2/manufacturing/sessions/{self.session_id}"
        try:
            resp = requests.get(
                url,
                headers=self._auth_headers,
                timeout=15,
                verify=_TLS_VERIFY,
            )
            if not resp.ok:
                log.warning("Failed to fetch session for recovery: %d", resp.status_code)
                return

            session_data = resp.json().get("data", {})
            runs = session_data.get("runs", [])

        except Exception as e:
            log.warning("Recovery check failed: %s", e)
            return

        # Mark ACTIVE runs as FAILED (they were interrupted by a previous crash)
        for run in runs:
            if run.get("status") == "ACTIVE":
                run_id = run.get("id")
                log.warning("Marking crashed run %s as FAILED", run_id)
                self._report_run_failed(run_id, "Runner crashed during execution")

        # Process any PENDING runs
        for run in runs:
            if run.get("status") == "PENDING":
                log.info("Processing pending run: %s", run.get("id"))
                self._on_manufacturing_run_start(run)

    # ------------------------------------------------------------------
    # Shutdown
    # ------------------------------------------------------------------

    def _handle_sigterm(self, signum, frame) -> None:
        """Handle SIGTERM/SIGINT for graceful shutdown."""
        sig_name = signal.Signals(signum).name
        log.info("Received %s -- initiating graceful shutdown", sig_name)
        self._shutting_down = True

        with self._running_lock:
            if self._current_run_id:
                log.info(
                    "Test in progress (run=%s) -- waiting for completion",
                    self._current_run_id,
                )
                return

        self._shutdown()

    def _shutdown(self) -> None:
        """Disconnect MTIB and WebSocket, then exit."""
        log.info("Shutting down...")

        if self.fixture_ctx:
            try:
                self.fixture_ctx.disconnect_all()
            except Exception as e:
                log.warning("Error disconnecting MTIB: %s", e)

        if self.sio and self.sio.connected:
            try:
                self.sio.disconnect()
            except Exception as e:
                log.warning("Error disconnecting WebSocket: %s", e)

        log.info("Shutdown complete")
        sys.exit(0)


# ======================================================================
# CLI entry point
# ======================================================================


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Persistent manufacturing test runner"
    )
    parser.add_argument(
        "--session-id",
        required=True,
        help="Manufacturing session ID to subscribe to",
    )
    args = parser.parse_args()

    api_url = os.environ.get("CONCORD_API_URL", "http://localhost:9001")
    api_key = os.environ.get("CONCORD_API_KEY", "")
    api_host = os.environ.get("CONCORD_API_HOST")

    if not api_key:
        log.error("CONCORD_API_KEY is required")
        sys.exit(1)

    runner = ManufacturingRunnerLoop(args.session_id, api_url, api_key, api_host)
    runner.run()
