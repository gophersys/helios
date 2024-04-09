#!/bin/bash

# This script manages protobuf, gRPC, and cipher file generation and cleanup for a project.
# It supports two operations: 'generate' and 'clean'.
# 'generate' operation generates Python, Dart/Flutter gRPC, and protobuf code from .proto files located in libs/protos,
# modifies import statements in the generated *_grpc.py files, and runs a custom Go tool for additional code generation.
# 'clean' operation removes all generated Python and Dart files except for __init__.py within libs/protos.

NANOPB_PLUGIN_PATH="/ncs/modules/lib/nanopb/generator/protoc-gen-nanopb"  # Adjust this path as necessary

operation="$1" # The first command-line argument determines the script's operation mode.

# Function to generate a space-separated list of all proto files
gather_all_proto_files() {
    find libs/protos -name '*.proto'
}

generate_nanopb() {
    local proto_files=("$@")
    local proto_dirs=$(printf "%s\n" "${proto_files[@]}" | xargs -n1 dirname | sort -u | xargs -n1 echo -I | tr '\n' ' ')

    if [ -x "$NANOPB_PLUGIN_PATH" ]; then
        for protofile in "${proto_files[@]}"; do
            local dir=$(dirname "$protofile")

            # Generate nanopb code, including all directories containing .proto files for imports
            protoc --plugin=protoc-gen-nanopb="$NANOPB_PLUGIN_PATH" \
                   --nanopb_out="$dir" \
                   $proto_dirs \
                   "$protofile"
            echo "Generated nanopb code for $protofile"
        done
    else
        echo "Warning: nanopb plugin not found. Skipping nanopb generation."
    fi
}

generate_python() {
    local root_dir="libs/protos"
    local proto_files=("$@")
    local proto_dirs=$(printf "%s\n" "${proto_files[@]}" | xargs -n1 dirname | sort -u | xargs -n1 echo -I | tr '\n' ' ')

    if python3 -c "import grpc_tools.protoc" &> /dev/null; then
        for protofile in "${proto_files[@]}"; do
            local dir=$(dirname "$protofile")
            local relative_dir=${dir#$root_dir/} # Remove the root_dir from dir to get the relative path
            local file=$(basename "$protofile")
            
            # Generate Python protobuf and gRPC code
            protoc --python_out="$dir" --proto_path="$dir" $proto_dirs "$protofile"
            python3 -m grpc_tools.protoc --grpc_python_out="$dir" --proto_path="$dir" $proto_dirs "$protofile" -I"$dir"
            echo "Generated Python protobuf and gRPC code for $protofile"

            # Modify import statements in all generated *_pb2.py and *_pb2_grpc.py files
            local generated_files=$(find "$dir" -type f -name "${file%.proto}_pb2*.py")
            for genfile in $generated_files; do
                # Extract package name from proto file
                local package_name=$(grep "^package " "$protofile" | sed -e "s/^package //" -e "s/;//" -e "s/\./_/g")
                # Update import statements to include the full nested package structure, assuming the package name mirrors directory structure.
                if [[ ! -z "$package_name" ]]; then
                    sed -i'' -e "s/import \([^ ]*\)_pb2 as \([^ ]*\)/import protos.${package_name}.\1_pb2 as \2/g" "$genfile" || echo "Failed to modify $genfile"
                    sed -i'' -e "s/from \([^ ]*\) import \([^ ]*\)_pb2 as \([^ ]*\)/from protos.${package_name}.\1 import \2_pb2 as \3/g" "$genfile" || echo "Failed to modify $genfile"
                fi
                echo "Modified import statements in $genfile"
            done
        done
    else
        echo "Warning: grpc_tools.protoc module not found. Skipping Python gRPC generation."
    fi
}


generate_cipher() {
    local proto_files=("$@")
    
    for protofile in "${proto_files[@]}"; do
        local dir=$(dirname "$protofile")

        # Generate cipher code in Python using the custom Go tool
        go run tools/cipherc/main.go -language=python -proto="$protofile" -out="$dir/"
        echo "Generated Python cipher code for $protofile"

        # Generate cipher code in C using the custom Go tool
        go run tools/cipherc/main.go -language=c -proto="$protofile" -out="$dir/"
        echo "Generated C cipher code for $protofile"
    done
}

proto_files=$(gather_all_proto_files)

case $operation in
  generate)
    find libs/protos -name '*.proto' | while read protofile; do
      echo "Processing $protofile..."

      echo "Generating code..."
      generate_nanopb $proto_files
      generate_python $proto_files
      generate_cipher $proto_files
    done
    ;;

  clean)
    # Remove all generated Python files except for __init__.py in libs/protos directory.
    find libs/protos -type f \( -name '*.py' ! -name '__init__.py' \) -exec rm {} +
    echo "Cleaned up generated Python files."

    # # Remove all generated .c files in libs/protos directory.
    find libs/protos -type f -name '*.c' -exec rm {} +
    echo "Cleaned up generated C files."

    # # Remove all generated .h files in libs/protos directory.
    find libs/protos -type f -name '*.h' -exec rm {} +
    echo "Cleaned up generated Header files."

    # Remove all generated Dart files in libs/protos directory.
    find libs/protos -type f -name '*.dart' -exec rm {} +
    echo "Cleaned up generated Dart files."

    # Remove all .yaml files in libs/protos directory, including pubspec.yaml.
    find libs/protos -type f -name '*.yaml' -exec rm {} +
    echo "Cleaned up Dart package configuration files."

    # Optionally, remove .lock files if they are not needed.
    find libs/protos -type f -name '*.lock' -exec rm {} +
    echo "Cleaned up lock files."

    ;;

  *)
    # If an unknown operation is specified, print usage information.
    echo "Unknown operation: $operation"
    echo "Usage: $0 [generate|clean]"
    exit 1
    ;;
esac