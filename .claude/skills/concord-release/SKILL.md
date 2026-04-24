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

## Definition of Done (READ FIRST, CHECK LAST)

A release is **not done** until **every** box below is checked. The AI must
walk this list before claiming the release is complete. If any box is unchecked,
the release is incomplete — continue work until all boxes pass.

```
[ ] VERSION bumped on a release branch (never on main directly)
[ ] Release branch merged into main
[ ] Annotated tag vX.Y.Z pushed to origin
[ ] Staging deployed and rollout verified
[ ] Staging release record exists in DB (POST /v2/releases returned 2xx)
[ ] Production deployed and rollout verified
[ ] Production release record exists in DB (POST /v2/releases returned 2xx)
[ ] Resolved bugs linked (or user confirmed "none") in both environments
```

**Why this exists:** the release records drive the `/releases` page, the
update-notification toast history, and bug-resolution traceability. A deploy
without a DB record is a silent data-loss bug. The pairing `deploy → record`
is enforced by structure (Phases 9 and 10 each bundle both steps).

Never treat the deploy as "the last step." The deploy is step 1 of 2 in each
Phase 9/10 pair.

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

0. **Record start time:** `RELEASE_START=$(date +%s%3N)` — used for `releaseDurationMs`
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

## Phase 5 — Changelog and release metadata collection

This phase collects ALL data that will be included in the release record.
Store every value as a shell variable for use in Phase 10.

### 5a. Generate changelog

```bash
CHANGELOG=$(python3 scripts/changelog.py <last-tag> HEAD)
```

The script outputs markdown grouped by category (Features, Bug Fixes, Refactors,
etc.) and prints the suggested bump type to stderr. Present the changelog to the
user for review. Ask if they want a human-written summary for the `summary`
field — if not, generate a one-liner from the changelog.

### 5b. Detect breaking changes

```bash
BREAKING=$(git log <last-tag>..HEAD --pretty=format:'%h %s%n%b' | grep -E 'BREAKING CHANGE:|^[a-f0-9]+ \w+(\(\w+\))?!:' || true)
```

If non-empty, format as markdown bullet list for the `breakingChanges` field.

### 5c. Collect diff stats

```bash
DIFF_STAT=$(git diff --shortstat <last-tag>..HEAD)
LINES_ADDED=$(echo "$DIFF_STAT" | grep -oP '\d+(?= insertion)' || echo 0)
LINES_REMOVED=$(echo "$DIFF_STAT" | grep -oP '\d+(?= deletion)' || echo 0)
```

### 5d. Read component versions

```bash
COREKINECT_VERSION=$(grep -oP '__version__\s*=\s*"\K[^"]+' libs/python/corekinect/__init__.py)
PROTO_VERSION=$(cat libs/protocols/mtib/VERSION 2>/dev/null || echo "unknown")
```

### 5e. Compute migration hash

```bash
MIGRATION_HASH=$(sha256sum prisma/schema.prisma | cut -d' ' -f1 | head -c 12)
```

### 5f. Run tests (inside devcontainer)

Run backend and frontend tests and capture results:

```bash
# Backend tests
BACKEND_TEST_OUTPUT=$(npx -y @devcontainers/cli exec \
  --workspace-folder /home/mateo/work/concord/concord \
  --config /home/mateo/work/concord/concord/.devcontainer/base/devcontainer.json \
  bash -c 'cd apps/backend/http-api && PYTHONPATH=src:$(pwd)/../../../libs/python:$(pwd)/../../../libs:. pytest tests/ -v --tb=short 2>&1' || true)

# Frontend tests
FRONTEND_TEST_OUTPUT=$(npx -y @devcontainers/cli exec \
  --workspace-folder /home/mateo/work/concord/concord \
  --config /home/mateo/work/concord/concord/.devcontainer/base/devcontainer.json \
  nx test app 2>&1 || true)
```

Parse the pytest/vitest output to extract:
- `testsPassed` — total passed across both suites
- `testsFailed` — total failed across both suites
- `testDurationMs` — combined duration
- `testDetails` — JSON with per-suite breakdown:

```json
{
  "backend": { "passed": N, "failed": N, "durationMs": N },
  "frontend": { "passed": N, "failed": N, "durationMs": N }
}
```

Pytest summary line format: `X passed, Y failed in Zs`
Vitest summary line format: `Tests  X passed | Y failed` and `Duration  Xs`

If tests fail, warn the user but don't block the release — they can override.

### 5g. Summarize for the user

Present a table of everything collected:

| Field | Value |
|-------|-------|
| Version | X.Y.Z |
| Previous | A.B.C |
| Changelog | (X features, Y fixes, Z other) |
| Breaking changes | yes/no |
| Lines | +N / -M |
| Tests | P passed, F failed |
| corekinect | version |
| proto | version |
| Migration hash | abc123... |

Wait for user confirmation before proceeding.

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

**Capture the PR URL** from the output for the release record's `prUrl` field.
If using Bitbucket (no `gh` CLI), capture the URL from the Bitbucket PR
creation response or construct it manually. If merging locally with
`git merge --no-ff`, set `prUrl` to `null`.

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

## Phase 9 — Deploy STAGING + create staging release record (one atomic pair)

**This phase has TWO mandatory steps. Do not move to Phase 10 until BOTH are
complete.** If you deploy without creating the record, the release is broken.
Think of these as a single logical operation, not two.

### 9.1 — Refresh .git-build-info and deploy staging

```bash
{ git -C /home/mateo/work/concord/concord rev-parse --short HEAD; ... } > .git-build-info && \
npx -y @devcontainers/cli exec ... nx update platform -c staging
```

Verify the output shows:
- Correct `version=X.Y.Z` and `commit=<expected>`
- All pods verified (checkmark for each deployment)
- Smoke tests passed

### 9.2 — Create the staging release record (IMMEDIATELY, before Phase 10)

Do this now, not later. See the "Create release record" section below for the
mechanics. Use the staging user ID and staging pod.

- Find the http-api pod: `kubectl get pods -n staging -o name | grep concord-http-api | head -1`
- Generate JWT inside the pod using `JWT_SECRET_KEY` env var
- POST `/v2/releases` with all collected metadata
- Verify the record by GET `/v2/releases?limit=5`

**Exit criteria for Phase 9:** the POST returned 2xx and the version appears in
the list. Do not proceed to Phase 10 otherwise.

## Phase 10 — Deploy PRODUCTION + create production release record (one atomic pair)

Same structure as Phase 9. Deploy and record are a single logical unit.

### 10.1 — Refresh .git-build-info and deploy production

```bash
{ git -C /home/mateo/work/concord/concord rev-parse --short HEAD; ... } > .git-build-info && \
npx -y @devcontainers/cli exec ... nx update platform -c production
```

### 10.2 — Create the production release record (IMMEDIATELY)

Same mechanics as 9.2 but with the production pod and the production user ID.

**Exit criteria for Phase 10:** the POST returned 2xx and the version appears
in production `/v2/releases`.

## Create release record — shared mechanics

Used by both Phase 9.2 and Phase 10.2. The steps are identical except for the
namespace, pod, and user ID.

### Step 1: Generate a JWT inside the pod

Use the pod's own `JWT_SECRET_KEY` env var (never pass secrets through shell):

```bash
TOKEN=$(kubectl exec -n <namespace> deploy/concord-http-api -- python3 -c "
import jwt, os
from datetime import datetime, timezone, timedelta
token = jwt.encode({
    'sub': '<USER_ID>',
    'email': 'mateo@corekinect.com',
    'name': 'Mateo Segura',
    'role': 'ADMIN',
    'iat': datetime.now(timezone.utc),
    'exp': datetime.now(timezone.utc) + timedelta(hours=1),
}, os.environ['JWT_SECRET_KEY'], algorithm='HS256')
print(token)
" 2>/dev/null)
```

**Known user IDs** (look up if stale — query `/v2/users` with any valid token):
- Staging: `cmnz59zya000ylno28xrj4gu1` (mateo@corekinect.com)
- Production: `cmny0hvd0000yq1k0vmv2mwto` (mateo@corekinect.com)

### Step 2: Compute release duration

```bash
RELEASE_END=$(date +%s%3N)
RELEASE_DURATION_MS=$(( RELEASE_END - RELEASE_START ))
```

### Step 3: POST the release record with ALL collected data

Include **every field** collected in Phase 5. The API accepts all of these:

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
    "summary": "<one-line summary>",
    "changelog": "<full markdown changelog from 5a>",
    "breakingChanges": "<breaking changes text from 5b, or null>",
    "linesAdded": <N from 5c>,
    "linesRemoved": <M from 5c>,
    "corekinectVersion": "<from 5d>",
    "protoVersion": "<from 5d>",
    "migrationHash": "<from 5e>",
    "testsPassed": <total from 5f>,
    "testsFailed": <total from 5f>,
    "testDurationMs": <total from 5f>,
    "testDetails": { "backend": { ... }, "frontend": { ... } },
    "prUrl": "<PR URL from Phase 7, or null if local merge>",
    "releaseOrigin": "manual",
    "releaseDurationMs": <RELEASE_DURATION_MS>,
    "gateStatus": "passed"
  }'
```

**Required fields:** version, commitSha, branch, status.
**All other fields are optional** but MUST be populated when available.

If the version already exists (409 Conflict), use PATCH instead to update
the existing record with the full data.

### Step 4: Verify

List releases and confirm the new version appears at the top:

```bash
kubectl exec -n <namespace> deploy/concord-http-api -- \
  curl -s http://localhost:9001/v2/releases?limit=3 \
  -H "Authorization: Bearer $TOKEN"
```

Only after this confirms the record exists may you claim the phase is done.

### Note on running both environments

Staging (Phase 9) and production (Phase 10) each follow this same recipe.
They have separate databases, separate JWT secrets, and separate user IDs.
Do not batch the POSTs together at the end — each deploy pairs with its own
record creation immediately.

## Phase 11 — Link resolved bugs (MANDATORY)

**Always run this step.** Query open/acknowledged error reports and ask the
user which ones this release fixes. Linking is the canonical close-loop:
the `/link-bugs` endpoint atomically stamps `resolvedInReleaseId`, flips
`status` to `RESOLVED`, and sets `resolvedAt`/`resolvedById`. There is no
separate "mark resolved" step anymore — linking == fixing.

### Step 1: Fetch open and acknowledged reports

The status param now accepts a comma-separated list:

```bash
kubectl exec -n <namespace> deploy/concord-http-api -- \
  curl -s "http://localhost:9001/v2/system/error-reports?status=OPEN,ACKNOWLEDGED&limit=50" \
  -H "Authorization: Bearer $TOKEN"
```

### Step 2: Present to user

Show the user a numbered list of open/acknowledged reports with:
- ID, type, severity, message, first/last seen, currentPath, appVersion

Ask which ones this release resolves (by number or "none").

### Step 3: Link selected reports

For each confirmed resolution, POST to `/link-bugs` using the release ID from
Phase 9.2 / 10.2:

```bash
kubectl exec -n <namespace> deploy/concord-http-api -- \
  curl -s -X POST "http://localhost:9001/v2/releases/<release-id>/link-bugs" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"errorReportIds": ["id1", "id2"]}'
```

One call per environment. The IDs and the release ID are environment-specific.

### Step 4: Verify the close-loop

Confirm the reports now appear under `resolvedErrorReports` on the release
detail:

```bash
kubectl exec -n <namespace> deploy/concord-http-api -- \
  curl -s "http://localhost:9001/v2/releases/<release-id>" \
  -H "Authorization: Bearer $TOKEN" | \
  python3 -c "import json, sys; d = json.load(sys.stdin); print(len(d['data']['resolvedErrorReports']), 'bugs linked')"
```

### Unlinking (rare)

If you realize a report was linked to the wrong release, use:

```bash
curl -s -X DELETE "http://localhost:9001/v2/releases/<release-id>/resolved-bugs/<report-id>" \
  -H "Authorization: Bearer $TOKEN"
```

This unlinks the report and flips it back to `OPEN`.

## Abort / Rollback

| Phase | Recovery |
|-------|----------|
| Before PR merge | Delete the branch: `git push origin --delete release/vX.Y.Z` |
| After merge, before deploy | `git tag -d vX.Y.Z && git push origin :refs/tags/vX.Y.Z` |
| After staging deploy | `nx rollback platform -c staging` (via devcontainer) |
| After production deploy | `nx rollback platform -c production` (via devcontainer) |

Always ask before performing destructive rollback actions.

## Common pitfalls

- **Skipping the release record**: The single most common failure mode. After
  a successful deploy, it feels like the release is "done" — but the `/releases`
  page is empty until the DB record is POSTed. Phases 9 and 10 pair deploy +
  record specifically to prevent this. If you have deployed but not POSTed,
  the release is not complete; go back and post the record before anything else.
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
