#!/usr/bin/env bash
# install.sh — point git at .claude/hooks/ for this clone.
#
# Idempotent. Run once after cloning the repo.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

existing=$(git config core.hooksPath 2>/dev/null || true)

if [ -n "$existing" ] && [ "$existing" != ".claude/hooks" ]; then
    echo "[install] WARNING: core.hooksPath is already set to '$existing'."
    echo "[install]          Overwriting with '.claude/hooks'. If you had hooks at"
    echo "[install]          '$existing', move them into .claude/hooks/ to keep them."
    echo ""
fi

git config core.hooksPath .claude/hooks
chmod +x .claude/hooks/commit-msg .claude/hooks/post-deploy-release-record.sh

# Sanity check: the executable bit should have stuck. If not, the filesystem
# may not support it (e.g., FAT32). The hook won't run there.
if [ ! -x .claude/hooks/commit-msg ]; then
    echo "[install] WARNING: .claude/hooks/commit-msg is not executable."
    echo "[install]          This filesystem may not support exec bits — the hook will not run."
fi

echo "git hooks installed:"
echo "  core.hooksPath = .claude/hooks"
echo "  active hooks:"
ls -1 .claude/hooks/ | grep -E '^(commit-msg|pre-commit|pre-push|post-commit|post-merge)$' | sed 's/^/    /' || echo "    (none yet)"
echo ""
echo "Done. Commits will now be checked for .claude/knowledge/ freshness."
echo "Bypass with [no-arch-change] in the commit message for cosmetic changes."
