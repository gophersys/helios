#!/usr/bin/env python3
"""Prune old ghcr versions of workspaces-api (our single-arch image): keep :latest
+ the N most-recent, delete older. App-token friendly (per-package endpoints)."""
import json, os, urllib.request, urllib.error

TOKEN = os.environ["GH_TOKEN"]
PKG = os.environ.get("PKG", "workspaces-api")
KEEP = int(os.environ.get("KEEP", "8"))
DRY = os.environ.get("DRY_RUN", "true") != "false"
BASE = f"/orgs/gophersys/packages/container/{PKG}/versions"


def api(method, path):
    req = urllib.request.Request(
        "https://api.github.com" + path, method=method,
        headers={"Authorization": "token " + TOKEN,
                 "Accept": "application/vnd.github+json",
                 "X-GitHub-Api-Version": "2022-11-28"})
    with urllib.request.urlopen(req) as r:
        return json.load(r) if method == "GET" else None


versions, page = [], 1
while True:
    batch = api("GET", f"{BASE}?per_page=100&page={page}")
    versions += batch
    if len(batch) < 100:
        break
    page += 1

versions.sort(key=lambda v: v["updated_at"], reverse=True)
keep, kept = set(), 0
for v in versions:
    tags = v.get("metadata", {}).get("container", {}).get("tags", [])
    if "latest" in tags:
        keep.add(v["id"]); continue
    if kept < KEEP:
        keep.add(v["id"]); kept += 1

drop = [v for v in versions if v["id"] not in keep]
print(f"total={len(versions)} keep={len(keep)} drop={len(drop)} dry_run={DRY}")
for v in drop:
    tags = v.get("metadata", {}).get("container", {}).get("tags", []) or "(untagged)"
    print(f"  {'WOULD DELETE' if DRY else 'DELETING'} id={v['id']} tags={tags} updated={v['updated_at']}")
    if not DRY:
        api("DELETE", f"{BASE}/{v['id']}")
print("done")
