#!/bin/bash

# This script manages protobuf, gRPC and cipher file generation and cleanup for a project.
# It supports two operations: 'generate' and 'clean'.
# 'generate' operation generates Python gRPC and protobuf code from .proto files located in libs/protos,
# modifies import statements in the generated *_grpc.py files, and runs a custom Go tool for additional code generation.
# 'clean' operation removes all generated Python files except __init__.py within libs/protos.

NANOPB_PLUGIN_PATH="/ncs/modules/lib/nanopb/generator/protoc-gen-nanopb"  # Adjust this path as necessary

operation="$1" # The first command-line argument determines the script's operation mode.

case $operation in
  generate)
    # Loop through each .proto file found within libs/protos directory.
    find libs/protos -name '*.proto' | while read protofile; do
      # Extract directory and filename from the protofile path.
      dir=$(dirname "$protofile")
      file=$(basename "$protofile")

      # Normalize the proto filename to match Python's naming conventions (replace '-' with '_').
      modname=$(echo "$file" | sed 's/.proto$//' | sed 's/-/_/g')

      # Further transform module name by replacing single underscores with double underscores for gRPC files.
      modname_double_underscore=$(echo "$modname" | sed 's/_/__/g')

      echo "Processing $file in $dir..."

      # Generate python protobuf code using protoc.
      protoc --python_out=. "$protofile"

      # Check if nanopb plugin exists
      if [ -x "$NANOPB_PLUGIN_PATH" ]; then
          # Generate C protobuf code using nanopb plugin.
          protoc --plugin=protoc-gen-nanopb="$NANOPB_PLUGIN_PATH" --nanopb_opt=-I"$dir" --nanopb_out="$dir" -I "$dir" "$protofile"
      else
          echo "Warning: nanopb plugin not found. Skipping nanopb generation."
      fi

      # Generate gRPC code using grpc_tools.protoc.
      python3 -m grpc_tools.protoc --grpc_python_out="$dir" --proto_path="$dir" "$protofile"

      # Generte python cipher code using Golang generator
      go run tools/cipherc/main.go -language=python -proto="$protofile" -out="$dir/"

      # Generte c cipher code using Golang generator
      go run tools/cipherc/main.go -language=c -proto="$protofile" -out="$dir/"

      # Modify import statements in all generated *_grpc.py files to match the expected format.
      grpcfiles=$(find "$dir" -type f -name "${modname}_pb2_grpc.py")
      for grpcfile in $grpcfiles; do
        # Replace import statements using sed to match the new naming convention.
        sed -i "s/import ${modname}_pb2 as.*/import protos.${modname}.${modname}_pb2 as ${modname_double_underscore}__pb2/g" "$grpcfile" || echo "Failed to modify $grpcfile"
      done
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
    ;;

  *)
    # If an unknown operation is specified, print usage information.
    echo "Unknown operation: $operation"
    echo "Usage: $0 [generate|clean]"
    exit 1
    ;;
esac