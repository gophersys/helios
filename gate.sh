#!/usr/bin/env bash
# The repository gate. This repo has ZERO CI — this script is the whole
# safety net, run inside the devcontainer. FAIL-NOT-SKIP: a missing tool,
# a missing workspace, or an empty check scope is a FAILURE that names
# itself, never a skip.
set -euo pipefail
cd "$(dirname "$0")"

fail() { echo "GATE FAIL: $*" >&2; exit 1; }

[ "${GOPHERSYS_DEVCONTAINER:-}" = "1" ] ||
    fail "must run inside the gophersys devcontainer (GOPHERSYS_DEVCONTAINER unset) — see .devcontainer/"

for tool in go west git; do
    command -v "$tool" >/dev/null 2>&1 || fail "missing tool: $tool"
done

[ -d ws/zephyr ] || fail "west workspace absent — run .devcontainer/west-init.sh first"

echo "── go vet + test (tools/sfd)"
( cd tools/sfd && go vet ./... && go test ./... -count=1 )

echo "── build sfd"
( cd tools/sfd && go build -o sfd . )

echo "── catalog verify against the pinned tree"
./tools/sfd/sfd verify --zephyr ws/zephyr --catalog catalog

echo "GATE OK"
