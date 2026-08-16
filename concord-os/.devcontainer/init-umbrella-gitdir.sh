#!/usr/bin/env bash
# Runs on the HOST via devcontainer.json `initializeCommand` before the
# container is created. Sets up `.devcontainer/.umbrella-gitdir` so the
# subsequent bind mount of that path always has a real source — required
# because Docker's `--mount type=bind` errors when the source doesn't
# exist.
#
# Two modes:
#   - Umbrella: the workspace's `.git` is a pointer file whose target lives
#     outside the workspace. Symlink `.umbrella-gitdir` to that real gitdir
#     so the bind mount surfaces it inside the container at
#     `/workspaces/.git/modules/concord/concord-os-yocto`. Both the relative
#     gitdir reference in the `.git` pointer and the relative `core.worktree`
#     in the gitdir's `config` then resolve identically inside vs outside
#     the container.
#   - Standalone: `.git` is a regular directory inside the workspace. The
#     bind mount is irrelevant in this mode (git uses the in-workspace
#     `.git` directly); we just create an empty stub so Docker has
#     something to mount.

set -eu

# initializeCommand runs in the workspace folder on the host.
WORKSPACE="$(pwd)"
STUB="$WORKSPACE/.devcontainer/.umbrella-gitdir"

# Idempotent — wipe any prior symlink/dir we may have created.
rm -rf "$STUB"

if [ -f "$WORKSPACE/.git" ]; then
    # Umbrella mode: `.git` is a pointer file. Read its gitdir target and
    # symlink the stub to the absolute path of the real gitdir on host.
    GITDIR_REL=$(sed -n 's/^gitdir: //p' "$WORKSPACE/.git" | head -n 1)
    if [ -z "$GITDIR_REL" ]; then
        echo "[init-umbrella-gitdir] WARN: $WORKSPACE/.git exists but has no 'gitdir:' line; falling back to empty stub" >&2
        mkdir -p "$STUB"
        exit 0
    fi
    REAL_GITDIR=$(cd "$WORKSPACE" && cd "$(dirname "$GITDIR_REL")" 2>/dev/null && pwd)/$(basename "$GITDIR_REL")
    if [ ! -d "$REAL_GITDIR" ]; then
        echo "[init-umbrella-gitdir] WARN: resolved umbrella gitdir $REAL_GITDIR does not exist; falling back to empty stub" >&2
        mkdir -p "$STUB"
        exit 0
    fi
    ln -s "$REAL_GITDIR" "$STUB"
else
    # Standalone mode: empty stub is sufficient.
    mkdir -p "$STUB"
fi
