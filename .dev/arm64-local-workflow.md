# arm64-local-workflow

phase:    pr
repo:     gophersys/.devcontainer
branch:   feat/arm64-local-workflow
worktree: ~/code/.worktrees/devcontainer-arm64-workflow
pr:       -
attempt:  1/2

## Goal
The local/CI 1:1 workflow becomes stated and enforced (#101): local dev on
the arm64 Mac opens the SAME published :latest image that CI runs, and the
suite refuses drift. Closes gaps G1-G4 of the plan.

## Plan
Approved by the orchestrator 2026-08-18 (authority delegated, standing
orders §4). As produced by dev-planner:
- G1 manifest↔devcontainer.json set equality + G2 self-reference: two new
  properties in ctl.sh check_devcontainer_json.
- G3 the statement: README "### The local/CI 1:1 workflow" section +
  00-identity.md Dev-in-container invariant (+2 properties to the "4 are").
- G4 mobile exception: ARM64_LOCAL_EXCEPTIONS literal in platform-policy
  (equality with no-arm64 rows) + README-names-each-exception check.
- New _ctl/tests/devcontainer-contract.test.sh + fixtures (dispatcher-mode
  shape); checks 1-5 with stated break directions.
- Out of scope: runArgs platform pin on mobile, generating devcontainer.json,
  arm64 registry smoke, any pin/build change.

## Proven
- RED (commit eb64fc5): `bash ./ctl.sh test` rc=1 — devcontainer-contract
  22 checks/6 red + platform-policy 35/2 red, other 22 files 822/0 green
  (822 re-measured by the verifier; an earlier 796 here did not reproduce).
  Each red fails for its stated reason (missing-image equality both ways,
  self-reference, README section + exception naming); counter-stimuli
  proven non-vacuous by exact-inverse breaks on scratch copies; committed
  files never edited during break-tests (shasum-identical).
- Refusal wording is pinned by format constants in the test (ABSENT_FORMAT,
  UNDECLARED_FORMAT, SELF_REFERENCE_FORMAT) — the implementer copies them.
- GREEN (commit 73bfa90): `bash ./ctl.sh test` rc=0 — 24 files, 879 checks,
  0 failed (devcontainer-contract 22/0, platform-policy 35/0, others 822/0;
  verifier-reproduced).
  `bash ./ctl.sh validate` rc=0; `shellcheck -x -S style ctl.sh` rc=0.
  3 files changed: ctl.sh (+2 properties via BUILD_ORDER, no second yaml
  reader), README 1:1 section naming mobile, 00-identity 4→6 enumeration.

## Blocked
- Nothing.

## Proven (verify round)
- Verifier REFUTED on 3 evidence counts, all fixed: state tallies corrected
  to reproduced 879/822 (53fde94); exception check tightened to code-span
  name-as-a-name with the prose counter-stimulus pinned (6aee97a, 35→36
  checks); README mobile paragraph made time-true vs the not-yet-existing
  ref (8ab55a6). Enforcement itself survived all 7 break-tests.
- Final gates on the combined tree (orchestrator-run): test rc=0 (24 files),
  validate rc=0.

## Next
Push, PR, reviewer, merge under authority; delete this file in the final
commit before merge.
