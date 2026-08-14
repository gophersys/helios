# pr-content-check

phase:    red
repo:     gophersys/.devcontainer
branch:   ci/pr-content-check
worktree: ~/code/.worktrees/devcontainer-pr-content-check
pr:       -
attempt:  0/2

## REMINDER: remove .dev BEFORE the PR (this repo has a pr-review workflow — it flags .dev); prove gone with git cat-file -e.

## Goal (#65)
The image-content check (`.ci/smoke.sh` — does the built image actually have bw/gh/etc, and does its
buildx pin match) runs ONLY post-merge (`build-and-push.yml`, `push: [main]`). The PR gate
(`validate.yml`) runs `ctl.sh validate`/`test` + a BUILD_ORDER check, but NOT smoke — so a PR that
breaks image content (removes a tool's install, drops an ARG pin) goes RED only AFTER merge, on the
build-and-push run. A control that can't see at PR time. When done: such a break is caught at PR time.

## Proven (vs .devcontainer origin/main c69ffee)
- `validate.yml`: `on: [pull_request, push]`, runs `ctl.sh validate`, `ctl.sh test`, and a BUILD_ORDER
  agreement check. Does NOT build images and does NOT run smoke.sh.
- `build-and-push.yml`: `on: push: branches:[main]` (POST-MERGE only), builds each image and runs the
  content check (smoke.sh reads back the pushed manifest).
- `smoke.sh` runs the ALREADY-BUILT image (needs the image built first) — dynamic tool checks + a
  static buildx-pin read from base/Dockerfile's ARG.
- The validate job runs INSIDE the base-runner image, but that's the OLD deployed image, not the
  image the PR's Dockerfile would produce — so smoking the runner does NOT catch a PR's Dockerfile break.

## THE PLANNER'S CRUX — recommend the tractable fix
The real check needs the PR's Dockerfile BUILT (expensive per-PR docker build of large images) OR a
cheaper approximation. Options to weigh:
(a) STATIC PR-time check: assert each Dockerfile still DECLARES/installs the tools + version ARGs that
    smoke.sh expects (parse smoke.sh's expected set — or its per-image tool list — and grep each
    Dockerfile). Cheap, catches the common deletion (a removed install line / dropped ARG), weaker
    than running the image. NON-Mateo, clean, additive (the real smoke stays post-merge).
(b) BUILD + smoke at PR time (build-only, no push): real, but an expensive CI cost per PR on large
    images — a COST DECISION for Mateo (like #43-infra's bake). If (b) is the only faithful path,
    FLAG it for Mateo rather than planning it.
(c) A hybrid — e.g. build+smoke ONLY the image whose Dockerfile the PR changed (affected-only), if the
    repo's structure makes that cheap enough.
RECOMMEND one. If (a) is a clean, real improvement (catches deletions at PR time), prefer it — a cheap
PR-time gate that fails loud beats a post-merge-only one, even if weaker than the full build.

## Blocked
Nothing yet — unless the planner concludes only (b) is faithful (then it's Mateo's CI-cost call).

## Next
dev-planner: read validate.yml, build-and-push.yml, smoke.sh (its per-image expected tools/ARGs), the
Dockerfiles (base/flutter/zephyr/base-runner), and .ci/ctl.sh. Recommend (a)/(b)/(c) with reasons +
the exact PR-time check + test recipe (for (a): a fixture Dockerfile missing a tool → the check fails).
Owners: test → dev-test-author; the check script/workflow → dev-implementer.

## Plan — APPROVED (dev-planner + orchestrator)
The FAITHFUL PR-time check ("does the built image contain the tool") is BUILD-ONLY; a static tool→
Dockerfile map would be a second drifting list this repo forbids ("an allowlist is a place for a real
defect to hide"). So:
- ESCALATE to Mateo: affected-only build+smoke at PR time (option c) — a CI-cost decision. NO code.
- SHIP NOW: the ORPHAN-ARG invariant, added to the EXISTING `_ctl/tests/dockerfile-args.test.sh` (which
  already has the DANGLING direction: referenced-but-undeclared). ORPHAN = declared-but-unreferenced
  version ARG — the tell of a deleted RUN-install with a lingering `ARG *_VERSION`. Single source = the
  Dockerfile; NO external list; already runs in the PR gate (`ctl.sh test`). Reuse the file's existing
  `declared_args`/`version_references` helpers. Catches the common partial deletion at PR time; a clean
  full-block deletion stays post-merge (build-only, escalated). Verified GREEN on the tree today (0 orphans).

OWNERSHIP: entirely in `_ctl/tests/dockerfile-args.test.sh` + a new `_ctl/tests/fixtures/dangling-arg/
Dockerfile` (an orphan ARG) → dev-test-author. dev-implementer has NO file to touch.

TESTS (mirror the file's existing counter-stimulus doctrine):
1. counter_stimulus_orphan_ARG_is_reported — orphan_args() on a fixture names the declared-unreferenced ARG.
2. counter_stimulus_does_not_report_a_referenced_ARG — a declared+referenced ARG is NOT reported (not over-broad).
3. counter_stimulus_orphan_detector_ignores_comments — a commented ARG line is not a declaration.
4. <file>_has_no_orphan_version_ARG ×5 real Dockerfiles — every declared version ARG is referenced (GREEN today).

GATE: `bash ./ctl.sh validate` (shellchecks the edited test) + `bash ./ctl.sh test` (runs it). Tools: bash/grep/sed/shellcheck/jq present; hadolint via pinned image.
