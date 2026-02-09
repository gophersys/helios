#!/bin/bash
# Sync proto stubs from the monorepo's canonical location into the MCP server package.
# Run this after regenerating proto files in libs/protocols/mtib_v2/.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SRC_DIR="$SCRIPT_DIR/../../../libs/protocols/mtib_v2"
DST_DIR="$SCRIPT_DIR/src/mtib_mcp/proto"

if [ ! -f "$SRC_DIR/mtib_v2_pb2.py" ]; then
    echo "ERROR: Source proto stubs not found at $SRC_DIR"
    echo "Run 'npx prisma generate' or the proto compiler first."
    exit 1
fi

# The local proto imports use 'protocols.mtib_v2.mtib_v2_pb2' but the MCP
# server package needs relative imports ('from . import mtib_v2_pb2').
# We copy and patch the import path.

cp "$SRC_DIR/mtib_v2_pb2.py" "$DST_DIR/mtib_v2_pb2.py"

# Patch the grpc file to use relative imports
sed 's/^import protocols\.mtib_v2\.mtib_v2_pb2 as mtib__v2__pb2$/from . import mtib_v2_pb2 as mtib__v2__pb2/' \
    "$SRC_DIR/mtib_v2_pb2_grpc.py" > "$DST_DIR/mtib_v2_pb2_grpc.py"

echo "Synced proto stubs from $SRC_DIR -> $DST_DIR"
