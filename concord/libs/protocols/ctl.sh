#!/bin/bash
#
# libs/protocols/ctl.sh
#
# Generates Python protobuf + gRPC stubs (and optionally nanopb C/H)
# from every .proto under libs/protocols/. Invoked by the Nx target
# `protocols:create`.
#
# This script runs under `set -euo pipefail` AND must be safe to call
# from `nx run protocols:create` as a `dependsOn` of every consumer's
# build target. Silent no-op behavior is forbidden: if codegen fails
# to produce the expected files, the script exits non-zero.
#
# History:
#   - v0.12.12: previously the `gather_proto_files` function exited
#     silently under `set -u` because `${proto_map[$name]}` errored on
#     first-key lookup. The script reported success without generating
#     anything, which caused a v0.12.11 production outage when the
#     http-api image shipped without `protocols.mtib.mtib_pb2`. Fixed
#     by using `:-` default-empty everywhere and adding an explicit
#     post-generation verification step (verify_generated_files) that
#     refuses to exit 0 if expected `*_pb2.py` / `*_pb2_grpc.py` files
#     are missing.

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

# Walk libs/protocols/ for *.proto. If two files share a basename
# (e.g., libs/protocols/foo/x.proto + libs/protocols/bar/x.proto), keep
# the first one found and warn — proto codegen otherwise overwrites
# itself in unpredictable ways.
#
# IMPORTANT: every associative-array read uses `:-` default-empty so
# the function works under `set -u`. Bash 4 raises "unbound variable"
# on a first-key read otherwise, and earlier versions of this function
# exited 0 silently — see header comment.
gather_proto_files() {
    local -A proto_map=()
    local file name
    while IFS= read -r file; do
        name=$(basename "$file")
        if [[ -z "${proto_map[$name]:-}" ]]; then
            proto_map[$name]="$file"
        else
            warn "Duplicate proto file found: $file (using ${proto_map[$name]:-})"
        fi
    done < <(find libs/protocols -name '*.proto')

    if [[ ${#proto_map[@]} -gt 0 ]]; then
        printf '%s\n' "${proto_map[@]}"
    fi
}

get_proto_dirs() {
    local files=("$@")
    if [[ ${#files[@]} -eq 0 ]]; then
        return 0
    fi
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
        local dir
        dir=$(dirname "$protofile")
        local includes
        includes=$(get_proto_dirs "${proto_files[@]}")

        protoc --plugin=protoc-gen-nanopb="$NANOPB_PLUGIN_PATH" \
               $includes \
               --nanopb_out="$dir" \
               "$protofile"
    done
}

generate_python() {
    local -a proto_files=("$@")

    info "Generating Python protobuf and gRPC code..."

    if ! python3 -c "import grpc_tools.protoc" &> /dev/null; then
        err "grpc_tools.protoc module not found — Python codegen REQUIRED for protocols:create."
        err "Install with: pip install grpcio-tools"
        return 1
    fi

    for protofile in "${proto_files[@]}"; do
        if [[ ! -f "$protofile" ]]; then
            continue
        fi

        local dir
        dir=$(dirname "$protofile")
        echo "Processing: $protofile"

        local includes
        includes=$(get_proto_dirs "${proto_files[@]}")

        protoc --python_out="$dir" --proto_path="$dir" $includes "$protofile"
        python3 -m grpc_tools.protoc --grpc_python_out="$dir" --proto_path="$dir" $includes "$protofile" -I"$dir"

        local base_name
        base_name=$(basename "$protofile" .proto)
        for genfile in "$dir/${base_name}_pb2"*.py; do
            if [[ -f "$genfile" ]]; then
                local package_name
                package_name=$(grep "^package " "$protofile" | sed -e "s/^package //" -e "s/;//" -e "s/\./_/g")
                if [[ -n "$package_name" ]]; then
                    sed -i'' -e "s/import \([^ ]*\)_pb2 as \([^ ]*\)/import protocols.\1.\1_pb2 as \2/g" "$genfile"
                    sed -i'' -e "s/from \([^ ]*\) import \([^ ]*\)_pb2 as \([^ ]*\)/from protocols.\1 import \2_pb2 as \3/g" "$genfile"
                fi
            fi
        done
    done
}

# Verify that for every input .proto, the matching _pb2.py and
# _pb2_grpc.py exist on disk after generation. This is the guard rail
# that makes silent no-op codegen impossible. If anything is missing,
# exit non-zero with a clear message so the Nx target fails loudly and
# the consumer's `dependsOn` chain aborts the build.
verify_generated_files() {
    local -a proto_files=("$@")
    local missing=()
    local protofile dir base_name

    for protofile in "${proto_files[@]}"; do
        if [[ ! -f "$protofile" ]]; then
            continue
        fi
        dir=$(dirname "$protofile")
        base_name=$(basename "$protofile" .proto)
        for expected in "${dir}/${base_name}_pb2.py" "${dir}/${base_name}_pb2_grpc.py"; do
            if [[ ! -f "$expected" ]]; then
                missing+=("$expected")
            fi
        done
    done

    if [[ ${#missing[@]} -gt 0 ]]; then
        err "Codegen succeeded but expected files are missing:"
        for f in "${missing[@]}"; do
            err "  - $f"
        done
        err ""
        err "This means \`generate_python\` reported success but produced no output."
        err "Re-run with bash -x to see where it bailed:"
        err "  bash -x ./libs/protocols/ctl.sh generate"
        return 1
    fi
}

ACTION="${1:-}"

case "$ACTION" in
    generate)
        mapfile -t proto_files < <(gather_proto_files)
        if [[ ${#proto_files[@]} -eq 0 ]]; then
            err "No .proto files found under libs/protocols/. Aborting."
            err "If this is a fresh clone, confirm libs/protocols/mtib/mtib.proto exists."
            exit 1
        fi
        generate_python "${proto_files[@]}"
        verify_generated_files "${proto_files[@]}"
        log "Generated stubs for ${#proto_files[@]} proto file(s)"
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
