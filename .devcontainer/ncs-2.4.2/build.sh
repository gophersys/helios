#!/bin/bash

# Enable strict error handling
set -euo pipefail

# Function to display usage and exit
usage() {
    echo "Usage: $0 <version>"
    exit 1
}

# Check if at least one argument is provided
if [ $# -lt 1 ]; then
    echo "Error: No version specified."
    usage
fi

# Capture the version argument
VERSION=$1

# Now, proceed with the docker build command using the provided version
docker build . -t ccr01.ad.corekinect.com/concord-dev-ncs-2.4.2:$VERSION

# Check if docker build command succeeded
if [ $? -eq 0 ]; then
    echo "Docker build successful."
else
    echo "Docker build failed."
    exit 1
fi
