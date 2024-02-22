#!/bin/bash

# Assuming this script is located in the same directory as the protos directory
PROTO_DIR=../protos
PROTO_FILE=mtib-opi.proto
GENERATED_FOLDER=../protos/generated

# Output python server code
python3 -m grpc_tools.protoc --python_out=$GENERATED_FOLDER --pyi_out=$GENERATED_FOLDER --grpc_python_out=$GENERATED_FOLDER -I$PROTO_DIR $PROTO_DIR/$PROTO_FILE

# Fix import in the generated mtib_opi_pb2_grpc.py file
sed -i 's/^import mtib_opi_pb2 as/from . import mtib_opi_pb2 as/' $GENERATED_FOLDER/mtib_opi_pb2_grpc.py
