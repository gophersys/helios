#!/bin/bash

set -euo pipefail

NANOPB_PLUGIN_PATH="/ncs/modules/lib/nanopb/generator/protoc-gen-nanopb"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

log()  { echo -e "${GREEN}[proto]${NC} $*"; }
warn() { echo -e "${YELLOW}[proto]${NC} $*"; }
err()  { echo -e "${RED}[proto]${NC} $*" >&2; }
info() { echo -e "${CYAN}[proto]${NC} $*"; }

gather_proto_files() {
    local -A proto_map
    while IFS= read -r file; do
        name=$(basename "$file")
        if [[ -z "${proto_map[$name]}" ]]; then
            proto_map[$name]="$file"
        else
            warn "Duplicate proto file found: $file (using ${proto_map[$name]})"
        fi
    done < <(find libs/protocols -name '*.proto')

    printf '%s\n' "${proto_map[@]}"
}

get_proto_dirs() {
    local files=("$@")
    printf "%s\n" "${files[@]}" | xargs -n1 dirname | sort -u | xargs -n1 echo -I | tr '\n' ' '
}

generate_nanopb() {
    local -a proto_files=("$@")

    if [ ! -x "$NANOPB_PLUGIN_PATH" ]; then
        warn "nanopb plugin not found at $NANOPB_PLUGIN_PATH — skipping nanopb generation"
        return 0
    fi

    info "Generating nanopb code..."
    for protofile in "${proto_files[@]}"; do
        if [[ ! -f "$protofile" ]]; then
            continue
        fi
        local dir=$(dirname "$protofile")
        local includes=$(get_proto_dirs "${proto_files[@]}")

        protoc --plugin=protoc-gen-nanopb="$NANOPB_PLUGIN_PATH" \
               $includes \
               --nanopb_out="$dir" \
               "$protofile"
    done
}

generate_python() {
    local -a proto_files=("$@")
    local root_dir="libs/protocols"

    info "Generating Python protobuf and gRPC code..."

    if python3 -c "import grpc_tools.protoc" &> /dev/null; then
        for protofile in "${proto_files[@]}"; do
            if [[ ! -f "$protofile" ]]; then
                continue
            fi

            local dir=$(dirname "$protofile")
            echo "Processing: $protofile"

            local includes=$(get_proto_dirs "${proto_files[@]}")

            protoc --python_out="$dir" --proto_path="$dir" $includes "$protofile"
            python3 -m grpc_tools.protoc --grpc_python_out="$dir" --proto_path="$dir" $includes "$protofile" -I"$dir"

            local base_name=$(basename "$protofile" .proto)
            for genfile in "$dir/${base_name}_pb2"*.py; do
                if [[ -f "$genfile" ]]; then
                    local package_name=$(grep "^package " "$protofile" | sed -e "s/^package //" -e "s/;//" -e "s/\./_/g")
                    if [[ ! -z "$package_name" ]]; then
                        sed -i'' -e "s/import \([^ ]*\)_pb2 as \([^ ]*\)/import protocols.\1.\1_pb2 as \2/g" "$genfile"
                        sed -i'' -e "s/from \([^ ]*\) import \([^ ]*\)_pb2 as \([^ ]*\)/from protocols.\1 import \2_pb2 as \3/g" "$genfile"
                    fi
                fi
            done
        done
    else
        warn "grpc_tools.protoc module not found — skipping Python gRPC generation"
    fi
}

ACTION="${1:-}"

case "$ACTION" in
    generate)
        mapfile -t proto_files < <(gather_proto_files)
        generate_python "${proto_files[@]}"
        ;;
    clean)
        info "Cleaning up generated files..."
        find libs/protocols -type f \( -name '*.py' ! -name '__init__.py' \) -delete &
        find libs/protocols -type f -name '*.c' -delete &
        find libs/protocols -type f -name '*.h' -delete &
        wait
        log "Clean complete"
        ;;
    *)
        err "Unknown operation: $ACTION"
        echo "Usage: $0 [generate|clean]"
        exit 1
        ;;
esac
