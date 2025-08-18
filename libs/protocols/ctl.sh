#!/bin/bash

# Exit on any error
set -e

# This script manages protobuf, gRPC, and cipher file generation and cleanup for a project.
# It supports two operations: 'generate' and 'clean'.
# 'generate' operation generates Python and protobuf code from .proto files located in libs/protocols,
# modifies import statements in the generated *_grpc.py files, and runs a custom Go tool for additional code generation for the cipher protocol.
# 'clean' operation removes all generated Python and C files except for __init__.py within libs/protocols.

NANOPB_PLUGIN_PATH="/ncs/modules/lib/nanopb/generator/protoc-gen-nanopb"  # Adjust this path as necessary

operation="$1" # The first command-line argument determines the script's operation mode.

# Gather all proto files once, storing them in an array
function gather_proto_files() {
    local -A proto_map
    while IFS= read -r file; do
        name=$(basename "$file")
        if [[ -z "${proto_map[$name]}" ]]; then
            proto_map[$name]="$file"
        else
            echo "Warning: Duplicate proto file found: $file (using ${proto_map[$name]})" >&2
        fi
    done < <(find libs/protocols -name '*.proto')

    # Return only the unique proto files
    printf '%s\n' "${proto_map[@]}"
}

# Get proto directories for include paths
function get_proto_dirs() {
    local files=("$@")
    local dirs=()
    for file in "${files[@]}"; do
        dirs+=("-I$(dirname "$file")")
    done
    printf '%s\n' "${dirs[@]}" | sort -u | tr '\n' ' '
}

function generate_nanopb() {
    local -a proto_files=("$@")

    if [ ! -x "$NANOPB_PLUGIN_PATH" ]; then
        echo "Warning: nanopb plugin not found at $NANOPB_PLUGIN_PATH. Skipping nanopb generation." >&2
        return 0  # Changed to not fail the script
    fi

    echo "Generating nanopb code..."
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

function generate_python() {
    local -a proto_files=("$@")
    local root_dir="libs/protocols"

    echo "Generating Python protobuf and gRPC code..."

    if python3 -c "import grpc_tools.protoc" &> /dev/null; then
        for protofile in "${proto_files[@]}"; do
            if [[ ! -f "$protofile" ]]; then
                continue
            fi

            local dir=$(dirname "$protofile")
            echo "Processing: $protofile"

            # Get include paths for this file
            local includes=$(get_proto_dirs "${proto_files[@]}")

            # Generate both protobuf and gRPC using grpc_tools.protoc
            python3 -m grpc_tools.protoc \
                $includes \
                --python_out="$dir" \
                --grpc_python_out="$dir" \
                "$protofile"

            # Process import statements for generated files
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
        echo "Warning: grpc_tools.protoc module not found. Skipping Python gRPC generation." >&2
    fi
}

function generate_cipher() {
    local -a proto_files=("$@")

    echo "Generating cipher code..."
    for protofile in "${proto_files[@]}"; do
        if [[ ! -f "$protofile" ]]; then
            continue
        fi
        local dir=$(dirname "$protofile")
        {
            go run tools/cipherc/main.go -language=python -proto="$protofile" -out="$dir/" &
            go run tools/cipherc/main.go -language=c -proto="$protofile" -out="$dir/" &
            wait
        } &
    done
    wait
}

function generate_go() {
    local -a proto_files=("$@")
    local root_dir="libs/protocols"

    # Get the GOPATH and check if the tools exist
    local GOPATH=${GOPATH:-$(go env GOPATH)}
    local PROTOC_GEN_GO="$GOPATH/bin/protoc-gen-go"
    local PROTOC_GEN_GO_GRPC="$GOPATH/bin/protoc-gen-go-grpc"

    if [ ! -f "$PROTOC_GEN_GO" ] || [ ! -f "$PROTOC_GEN_GO_GRPC" ]; then
        echo "Installing Go protoc plugins..."
        go install google.golang.org/protobuf/cmd/protoc-gen-go@latest
        go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@latest
    fi

    echo "Generating Go protobuf and gRPC code..."
    for protofile in "${proto_files[@]}"; do
        if [[ ! -f "$protofile" ]]; then
            continue
        fi

        # Get the directory of the .proto file
        dir=$(dirname "$protofile")
        echo "Processing: $protofile"

        # Run the protoc command in the directory of the .proto file
        (
            cd "$dir" || exit
            protoc --go_out=. \
                   --go_opt=paths=source_relative \
                   --go-grpc_out=. \
                   --go-grpc_opt=paths=source_relative \
                   "$(basename "$protofile")"
        )
        
        if [ $? -ne 0 ]; then
            echo "Error generating code for $protofile" >&2
            return 1
        fi
    done

    echo "Go code generation complete"
}

case $operation in
  generate)
    # Gather proto files into an array
    mapfile -t proto_files < <(gather_proto_files)

    # Generate all types of code
    # generate_nanopb "${proto_files[@]}"
    generate_python "${proto_files[@]}" &
    # generate_cipher "${proto_files[@]}"
    generate_go "${proto_files[@]}" &
    wait
    ;;

  clean)
    echo "Cleaning up generated files..."
    {
        find libs/protocols -type f \( -name '*.py' ! -name '__init__.py' \) -delete &
        find libs/protocols -type f -name '*.c' -delete &
        find libs/protocols -type f -name '*.h' -delete &
        find libs/protocols -type f -name '*.go' -delete &
        wait
    }
    ;;

  *)
    echo "Unknown operation: $operation"
    echo "Usage: $0 [generate|clean]"
    exit 1
    ;;
esac