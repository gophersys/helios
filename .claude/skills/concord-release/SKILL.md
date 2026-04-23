---
name: concord-release
description: Create a Concord platform release — version bump, changelog, gate checks, deploy, and release record creation
user-invocable: true
argument-hint: "[version] or leave blank for auto-detect"
---

# Concord Platform Release

Orchestrate a full Concord platform release. A release is an atomic semver-tagged
commit on `main` that covers all platform services (http-api, frontend, docs,
git-poller, build-service, runner) plus independently-versioned components.

Arguments: $ARGUMENTS

## Version: Single Source of Truth

The `VERSION` file at the repo root is the **sole authority** for the platform
version. Three UI locations display it — all read the same build-time constant
`PUBLIC_APP_VERSION`, which is set from `VERSION` by `ctl.sh` during Docker builds:

| Location | File | Source |
|----------|------|--------|
| Sidebar (bottom-left) | `sidebar.svelte` | `PUBLIC_APP_VERSION` |
| Settings → System tab | `settings-modal.svelte` | `PUBLIC_APP_VERSION` |
| Releases page badge | `releases/+page.svelte` | `PUBLIC_APP_VERSION` |

Changing the `VERSION` file and deploying updates all three atomically.
**Never set version anywhere else.** The release record in the database is
historical metadata — it does not drive what the UI displays.

## Update notification

After deploying a new version, users with open tabs see a persistent banner:
"Concord vX.Y.Z is available (you're on vA.B.C) — Reload". This is powered by
`/build-info.json` polling in `+layout.svelte`. No manual action needed — it
fires automatically when the deployed version differs from the baked-in bundle.

## What a release covers

- **Platform version** (`VERSION`) — one semver for all services
- **corekinect SDK** (`libs/python/corekinect/__init__.py` → `__version__`) — independently versioned
- **MTIB proto** (`libs/protocols/mtib/VERSION`) — independently versioned
- **Prisma migration hash** — current schema fingerprint
- **Changelog** — auto-generated from conventional commits since last tag

## Git workflow: NEVER push directly to main

All release work happens on a branch. **Never commit or push directly to main.**

```
main ─────────────────────●── (merge) ──● tag vX.Y.Z ── deploy
                         ╱
release/vX.Y.Z ────●────●
                  bump  fixes
```

1. Create a release branch from main
2. Do all version bump / changelog / fixes on the branch
3. Push the branch
4. Create a PR to main
5. Merge the PR (squash or merge commit — user's preference)
6. Tag the merge commit on main
7. Deploy from main

## DevContainer & Submodule Rules

All `nx` commands MUST run through the devcontainer:

```bash
npx -y @devcontainers/cli exec \
  --workspace-folder /home/mateo/work/concord/concord \
  --config /home/mateo/work/concord/concord/.devcontainer/base/devcontainer.json \
  <command>
```

When operating from the umbrella repo (`/home/mateo/work/`), concord is a git
submodule. Git does not work inside the devcontainer because `.git` is a pointer
file to an unmounted parent directory. The deploy script falls back to
`.git-build-info` for commit metadata.

**Before EVERY deploy command**, refresh `.git-build-info` on the host:

```bash
{ git -C /home/mateo/work/concord/concord rev-parse --short HEAD; \
  git -C /home/mateo/work/concord/concord rev-parse --abbrev-ref HEAD; \
  [ -n "$(git -C /home/mateo/work/concord/concord status --porcelain 2>/dev/null)" ] \
    && echo true || echo false; \
} > /home/mateo/work/concord/concord/.git-build-info
```

Chain it before the devcontainer exec with `&&`.

## Phase 1 — Pre-flight

1. Confirm we are on `main` branch and it is clean
2. Read current `VERSION` file
3. Find the latest git tag (`git describe --tags --abbrev=0`)
4. If the user supplied an explicit version in `$ARGUMENTS`, use that.
   Otherwise determine bump type from commit history:
   - Any `feat:` → minor bump
   - Only `fix:/chore:/refactor:` → patch bump
   Propose the bump and wait for confirmation.

## Phase 2 — Create release branch

```bash
git checkout -b release/vX.Y.Z
```

All subsequent changes happen on this branch.

## Phase 3 — Gate checks

Run the release gate:

```bash
python3 scripts/release_gate.py --skip-slow
```

If any check fails, explain which and ask the user whether to override or fix.

For the full gate (with tests + typecheck), run inside the devcontainer:

```bash
npx -y @devcontainers/cli exec ... python3 scripts/release_gate.py
```

## Phase 4 — Version bump

Write the new version to `VERSION`:

```bash
echo "X.Y.Z" > VERSION
```

## Phase 5 — Changelog

Generate the changelog from the last tag:

```bash
python3 scripts/changelog.py <last-tag> HEAD
```

Present to the user for review. Ask if they want a human-written summary.

## Phase 6 — Commit and push the release branch

1. Set git identity:
   ```bash
   git config user.name "Mateo Segura" && git config user.email "mateo@corekinect.com"
   ```

2. Stage and commit:
   ```bash
   git add VERSION
   git commit -m "chore(release): vX.Y.Z"
   ```

3. Push the branch:
   ```bash
   git push -u origin release/vX.Y.Z
   ```

**Never include AI/Claude/LLM references in commit messages.**

## Phase 7 — Create PR and merge

Create a pull request to main:

```bash
gh pr create --base main --head release/vX.Y.Z \
  --title "release: vX.Y.Z" \
  --body "$(cat <<'EOF'
## Release vX.Y.Z

### Changes
<changelog summary>

### Checklist
- [ ] Gate checks passed
- [ ] Version bumped in VERSION file
- [ ] Changelog reviewed
EOF
)"
```

Wait for user confirmation, then merge:

```bash
gh pr merge release/vX.Y.Z --merge --delete-branch
```

## Phase 8 — Tag on main

After the merge, switch to main, pull, and tag:

```bash
git checkout main
git pull origin main
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin --tags
```

## Phase 9 — Deploy staging and production (parallel)

Deploy both environments in parallel. Each deploy command must be preceded by
the `.git-build-info` refresh.

**Staging:**
```bash
{ git -C /home/mateo/work/concord/concord rev-parse --short HEAD; ... } > .git-build-info && \
npx -y @devcontainers/cli exec ... nx update platform -c staging
```

**Production:**
```bash
{ git -C /home/mateo/work/concord/concord rev-parse --short HEAD; ... } > .git-build-info && \
npx -y @devcontainers/cli exec ... nx update platform -c production
```

Run both as background tasks. Verify the output shows:
- Correct `version=X.Y.Z` and `commit=<expected>`
- All pods verified (checkmark for each deployment)
- Smoke tests passed

## Phase 10 — Create release records (both environments)

Create release records in both staging and production databases. The API requires
a valid JWT.

### Generate a JWT inside the pod

```bash
JWT_SECRET=$(kubectl get secret -n <namespace> concord-secrets -o jsonpath='{.data.JWT_SECRET_KEY}' | base64 -d)

TOKEN=$(kubectl exec -n <namespace> deploy/concord-http-api -- python3 -c "
import jwt; from datetime import datetime, timezone, timedelta
token = jwt.encode({
    'sub': '<USER_ID>',
    'email': 'mateo@corekinect.com',
    'name': 'Mateo Segura',
    'role': 'ADMIN',
    'iat': datetime.now(timezone.utc),
    'exp': datetime.now(timezone.utc) + timedelta(hours=1),
}, '$JWT_SECRET', algorithm='HS256')
print(token)
")
```

The `sub` claim MUST be a real user ID from the database — synthetic IDs
cause a foreign key violation on `createdById`.

### POST the release record

```bash
kubectl exec -n <namespace> deploy/concord-http-api -- \
  curl -s -X POST http://localhost:9001/v2/releases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "version": "X.Y.Z",
    "commitSha": "<sha>",
    "branch": "main",
    "status": "RELEASED",
    "previousVersion": "<prev>",
    "changelog": "<changelog_markdown>",
    "summary": "<user_summary>",
    "gateStatus": "passed"
  }'
```

If the version already exists (409 Conflict), use PATCH instead:

```bash
curl -s -X PATCH http://localhost:9001/v2/releases/<id> \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"status": "RELEASED", "commitSha": "<sha>"}'
```

Create records in **both** staging and production — they have separate databases.

## Phase 11 — Link resolved bugs

If there are error reports fixed in this release:

1. List acknowledged/open error reports
2. Ask the user which ones were resolved
3. Link them:
   ```bash
   curl -s -X POST http://localhost:9001/v2/releases/<id>/link-bugs \
   -H "Content-Type: application/json" \
   -d '{"errorReportIds": ["id1", "id2"]}'
   ```

## Abort / Rollback

| Phase | Recovery |
|-------|----------|
| Before PR merge | Delete the branch: `git push origin --delete release/vX.Y.Z` |
| After merge, before deploy | `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z` |
| After staging deploy | `nx rollback platform -c staging` (via devcontainer) |
| After production deploy | `nx rollback platform -c production` (via devcontainer) |

Always ask before performing destructive rollback actions.

## Common pitfalls

- **Pushing directly to main**: Never. Always use a release branch + PR.
- **Stale commit hash in builds**: Forgetting to refresh `.git-build-info` before
  the devcontainer exec. The build output will show the wrong commit.
- **OOMKill after changes**: http-api has memory limits (staging: 1Gi, production: 1Gi).
  If a change increases memory usage, check pod status after deploy.
- **Release record already exists**: The POST returns 409 if the version string
  already exists. Use PATCH to update the existing record.
- **Import crashes in http-api**: Module-level imports that trigger config
  initialization will crash the pod. Board discovery and similar heavy inits
  must be lazy-imported inside `if __name__ == "__main__":`.
- **Version mismatch across UI**: All three version displays (sidebar, settings,
  releases badge) read `PUBLIC_APP_VERSION`. If they ever show different values,
  something bypassed the `VERSION` file. Fix the source, don't patch the UI.

## Quick reference

| Nx command (via devcontainer) | Purpose |
|-------------------------------|---------|
| `nx diff platform -c staging` | Preview Helm changes |
| `nx update platform -c staging` | Build + deploy staging |
| `nx status platform -c staging` | Check pod status |
| `nx rollback platform -c staging` | Rollback last deploy |

| API endpoint | Method | Purpose |
|-------------|--------|---------|
| `/v2/releases` | POST | Create release record |
| `/v2/releases` | GET | List releases |
| `/v2/releases/<id>` | PATCH | Update status / fields |
| `/v2/releases/<id>/link-bugs` | POST | Link resolved bugs |
