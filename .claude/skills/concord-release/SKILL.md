---
name: concord-release
description: Create a Concord platform release — version bump, changelog, gate checks, deploy, and release record creation
user-invocable: true
argument-hint: "[version] or leave blank for auto-detect"
---

# Concord Platform Release

Orchestrate a full Concord platform release. A release is an atomic semver-tagged
commit on `main` that covers all 5 platform services (http-api, frontend, docs,
git-poller, mtib-server) plus the independently-versioned components (corekinect
SDK, MTIB proto).

Arguments: $ARGUMENTS

## What a release covers

A release bundles:
- **Platform version** (`VERSION` file at repo root) — one semver for all 5 services
- **corekinect SDK** (`libs/python/corekinect/__init__.py` → `__version__`) — independently versioned
- **MTIB proto** (`libs/protocols/mtib/VERSION`) — independently versioned
- **Prisma migration hash** — current schema fingerprint
- **Changelog** — auto-generated from conventional commits since last tag
- **Compatibility matrix** — which versions of each component ship together

## Phase 1 — Pre-flight

1. Confirm we are on `main` branch (or the user has a reason not to be)
2. Confirm the working tree is clean (`git status --porcelain`)
3. Read current `VERSION` file
4. Find the latest git tag (`git describe --tags --abbrev=0`)
5. Run the changelog script to determine the suggested bump type:
   ```bash
   python3 scripts/changelog.py
   ```
   The exit code tells you the bump: 0=patch, 1=minor, 2=major.
6. If the user supplied an explicit version in `$ARGUMENTS`, use that. Otherwise
   propose the auto-detected bump (e.g. "Commits suggest a minor bump: 0.4.0 → 0.5.0").
   Wait for confirmation before proceeding.

## Phase 2 — Gate checks

Run the release gate (fast mode first for quick feedback):

```bash
python3 scripts/release_gate.py --skip-slow
```

Review the JSON output. If any check fails:
- Explain which check failed and why
- Ask if the user wants to `--override` with a reason, or fix the issue first

If the user wants the full gate (with tests + typecheck):

```bash
docker exec concord-dev bash -c "cd /workspaces/concord && python3 scripts/release_gate.py"
```

This runs inside the devcontainer where nx/npx are available.

## Phase 3 — Version bump

1. Write the new version to `VERSION`:
   ```bash
   echo "X.Y.Z" > VERSION
   ```

2. Gather compatibility info:
   ```bash
   python3 scripts/compatibility.py
   ```
   Save this output — it goes into the release record.

## Phase 4 — Changelog

Generate the full changelog from the last tag to HEAD:

```bash
python3 scripts/changelog.py <last-tag> HEAD
```

Capture the markdown output. Present it to the user for review. Ask if they
want to add a human-written summary or edit the changelog before committing.

## Phase 5 — Commit and tag

1. Stage the VERSION file:
   ```bash
   git add VERSION
   ```

2. Commit with conventional commit format:
   ```bash
   git commit -m "chore(release): vX.Y.Z"
   ```

3. Create an annotated tag:
   ```bash
   git tag -a vX.Y.Z -m "Release vX.Y.Z"
   ```

4. Push the commit and tag:
   ```bash
   git push origin main --follow-tags
   ```
   **Wait for user confirmation before pushing.**

## Phase 6 — Deploy staging

Deploy to staging and verify:

```bash
nx diff platform -c staging
```

Show the diff to the user. If it looks correct:

```bash
nx update platform -c staging
```

Then verify:

```bash
nx status platform -c staging
```

Wait for all pods to be Running/Ready before proceeding.

## Phase 7 — Create release record (staging)

The API requires authentication even for internal calls. Generate a JWT inside
the pod (PyJWT is available) using the environment's secret and a real user ID.

### Step 1: Get the JWT secret and a user ID

```bash
JWT_SECRET=$(kubectl get secret -n staging concord-secrets -o jsonpath='{.data.JWT_SECRET_KEY}' | base64 -d)
```

List users to find Mateo's ID (or whichever admin is doing the release):
```bash
kubectl exec -n staging deploy/concord-http-api -- python3 -c "
import jwt; from datetime import datetime, timezone, timedelta
secret = '<JWT_SECRET>'
# Use a known admin user ID from the DB
token = jwt.encode({
    'sub': '<USER_ID>',
    'email': 'mateo@corekinect.com',
    'name': 'Mateo Segura',
    'role': 'ADMIN',
    'iat': datetime.now(timezone.utc),
    'exp': datetime.now(timezone.utc) + timedelta(hours=1),
}, secret, algorithm='HS256')
print(token)
"
```

### Step 2: Create the release record

```bash
kubectl exec -n staging deploy/concord-http-api -- \
  curl -s -X POST http://localhost:9001/v2/releases \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{
    "version": "X.Y.Z",
    "commitSha": "<sha>",
    "branch": "main",
    "status": "RELEASED",
    "previousVersion": "<prev>",
    "corekinectVersion": "<ck_ver>",
    "protoVersion": "<proto_ver>",
    "changelog": "<changelog_markdown>",
    "summary": "<user_summary>",
    "gateStatus": "passed"
  }'
```

**Critical:** The JWT `sub` claim MUST be a real user ID from the database —
a synthetic ID like `"system-release"` causes a foreign key violation on
`createdById`.

Verify: list releases to confirm the record exists.

## Phase 8 — Staging validation

Ask the user to validate staging:
- Check the Releases page shows the new version
- Smoke test critical paths
- Verify the changelog renders correctly

If the user reports issues, help debug. Do not proceed to production until
staging is validated.

## Phase 9 — Deploy production

Same flow as staging:

```bash
nx diff platform -c production
nx update platform -c production
nx status platform -c production
```

Wait for pods. Then create the production release record using the same JWT
generation pattern as Phase 7 but with the **production** namespace and its
own JWT secret:

```bash
JWT_SECRET=$(kubectl get secret -n production concord-secrets -o jsonpath='{.data.JWT_SECRET_KEY}' | base64 -d)
```

Generate a token and POST to `/v2/releases` in the production namespace.
Use `status: "RELEASED"` if deploying directly to production.

## Phase 10 — Update release status

If you created the release record as DRAFT initially (e.g., during staging),
update it to RELEASED after production deploy is verified:

```bash
kubectl exec -n <namespace> deploy/concord-http-api -- \
  curl -s -X PATCH http://localhost:9001/v2/releases/<id> \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <TOKEN>" \
  -d '{"status": "RELEASED"}'
```

## Phase 11 — Link resolved bugs

If there are error reports that were fixed in this release:

1. List acknowledged/open error reports
2. Ask the user which ones were resolved
3. Link them:
   ```bash
   curl -s -X POST http://localhost:9001/v2/releases/<id>/link-bugs \
   -H "Content-Type: application/json" \
   -d '{"errorReportIds": ["id1", "id2"]}'
   ```

## Abort / Rollback

If something goes wrong at any phase:

- **Before push (Phase 5):** `git tag -d vX.Y.Z && git reset --soft HEAD~1` to undo
- **After staging deploy:** `nx rollback platform -c staging`
- **After production deploy:** `nx rollback platform -c production`

Always ask before performing destructive rollback actions.

## Quick reference

| Script | Purpose | Run from |
|--------|---------|----------|
| `scripts/release_gate.py` | Pre-flight checks | repo root |
| `scripts/release_gate.py --skip-slow` | Fast gate (no tests) | repo root |
| `scripts/changelog.py [from] [to]` | Generate changelog | repo root |
| `scripts/compatibility.py` | Version matrix | repo root |

| Nx command | Purpose |
|-----------|---------|
| `nx diff platform -c staging` | Preview Helm changes |
| `nx update platform -c staging` | Build + deploy staging |
| `nx status platform -c staging` | Check pod status |
| `nx rollback platform -c staging` | Rollback last deploy |

| API endpoint | Method | Purpose |
|-------------|--------|---------|
| `/v2/releases` | POST | Create release record |
| `/v2/releases` | GET | List releases |
| `/v2/releases/<id>` | PATCH | Update status |
| `/v2/releases/<id>/link-bugs` | POST | Link resolved bugs |
