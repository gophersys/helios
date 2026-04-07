"""Git poller entry point.

Responsibilities:
1. Write SSH key to disk from BITBUCKET_SSH_KEY env var (base64).
2. Start a minimal health HTTP server on SERVICE_PORT.
3. Install SIGTERM/SIGINT handlers for graceful shutdown.
4. Run the GitPoller loop (blocks until shutdown).
"""

import atexit
import base64
import logging
import os
import signal
import stat
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from corekinect.utils import print_banner
from config import GitPollerConfig
from poller import GitPoller

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s [%(name)s] %(message)s",
)
log = logging.getLogger("git-poller")

# Set to True after the first successful poll cycle — gates /ready
_ready = False


# ---------------------------------------------------------------------------
# SSH key setup
# ---------------------------------------------------------------------------


def _setup_ssh_key(config: GitPollerConfig) -> None:
    """Decode and write the SSH private key from the env var if provided."""
    sock = config.ssh_key_path  # reuse path only if SSH agent is active
    import os

    agent_sock = os.environ.get("SSH_AUTH_SOCK", "")
    if agent_sock and Path(agent_sock).exists():
        log.info("SSH: using agent at %s", agent_sock)
        return

    if not config.bitbucket_ssh_key:
        key_path = Path(config.ssh_key_path)
        if not key_path.exists():
            log.warning(
                "SSH: BITBUCKET_SSH_KEY not set and %s does not exist — "
                "git operations will fail",
                config.ssh_key_path,
            )
        return

    key_bytes = base64.b64decode(config.bitbucket_ssh_key)
    key_path = Path(config.ssh_key_path)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    key_path.write_bytes(key_bytes)
    key_path.chmod(stat.S_IRUSR)
    log.info("SSH: key written to %s (%d bytes)", config.ssh_key_path, len(key_bytes))


# ---------------------------------------------------------------------------
# Health server
# ---------------------------------------------------------------------------


def _run_health_server(port: int) -> None:
    """Minimal HTTP server for K8s readiness/liveness probes."""
    import json as _json

    class _Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/health":
                body = _json.dumps({"status": "ok", "service": "git-poller"})
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body.encode())
            elif self.path == "/ready":
                if _ready:
                    body = _json.dumps({"status": "ready", "service": "git-poller"})
                    self.send_response(200)
                else:
                    body = _json.dumps({"status": "not_ready", "service": "git-poller"})
                    self.send_response(503)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(body.encode())
            else:
                self.send_response(404)
                self.end_headers()

        def log_message(self, *args):
            pass  # suppress access logs

    HTTPServer(("0.0.0.0", port), _Handler).serve_forever()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    config = GitPollerConfig()

    print_banner(
        "concord-git-poller",
        API=config.concord_api_url,
        Interval=f"{config.poll_interval}s",
        Port=str(config.service_port),
    )

    _setup_ssh_key(config)

    # Health server (daemon — dies with main thread)
    health_thread = threading.Thread(
        target=_run_health_server,
        args=(config.service_port,),
        daemon=True,
        name="health-server",
    )
    health_thread.start()
    log.info("Health server on :%d", config.service_port)

    # Create poller before installing signal handlers
    poller = GitPoller(config=config)

    def _handle_signal(signum, _frame):
        name = signal.Signals(signum).name
        log.info("Received %s — requesting shutdown", name)
        poller.signal_shutdown()

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)
    atexit.register(lambda: log.info("git-poller stopped"))

    def _mark_ready():
        global _ready
        _ready = True
        log.info("First poll complete — service is ready")

    poller.run(on_first_success=_mark_ready)


if __name__ == "__main__":
    main()
