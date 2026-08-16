#!/bin/bash

# Function to find the workspace root by looking for nx.json
function find_workspace_root() {
    local current_dir="$PWD"
    while [[ "$current_dir" != "/" ]]; do
        if [[ -f "$current_dir/nx.json" ]]; then
            echo "$current_dir"
            return 0
        fi
        current_dir="$(dirname "$current_dir")"
    done
    return 1
}

# Get workspace root
WORKSPACE_ROOT=$(find_workspace_root)
if [ $? -ne 0 ]; then
    echo "Error: Could not find workspace root (nx.json not found)"
    exit 1
fi

# Source all bash libraries
source "${WORKSPACE_ROOT}/libs/bash/production.sh"
source "${WORKSPACE_ROOT}/libs/bash/vault.sh"