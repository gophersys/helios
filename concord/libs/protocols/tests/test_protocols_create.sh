#!/bin/bash
#
# libs/protocols/tests/test_protocols_create.sh
#
# Regression test for ctl.sh — verifies that `nx run protocols:create`
# (and the underlying `./libs/protocols/ctl.sh generate`) ALWAYS
# produces the expected *_pb2.py / *_pb2_grpc.py files for every
# .proto under libs/protocols/.
#
# The v0.12.11 production outage was caused by ctl.sh silently no-op'ing
# under `set -u` (an unbound-variable read in `gather_proto_files`).
# The script reported success but produced zero files; the http-api
# Docker image then shipped without the protobuf stubs and crashed at
# startup on ModuleNotFoundError. This test exists to catch that class
# of regression.
#
# Run with: nx run protocols:test  (or directly: bash libs/protocols/tests/test_protocols_create.sh)

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { echo -e "  ${GREEN}PASS${NC}  $*"; }
fail() { echo -e "  ${RED}FAIL${NC}  $*" >&2; exit 1; }

# ── 1. Clean slate ────────────────────────────────────────────────
echo "[test] Cleaning generated files…"
./libs/protocols/ctl.sh clean

# Confirm clean removed the expected files (and only those)
test ! -f libs/protocols/mtib/mtib_pb2.py     || fail "mtib_pb2.py survived clean"
test ! -f libs/protocols/mtib/mtib_pb2_grpc.py || fail "mtib_pb2_grpc.py survived clean"
test -f   libs/protocols/mtib/mtib.proto       || fail "mtib.proto unexpectedly deleted by clean"
test -f   libs/protocols/mtib/__init__.py      || fail "__init__.py unexpectedly deleted by clean (must survive)"
pass "clean removed generated files but preserved sources + __init__.py"

# ── 2. Generate ───────────────────────────────────────────────────
echo "[test] Running generate…"
./libs/protocols/ctl.sh generate

# Every .proto under libs/protocols/ must produce both stubs
mapfile -t PROTOS < <(find libs/protocols -name '*.proto')
test ${#PROTOS[@]} -gt 0 || fail "no .proto files found under libs/protocols/"

for protofile in "${PROTOS[@]}"; do
    dir=$(dirname "$protofile")
    base=$(basename "$protofile" .proto)
    test -f "${dir}/${base}_pb2.py"      || fail "missing ${dir}/${base}_pb2.py after generate"
    test -f "${dir}/${base}_pb2_grpc.py" || fail "missing ${dir}/${base}_pb2_grpc.py after generate"
    pass "${base}.proto → both stubs generated"
done

# ── 3. The actual import that http-api does at startup ────────────
echo "[test] Verifying http-api's runtime import works…"
PYTHONPATH=libs python3 -c "from protocols.mtib.mtib_pb2 import Empty" \
    || fail "from protocols.mtib.mtib_pb2 import Empty FAILED — this is exactly the v0.12.11 crash"
PYTHONPATH=libs python3 -c "from protocols.mtib.mtib_pb2_grpc import MtibV1Stub" \
    || fail "from protocols.mtib.mtib_pb2_grpc import MtibV1Stub FAILED"
pass "http-api startup imports resolve"

# ── 4. Empty-proto-set failure (negative test) ────────────────────
echo "[test] Verifying generate fails loudly when no .proto files exist…"
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT
# Copy a temp libs/protocols/ with no protos, point ctl.sh at it
mkdir -p "$TMPDIR/libs/protocols/empty"
cp libs/protocols/ctl.sh "$TMPDIR/libs/protocols/ctl.sh"
(
    cd "$TMPDIR"
    if ./libs/protocols/ctl.sh generate >/dev/null 2>&1; then
        echo "  FAIL  ctl.sh generate succeeded with zero .proto files — should have failed loudly" >&2
        exit 1
    fi
)
pass "ctl.sh generate exits non-zero when no protos are found"

echo
echo -e "${GREEN}All protocols regression tests passed.${NC}"
