#!/bin/bash

# This script manages protobuf, gRPC, and cipher file generation and cleanup for a project.
# It supports two operations: 'generate' and 'clean'.
# 'generate' operation generates Python, Dart/Flutter gRPC, and protobuf code from .proto files located in libs/protos,
# modifies import statements in the generated *_grpc.py files, and runs a custom Go tool for additional code generation.
# 'clean' operation removes all generated Python and Dart files except for __init__.py within libs/protos.

NANOPB_PLUGIN_PATH="/ncs/modules/lib/nanopb/generator/protoc-gen-nanopb"  # Adjust this path as necessary

operation="$1" # The first command-line argument determines the script's operation mode.

generate_nanopb() {
    local protofile="$1"
    local dir=$(dirname "$protofile")

    if [ -x "$NANOPB_PLUGIN_PATH" ]; then
        protoc --plugin=protoc-gen-nanopb="$NANOPB_PLUGIN_PATH" --nanopb_opt=-I"$dir" --nanopb_out="$dir" -I "$dir" "$protofile"
        echo "Generated nanopb code for $protofile"
    else
        echo "Warning: nanopb plugin not found. Skipping nanopb generation."
    fi
}

generate_python() {
    local protofile="$1"
    local dir=$(dirname "$protofile")
    local file=$(basename "$protofile")
    
    # Normalize the proto filename to match Python's naming conventions (replace '-' with '_').
    local modname=$(echo "$file" | sed 's/.proto$//' | sed 's/-/_/g')
  
    # Further transform module name by replacing single underscores with double underscores for gRPC files.
    local modname_double_underscore=$(echo "$modname" | sed 's/_/__/g')
  
    if python3 -c "import grpc_tools.protoc" &> /dev/null; then
        protoc --python_out="$dir" --proto_path="$dir" "$protofile"
        python3 -m grpc_tools.protoc --grpc_python_out="$dir" --proto_path="$dir" "$protofile"
        echo "Generated Python protobuf and gRPC code for $protofile"

        # Modify import statements in all generated *_grpc.py files to match the expected format.
        local grpcfiles=$(find "$dir" -type f -name "${modname}_pb2_grpc.py")
        for grpcfile in $grpcfiles; do
          # Replace import statements using sed to match the new naming convention.
          sed -i'' -e "s/import ${modname}_pb2 as.*/import protos.${modname}.${modname}_pb2 as ${modname_double_underscore}__pb2/g" "$grpcfile" || echo "Failed to modify $grpcfile"
        done
    else
        echo "Warning: grpc_tools.protoc module not found. Skipping Python gRPC generation."
    fi
}

generate_dart() {
  local protofile="$1"
  local dir=$(dirname "$protofile")
  local file=$(basename "$protofile")
  local dart_out_dir="${dir}/lib" # Specify the output directory for Dart files within the lib folder
  
  # Normalize the proto filename to create a Dart-friendly package name (lowercase and underscores)
  local pkgname=$(echo "$file" | sed 's/.proto$//' | tr '-' '_' | tr '[:upper:]' '[:lower:]')
  
  # Check if Dart gRPC plugin exists before generating Dart code.
  if command -v protoc-gen-dart >/dev/null; then
      mkdir -p "$dart_out_dir"
      protoc --dart_out=grpc:"$dart_out_dir" --proto_path="$dir" "$protofile"
      echo "Dart gRPC and protobuf code generated for $pkgname in $dart_out_dir"
  else
      echo "Warning: Dart gRPC plugin not found. Skipping Dart/Flutter generation."
      return
  fi

  # Check if pubspec.yaml already exists, only generate if it does not
  if [ ! -f "$dir/pubspec.yaml" ]; then
      # Generate pubspec.yaml for the Dart package using the normalized package name
      cat > "$dir/pubspec.yaml" <<EOF
name: ${pkgname}_protos
description: A Dart package for protobuf-generated files for ${pkgname}.
version: 0.1.0
environment:
  sdk: '>=2.12.0 <3.0.0'

dependencies:
  protobuf: ^2.0.0
  grpc: ^3.0.0
EOF

      echo "Created pubspec.yaml in $dir for package ${pkgname}_protos"
  else
      echo "pubspec.yaml already exists in $dir, skipping creation."
  fi
}

generate_cipher() {
    local protofile="$1"
    local dir=$(dirname "$protofile")

    # Generate python cipher code using Golang generator
    go run tools/cipherc/main.go -language=python -proto="$protofile" -out="$dir/"
    echo "Generated Python cipher code for $protofile"

    # Generate C cipher code using Golang generator
    go run tools/cipherc/main.go -language=c -proto="$protofile" -out="$dir/"
    echo "Generated C cipher code for $protofile"
}

case $operation in
  generate)
    find libs/protos -name '*.proto' | while read protofile; do
      echo "Processing $protofile..."

      generate_nanopb "$protofile"
      generate_python "$protofile"
      generate_dart "$protofile"
      generate_cipher "$protofile"
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