#!/usr/bin/env python3
"""
Simulate a TeamCity build-server → Concord validation trigger flow.

Mimics the CI pipeline: creates a validation run, then triggers a K8s Job
to execute the validation tests. Useful for local E2E testing without TeamCity.

Usage:
    python3 scripts/simulate-build-trigger.py \
        --api-url http://localhost:9001 \
        --product-id prod-1 \
        --node-id node-1 \
        --serial-number 70B3D584C01E1FCC \
        --build-dir apps/firmware/products/build-server/0.1.12

    # With --wait to poll until completion:
    python3 scripts/simulate-build-trigger.py ... --wait
"""

import argparse
import json
import os
import sys
import time
import zipfile

import requests


def read_commit_log(build_dir: str) -> str:
    """Read commit.log from the build directory."""
    path = os.path.join(build_dir, "commit.log")
    if os.path.isfile(path):
        with open(path) as f:
            return f.read().strip()
    return ""


def zip_build_dir(build_dir: str) -> str:
    """Zip the build directory contents and return the temp zip path."""
    zip_path = os.path.join(build_dir, "_build.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(build_dir):
            for fname in files:
                if fname == "_build.zip":
                    continue
                full_path = os.path.join(root, fname)
                arcname = os.path.relpath(full_path, build_dir)
                zf.write(full_path, arcname)
    return zip_path


def extract_firmware_version(build_dir: str) -> str:
    """Extract firmware version from the build directory name."""
    return os.path.basename(os.path.normpath(build_dir))


def create_run(api_url: str, token: str, name: str, product_id: str,
               node_id: str, serial_number: str, firmware_variant: str,
               notes: str) -> dict:
    """POST /v2/sessions — create a new validation run."""
    resp = requests.post(
        f"{api_url}/v2/sessions",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "name": name,
            "productId": product_id,
            "nodeId": node_id,
            "serialNumber": serial_number,
            "firmwareVariant": firmware_variant,
            "notes": notes,
        },
    )
    resp.raise_for_status()
    return resp.json()["data"]


def trigger_run(api_url: str, token: str, run_id: str,
                firmware_version: str, firmware_path: str = "") -> dict:
    """POST /v2/sessions/<run_id>/trigger — trigger K8s job."""
    body = {"firmwareVersion": firmware_version}
    if firmware_path:
        body["firmwarePath"] = firmware_path
    resp = requests.post(
        f"{api_url}/v2/sessions/{run_id}/trigger",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=body,
    )
    resp.raise_for_status()
    return resp.json()["data"]


def get_run(api_url: str, token: str, run_id: str) -> dict:
    """GET /v2/sessions/<run_id> — fetch run status."""
    resp = requests.get(
        f"{api_url}/v2/sessions/{run_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    resp.raise_for_status()
    return resp.json()["data"]


def poll_until_complete(api_url: str, token: str, run_id: str,
                        interval: int = 10, timeout: int = 600) -> dict:
    """Poll the run until it reaches a terminal status."""
    terminal = {"COMPLETED", "CANCELLED", "FAILED"}
    start = time.time()

    while time.time() - start < timeout:
        run = get_run(api_url, token, run_id)
        status = run.get("status", "UNKNOWN")
        completed = run.get("completedCount", 0)
        target = run.get("targetCount", 0)
        passed = run.get("passedCount", 0)
        failed = run.get("failedCount", 0)

        print(f"  [{status}] {completed}/{target} tests — {passed}P {failed}F", flush=True)

        if status in terminal:
            return run

        time.sleep(interval)

    print(f"  Timeout after {timeout}s — run still not complete", file=sys.stderr)
    return get_run(api_url, token, run_id)


def main():
    parser = argparse.ArgumentParser(
        description="Simulate a TeamCity → Concord validation trigger flow."
    )
    parser.add_argument("--api-url", required=True, help="Concord API base URL (e.g., http://localhost:9001)")
    parser.add_argument("--token", required=True, help="JWT or API key for authentication")
    parser.add_argument("--product-id", required=True, help="Concord product ID")
    parser.add_argument("--node-id", required=True, help="MTIB node ID")
    parser.add_argument("--serial-number", required=True, help="DUT serial number")
    parser.add_argument("--build-dir", default="apps/firmware/products/build-server/0.1.12",
                        help="Build directory with firmware artifacts (default: build-server/0.1.12)")
    parser.add_argument("--firmware-variant", default="debug", help="Firmware variant (default: debug)")
    parser.add_argument("--wait", action="store_true", help="Poll until run completes")
    parser.add_argument("--poll-interval", type=int, default=10, help="Polling interval in seconds (default: 10)")
    parser.add_argument("--timeout", type=int, default=600, help="Max wait time in seconds (default: 600)")

    args = parser.parse_args()

    build_dir = os.path.abspath(args.build_dir)
    if not os.path.isdir(build_dir):
        print(f"Error: build directory not found: {build_dir}", file=sys.stderr)
        sys.exit(1)

    fw_version = extract_firmware_version(build_dir)
    commit_log = read_commit_log(build_dir)

    print(f"Build directory: {build_dir}")
    print(f"Firmware version: {fw_version}")
    if commit_log:
        print(f"Commit: {commit_log.splitlines()[0]}")
    print()

    # Step 1: Create validation run
    run_name = f"Sim {fw_version} {args.firmware_variant}"
    notes = f"Simulated trigger from build-server/{fw_version}\n{commit_log}"

    print("1. Creating validation run...")
    run = create_run(
        api_url=args.api_url,
        token=args.token,
        name=run_name,
        product_id=args.product_id,
        node_id=args.node_id,
        serial_number=args.serial_number,
        firmware_variant=args.firmware_variant,
        notes=notes,
    )
    run_id = run["id"]
    print(f"   Run created: {run_id}")
    print(f"   View: {args.api_url.replace('/v2', '')}/validation/runs/{run_id}")
    print()

    # Step 2: Trigger the run
    print("2. Triggering K8s validation job...")
    result = trigger_run(
        api_url=args.api_url,
        token=args.token,
        run_id=run_id,
        firmware_version=fw_version,
    )
    job_name = result.get("jobName", "unknown")
    print(f"   K8s job created: {job_name}")
    print()

    # Step 3: Optionally wait for completion
    if args.wait:
        print("3. Polling for completion...")
        final = poll_until_complete(
            api_url=args.api_url,
            token=args.token,
            run_id=run_id,
            interval=args.poll_interval,
            timeout=args.timeout,
        )
        print()
        print("Final result:")
        print(f"  Status:    {final.get('status')}")
        print(f"  Passed:    {final.get('passedCount', 0)}")
        print(f"  Failed:    {final.get('failedCount', 0)}")
        print(f"  Total:     {final.get('completedCount', 0)}/{final.get('targetCount', 0)}")
    else:
        print("Done. Use --wait to poll until completion.")
        print(f"  Monitor: GET {args.api_url}/v2/sessions/{run_id}")


if __name__ == "__main__":
    main()
