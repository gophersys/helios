"""Dev Build Worker — simulates firmware builds for local development.

Polls the Concord API for QUEUED build jobs, claims them, generates placeholder
artifacts, uploads them, and reports SUCCESS. This exercises the full pipeline:
trigger → queue → claim → build → upload → complete → promote → auto-progress.

The same API contract is used by real build workers in staging/production
(K8s Jobs and Build Service DaemonSet), so validating this flow locally
guarantees a smooth transition to deployed environments.

Usage:
    CONCORD_API_URL=http://localhost:9001 python worker.py
"""

import io
import json
import logging
import os
import random
import sys
import time
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_URL = os.environ.get("CONCORD_API_URL", "http://localhost:9001")
WORKER_ID = os.environ.get("WORKER_ID", "dev-builder-1")
POLL_INTERVAL = int(os.environ.get("POLL_INTERVAL", "3"))
BUILD_DELAY_MIN = float(os.environ.get("BUILD_DELAY_MIN", "2"))
BUILD_DELAY_MAX = float(os.environ.get("BUILD_DELAY_MAX", "4"))

# Alpha B0 defaults — used when product targets can't be resolved
DEFAULT_TARGETS = [
    {"role": "comms", "soc": "nRF9151", "appId": 108, "processor": "nrf9151"},
    {"role": "app", "soc": "nRF52840", "appId": 109, "processor": "nrf52840"},
]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
log = logging.getLogger("dev-build-worker")

# Cache product targets to avoid repeated API calls
_target_cache: dict = {}


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

session = requests.Session()
session.headers.update({"Content-Type": "application/json"})


def api_get(path: str) -> dict | None:
    try:
        resp = session.get(f"{API_URL}{path}", timeout=10)
        if resp.status_code == 200:
            return resp.json()
        log.warning("GET %s → %d", path, resp.status_code)
        return None
    except requests.RequestException as e:
        log.warning("GET %s failed: %s", path, e)
        return None


def api_patch(path: str, data: dict) -> dict | None:
    try:
        resp = session.patch(f"{API_URL}{path}", json=data, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 409:
            return None  # Lost race — another worker claimed it
        log.warning("PATCH %s → %d: %s", path, resp.status_code, resp.text[:200])
        return None
    except requests.RequestException as e:
        log.warning("PATCH %s failed: %s", path, e)
        return None


def api_upload(path: str, filename: str, content: bytes, metadata: dict) -> bool:
    try:
        files = {"file": (filename, io.BytesIO(content), "application/octet-stream")}
        data = {k: v for k, v in metadata.items() if v is not None}
        # Use a clean request without the session's Content-Type header
        # (requests lib sets correct multipart boundary when files= is used)
        headers = {k: v for k, v in session.headers.items() if k.lower() != "content-type"}
        resp = requests.post(
            f"{API_URL}{path}",
            files=files,
            data=data,
            headers=headers,
            timeout=30,
        )
        if resp.status_code in (200, 201):
            return True
        log.warning("Upload %s → %d: %s", filename, resp.status_code, resp.text[:200])
        return False
    except requests.RequestException as e:
        log.warning("Upload %s failed: %s", filename, e)
        return False


# ---------------------------------------------------------------------------
# Product target resolution
# ---------------------------------------------------------------------------

def get_targets_for_job(job: dict) -> list[dict]:
    """Resolve product targets (appId, role, processor) for a build job."""
    product_id = job.get("productId")
    if not product_id:
        return DEFAULT_TARGETS

    if product_id in _target_cache:
        return _target_cache[product_id]

    resp = api_get(f"/v2/products/{product_id}")
    if not resp:
        _target_cache[product_id] = DEFAULT_TARGETS
        return DEFAULT_TARGETS

    product_data = resp.get("data", resp)
    targets = []

    # Extract targets from board revisions
    boards = product_data.get("boards") or []
    for board in boards:
        for rev in board.get("revisions") or []:
            for target in rev.get("targets") or []:
                targets.append({
                    "role": target.get("role", "app"),
                    "soc": target.get("soc", "unknown"),
                    "appId": target.get("appId", 0),
                    "processor": target.get("soc", "unknown").lower(),
                })

    if not targets:
        targets = DEFAULT_TARGETS

    _target_cache[product_id] = targets
    return targets


# ---------------------------------------------------------------------------
# Artifact generation
# ---------------------------------------------------------------------------

def generate_intel_hex(size: int = 64) -> bytes:
    """Generate a minimal valid Intel HEX file."""
    lines = [
        ":020000040000FA",  # Extended linear address 0x0000
        f":10000000{'AA' * 16}",  # 16 bytes of data at address 0
        ":00000001FF",  # EOF record
    ]
    # Fix checksum for data line
    data_bytes = bytes([0x10, 0x00, 0x00, 0x00] + [0xAA] * 16)
    checksum = (~sum(data_bytes) + 1) & 0xFF
    lines[1] = f":10000000{'AA' * 16}{checksum:02X}"
    return "\n".join(lines).encode()


def generate_cfw_placeholder() -> bytes:
    """Generate a minimal CFW placeholder (binary header)."""
    # Real CFW has a structured header, but the API-side validator
    # only checks that the file exists and has the right metadata.
    return b"\x00" * 128


def generate_manifest(job: dict, targets: list[dict], version: str) -> bytes:
    """Generate a build.json manifest."""
    manifest = {
        "schemaVersion": 2,
        "product": job.get("product") or "alpha",
        "board": job.get("board") or "alpha_b0",
        "version": version,
        "variant": job.get("variant") or "release",
        "track": "BM",
        "matrixLabel": job.get("matrixLabel"),
        "commitSha": job.get("commitSha"),
        "branch": job.get("branch") or "main",
        "buildNum": job.get("buildNum") or 1,
        "worker": WORKER_ID,
        "builtAt": datetime.now(timezone.utc).isoformat(),
        "targets": [
            {
                "role": t["role"],
                "processor": t["processor"],
                "appId": t["appId"],
                "hexFile": f"{t['appId']}.{version}.hex",
            }
            for t in targets
        ],
    }
    return json.dumps(manifest, indent=2).encode()


def generate_and_upload_artifacts(job: dict) -> tuple[bool, str]:
    """Generate placeholder artifacts and upload them. Returns (success, version_string)."""
    job_id = job["id"]
    targets = get_targets_for_job(job)
    config_flags = job.get("configFlags") or {}
    produces_hex = config_flags.get("produces_hex", True)
    produces_cfw = config_flags.get("produces_cfw", False)
    build_num = job.get("buildNum") or 1
    version = f"0.0.{build_num}"

    # Determine which target this build is for based on fw_type
    fw_type = job.get("target") or "app"  # "app", "mfg", "driver_test"

    uploaded = 0
    failed = 0

    for target in targets:
        role = target["role"]
        processor = target["processor"]
        app_id = target["appId"]

        # For mfg builds, use both targets. For app builds, use the matching role.
        if fw_type == "app" and role == "comms":
            # App builds target the app processor, but still produce comms artifacts
            pass  # Include all targets for completeness

        if produces_hex:
            hex_name = f"{app_id}.{version}.hex"
            hex_data = generate_intel_hex()
            ok = api_upload(
                f"/v2/builds/{job_id}/artifacts",
                hex_name, hex_data,
                {"role": role, "processor": processor, "artifactType": "plaintextHex"},
            )
            if ok:
                uploaded += 1
                log.info("  Uploaded %s (%s/%s)", hex_name, role, processor)
            else:
                failed += 1

        if produces_cfw:
            cfw_name = f"{app_id}.{version}-BM.cfw"
            cfw_data = generate_cfw_placeholder()
            ok = api_upload(
                f"/v2/builds/{job_id}/artifacts",
                cfw_name, cfw_data,
                {"role": role, "processor": processor, "artifactType": "encryptedCfw"},
            )
            if ok:
                uploaded += 1
                log.info("  Uploaded %s (%s/%s)", cfw_name, role, processor)
            else:
                failed += 1

    # Upload manifest
    manifest_data = generate_manifest(job, targets, version)
    ok = api_upload(
        f"/v2/builds/{job_id}/artifacts",
        "build.json", manifest_data,
        {"role": "manifest", "artifactType": "manifest"},
    )
    if ok:
        uploaded += 1
    else:
        failed += 1

    # Version string: use first target's appId for the canonical version
    primary_app_id = targets[0]["appId"] if targets else 109
    version_string = f"{primary_app_id}.{version}-BM"

    log.info("  Artifacts: %d uploaded, %d failed", uploaded, failed)
    return failed == 0, version_string


# ---------------------------------------------------------------------------
# Build processing
# ---------------------------------------------------------------------------

def process_job(job: dict) -> bool:
    """Process a single build job: claim → simulate → upload → report."""
    job_id = job["id"]
    label = job.get("matrixLabel") or "unknown"
    variant = job.get("variant") or "?"
    target = job.get("target") or "?"

    log.info("Claiming job %s (%s, %s/%s)...", job_id[:8], label, target, variant)

    # Step 1: Claim (QUEUED → CLONING)
    result = api_patch(f"/v2/builds/{job_id}", {
        "status": "CLONING",
        "workerId": WORKER_ID,
    })
    if not result:
        log.info("  Lost race on %s (already claimed)", job_id[:8])
        return False

    # Step 2: Report BUILDING
    started_at = datetime.now(timezone.utc)
    api_patch(f"/v2/builds/{job_id}", {
        "status": "BUILDING",
        "startedAt": started_at.isoformat(),
    })
    log.info("  Building %s (%s)...", job_id[:8], label)

    # Step 3: Simulate build
    delay = random.uniform(BUILD_DELAY_MIN, BUILD_DELAY_MAX)
    time.sleep(delay)

    # Step 4: Generate and upload artifacts
    success, version_string = generate_and_upload_artifacts(job)

    # Step 5: Report result
    finished_at = datetime.now(timezone.utc)
    duration = int((finished_at - started_at).total_seconds())

    if success:
        api_patch(f"/v2/builds/{job_id}", {
            "status": "SUCCESS",
            "versionString": version_string,
            "finishedAt": finished_at.isoformat(),
            "durationSeconds": duration,
        })
        log.info("  ✓ %s SUCCESS (%s) in %ds", job_id[:8], label, duration)
    else:
        api_patch(f"/v2/builds/{job_id}", {
            "status": "FAILED",
            "errorMessage": "Dev worker: artifact upload failed",
            "finishedAt": finished_at.isoformat(),
            "durationSeconds": duration,
        })
        log.warning("  ✗ %s FAILED (%s)", job_id[:8], label)

    return success


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def poll_once() -> int:
    """Poll for QUEUED jobs and process them. Returns number processed."""
    resp = api_get("/v2/builds?status=QUEUED&limit=5")
    if not resp:
        return 0

    # Unwrap the double envelope: {"data": {"data": [...], "pagination": {...}}}
    outer = resp.get("data", resp)
    if isinstance(outer, dict):
        jobs = outer.get("data", [])
    elif isinstance(outer, list):
        jobs = outer
    else:
        jobs = []

    if not jobs:
        return 0

    log.info("Found %d QUEUED job(s)", len(jobs))
    processed = 0
    for job in jobs:
        if process_job(job):
            processed += 1

    return processed


def main():
    log.info("╔══════════════════════════════════════════╗")
    log.info("║  Concord Dev Build Worker                ║")
    log.info("╠══════════════════════════════════════════╣")
    log.info("║  API:     %-30s ║", API_URL)
    log.info("║  Worker:  %-30s ║", WORKER_ID)
    log.info("║  Poll:    every %ds%-24s║", POLL_INTERVAL, "")
    log.info("╚══════════════════════════════════════════╝")

    # Wait for API to be ready
    log.info("Waiting for API at %s...", API_URL)
    for attempt in range(60):
        try:
            resp = session.get(f"{API_URL}/v2/docs", timeout=3)
            if resp.status_code == 200:
                log.info("API is ready!")
                break
        except requests.RequestException:
            pass
        time.sleep(2)
    else:
        log.error("API not reachable after 120s, starting anyway...")

    # Poll loop
    while True:
        try:
            poll_once()
        except KeyboardInterrupt:
            log.info("Shutting down...")
            break
        except Exception as e:
            log.error("Poll error: %s", e)

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
