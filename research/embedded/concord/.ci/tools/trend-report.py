#!/usr/bin/env python3
"""Historical trend tracker for AI review reports.

Reads current run findings from /tmp/ai-review/*.json, compares against
previous runs (fetched from MinIO), computes trends, and uploads a
dashboard-ready snapshot.

Output schema (designed for visualization in Grafana/custom dashboards):
{
  "generated_at": "ISO timestamp",
  "current_run": {
    "timestamp": "ISO",
    "branch": "string",
    "commit": "string",
    "stages": [{ stage, verdict, severity, issues, cost_usd }],
    "totals": { issues, cost_usd, passed, failed }
  },
  "history": [
    { "timestamp", "commit", "totals": { issues, cost_usd, passed, failed } }
  ],
  "trends": {
    "issue_direction": "rising|falling|stable",
    "cost_direction": "rising|falling|stable",
    "issue_7d_avg": float,
    "cost_7d_avg": float,
    "recurring_files": [{ file, count, stages }],
    "severity_distribution": { critical: N, high: N, ... }
  },
  "hotspots": [
    { "file": "path", "appearances": N, "severities": ["critical", ...] }
  ]
}

Usage:
    python3 .ci/tools/trend-report.py \\
        --reports-dir /tmp/ai-review \\
        --minio-endpoint http://concord-minio.staging.svc:9000 \\
        --minio-access-key key --minio-secret-key secret \\
        --minio-bucket devops
"""
import argparse
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def load_current_reports(reports_dir: Path) -> list[dict]:
    """Load AI review stage reports from the current run."""
    reports = []
    skip = {"trend-report.json", "summary.json", "serializer-check.json"}
    for f in sorted(reports_dir.glob("*.json")):
        if f.name in skip:
            continue
        try:
            data = json.loads(f.read_text())
            if "stage" in data and "verdict" in data:
                reports.append(data)
        except (json.JSONDecodeError, KeyError):
            continue
    return reports


def fetch_previous_snapshots(endpoint: str, access_key: str, secret_key: str,
                              bucket: str, limit: int = 14) -> list[dict]:
    """Fetch up to `limit` previous trend snapshots from MinIO."""
    if not all([endpoint, access_key, secret_key]):
        return []

    try:
        subprocess.run(
            ["mc", "alias", "set", "trend-src", endpoint, access_key, secret_key, "--quiet"],
            capture_output=True, timeout=10, check=False
        )

        result = subprocess.run(
            ["mc", "ls", f"trend-src/{bucket}/trends/", "--json"],
            capture_output=True, text=True, timeout=30, check=False
        )

        keys = []
        for line in result.stdout.strip().splitlines():
            try:
                entry = json.loads(line)
                key = entry.get("key", "")
                if key.endswith(".json"):
                    keys.append(key)
            except json.JSONDecodeError:
                continue

        keys.sort(reverse=True)
        snapshots = []
        for k in keys[:limit]:
            dl = subprocess.run(
                ["mc", "cat", f"trend-src/{bucket}/trends/{k}"],
                capture_output=True, text=True, timeout=15, check=False
            )
            try:
                snapshots.append(json.loads(dl.stdout))
            except json.JSONDecodeError:
                continue

        return snapshots

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def compute_snapshot(current: list[dict], previous: list[dict]) -> dict:
    """Build a dashboard-ready trend snapshot."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Current run summary
    stages = []
    total_issues = 0
    total_cost = 0.0
    passed = 0
    failed = 0
    severity_dist: Counter = Counter()
    file_tracker: dict[str, list[str]] = {}  # file -> [stages it appeared in]

    for r in current:
        s = {
            "stage":    r.get("stage", "unknown"),
            "verdict":  r.get("verdict", "unknown"),
            "severity": r.get("severity", "info"),
            "issues":   r.get("issues", 0),
            "cost_usd": r.get("cost_usd", 0),
        }
        stages.append(s)
        total_issues += s["issues"]
        total_cost += s["cost_usd"]
        if s["verdict"] == "pass":
            passed += 1
        elif s["verdict"] == "fail":
            failed += 1

        # Track file-level hotspots
        for f in r.get("findings", []):
            sev = f.get("severity", "info")
            severity_dist[sev] += 1
            fp = f.get("file", "")
            if fp:
                file_tracker.setdefault(fp, []).append(s["stage"])

    current_run = {
        "timestamp": now,
        "branch":    current[0].get("branch", "unknown") if current else "unknown",
        "commit":    current[0].get("commit", "unknown") if current else "unknown",
        "stages":    stages,
        "totals": {
            "issues":  total_issues,
            "cost_usd": round(total_cost, 4),
            "passed":  passed,
            "failed":  failed,
        },
    }

    # Historical comparison
    history = []
    for snap in previous:
        cr = snap.get("current_run", {})
        history.append({
            "timestamp": cr.get("timestamp", ""),
            "commit":    cr.get("commit", ""),
            "totals":    cr.get("totals", {}),
        })

    # Trend computation
    prev_issues = [h["totals"].get("issues", 0) for h in history if h["totals"]]
    prev_costs = [h["totals"].get("cost_usd", 0) for h in history if h["totals"]]

    issue_avg = sum(prev_issues) / len(prev_issues) if prev_issues else total_issues
    cost_avg = sum(prev_costs) / len(prev_costs) if prev_costs else total_cost

    def direction(current_val: float, avg: float) -> str:
        if avg == 0:
            return "stable"
        ratio = current_val / avg
        if ratio > 1.2:
            return "rising"
        elif ratio < 0.8:
            return "falling"
        return "stable"

    # Hotspots: files appearing in multiple findings
    hotspots = []
    for fp, stage_list in sorted(file_tracker.items(), key=lambda x: -len(x[1])):
        if len(stage_list) >= 2 or fp in [h.get("file", "") for snap in previous
                                           for s in snap.get("current_run", {}).get("stages", [])
                                           for h in []]:  # simplified — just count current run
            hotspots.append({
                "file": fp,
                "appearances": len(stage_list),
                "stages": sorted(set(stage_list)),
            })

    return {
        "generated_at":  now,
        "current_run":   current_run,
        "history":       history[:14],
        "trends": {
            "issue_direction":       direction(total_issues, issue_avg),
            "cost_direction":        direction(total_cost, cost_avg),
            "issue_7d_avg":          round(issue_avg, 1),
            "cost_7d_avg":           round(cost_avg, 4),
            "severity_distribution": dict(severity_dist),
        },
        "hotspots": hotspots[:20],
    }


def upload(snapshot: dict, endpoint: str, access_key: str,
           secret_key: str, bucket: str, commit: str) -> bool:
    """Upload trend snapshot to MinIO at devops/trends/{date}-{commit}.json."""
    if not all([endpoint, access_key, secret_key]):
        return False

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    filename = f"{date_str}-{commit[:7]}.json"
    local_path = Path(f"/tmp/ai-review/trend-snapshot.json")
    local_path.write_text(json.dumps(snapshot, indent=2))

    try:
        subprocess.run(
            ["mc", "alias", "set", "trend-src", endpoint, access_key, secret_key, "--quiet"],
            capture_output=True, timeout=10, check=False
        )
        subprocess.run(
            ["mc", "mb", "-p", f"trend-src/{bucket}"],
            capture_output=True, timeout=10, check=False
        )
        r = subprocess.run(
            ["mc", "cp", str(local_path), f"trend-src/{bucket}/trends/{filename}", "--quiet"],
            capture_output=True, timeout=15, check=False
        )
        return r.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def main():
    p = argparse.ArgumentParser(description="AI review trend tracker")
    p.add_argument("--reports-dir", default="/tmp/ai-review")
    p.add_argument("--minio-endpoint", default="")
    p.add_argument("--minio-access-key", default="")
    p.add_argument("--minio-secret-key", default="")
    p.add_argument("--minio-bucket", default="devops")
    args = p.parse_args()

    reports_dir = Path(args.reports_dir)
    current = load_current_reports(reports_dir)
    if not current:
        print("No AI review reports found")
        sys.exit(0)

    print(f"Current run: {len(current)} stage(s)")

    previous = fetch_previous_snapshots(
        args.minio_endpoint, args.minio_access_key,
        args.minio_secret_key, args.minio_bucket
    )
    print(f"Historical:  {len(previous)} previous snapshot(s)")

    snapshot = compute_snapshot(current, previous)

    # Save locally
    out = reports_dir / "trend-report.json"
    out.write_text(json.dumps(snapshot, indent=2))

    # Print summary
    t = snapshot["current_run"]["totals"]
    tr = snapshot["trends"]
    print(f"Issues:      {t['issues']} ({tr['issue_direction']}, 7d avg: {tr['issue_7d_avg']})")
    print(f"Cost:        ${t['cost_usd']:.4f} ({tr['cost_direction']}, 7d avg: ${tr['cost_7d_avg']:.4f})")
    print(f"Verdicts:    {t['passed']} passed, {t['failed']} failed")
    if tr["severity_distribution"]:
        print(f"Severities:  {dict(tr['severity_distribution'])}")
    if snapshot["hotspots"]:
        print(f"Hotspots:    {len(snapshot['hotspots'])} file(s) flagged across multiple stages")

    # Upload
    commit = subprocess.run(
        ["git", "rev-parse", "--short=7", "HEAD"],
        capture_output=True, text=True, check=False
    ).stdout.strip() or "unknown"

    if args.minio_endpoint and args.minio_access_key:
        if upload(snapshot, args.minio_endpoint, args.minio_access_key,
                  args.minio_secret_key, args.minio_bucket, commit):
            print(f"Uploaded:    trends/{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{commit}.json")
        else:
            print("Upload:      failed (non-fatal)")


if __name__ == "__main__":
    main()
