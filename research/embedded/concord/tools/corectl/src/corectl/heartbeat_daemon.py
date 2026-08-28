"""Background heartbeat for a DEV_HOLD fixture claim.

Spawned by ``corectl test claim`` and detached from the parent shell.
Posts ``/v2/fixture-claims/<id>/heartbeat`` every ``INTERVAL_SECONDS``
to extend the lease's sliding TTL. Exits cleanly when any of the
following happens:

1. The state file at ``.concord-claim.json`` is deleted (the CLI's
   ``unclaim`` command, or an operator manually removing it).
2. The backend returns HTTP 410 (claim is EXPIRED, RELEASED, or
   ABANDONED — heartbeating is pointless).
3. A SIGTERM lands (orderly shutdown by an init system or the OS).

Logs to ``.concord-claim.log`` in the project root using a rotating
handler capped at 1 MB. Two backups are kept so the dev has enough
history to debug a stuck daemon without burning disk.

The daemon is intentionally written to import only stdlib + ``requests``
+ corectl's own modules — no Click, no Rich, no API client. Keeping the
import graph tiny lets the daemon survive a partially-broken environment
the parent shell might have at spawn time (e.g., an in-progress
``pip install`` inside the same venv).

Usage::

    python -m corectl.heartbeat_daemon /path/to/project --api-url URL [--token T | --api-key K]

Run via ``subprocess.Popen([...], start_new_session=True, stdin=DEVNULL,
stdout=DEVNULL, stderr=DEVNULL)`` from the parent. The daemon's PID is
stored in the state file so ``unclaim`` (or an operator) can validate
the daemon's identity before signaling.
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import signal
import sys
import time
from pathlib import Path
from typing import Optional


# Default cadence. The backend's sliding TTL is 5 minutes; 60 s gives us
# 5x headroom which absorbs the occasional packet loss or network hiccup
# without burning request volume.
INTERVAL_SECONDS = 60

# Max-size cap on the log before rotation. 1 MB is large enough to hold a
# week of normal "heartbeat OK" lines but small enough that a stuck
# daemon doesn't fill a dev's disk before they notice.
LOG_MAX_BYTES = 1024 * 1024
LOG_BACKUPS = 2

# How long to back off when a heartbeat fails transiently (network blip,
# 5xx from the API). Shorter than INTERVAL so a flaky link recovers in
# under a minute; longer than INTERVAL/10 so we don't hammer the API.
RETRY_BACKOFF_SECONDS = 15


_should_exit = False


def _handle_signal(signum, _frame):
    """SIGTERM / SIGINT → flag the main loop to exit on next tick."""
    global _should_exit
    _should_exit = True


def _setup_logging(log_file: Path) -> logging.Logger:
    """Configure a rotating file logger.

    Returns a named logger so callers can attach context (claim id) to
    every line via the standard ``logging.Logger.info`` call.
    """
    logger = logging.getLogger("concord.claim.heartbeat")
    logger.setLevel(logging.INFO)
    # Strip any pre-existing handlers — defensive in case the module gets
    # imported a second time within the same interpreter (tests).
    for h in list(logger.handlers):
        logger.removeHandler(h)
    handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUPS, encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    )
    logger.addHandler(handler)
    return logger


def _send_heartbeat(
    *,
    api_url: str,
    claim_id: str,
    token: Optional[str],
    api_key: Optional[str],
    verify: bool,
    timeout: float = 10.0,
) -> int:
    """POST one heartbeat. Returns the HTTP status code.

    Network errors are translated to ``0`` so the caller treats them as
    a transient failure (retry on backoff) — not as a backend-rejected
    claim (exit).
    """
    # Local import — keeps module-import cheap on the parent process.
    import requests

    headers = {}
    if api_key:
        headers["Authorization"] = f"ApiKey {api_key}"
    elif token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        resp = requests.post(
            f"{api_url.rstrip('/')}/v2/fixture-claims/{claim_id}/heartbeat",
            headers=headers,
            verify=verify,
            timeout=timeout,
        )
        return resp.status_code
    except requests.RequestException:
        return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="DEV_HOLD heartbeat daemon")
    parser.add_argument("project_dir", help="Path to the project root holding .concord-claim.json")
    parser.add_argument("--api-url", required=True, help="Concord API base URL")
    parser.add_argument("--token", default=None, help="Bearer access token")
    parser.add_argument("--api-key", default=None, help="Service-account API key")
    parser.add_argument(
        "--insecure", action="store_true",
        help="Skip TLS verification (passes verify=False to requests)",
    )
    parser.add_argument(
        "--interval", type=int, default=INTERVAL_SECONDS,
        help="Heartbeat cadence in seconds (default: %(default)s)",
    )
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir).resolve()

    # Lazy import — avoids loading PyYAML/etc when the daemon doesn't
    # need them, and keeps the daemon's import graph minimal.
    from corectl import claim_state

    log_file = claim_state.log_path(project_dir)
    logger = _setup_logging(log_file)

    # Install signal handlers AFTER logging is set up so a SIGTERM during
    # boot still surfaces in the log.
    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    # Read the state file once at boot so we know which claim to ping.
    # The id is immutable for the lifetime of the daemon — even when the
    # CLI rewrites the file (e.g., to refresh expiresAt from a response)
    # the id never changes.
    state = claim_state.load(project_dir)
    if state is None:
        logger.error("No state file at %s — exiting", claim_state.state_path(project_dir))
        return 1
    cid = claim_state.claim_id(state)
    logger.info("Heartbeat daemon started for claim %s (pid=%d, interval=%ds)",
                cid, os.getpid(), args.interval)

    verify = not args.insecure
    consecutive_errors = 0

    while not _should_exit:
        # First check: did the CLI delete the state file? That's our
        # cooperative "please stop" signal — no need to hit the backend.
        if not claim_state.state_path(project_dir).exists():
            logger.info("State file removed — exiting cleanly")
            return 0

        status = _send_heartbeat(
            api_url=args.api_url,
            claim_id=cid,
            token=args.token,
            api_key=args.api_key,
            verify=verify,
        )

        if status == 200:
            consecutive_errors = 0
            logger.debug("Heartbeat OK")
        elif status == 410:
            # Backend says the claim is terminal — EXPIRED / RELEASED /
            # ABANDONED. Wipe the state file so the CLI's next ``status``
            # call doesn't lie to the dev.
            logger.warning("Backend reports claim %s is terminal (410) — exiting", cid)
            claim_state.remove(project_dir)
            return 0
        elif status == 401 or status == 403:
            # Permission was revoked mid-session — usually a token
            # expiry that the parent CLI was supposed to refresh but
            # we're using a snapshot. Log loud and exit; the dev can
            # re-claim.
            logger.error("Heartbeat denied (HTTP %d) — exiting", status)
            return 2
        else:
            # Transient (0 = network error, 5xx, etc) — keep going with
            # a shorter backoff so we recover faster than the normal
            # cadence allows.
            consecutive_errors += 1
            logger.warning("Heartbeat failed (HTTP %d, attempt %d)", status, consecutive_errors)
            # If we've failed for ~5 minutes straight, the lease has
            # almost certainly expired anyway — exit so the daemon
            # doesn't linger forever on a network partition.
            if consecutive_errors >= 20:
                logger.error("Too many consecutive failures — exiting")
                return 3
            _sleep_with_signal_check(RETRY_BACKOFF_SECONDS)
            continue

        _sleep_with_signal_check(args.interval)

    logger.info("Received exit signal — shutting down")
    return 0


def _sleep_with_signal_check(seconds: int) -> None:
    """Sleep in 1-second slices so SIGTERM lands within a second.

    A plain ``time.sleep(60)`` would block signal handlers for up to a
    minute on some platforms; slicing keeps shutdown responsive.
    """
    end = time.monotonic() + seconds
    while not _should_exit and time.monotonic() < end:
        time.sleep(min(1.0, end - time.monotonic()))


if __name__ == "__main__":
    sys.exit(main())
