#!/usr/bin/env python3
"""Prune old ghcr versions of workspaces-api. Build-push with provenance creates
THREE versions per build: the tagged OCI index + two UNTAGGED children (the
arch image + the provenance attestation) that the index references by digest.
A flat "keep newest N versions" therefore splits a kept index from its children
and corrupts the retained image (verified against live GHCR).

Retention model (manifest-graph-safe without registry API calls):
  - keep the KEEP most-recent TAGGED versions (plus anything tagged `latest`);
  - delete tagged versions beyond KEEP;
  - delete UNTAGGED versions only if strictly older than the oldest kept tagged
    version minus MARGIN. Children are pushed seconds before their index, so
    children of every kept tag always survive; orphans of pruned tags fall out
    of the window and are GC'd on a later run. Deleting a stale untagged child
    a run late is harmless; deleting a live one is not — err old.
App-token friendly (per-package endpoints only)."""
import json, os, urllib.request
from datetime import datetime, timedelta, timezone

TOKEN = os.environ["GH_TOKEN"]
PKG = os.environ.get("PKG", "workspaces-api")
KEEP = int(os.environ.get("KEEP", "8"))
MARGIN = timedelta(hours=int(os.environ.get("MARGIN_HOURS", "6")))
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


def ts(v):
    return datetime.fromisoformat(v["updated_at"].replace("Z", "+00:00"))


versions, page = [], 1
while True:
    batch = api("GET", f"{BASE}?per_page=100&page={page}")
    versions += batch
    if len(batch) < 100:
        break
    page += 1

def tags_of(v):
    return v.get("metadata", {}).get("container", {}).get("tags", [])

tagged = sorted((v for v in versions if tags_of(v)), key=ts, reverse=True)
untagged = [v for v in versions if not tags_of(v)]

if not tagged:
    print(f"total={len(versions)} — no tagged versions; refusing to prune (nothing to anchor the window)")
    raise SystemExit(0)

keep_tagged = {v["id"] for v in tagged[:KEEP]} | {v["id"] for v in tagged if "latest" in tags_of(v)}
oldest_kept = min(ts(v) for v in tagged if v["id"] in keep_tagged)
cutoff = oldest_kept - MARGIN

drop = [v for v in tagged if v["id"] not in keep_tagged]
drop += [v for v in untagged if ts(v) < cutoff]

print(f"total={len(versions)} tagged={len(tagged)} keep_tagged={len(keep_tagged)} "
      f"cutoff={cutoff.isoformat()} drop={len(drop)} dry_run={DRY}")
for v in drop:
    print(f"  {'WOULD DELETE' if DRY else 'DELETING'} id={v['id']} tags={tags_of(v) or '(untagged)'} updated={v['updated_at']}")
    if not DRY:
        api("DELETE", f"{BASE}/{v['id']}")
print("done")
