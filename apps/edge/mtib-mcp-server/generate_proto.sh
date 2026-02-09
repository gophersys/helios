#!/usr/bin/env bash
# Generate Python gRPC stubs from mtib_v2.proto
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROTO_SRC="${1:-$HOME/mtib_v2/mtib_v2.proto}"
OUT_DIR="$SCRIPT_DIR/src/mtib_mcp/proto"

python3 -m grpc_tools.protoc \
    --proto_path="$(dirname "$PROTO_SRC")" \
    --python_out="$OUT_DIR" \
    --grpc_python_out="$OUT_DIR" \
    "$(basename "$PROTO_SRC")"

# Fix relative import in generated grpc stub
sed -i 's/^import mtib_v2_pb2/from . import mtib_v2_pb2/' "$OUT_DIR/mtib_v2_pb2_grpc.py"

echo "Generated stubs in $OUT_DIR"
