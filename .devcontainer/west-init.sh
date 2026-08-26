#!/usr/bin/env bash
# Initialize the pinned west workspace inside the devcontainer.
# Idempotent: a second run updates, it does not re-init.
# FAIL-NOT-SKIP: a missing tool is a failure that names the tool.
set -euo pipefail

for tool in west git cmake; do
    command -v "$tool" >/dev/null 2>&1 || {
        echo "FAIL: '$tool' not found in the devcontainer image" >&2
        exit 1
    }
done

if [ ! -d .west ]; then
    west init -l ws
fi
west update --narrow

echo "west workspace ready:"
west list -f '{name:20} {revision:12} {path}'
