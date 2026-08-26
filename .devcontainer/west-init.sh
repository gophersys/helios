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

# The workspace repos may be fetched by a different uid than later runs
# (container recreate, exec user change). Git then refuses with "dubious
# ownership" — mark each fetched repo safe, explicitly and only them,
# never a blanket '*'.
while read -r p; do
    [ "$p" = "ws" ] && continue
    dir="$(pwd)/$p"
    if ! git config --global --get-all safe.directory 2>/dev/null | grep -qx "$dir"; then
        git config --global --add safe.directory "$dir"
    fi
done < <(west list -f '{path}')

echo "west workspace ready:"
west list -f '{name:20} {revision:12} {path}'
