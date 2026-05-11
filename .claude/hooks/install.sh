#!/usr/bin/env bash
# install.sh — point git at .claude/hooks/ for this clone.
#
# Idempotent. Run once after cloning the repo.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

git config core.hooksPath .claude/hooks
chmod +x .claude/hooks/commit-msg .claude/hooks/post-deploy-release-record.sh

echo "git hooks installed:"
echo "  core.hooksPath = .claude/hooks"
echo "  active hooks:"
ls -1 .claude/hooks/ | grep -E '^(commit-msg|pre-commit|pre-push|post-commit)$' | sed 's/^/    /' || echo "    (none yet)"
echo ""
echo "Done. Commits will now be checked for .claude/knowledge/ freshness."
echo "Bypass with [no-arch-change] in the commit message for cosmetic changes."
