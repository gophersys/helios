# Worktree Safety Protocol

Git worktrees are fresh checkouts that miss untracked files (.env, node_modules).
This causes silent failures when teammates try to run code. Follow this protocol.

## Problem: Missing .env Files

Worktrees don't include `.env` files (gitignored). Without them:
- Database connections fail (no DATABASE_URL)
- API auth fails (no JWT_SECRET_KEY)
- Bitbucket operations fail (no BITBUCKET_API_TOKEN)
- MinIO fails (no STORAGE_ACCESS_KEY)

## Solution: .worktreeinclude

Create `.worktreeinclude` in the repo root. This file lists gitignored files
that should be COPIED into new worktrees:

```
# .worktreeinclude — files to copy into git worktrees
# One path per line, relative to repo root

.env
deploy/development/.env
apps/backend/http-api/.env
apps/backend/build-service/.env
apps/backend/git-poller/.env
prisma/.env
```

### Enforcement

Before creating a worktree agent, the orchestrator MUST:

```bash
# 1. Verify .worktreeinclude exists
if [ ! -f .worktreeinclude ]; then
  echo "WARNING: No .worktreeinclude — worktree agents will miss .env files"
fi

# 2. After worktree creation, copy listed files
WORKTREE_PATH=".claude/worktrees/<name>"
while IFS= read -r file; do
  [[ "$file" =~ ^#.*$ || -z "$file" ]] && continue
  if [ -f "$file" ]; then
    mkdir -p "$WORKTREE_PATH/$(dirname "$file")"
    cp "$file" "$WORKTREE_PATH/$file"
  fi
done < .worktreeinclude
```

### Alternative: WorktreeCreate Hook

If supported by Claude Code, configure in settings.json:

```json
{
  "hooks": {
    "WorktreeCreate": [
      {
        "type": "command",
        "command": "scripts/copy-worktree-env.sh"
      }
    ]
  }
}
```

## Branch Base Verification

Worktrees branch from wherever `origin/HEAD` points. If this is wrong,
the worktree starts from the wrong base:

```bash
# Before creating worktrees, verify branch base
git remote set-head origin -a  # Sync with remote's default

# Verify
git symbolic-ref refs/remotes/origin/HEAD
# Should output: refs/remotes/origin/HEAD -> refs/remotes/origin/main
```

If your project uses a non-default branch (e.g., `feature/e2e`), set it:

```bash
git remote set-head origin feature/e2e
```

## Post-Worktree Validation

After a worktree is created, verify it's functional:

```bash
WORKTREE_PATH=".claude/worktrees/<name>"

# Check critical files exist
[ -f "$WORKTREE_PATH/.env" ] || echo "MISSING: .env"
[ -f "$WORKTREE_PATH/deploy/development/.env" ] || echo "MISSING: deploy .env"

# Check node_modules (symlinked or installed)
[ -d "$WORKTREE_PATH/apps/frontend/app/node_modules" ] || echo "MISSING: node_modules"

# Check prisma client generated
[ -d "$WORKTREE_PATH/node_modules/.prisma" ] || echo "MISSING: prisma client"
```

If validation fails, the agent should fix (copy files, npm install) before
starting implementation work.

## Teammate Prompt Addendum

Include in EVERY worktree teammate's prompt:

```
WORKTREE SAFETY:
- Your worktree may be missing .env files. If you get connection errors,
  check if .env exists and copy from main repo if needed.
- Run "ls .env deploy/development/.env" as a first step to verify.
- If node_modules is missing, run "npm install" in your worktree.
- Your worktree branches from origin/HEAD. If files seem wrong,
  verify you're on the right base branch.
```
