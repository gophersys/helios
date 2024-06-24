#!/bin/bash

GO_VERSION=1.20.5

# Enable strict error handling
set -euo pipefail

# Function to display usage and exit
usage() {
    echo "Usage: $0 <version>"
    exit 1
}

# Check if at least two arguments are provided
if [ $# -lt 1 ]; then
    echo "Error: Not enough arguments."
    usage
fi

# Capture the container version argument
VERSION=$1

# Create or use an existing builder that enables multi-architecture builds
docker buildx create --use --use --name concord-env-builder || true

# Now, proceed with the docker buildx build command using the provided version and Go version
docker build \
    --tag ccr01.ad.corekinect.com/concord-dev-env:$VERSION \
    --build-arg GO_VERSION=$GO_VERSION \
    .