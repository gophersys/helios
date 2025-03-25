#!/bin/bash

# Set the workspace directory explicitly
WORKSPACE="/workspaces/concord"

# Add the main repository as safe first
git config --global --add safe.directory "$WORKSPACE"

# Find all git repositories (including submodules) and add them as safe directories
find "$WORKSPACE" -type d -name ".git" | while read gitdir; do
    # Get the parent directory of the .git folder
    repo_path=$(dirname "$gitdir")
    echo "Adding safe directory: $repo_path"
    git config --global --add safe.directory "$repo_path"
done

# Now change to workspace
cd "$WORKSPACE" || exit

# Create the platform builder if it doesn't exist
nx create-platform-builder devcontainers