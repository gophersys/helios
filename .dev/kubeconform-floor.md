# kubeconform-floor

phase:    red
repo:     gophersys/infrastructure
branch:   ci/kubeconform-floor
worktree: ~/code/.worktrees/infra-kubeconform-floor
pr:       -
attempt:  0/2

## REMINDER: delete this .dev file in the FINAL commit before merge; prove gone with git cat-file -e.

## Goal
The kubeconform manifest gate goes GREEN over zero files — the same `xargs -r` swallow #57 just closed
for shellcheck, one job over. When fixed, the manifest validation FAILS loudly if it finds no manifests
to check, instead of passing over nothing.

## Proven (verification sweep + #176 review)
`.github/workflows/validate.yml:49` ("kubeconform — raw manifests" step): `find $roots … -print0 |
sort -zu | xargs -0 -r kubeconform -strict -ignore-missing-schemas -summary`. The `-r`
(--no-run-if-empty) → empty file list runs kubeconform ZERO times, exits 0. Same class as #57;
reproduced there (`printf '' | xargs -0 -r <tool>` → rc 0). The #176 pr-review explicitly asked this
follow-up be tracked (this is that task, ledger #77).

## Scope (verified)
- kubeconform is WORKFLOW-ONLY (grep: no ctl.sh cmd for it) — so, unlike #57, there is no ctl.sh half.
- ONLY the "raw manifests" step (validate.yml:31-49) has the swallow. The 2nd step "kubeconform —
  kustomize overlays" (51-55) pipes `kubectl kustomize "$d" | kubeconform` per dir — always has input,
  no zero-file swallow. Leave it (or floor it too if trivial — planner decides).
- The discovery is non-trivial: `roots` is computed above line 46 (find its source), then
  `find $roots -name '*.yaml' -not -path '*/config-enforce/*' -not -path '*/zephyr-devbox/*'
  -not -path '*/envs/*' -not -name 'kustomization.yaml'`. The extraction MUST preserve these exact
  roots + 4 excludes, or it changes what is validated.

## Fix direction (planner to make concrete)
Mirror #57's `scripts/lint-shell.sh` + `scripts/test-lint-shell.sh`: extract `scripts/lint-manifests.sh`
that discovers the raw manifests (same roots + excludes), FLOORS on zero files (exit non-zero, named),
then runs `kubeconform -strict -ignore-missing-schemas -summary "${files[@]}"` with output visible.
Missing kubeconform → exit 127 (FAIL-NOT-SKIP). The workflow "raw manifests" step calls it + a test step
`bash scripts/test-lint-manifests.sh`. Bash 3.2-safe (no mapfile; `read -r -d ''`). shellcheck-clean
(the shellcheck gate — now the lint-shell.sh floor — will lint the 2 new .sh).
PLANNER DECISIONS: (a) script vs inline floor (script is testable + matches infra verify-*.sh + the
lint-shell precedent → prefer script); (b) how to test the floor without a live kubeconform run over
manifests (a fixture dir with 0 yaml → floor fires; a fixture with 1 invalid manifest → kubeconform
fails and its finding is visible; test may need kubeconform present — confirm it is, else state the
FAIL-NOT-SKIP); (c) whether to also floor the kustomize-overlay step.

## Conflict
DISJOINT vs #175 (validate.yml manifests-job region ~31-55 vs #175's verify-buildx step ~65) and
#174 (image-warmer manifests). #57 already merged (main 9974fb4), so no overlap with it. Most logic
moves to 2 NEW files.

## Blocked
Nothing. Non-Mateo (CI hardening).

## Next
dev-planner: locate the `roots` source, produce the exact `scripts/lint-manifests.sh` (preserving roots
+ excludes), decide script-vs-inline + the kustomize-step question, and give the red/green + test recipe
(esp. how the floor is proven without needing a real cluster). Then approve.
