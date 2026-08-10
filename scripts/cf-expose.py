#!/usr/bin/env python3
"""Reconcile Cloudflare DNS to match contracts/exposure.yaml.

You should never click in the Cloudflare dashboard to publish a service. Declare
the hostname in contracts/exposure.yaml, run `apply`, then run
scripts/verify-exposure.sh. That is the whole workflow.

  cf-expose.py check    what would change (read-only)
  cf-expose.py apply    make Cloudflare match the declaration

Credentials come from the vault item shared/cloudflare/api-token and are never
printed. NOTE: that item's CLOUDFLARE_ZONE_ID is code-kit.dev's, not
mateosegura.com's (debt D19) — the zone is resolved by name here instead.
"""
import json
import os
import pathlib
import re
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent.parent
DECL = ROOT / "contracts" / "exposure.yaml"
TUNNEL = "04d7229c-33fe-4479-98f7-d36154dd9cbc"          # eden-home
TUNNEL_TARGET = f"{TUNNEL}.cfargotunnel.com"
HOMELAB_VIP = "10.168.0.240"
PROD_IP = "144.24.23.2"

# class -> (record type, content, proxied)
DESIRED = {
    "tailnet":       ("A", HOMELAB_VIP, False),
    "public-access": ("CNAME", TUNNEL_TARGET, True),
    "public-open":   ("CNAME", TUNNEL_TARGET, True),
    "direct-auth":   ("A", PROD_IP, False),
}

token = None
def creds():
    global token
    if token is None:
        out = subprocess.run(["bw", "get", "notes", "shared/cloudflare/api-token"],
                             capture_output=True, text=True, env=dict(os.environ)).stdout
        kv = dict(l.split("=", 1) for l in out.splitlines() if "=" in l)
        token = kv["CLOUDFLARE_API_TOKEN"].strip()
    return token


def call(method, url, body=None):
    req = urllib.request.Request(
        url, method=method,
        headers={"Authorization": f"Bearer {creds()}", "Content-Type": "application/json"},
        data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(req) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return json.load(e)


def parse_declaration():
    """Read hostname -> class out of exposure.yaml. Handles both the block form
    and the inline {class: x} form; deliberately avoids a yaml dependency so this
    runs on a bare CI image."""
    hosts, cur = {}, None
    zone = "mateosegura.com"
    for line in DECL.read_text().splitlines():
        m = re.match(r"^zone:\s*(\S+)", line)
        if m:
            zone = m.group(1)
        m = re.match(r"^  ([a-z0-9-]+):\s*\{.*class:\s*([a-z-]+)", line)
        if m:
            hosts[m.group(1)] = m.group(2); cur = None; continue
        m = re.match(r"^  ([a-z0-9-]+):\s*$", line)
        if m:
            cur = m.group(1); continue
        m = re.match(r"^    class:\s*([a-z-]+)", line)
        if m and cur:
            hosts[cur] = m.group(1); cur = None
    return zone, hosts


def main():
    action = sys.argv[1] if len(sys.argv) > 1 else "check"
    zone_name, declared = parse_declaration()
    z = call("GET", f"https://api.cloudflare.com/client/v4/zones?name={zone_name}")
    if not z.get("result"):
        print(f"cannot resolve zone {zone_name}", file=sys.stderr); return 1
    zid = z["result"][0]["id"]
    base = f"https://api.cloudflare.com/client/v4/zones/{zid}/dns_records"
    existing = {}
    for r in call("GET", base + "?per_page=200").get("result") or []:
        existing.setdefault(r["name"], []).append(r)

    changes = 0
    for host, klass in sorted(declared.items()):
        fq = f"{host}.{zone_name}"
        want = DESIRED.get(klass)
        if not want:
            print(f"  ?    {fq:34} unknown class '{klass}'"); continue
        rtype, content, proxied = want
        have = existing.get(fq, [])
        match = [r for r in have
                 if r["type"] == rtype and r["content"] == content and r["proxied"] == proxied]
        if match:
            print(f"  ok   {fq:34} {rtype} -> {content[:30]}")
            continue
        changes += 1
        if action != "apply":
            cur = ", ".join(f"{r['type']}->{r['content'][:24]}" for r in have) or "(absent, wildcard-served)"
            print(f"  DIFF {fq:34} want {rtype} -> {content[:30]} (proxied={proxied}); have {cur}")
            continue
        for r in have:                      # remove anything conflicting
            call("DELETE", f"{base}/{r['id']}")
            print(f"  del  {fq:34} {r['type']} -> {str(r['content'])[:30]}")
        d = call("POST", base, {"type": rtype, "name": fq, "content": content,
                                "proxied": proxied, "ttl": 1 if proxied else 300,
                                "comment": f"{klass}; declared in contracts/exposure.yaml"})
        print(f"  set  {fq:34} {rtype} -> {content[:30]}  ok={d.get('success')}")

    # the catch-all is part of the contract too
    wc = f"*.{zone_name}"
    if not any(r["type"] == "A" and r["content"] == PROD_IP for r in existing.get(wc, [])):
        changes += 1
        if action == "apply":
            d = call("POST", base, {"type": "A", "name": wc, "content": PROD_IP,
                                    "proxied": False, "ttl": 300,
                                    "comment": "catch-all -> prod cluster; explicit records override"})
            print(f"  set  {wc:34} A -> {PROD_IP}  ok={d.get('success')}")
        else:
            print(f"  DIFF {wc:34} want A -> {PROD_IP} (catch-all)")
    else:
        print(f"  ok   {wc:34} A -> {PROD_IP}")

    print(f"\n{'applied' if action == 'apply' else 'would change'}: {changes}")
    print("next: bash scripts/verify-exposure.sh")
    return 0


if __name__ == "__main__":
    sys.exit(main())
