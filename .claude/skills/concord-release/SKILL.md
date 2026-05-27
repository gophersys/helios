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
[ ] Phase 0 pre-release hook reviewed (coupling reminder, if any)
[ ] Phase 0.5 release-impact auditor agent run (if Phase 0 flagged anything)
[ ] Component-impact matrix consulted (see next section) — release type chosen
[ ] Runner-rebuild gate passed (Phase 1.5 — Phase D Layer 3)
[ ] VERSION bumped on a release branch (never on main directly)
[ ] corectl version bumped IF the release touches corectl
[ ] corekinect version bumped IF the release touches corekinect
[ ] Release branch merged into main
[ ] Annotated tag vX.Y.Z pushed to origin
[ ] Staging deployed and rollout verified
[ ] corectl + corekinect wheels published to STAGING pypi (only the bumped ones)
[ ] **If corekinect bumped: staging http-api/runner image rebuilt and rolled** —
    the runner pod bakes corekinect at image-build time, NOT pip-installs at
    session start. A wheel-only republish leaves runners on the old version.
[ ] Staging release record exists in DB (POST /v2/releases returned 2xx)
[ ] Production deployed and rollout verified
[ ] corectl + corekinect wheels published to PRODUCTION pypi (only the bumped ones)
[ ] **If corekinect bumped: production http-api/runner image rebuilt and rolled**
[ ] Production release record exists in DB (with corectlMinVersion + corekinectVersion populated)
[ ] **Phase 11 — Test-app refresh sweep run (every entry in .claude/known-test-apps.yaml refreshed + re-uploaded)** — Phase D Layer 5
[ ] Resolved bugs linked (or user confirmed "none") in both environments
```

**Why this exists:** the release records drive the `/releases` page, the
update-notification toast history, and bug-resolution traceability. A deploy
without published wheels is broken — the new backend expects clients running
the new corectl/corekinect — so deploy and publish must ship together. A deploy
without a DB record is a silent data-loss bug.

**The runner-image gotcha:** the `concord-mtib-runner` and `concord-http-api`
Docker images install corekinect from the in-repo source at build time
(`pip install -e libs/python`). They do NOT pip-install corekinect from pypi
at runtime. Bumping corekinect on pypi without rebuilding the platform images
means: tools that install corekinect via `pip install corekinect` (corectl,
local dev) get the new version, but every manufacturing/validation runner pod
keeps using whatever corekinect was bundled in the image it was deployed
from. ALWAYS pair a corekinect bump with a platform deploy.

Phases 9 and 10 each bundle the steps: **deploy → publish wheels → create
record**. Never treat the deploy as "the last step."

## Hard gate: clean tree required (Phases 1, 9, 10)

Releases and deploys MUST run from a clean working tree. Before:
- Phase 1 (starting the release)
- Phase 9 (`nx update platform -c staging`)
- Phase 10 (`nx update platform -c production`)

run this check:

```bash
DIRTY=$(git -C /home/bottinger/work/concord/concord status --porcelain)
if [ -n "$DIRTY" ]; then
  echo "Working tree is dirty — release/deploy refused. Offending entries:"
  echo "$DIRTY"
  exit 1
fi
```

If the gate fails, **STOP**. Do NOT:
- `git stash` (silently hides work)
- `git checkout .` or `git restore .` (destroys uncommitted changes)
- `git clean -fd` (deletes untracked files — could be in-progress work)
- auto-add and commit "WIP" (poisons history)
- proceed anyway "because it's just untracked"

The user MUST resolve the dirty state themselves. Their options:
- commit the changes to a feature branch (e.g.
  `feature/mega-cleanup-that-may-never-happen` is the holding pen for
  long-lived "park this for later" work)
- stash with `git stash -u` themselves and reapply after the release
- delete files they confirm are trash
- add a `.gitignore` rule if a file should never be tracked

This rule applies even if the user says "just go" or "ignore the dirty
files" — refuse and quote this gate. The reasons:

1. **Reproducibility.** A deploy from a dirty tree means the running
   image's source state is impossible to reconstruct from the tag.
2. **`.git-build-info` lies.** The submodule fallback for `commit` and
   `branch` doesn't capture uncommitted local edits — pods come up
   reporting a commit SHA that doesn't match what they're actually
   running.
3. **Build cache poisoning.** Some Dockerfile layers `COPY .` and pick up
   stray files (like an editor swap file or a `.git-build-info` written by
   a previous run); those bake into the image silently.
4. **Untracked artifacts get pushed by accident.** If a later step does a
   `git add -A` the dirty entries get swept into the release commit.

If you're tempted to bypass: don't. This gate exists because every prior
"just this once" turned into the next debugging session.

## Versioning model — lockstep major.minor

Platform, corectl, and corekinect share the same `major.minor` version. Patch
versions can diverge for hot-fixes that touch only one component, but every
**minor or major** release bumps all three together. This makes "I'm running
0.6.x" mean platform, corectl, and corekinect are all at 0.6.x and known to
be compatible.

| Component | Source of truth | Where it ships |
|-----------|-----------------|----------------|
| Platform (http-api, frontend, runners) | `VERSION` (repo root) | Docker images on `containers.ad.corekinect.com` |
| corectl CLI | `tools/corectl/src/corectl/__init__.py` `__version__` | `pypi.<host>/simple/corectl/` |
| corekinect framework | `libs/python/corekinect/__init__.py` `__version__` | `pypi.<host>/simple/corekinect/` |

`tools/corectl/pyproject.toml` reads its version dynamically from the
`__init__.py` (`[tool.hatch.version] path = "src/corectl/__init__.py"`). The
top-level `libs/python/pyproject.toml` reads corekinect's version from
`corekinect.__version__` via `setuptools.dynamic`. Bumping the `__init__.py`
is the only edit needed.

Each release record carries:
- `corectlMinVersion` — minimum corectl that works against this backend (set
  to the version published with this release; older corectl gets rejected at
  upload time when the compat-check lands)
- `corekinectVersion` — the corekinect framework version published with this
  release

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

- **Platform version** (`VERSION`) — one semver for all services. Drives Docker image tags.
- **corectl CLI** (`tools/corectl/src/corectl/__init__.py` `__version__`) — published as a wheel to the pypi server. Lockstep `major.minor` with platform.
- **corekinect framework** (`libs/python/corekinect/__init__.py` `__version__`) — published as a wheel to the pypi server. Lockstep `major.minor` with platform.
- **MTIB proto** (`libs/protocols/mtib/VERSION`) — independently versioned
- **Prisma migration hash** — current schema fingerprint
- **Changelog** — auto-generated from conventional commits since last tag

## Component impact matrix — pick this BEFORE Phase 1

Walk this table on every release. Mismatches between "what changed" and "what
shipped" are the source of every subtle release bug we've hit (corekinect on
pypi but not in runner image, corectl bumped but the new templates not picked
up by users, schema migration committed but no platform deploy to apply it).

| Files changed | Bump | Wheel publish | Platform deploy | Why |
|---|---|---|---|---|
| `apps/backend/**`, `apps/frontend/**`, `deploy/**`, `prisma/**` | VERSION | no | yes | Backend/frontend/infra change. The runner image rebuilds with whatever corekinect is in `libs/python` even if you don't bump corekinect. |
| `libs/python/corekinect/**` | VERSION + corekinect | corekinect | **yes** | Runner + http-api pods bake corekinect at image-build time. Wheel publish without deploy → tools updated, but every runner pod still on the old version. |
| `tools/corectl/**` (templates, validator, CLI) | VERSION + corectl | corectl | usually no | corectl runs on the operator's host; pypi update is enough. Skip the platform deploy unless `apps/backend` also changed. |
| `tools/corectl/templates/_shared/**` only | corectl | corectl | no | Operators get new templates on next `corectl test update`. No backend change required. |
| `libs/protocols/mtib/**` | VERSION + corekinect (regenerate stubs) | corekinect | yes | Wire-format change — runners and tools must agree on the same proto version. |
| `prisma/schema.prisma` + migration | VERSION | no | yes | Migration runs as init-container on http-api pod start. Always bump VERSION so the deploy is traceable. |
| `infrastructure/**` | none | no | no | Cluster provisioning is its own layer; use `infrastructure/ctl.sh`. |

**Patch-only releases.** Patches MAY bump only the changed component as long
as they don't break the major.minor lockstep. Examples that worked cleanly:

- `concord 0.9.5` (backend-only, no wheel) — corectl/corekinect stayed at 0.9.0.
- `corekinect 0.9.2` (autoconf fix only) — bumped corekinect AND VERSION
  because the runner image needed to rebuild; corectl stayed at 0.9.1.
- `corectl 0.9.1` (templates + validator) — bumped corectl, no platform deploy
  needed because no in-repo backend code changed.

**Patch-only releases are an exception to the lockstep rule, NOT to the
component-impact matrix.** If corekinect bumped, the platform deploys —
period.

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
  --workspace-folder /home/bottinger/work/concord/concord \
  --config /home/bottinger/work/concord/concord/.devcontainer/base/devcontainer.json \
  <command>
```

When operating from the umbrella repo (`/home/bottinger/work/`), concord is a git
submodule. Git does not work inside the devcontainer because `.git` is a pointer
file to an unmounted parent directory. The deploy script falls back to
`.git-build-info` for commit metadata.

**Before EVERY deploy command**, refresh `.git-build-info` on the host:

```bash
{ git -C /home/bottinger/work/concord/concord rev-parse --short HEAD; \
  git -C /home/bottinger/work/concord/concord rev-parse --abbrev-ref HEAD; \
  [ -n "$(git -C /home/bottinger/work/concord/concord status --porcelain 2>/dev/null)" ] \
    && echo true || echo false; \
} > /home/bottinger/work/concord/concord/.git-build-info
```

Chain it before the devcontainer exec with `&&`.

## Phase 0 — Coupling scan (pre-flight instrumentation)

Before any other release work, run the read-only coupling scan:

```bash
LAST_TAG=$(git describe --tags --abbrev=0)
bash .claude/hooks/pre-release "${LAST_TAG}" HEAD
```

The hook scans the `${LAST_TAG}..HEAD` range for risky path patterns
(corekinect, mtib protocols, corectl, prisma, deploy/) and emits a
`<system-reminder>`-formatted block listing downstream artifacts that
need attention and which Phase D enforcement layer will catch a
missed step. Silent when nothing risky is touched.

This is **purely informational** — it never blocks the release. The
actual gating happens later:
- Phase 1.5 (Phase D Layer 3): hard gate via
  `scripts/release-gates/check-runner-affected.sh`
- Deploy time (Phase D Layer 2): runner SHA gate in `ctl.sh`
- Runtime (Phase D Layer 4): framework-constraint gate in the
  runner pod

Read the section(s) the hook emits and confirm you've planned for the
listed downstream artifacts before moving to Phase 1.

## Phase 0.5 — Release-impact audit (when Phase 0 flagged anything)

If Phase 0 emitted a `<system-reminder>` (i.e., the range touched
something risky), spawn the `release-impact-auditor` sub-agent before
proceeding to Phase 1. Its persona at
[`.claude/agents/release-impact-auditor.md`](../../agents/release-impact-auditor.md)
reads the actual file diffs and produces a structured report
distinguishing test-only changes (low impact) from public-API or
wire-format changes (high impact), names specific verification
commands, and gives a go/no-go recommendation.

The auditor has **no Edit/Write tools** — it produces a Markdown
report on stdout, no mutations. Embed the report into your turn
output verbatim so the user sees it before they approve Phase 1.

If the auditor returns "Block — resolve these first", stop. Surface
the items to the user. Do not proceed to Phase 1 without explicit
user confirmation that they accept the listed risks.

## Phase 1 — Pre-flight

0. **Record start time:** `RELEASE_START=$(date +%s%3N)` — used for `releaseDurationMs`
1. Confirm we are on `main` branch and **the working tree is clean** — see
   "Hard gate: clean tree required" below. If `git status --porcelain` returns
   anything (modified, staged, untracked, ignored-but-tracked), **STOP**. Do
   not stash, do not auto-commit, do not `git clean`, do not start the
   release. Print the dirty entries and ask the user to handle them. The
   user's options are typically:
   - commit the changes to a feature branch
   - stash them with `git stash -u` themselves
   - delete the files themselves if they're trash
   - add a `.gitignore` rule if the file should never be tracked

   This rule applies even if the user says "just go" — refuse and quote this
   gate. The reason is below.

2. Read current `VERSION` file
3. Find the latest git tag (`git describe --tags --abbrev=0`)
4. If the user supplied an explicit version in `$ARGUMENTS`, use that.
   Otherwise determine bump type from commit history:
   - Any `feat:` → minor bump
   - Only `fix:/chore:/refactor:` → patch bump
   Propose the bump and wait for confirmation.

   **No digit-rollover.** Each version component (major, minor, patch) is an
   independent integer with no upper bound. We ship many revisions, so
   components routinely go past 9 — accept values up to at least 100 before
   ever considering a major bump:
   - `0.9.0` + minor bump → `0.10.0` (NOT `1.0.0`)
   - `0.9.99` + patch bump → `0.9.100` (NOT `0.10.0`)
   - `0.99.0` + minor bump → `0.100.0` (NOT `1.0.0`)
   - `0.10.5` + minor bump → `0.11.0`
   A major bump (`X.0.0` → `X+1.0.0`) only happens when there is an explicit
   `BREAKING CHANGE:` commit footer / `!` marker, or the user explicitly asks
   for a major bump. Never auto-roll a minor → major just because minor hit
   double digits. The release gate's semver pattern (`^\d+\.\d+\.\d+$`) already
   accepts any digit count — this rule is about your bump *decision*, not the
   format check.

## Phase 1.5 — Runner rebuild gate (Phase D Layer 3)

Before the release branch is cut, verify that if this release touches
`libs/python/corekinect/`, `libs/protocols/mtib/`, or `tools/corectl/`,
then the `test-runner` project will actually be rebuilt by the deploy.

The runner Docker image bakes those three trees in at build time. A
release that ships changes to them without rebuilding the runner
leaves deployed pods running stale code — the v0.12.0 → v0.12.3
silent-skew failure mode this enforcement was built to prevent.

```bash
LAST_TAG=$(git describe --tags --abbrev=0)
bash scripts/release-gates/check-runner-affected.sh "${LAST_TAG}" HEAD
```

Exit codes:
- `0` silent — nothing of interest touched in range (most releases)
- `0` info-banner — paths touched AND `test-runner` is in the Nx
  affected set; deploy will rebuild the runner image
- `0` loud-warn — touched-but-not-affected, bypassed via
  `CONCORD_FORCE_NO_RUNNER_REBUILD=1` (use only with explicit user
  approval; the deployed runner WILL be stale)
- `1` hard fail — paths touched, runner NOT affected. The script's
  error message names the touched projects and points at
  `deploy/runner/project.json` `implicitDependencies` (Phase D Layer 1)
  as the fix location.

If the gate fails:
1. Read the gate's error output — it lists which projects-of-interest
   changed and tells you what nx-affected query was used.
2. The fix is almost always missing `implicitDependencies` on the
   runner project. See [`.claude/knowledge/deploy/runner.md`](../../knowledge/deploy/runner.md).
3. Land the fix on a separate branch first, then retry the release.
4. Only set `CONCORD_FORCE_NO_RUNNER_REBUILD=1` with the user's
   explicit blessing.

The full layered enforcement is documented in
[`.claude/knowledge/deploy/runner.md`](../../knowledge/deploy/runner.md).
Tests for this gate live at
[`scripts/tests/test_check_runner_affected.py`](../../../scripts/tests/test_check_runner_affected.py).

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

Write the new version to `VERSION` and bump corectl + corekinect + Helm chart in lockstep:

```bash
echo "X.Y.Z" > VERSION

# corectl: bump src/corectl/__init__.py (pyproject.toml reads it dynamically)
sed -i 's/^__version__ = ".*"$/__version__ = "X.Y.Z"/' \
  tools/corectl/src/corectl/__init__.py

# corekinect: bump libs/python/corekinect/__init__.py
sed -i 's/^__version__ = ".*"$/__version__ = "X.Y.Z"/' \
  libs/python/corekinect/__init__.py

# Helm chart: bump version + appVersion in lockstep with VERSION.
# The chart is never published to a repo (helm upgrade runs from local
# checkout) so the bump is mostly an audit trail, but keeping it
# synchronized makes `helm history` and release records coherent.
sed -i 's/^version: .*/version: X.Y.Z/' deploy/production/helm/concord/Chart.yaml
sed -i 's/^appVersion: .*/appVersion: "X.Y.Z"/' deploy/production/helm/concord/Chart.yaml

# Verify
grep '^__version__' tools/corectl/src/corectl/__init__.py
grep '^__version__' libs/python/corekinect/__init__.py
grep -E '^(version|appVersion):' deploy/production/helm/concord/Chart.yaml
cat VERSION
```

All four should report `X.Y.Z`. **Patch-only releases that touch ONE component
(e.g. a corectl-only fix)** can keep the others' minors and bump only the patch
of the changed component — but that should be an exception, not the norm.

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
CORECTL_VERSION=$(grep -oP '__version__\s*=\s*"\K[^"]+' tools/corectl/src/corectl/__init__.py)
PLATFORM_VERSION=$(cat VERSION)
PROTO_VERSION=$(cat libs/protocols/mtib/VERSION 2>/dev/null || echo "unknown")
```

All three of `PLATFORM_VERSION`, `CORECTL_VERSION`, `COREKINECT_VERSION` MUST
match per the lockstep rule. If they don't, fix the bumps in Phase 4 before
proceeding.

```bash
[ "$PLATFORM_VERSION" = "$CORECTL_VERSION" ] && [ "$PLATFORM_VERSION" = "$COREKINECT_VERSION" ] \
  && echo "lockstep ok: $PLATFORM_VERSION" \
  || { echo "VERSIONS DRIFTED — fix Phase 4"; exit 1; }
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
  --workspace-folder /home/bottinger/work/concord/concord \
  --config /home/bottinger/work/concord/concord/.devcontainer/base/devcontainer.json \
  bash -c 'cd apps/backend/http-api && PYTHONPATH=src:$(pwd)/../../../libs/python:$(pwd)/../../../libs:. pytest tests/ -v --tb=short 2>&1' || true)

# Frontend tests
FRONTEND_TEST_OUTPUT=$(npx -y @devcontainers/cli exec \
  --workspace-folder /home/bottinger/work/concord/concord \
  --config /home/bottinger/work/concord/concord/.devcontainer/base/devcontainer.json \
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
   git config user.name "Blake Ottinger" && git config user.email "blake@corekinect.com"
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

## Phase 9 — Deploy STAGING + publish wheels + create staging release record

**This phase has THREE mandatory steps. Do not move to Phase 10 until ALL three
are complete.** Skipping wheel publishing leaves the new backend without a
matching corectl/corekinect on pypi — clients can't talk to it. Skipping the
record is a silent data-loss bug.

### 9.0 — Re-run the clean-tree gate

```bash
DIRTY=$(git -C /home/bottinger/work/concord/concord status --porcelain)
if [ -n "$DIRTY" ]; then echo "DIRTY — STOP"; echo "$DIRTY"; exit 1; fi
```

Even if Phase 1 was clean, files may have appeared between then and now
(test artifacts, editor temp files, in-progress edits during a long
release). Refuse the deploy if dirty — see "Hard gate: clean tree
required" near the top of this file.

### 9.1 — Refresh .git-build-info and deploy staging

```bash
{ git -C /home/bottinger/work/concord/concord rev-parse --short HEAD; ... } > .git-build-info && \
npx -y @devcontainers/cli exec ... nx update platform -c staging
```

Verify the output shows:
- Correct `version=X.Y.Z` and `commit=<expected>`
- All pods verified (checkmark for each deployment)
- Smoke tests passed

### 9.2 — Build + publish corectl and corekinect wheels to STAGING pypi

Build + push both wheels through the `nx push` targets. Each target depends
on `build`, port-forwards to `svc/concord-pypi` (port 18080 staging, 18081
production), and twine-uploads with authenticated htpasswd creds.

**Prereq — set pypi creds.** The push targets fail-fast if `PYPI_USERNAME`
or `PYPI_PASSWORD` is unset. Source them from wherever your team keeps the
htpasswd plaintext (the same one that landed in `infrastructure/clusters/office/secrets/shared.env`
as `PYPI_HTPASSWD`):

```bash
export PYPI_USERNAME=concord
export PYPI_PASSWORD=<plaintext from your team's secret store>
```

`twine` must be on PATH. If missing: `pip install --user twine`.

**Auto-detect what to publish.** Only push the wheels that changed in this
release (per the component impact matrix). Use git to detect:

```bash
RELEASE_BASE=$(git describe --tags --abbrev=0 HEAD^ 2>/dev/null || echo HEAD~1)
PUBLISH_CORECTL=$(git diff --name-only $RELEASE_BASE..HEAD -- tools/corectl/ | head -1 && echo yes || echo no)
PUBLISH_COREKINECT=$(git diff --name-only $RELEASE_BASE..HEAD -- libs/python/ libs/protocols/ | head -1 && echo yes || echo no)
```

If both report `no` and Phase 1 confirmed no version bump for that wheel,
skip the corresponding push.

**Push.** `nx push` re-runs `nx build` as a dependency, so this is one shot:

```bash
if [ "$PUBLISH_COREKINECT" = "yes" ]; then
  npx nx run corekinect:push:staging
fi
if [ "$PUBLISH_CORECTL" = "yes" ]; then
  npx nx run corectl:push:staging
fi
```

**Tests-passing gate.** Phase 6 already runs the full test suite as a
release gate. If Phase 6 reported any failure for `corectl` or
`corekinect` (e.g., `nx test corectl` or `nx test corekinect-python`),
the release halts — that test failure blocks the wheel publish for the
same reason it blocks the deploy. Do not push a wheel from a red test
suite.

**Verify both are listed:**

```bash
[ "$PUBLISH_CORECTL" = "yes" ] && curl -sSk https://pypi.staging.concord.ad.corekinect.com/simple/corectl/ | grep "X.Y.Z"
[ "$PUBLISH_COREKINECT" = "yes" ] && curl -sSk https://pypi.staging.concord.ad.corekinect.com/simple/corekinect/ | grep "X.Y.Z"
```

Each `grep` must find the version if its publish ran. If the pypi pod was
just restarted by the deploy in 9.1, give it ~5s to come back before the
push (the port-forward in the nx target retries on failure).

### 9.3 — Create the staging release record (IMMEDIATELY)

Do this now, not later. See the "Create release record" section below for the
mechanics. Use the staging user ID and staging pod.

- Find the http-api pod: `kubectl get pods -n staging -o name | grep concord-http-api | head -1`
- Generate JWT inside the pod using `JWT_SECRET_KEY` env var
- POST `/v2/releases` with all collected metadata. **Set
  `corectlMinVersion: "X.Y.Z"` and `corekinectVersion: "X.Y.Z"`** so the
  /releases page shows the matching SDK versions.
- Verify the record by GET `/v2/releases?limit=5`

**Exit criteria for Phase 9:** rollout verified + both wheels visible on
staging pypi + POST returned 2xx with corectlMinVersion + corekinectVersion
populated. Do not proceed to Phase 10 otherwise.

## Phase 10 — Deploy PRODUCTION + publish wheels + create production release record

Same three-step structure as Phase 9. Deploy, publish wheels, and record are
one atomic group.

### 10.0 — Re-run the clean-tree gate

```bash
DIRTY=$(git -C /home/bottinger/work/concord/concord status --porcelain)
if [ -n "$DIRTY" ]; then echo "DIRTY — STOP"; echo "$DIRTY"; exit 1; fi
```

Production deploys MUST run from a clean tree. Same enforcement as Phase
9.0 — see "Hard gate: clean tree required" near the top.

### 10.1 — Refresh .git-build-info and deploy production

```bash
{ git -C /home/bottinger/work/concord/concord rev-parse --short HEAD; ... } > .git-build-info && \
npx -y @devcontainers/cli exec ... nx update platform -c production
```

### 10.2 — Publish corectl + corekinect wheels to PRODUCTION pypi

Same nx push pattern as 9.2, against production. Wheels already built in
9.2 (cached by nx); production push is just the twine step.

Reuse `PUBLISH_CORECTL` / `PUBLISH_COREKINECT` from 9.2 — what shipped to
staging must ship to production:

```bash
if [ "$PUBLISH_COREKINECT" = "yes" ]; then
  npx nx run corekinect:push:production
fi
if [ "$PUBLISH_CORECTL" = "yes" ]; then
  npx nx run corectl:push:production
fi

# Verify
[ "$PUBLISH_CORECTL" = "yes" ] && curl -sSk https://pypi.concord.ad.corekinect.com/simple/corectl/ | grep "X.Y.Z"
[ "$PUBLISH_COREKINECT" = "yes" ] && curl -sSk https://pypi.concord.ad.corekinect.com/simple/corekinect/ | grep "X.Y.Z"
```

`PYPI_USERNAME` and `PYPI_PASSWORD` must still be in the environment from
Phase 9.2. The production push target port-forwards `svc/concord-pypi` to
`localhost:18081` and twine-uploads with htpasswd auth.

### 10.3 — Create the production release record (IMMEDIATELY)

Same mechanics as 9.3 but with the production pod and the production user ID.

**Exit criteria for Phase 10:** rollout verified + both wheels visible on
production pypi + POST returned 2xx with corectlMinVersion + corekinectVersion
populated.

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
    'email': 'blake@corekinect.com',
    'name': 'Blake Ottinger',
    'role': 'ADMIN',
    'iat': datetime.now(timezone.utc),
    'exp': datetime.now(timezone.utc) + timedelta(hours=1),
}, os.environ['JWT_SECRET_KEY'], algorithm='HS256')
print(token)
" 2>/dev/null)
```

**Known user IDs** (look up if stale — query `/v2/users` with any valid token):
- Staging: `cmnz59zya000ylno28xrj4gu1` (blake@corekinect.com)
- Production: `cmny0hvd0000yq1k0vmv2mwto` (blake@corekinect.com)

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
    "corekinectVersion": "<X.Y.Z — same as platform per lockstep>",
    "corectlMinVersion": "<X.Y.Z — same as platform per lockstep>",
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

## Phase 11 — Test-app refresh sweep (Phase D Layer 5)

**Run this step whenever the release touched corekinect, protocols/mtib,
or corectl** (i.e., the Phase 0 hook flagged any of those, or the Phase
0.5 auditor identified scaffold-affecting changes). Skip ONLY when the
release was a pure backend/frontend/deploy change with no impact on the
test app scaffold.

This phase closes the gap that bit us on 2026-05-26 (see case study #4
in [`.claude/knowledge/workflows/version-skew.md`](../../knowledge/workflows/version-skew.md)):
the runtime safety gates (Layers 1-4) pass even when the test apps'
`.claude/rules/`, `.claude/skills/`, `.devcontainer/`, and corectl
validator templates have drifted from the canonical templates. The
drift accumulates silently across releases until a contract tightens
and unrelated uploads break. Operators forget to refresh because at
runtime "the framework constraint is still satisfied" — true, but the
scaffold rots.

### Step 1: Load the manifest

```bash
MANIFEST=.claude/known-test-apps.yaml
test -f "$MANIFEST" || {
  echo "Manifest missing — Phase 11 cannot run. See $MANIFEST header"
  echo "for discovery instructions, or add --skip-test-app-refresh"
  echo "if this release genuinely doesn't touch the scaffold."
  exit 1
}
```

If `--skip-test-app-refresh` was supplied AND the user confirmed the
skip is intentional, log a loud-warn banner and proceed to Phase 12.

### Step 2: For each entry, refresh + commit + push + re-upload

Iterate every entry in the manifest. For each one:

```bash
# Example: sigma5_validation
cd /home/<user>/work/validation/sigma5_validation

# 2a. Pull latest main so we're not refreshing onto a stale branch
git checkout main
git pull origin main

# 2b. Pull the new corectl templates into the test app
corectl test update --apply

# 2c. Validate that the refresh produced a coherent app
corectl test validate

# 2d. Commit and push the scaffold refresh
git add -A
git commit -m "chore: refresh framework artifacts to corectl X.Y.Z [no-arch-change]"
git push origin main

# 2e. Re-upload the test package so the runner picks up the fresh scaffold
corectl test upload -m "Refresh for corekinect X.Y.Z (concord vX.Y.Z release)"
```

The release ID in step 2e's message is the production release record
from Phase 10.3 — Phase 11 runs AFTER both staging and production
deploys are complete, so both ends of the wire are on the new version.

### Step 3: Halt on any failure

If `corectl test validate`, `git push`, or `corectl test upload` fails
for any test app:

1. **Halt the release.** Do NOT proceed to Phase 12 with a partially-
   refreshed fleet — that leaves some test apps on the new scaffold and
   others on the old, which is worse than the all-old starting state.
2. **Inspect the failure** in that specific test app. Common causes:
   - `corectl test update --apply` introduced a conflicting change in
     a template the test app has customized → reconcile manually.
   - `corectl test validate` flagged a contract that the test app
     never satisfied, even on the old templates → file a defect against
     the test app, not corectl.
   - `git push` rejected because main moved → fetch, rebase, retry.
3. **Resume from the failed entry.** Phase 11 is idempotent per-app —
   re-running it on already-refreshed apps is a no-op (the commit
   step finds nothing to commit).

### Escape: `--skip-test-app-refresh`

For releases that genuinely have no scaffold impact (e.g., a hot-fix
to `apps/backend/http-api/` that does not touch corekinect, protocols,
or corectl), pass `--skip-test-app-refresh`. The skill logs a loud
banner:

```
[ Phase 11 SKIPPED via --skip-test-app-refresh ]
Reason: release range does not touch corekinect/protocols/corectl
Operator: <name>
Time: <ISO timestamp>
```

Never use this flag to "ship faster" on a corekinect/corectl/protocols
release. The whole point of Layer 5 is that operators always think
"the constraint is still satisfied" and defer the refresh — that
deferral IS the bug.

### Definition of done for Phase 11

- Every entry in `.claude/known-test-apps.yaml` either:
  - has a fresh `chore: refresh framework artifacts to corectl X.Y.Z`
    commit on its `main` branch dated within this release window, OR
  - was logged as missing-on-host (operator must refresh elsewhere or
    confirm intentional skip), OR
  - was logged as skipped via `--skip-test-app-refresh` with a
    documented reason
- A new test package upload exists in the backend for every refreshed
  app (visible via `corectl test list`)

## Phase 12 — Link resolved bugs (MANDATORY)

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
- **Skipping wheel publishing**: The new backend expects clients running the
  new corectl/corekinect (lockstep major.minor). If you bump VERSION and deploy
  without publishing the matching wheels, every fresh `pip install corectl`
  pulls the OLD wheel that doesn't speak the new wire format. Phases 9.2 and
  10.2 are not optional.
- **Skipping the platform deploy on a corekinect-only bump**: The runner +
  http-api images install corekinect from `libs/python` at image-build time.
  Publishing a corekinect wheel to pypi updates `pip install corekinect` for
  operators, but every runner pod keeps using the corekinect that was in the
  image when it was deployed. Symptoms: operators see fixes (`corekinect 0.9.2`
  on local), but live manufacturing sessions still fail with the old behavior.
  Always pair a corekinect bump with a VERSION bump and a platform deploy.
- **Skipping the corekinect bump on a corekinect-only fix**: If you change
  `libs/python/corekinect/**` and only bump `VERSION`, the next deploy ships
  the fix to the runner — but operators running `pip install corekinect`
  locally pull the unchanged old wheel. Bump corekinect even if the only
  consumer you care about is the runner image; the wheel republish costs
  nothing and keeps versions consistent.
- **Bumping corectl without rolling templates downstream**: corectl publishes
  new `.claude/rules/...` template versions every release. Test apps don't
  pick those up until the operator runs `corectl test update --apply`. If a
  release tightens a contract the platform enforces server-side, the next
  upload from a stale test app will fail. Note this in the changelog so
  operators know to update.
- **Version drift between platform / corectl / corekinect**: All three
  `__version__`-style fields (`VERSION`, `tools/corectl/src/corectl/__init__.py`,
  `libs/python/corekinect/__init__.py`) MUST share the same `major.minor`
  inside a release commit. Phase 5d's lockstep check fails the release if any
  drift exists.
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
