#!/usr/bin/env python3
"""Idempotently enforce required qBittorrent.conf settings.

Runs as an initContainer before qBittorrent starts (see the qbittorrent
Deployment). It guarantees the settings that make downloads work survive a
config-PVC rebuild — without them, torrent traffic leaks to eth0 and Gluetun's
kill-switch drops everything (see docs/debt-register.md, D1).

Surgical by design: only the REQUIRED keys are touched; every other line is
preserved. qBittorrent rewrites this file in its own style on clean shutdown,
so our formatting is transient — all that matters is the keys are correct when
qBittorrent starts.
"""
import os
import sys

# The exact settings we reconcile. Section -> { key: value }.
REQUIRED = {
    "BitTorrent": {
        # Bind the BitTorrent engine to the VPN interface. Without this,
        # traffic egresses via eth0 and the kill-switch blocks it.
        "Session\\Interface": "tun0",
        "Session\\InterfaceName": "tun0",
    },
    "Preferences": {
        # Let in-cluster clients (Prowlarr, Homepage widget) reach the API
        # without a password — the pod network is already trusted.
        "WebUI\\AuthSubnetWhitelist": "10.42.0.0/16",
        "WebUI\\AuthSubnetWhitelistEnabled": "true",
        "WebUI\\LocalHostAuth": "false",
    },
}


def _key_of(line):
    return line.split("=", 1)[0].strip() if "=" in line else None


def enforce_config(text, required=REQUIRED):
    """Return `text` with every REQUIRED entry present and correct.

    Preserves all unrelated lines and section order; idempotent.
    """
    preamble = []
    sections = []            # list of [name, [lines...]] preserving order
    current = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            current = [stripped[1:-1], []]
            sections.append(current)
        else:
            (current[1] if current is not None else preamble).append(line)

    by_name = {name: lines for name, lines in sections}
    for section, kvs in required.items():
        if section not in by_name:
            new = []
            sections.append([section, new])
            by_name[section] = new
        lines = by_name[section]
        for key, val in kvs.items():
            for i, ln in enumerate(lines):
                if _key_of(ln) == key:
                    if ln.split("=", 1)[1].strip() != val:
                        lines[i] = f"{key}={val}"
                    break
            else:
                lines.append(f"{key}={val}")

    out = list(preamble)
    for name, lines in sections:
        out.append(f"[{name}]")
        out.extend(lines)
    result = "\n".join(out)
    if out:
        result += "\n"
    return result


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else \
        "/config/qBittorrent/qBittorrent.conf"
    try:
        with open(path, encoding="utf-8") as f:
            original = f.read()
    except FileNotFoundError:
        original = ""
    updated = enforce_config(original)
    if updated != original:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(updated)
        print(f"enforce_qbt: reconciled {path}")
    else:
        print(f"enforce_qbt: {path} already compliant")


if __name__ == "__main__":
    main()
