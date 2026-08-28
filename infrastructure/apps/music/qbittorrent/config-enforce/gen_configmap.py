#!/usr/bin/env python3
"""Render the qbittorrent-config-enforce ConfigMap from enforce_qbt.py.

enforce_qbt.py is the single source of truth (it's the tested code). The
committed ConfigMap (../15-config-enforce.configmap.yaml) is generated from it
so the two can never drift — test_enforce_qbt.py asserts the committed file
equals this renderer's output.

Regenerate:  python3 gen_configmap.py > ../15-config-enforce.configmap.yaml
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT_PATH = os.path.join(HERE, "enforce_qbt.py")
CONFIGMAP_PATH = os.path.join(HERE, os.pardir, "15-config-enforce.configmap.yaml")

HEADER = (
    "# GENERATED from config-enforce/enforce_qbt.py — do not edit by hand.\n"
    "# Regenerate: python3 config-enforce/gen_configmap.py > "
    "15-config-enforce.configmap.yaml\n"
)


def render():
    with open(SCRIPT_PATH, encoding="utf-8") as f:
        script = f.read()
    body = "\n".join(("    " + ln) if ln else "" for ln in script.splitlines())
    return (
        HEADER
        + "apiVersion: v1\n"
        + "kind: ConfigMap\n"
        + "metadata:\n"
        + "  name: qbittorrent-config-enforce\n"
        + "  namespace: media\n"
        + "  labels:\n"
        + "    app: qbittorrent\n"
        + "    app.kubernetes.io/part-of: music\n"
        + "data:\n"
        + "  enforce_qbt.py: |\n"
        + body + "\n"
    )


if __name__ == "__main__":
    print(render(), end="")
