# p0-gates-real

phase:    red
repo:     gophersys/eden
branch:   feat/p0-gates-real
worktree: ~/code/.worktrees/eden-p0-gates-real
pr:       -
attempt:  0/2

## Authority

Blueprint `docs/plans/eden-rework-blueprint.md` §4 + §7 Phase P0, 10-pass
certified. Execution order: "P0 starts after eden PR #14 lands" — #14 MERGED
2026-08-27T02:54Z (`bc84ea2`). Run under Mateo's walk-away grant 2026-08-25 —
gate not individually exercised by Mateo.

`/dev` default is NO-STOP (Mateo, 2026-08-26): plan self-approved, merge on the
four §5 conditions. §5 human-only items still stop this lane.

## Goal

Make eden's gates capable of going red. Today ten verbs in `.ci/ctl.sh` return 0
when `nx` is absent, `libs/.ci/ctl.sh` returns 0 when the affected set holds no
gateable project, the sqlc drift check exits 127 in every lane it is not in,
every eden workflow job runs without a timeout, and the ctl.sh standard that all
of this is judged against exists only as practice in four separate copies. P0
turns each of those into a failure that names itself, and writes the standard
down once in `.devcontainer/docs/ctl-standard.md` with `_ctl/lib.sh` as its
executable half.

## Scope — the P0 items

| # | Item | Repo |
| --- | --- | --- |
| P0-1 | `.devcontainer` pointer → `origin/main` (6 commits). `libs` + `infrastructure` ALREADY current at `bc84ea2` — PR #14 did those two. | eden |
| P0-2 | Missing `nx` is a FAILURE: 10 verbs + `cmd_validate`. Delete the dead `-z "$NX_BASE"` arm. | eden |
| P0-3 | Empty gateable set is a FAILURE (`libs/.ci/ctl.sh:252-253`). | libs |
| P0-4 | Pin + install `sqlc`; wire `persistence:verify` into a gate verb list. | .devcontainer + eden |
| P0-5 | `timeout-minutes` on all eden jobs; `harness-upgrade-check.yml` off `ubuntu-latest`. | eden |
| P0-6 | Write the standard down (C1-C10 + I1-I7 + V1-V5) at `.devcontainer/docs/ctl-standard.md`; `_ctl/lib.sh` sourced by eden + libs + infrastructure; `ctl.sh verbs --check` asserts the per-class table. | all four |
| P0-7 | **ROUTED TO THE ORCHESTRATOR — NOT IN THIS LANE.** Terraform state locking is a §5 human-only item ("secrets, backups, terraform state"). No agent authority covers it. | infrastructure |

## Plan

plan: SELF-APPROVED (autonomous mode, Mateo 2026-08-26). The one risk weighed:
P0-6 as certified rests on two premises this lane MEASURED to be false, so it
lands the half that can go green and registers the half that cannot, rather
than manufacturing a gate that passes by silence.

### The two false premises in the certified blueprint

1. **§4.1 "`_ctl/lib.sh` … is a submodule of every repository already. That is
   the seam."** It is not. `.devcontainer` is a submodule of **eden only** —
   `libs/.gitmodules` and `infrastructure/.gitmodules` DO NOT EXIST (measured:
   `ls libs/.gitmodules infrastructure/.gitmodules` → No such file). A `source
   .devcontainer/_ctl/lib.sh` in `libs/.ci/ctl.sh` or `infrastructure/ctl.sh`
   is a hard `set -e` failure in every verb those repositories own, because
   their own CI checks out their repository alone. So the exit-proof line
   `grep -L '_ctl/lib.sh' eden/.ci/ctl.sh libs/.ci/ctl.sh infrastructure/ctl.sh`
   → empty **cannot be satisfied** without first creating a submodule seam that
   does not exist. Creating it is a repository-structure decision (§5
   human-only) and carries a measured hazard: three checkouts of `.devcontainer`
   inside eden's tree give duplicate nx project names (`images-base` ×3), and
   `nx show projects` REFUSES a duplicate-name graph — eden's graph would stop
   resolving. **Routed to the orchestrator.**
2. **P0-6 "walks all 56 `project.json`".** The roster holds **49** projects;
   `find -name project.json` returns 57, the 8 extra being submodule fixtures
   `.nxignore` deliberately excludes. `verbs --check` reports the real 49 and
   reads `.ci/graph-roster.txt`, never a second census (eden cohesion contract:
   one concept, one home).

### The class table, measured against the real 49

Classes resolved from the tree, per run, never a hand-kept list: `go.mod` → Go
(24) · `package.json` + `tsconfig*.json` → TypeScript (5) · neither → bash /
config (20) · both → AMBIGUOUS, which is RED (0 today, still able to fire).

- **47 of 49 projects are OFF-CLASS.** CORRECTED after phase 2 refuted my first
  count: the register is **62 `OWES-GAP` rows** — `validate` 38, `test` 20,
  `build` 2, `lint` 2 — not the "44 miss validate" I first wrote. Exactly 11 of
  49 declare `validate` today and 5 declare `typecheck` (all TypeScript).
  Building that half is ~62 targets that must REALLY run across four
  repositories; a `validate` that no-ops is exactly the ~200 no-op greens §4.2
  bans. **It is a phase of its own, not a P0 item.**
- **7 targets are declared outside their class and GENUINELY RUN** — the six
  `.devcontainer` image units declare `build` (docker build) and
  `repository-scripts` declares `lint` (shellcheck). Reading "declares nothing
  it cannot run" through the class table would red all seven falsely. It is a
  DIFFERENT clause from "declares what its class owes", and conflating them is
  refuted by these seven measurements.
- **R-BODY: my "100% clean" was WRONG, and the repair is a RULING not a code
  change.** My first check tested only that the command CONTAINED `ctl.sh`. An
  exact-form check finds one row: `apps/frontend` target `test` runs
  `bash ./ctl.sh unit`. RULING: **R-BODY governs the BODY, R-NAME governs the
  NAME.** The blueprint's R-BODY says a target "contains exactly one command:
  `bash ./ctl.sh <verb>`. Logic in a `project.json` is a defect" — and
  `bash ./ctl.sh unit` is one command of that form with no logic, so it
  SATISFIES R-BODY. Clause 2 is therefore a FORM check, never target-name /
  verb-name identity, and `apps/frontend/project.json` is NOT edited: renaming
  its verb is a behaviour change outside P0.

### `verbs --check` — what it asserts, all of it green today and all able to fail

1. every roster project resolves to exactly ONE class; ambiguous is RED
2. R-BODY — a closed-set target's command is exactly `bash ./ctl.sh <verb>`
3. the live tree vs the class table, diffed against `.ci/verb-exceptions.txt`,
   a SHRINK-ONLY register in the `SUBSTRATE_ENV_REGISTER` shape: an
   unregistered difference is RED naming project and verb; a row whose
   difference has been REPAIRED is STALE and RED until deleted. Two row kinds,
   one home: `OWES-GAP` (47) and `EXTRA` (7, each carrying the reason it really
   runs). It cannot rot into a permanent skip.

This satisfies the certified NEGATIVE exit proof exactly: a no-op `typecheck`
added to a Go module is an unregistered `EXTRA` → non-zero, naming the project
and the verb.

**Clause 4 — dispatchability probed by a `__verbs` lister — is DEFERRED**, with
the measurement: 19 distinct dispatcher BODIES carry the closed-set targets
(eden 8, `infrastructure` 6, `libs` 4, `.devcontainer` 1 shared), and 6 of them
sit in `infrastructure`, whose sourcing seam does not exist. It is the general
fix and it belongs with premise 1.

### Lane structure — 3 content PRs + 1 pointer PR, forced by repository boundaries

| PR | repo / branch | contents |
| --- | --- | --- |
| A | `.devcontainer` `feat/ctl-standard` | `_ctl/standard.sh` (C1·C4 incl. `log_success`·C5·I7, NO `PROJECT_ROOT` assertion so it sources unconfigured); `_ctl/lib.sh` sources it and DELETES its own four duplicates; `docs/ctl-standard.md` = C1–C10 + I1–I7 + V1–V5; `docs/README.md` gains the canonical class; `versions.env` `SQLC_VERSION` + `_build/upstreams.txt` row + install + `.ci/smoke.sh` class row; `_ctl/tests/standard.test.sh` |
| B ✅ **OPEN: libs#40** | `libs` `fix/empty-gate-set-fails` | `.ci/ctl.sh` — a NON-EMPTY affected set that yields zero gateable projects is a FAILURE. The adjacent `:181-184` early return stays 0 deliberately: an empty affected set is a true statement about the diff; the blueprint's named defect is the second arm, and `.ci/`-only changes land there. |
| D | eden, LIGHT lane, own PR (§8) | `.devcontainer` + `libs` pointer bumps. **Cannot be merged by this lane** — §8 forbids an unattended pointer-bump merge. Routed to the orchestrator. |
| E | eden `feat/p0-gates-real` (this branch) | `.ci/ctl.sh`: 11 verbs `require_cmd`-fail on absent nx, dead `-z "$NX_BASE"` arm deleted, the now-untrue header `:6-9` and the `:192-194` comment that JUSTIFIES the no-ops rewritten, sources `standard.sh`, `verbs --check` + `.ci/verb-exceptions.txt`; `persistence:verify` into `cmd_affected_gate_fast`; `timeout-minutes` on the 9 uncovered jobs and `harness-upgrade-check` off `ubuntu-latest`, in `.github/workflows/` AND the byte-identical `.ci/providers/github/` twins |

**Hard ordering:** A and B are disjoint and run in parallel → merge → D (pointer)
→ E rebased on D. E cannot source `standard.sh` until the pointer moves, and its
`persistence:verify` lane stays red until sqlc is in the published
`ghcr.io/gophersys/base:latest`.

### Prior art followed, not invented

`cmd_graph_guard:190-198` and `cmd_graph_roster_update:466-469` already do what
P0-2 asks and state why. They are the model. The comment at `:192-194` that
excuses the sibling verbs ("they are RUNNERS and a fresh scaffold has no nx") is
what P0-2 overrules, so it becomes untrue and is rewritten in the same commit.

### Deliberately NOT included

- **P0-7** terraform state locking — §5 human-only. The exit proof's last line
  (`terraform plan & terraform plan`) therefore cannot be run by this lane.
- **`libs` / `infrastructure` sourcing the shared standard** — premise 1 above.
- **The class table's "owes" half** (~60 real targets) — registered, not built.
- **`verbs --check` clause 4** (`__verbs` dispatch probe, 19 bodies).
- **`.claude/` edits** that P0-6 makes stale (`.devcontainer/.claude/rules/00-identity.md`)
  — a §5 process change; routed to the orchestrator.
- `oapi-codegen` (§4.3 — P1-1 deletes the contract it serves); `.githooks/`
  linting (git-process §14 row 13).

## Proven

Measured at intake, `bc84ea2` + submodules at their pinned commits:

- `git ls-tree origin/main .devcontainer infrastructure libs` vs each submodule's
  `origin/main`: `.devcontainer` pinned `69fc6a9`, origin/main `6812b88` — 6
  commits behind. `infrastructure` `6d1bb08` == origin/main. `libs` `8683fea` ==
  origin/main. So P0-1 is ONE pointer, not three.
- `.ci/ctl.sh`: 10 verbs return 0 on absent nx — `cmd_build_all:92`,
  `cmd_test_all:100`, `cmd_lint_all:108`, `cmd_typecheck_all:116`,
  `cmd_affected_build:124`, `cmd_affected_test:129`, `cmd_affected_check:134`,
  `cmd_affected_gate:145`, `cmd_affected_gate_fast:159`,
  `cmd_affected_gate_substrate:508`. `cmd_validate:82-88` warns then prints
  `log_success` having run only shellcheck. The dead arm is `:45`. The
  blueprint's line numbers are stale (it measured a 180-line file; the file is
  597 lines) — every defect it names is still present.
- `libs/.ci/ctl.sh:252-253` — `log_info "affected projects had no gateable
  ctl.sh — clean no-op"; return 0`.
- `grep -in sqlc .devcontainer/versions.env` → no match. No sqlc pin exists.
- `apps/platformgateway/persistence/ctl.sh:29` `require_cmd sqlc`;
  `project.json` declares `generate` + `verify`, and neither is in any verb list
  of `.ci/ctl.sh`.
- `grep -c timeout-minutes` per workflow: harness-conformance 1,
  harness-upgrade-check 0, on-pr 0, on-push 0, release 0.
  `grep -c ubuntu-latest`: harness-upgrade-check 1, all others 0.
- `find -name project.json` (submodules initialised): 49, not the 56 the
  blueprint states. eden 10 · libs 25 · infrastructure 7 · .devcontainer 7.
  `verbs --check` must report the REAL count and the roster must agree.
- Host tooling: shellcheck, jq, yarn, node, gh present; `nx`, `sqlc`,
  `terraform` ABSENT on the host. Devcontainer `base-devcontainer` up 8 days,
  `ghcr.io/gophersys/base:latest`. Gates run in the container.

### Measured during phase 2, and each one changes an action

- **`origin/main` ADVANCED 9 commits mid-lane**, `bc84ea2` → `b4ff75c` (eden PRs
  #18/#19). Those commits add 77 lines to BOTH copies of
  `harness-conformance.yml`. That is a file P0-5 edits, so the timeout census
  must be RE-TAKEN after a rebase, not carried from intake. Rebase before
  phase 4.
- **The eden suite CANNOT run on this host and correctly refuses to.**
  `bash scripts/ctl.sh test` on macOS exits 1 at `assert-no-skipped-tests_test`:
  "GNU mktemp is required; this host has none … BSD mktemp accepts the template
  GNU rejects, so this test cannot fail here." That is FAIL-NOT-SKIP behaving
  exactly as designed, and it makes Mateo's devcontainer ruling a hard
  requirement rather than a preference.
- **A devcontainer bound to the WORKTREE exists**: container `p0-devcontainer`,
  image `ghcr.io/gophersys/base:latest`, with `/Users/mateo/code` mounted at the
  same path so the worktree's `.git` GITFILE resolves to
  `/Users/mateo/code/eden/.git/worktrees/…` inside the container. Proven:
  `git rev-parse --show-toplevel` returns the worktree and `mktemp --version`
  reports GNU coreutils 9.4. `.devcontainer/base/ctl.sh up` alone cannot do this
  — it mounts a single `WORKSPACE_HOST`, and a worktree needs its parent
  repository mounted too.
- **Baseline at `b4ff75c`, in that container**: `bash scripts/ctl.sh lint` → 0,
  11 scripts. `bash scripts/ctl.sh test` → 1, and the ONLY failure is
  `graph-guard_test`: "no nx on PATH and no node_modules/.bin/nx — this gate
  cannot be tested, which is a failure, not a skip." Pre-existing and correct;
  it clears once `yarn install` has run. Any OTHER red after my change is
  CAUSED by me, not surfaced.
- `sqlc` is a Go tool, so it follows the `GOFUMPT_VERSION` idiom exactly:
  `versions.env` pin · `_build/upstreams.txt` `go-proxy` row · value-less `ARG` +
  `go install` in `base/Dockerfile` · an `asserted` row in `.ci/smoke.sh`.
- `.devcontainer/docs/README.md` declares that directory **"proposals, not
  specifications"** and names `.claude/rules/00-identity.md` as the record of
  what the repository builds. The blueprint puts the canonical
  `docs/ctl-standard.md` there, so the README MUST gain a canonical class in the
  same change or the new file lands in a directory that disclaims it. Amending
  `docs/README.md` is a documentation edit and is allowed; moving the standard
  into `.claude/` would be a §5 process change and is NOT.

### Phase 2 RED — PR-B (`libs`), proven failing

Tests live in the repository's OWN harness, `libs/.ci/ctl_test.sh` — a two-phase
driver where phase 2 re-runs each test under a COUNTER-STIMULUS and requires it
to fail, so "proven able to fail" is machine-checked, not claimed. Three tests
added (16, 17, 18); no new harness invented.

- `bash .ci/ctl_test.sh t_an_ungateable_affected_set_fails_the_tier` → EXIT=1:
  "cictl named 2 affected projects, the tier gated NONE of them, and it exited
  0; a tier that gates nothing has not passed, it has not looked" — the log
  shows `skipping .ci: not a library`, `skipping templates/go/http-gateway: not
  a library`, then `affected projects had no gateable ctl.sh — clean no-op`.
  The affected set is NON-EMPTY, zero were gated, rc=0. The defect verbatim.
- `bash .ci/ctl_test.sh t_every_tier_verb_refuses_an_ungateable_affected_set`
  → EXIT=1. The author then MEASURED each verb directly rather than inferring
  the class: `affected-gate-fast` rc=0 · `affected-gate-substrate` rc=0 ·
  `gate-all` rc=0, each printing the same "clean no-op". **All three tiers —
  pr, merge and nightly — are false-green today**, because the arm is shared.
  The blueprint named one verb; the real blast radius is three.
- GREEN BY DESIGN, not red evidence: `t_a_gateable_affected_set_reaches_the_
  per_project_gate` (the non-vacuous positive that stops the fix being
  `return 1`) and the pre-existing `t_an_empty_affected_set_is_a_clean_pass`
  (which pins `:181-184`, the arm that must NOT change).
- Whole suite: `bash .ci/ctl_test.sh` → phase 1: 15 pre-existing ok, 16 FAIL,
  17 FAIL, 18 ok; phase 2: 18/18 proven able to fail; EXIT=1.
- `shellcheck -S style .ci/ctl_test.sh` → 0.
- Baseline before the change, measured by me at `85ab8ca` in the container:
  `bash .ci/ctl.sh validate` → rc=0. So the red is CAUSED by the new tests, not
  surfaced from drift.

Implementer target: `.ci/ctl.sh` lines 251-254 only. No non-test file needs
editing to wire the tests in — the repository `ctl.sh validate` discovers every
`*_test.sh` by `find`.

### A correction to my own record, made the moment it happened

I first wrote that `NX_BASE=HEAD bash .ci/ctl.sh affected-check` exited **0**
while printing `Failed tasks: repository-scripts:test`. That was FALSE, and the
reason is the exact trap `/dev` §"rules that outrank convenience" names: I ran
`… | tail -6` and then read `rc=$?`, which is **`tail`'s** status, never the
gate's. Re-read with `set +e; cmd >file 2>&1; rc=$?; set -e` the true status is
**1**, with `repository-scripts:test` AND `repository-scripts:lint` failing.

Both readings are kept here on purpose. The manufactured 0 is the failure mode
the rule exists for, and I hit it while holding the rule — the same way Mateo
did, twice in one session, while quoting it.

The corrected run also proves two things worth having: eden's real nx lane DOES
select `repository-scripts` when a `scripts/*_test.sh` changes, and the new red
tests are therefore red THROUGH THE REAL GATE, not only when invoked directly.

### Environment provisioned for phase 4 (all inside `p0-devcontainer`)

`yarn install --immutable` (nx at `node_modules/.bin/nx`) · `bun install
--frozen-lockfile` in `libs/typescript` · the four TypeScript libs built in
dependency order (scale → theme → visualization → primitives) · `go.work`
regenerated by the tracked generator. `nx show projects` → 49, and
`bash .ci/ctl.sh graph-guard` → rc=0, "the graph matches the roster exactly (49
project(s))", "8 project-shaped file(s) sit under a submodule fixture directory
and produced no project" — which is exactly the 57 − 49 the intake census found.

### P0-1 pointer ranges (§8 requires the count in the PR body)

`.devcontainer` `69fc6a91` → `6812b885`, **6 commits**. `libs` `8683feab` →
`85ab8caa`, **4 commits**. `infrastructure` `6d1bb083` → `6d1bb083`, **0** — it
is already current, so P0-1 is two pointers, not three. PR-A and PR-B add their
own commits on top of those ranges.

### §10 merge-method guard, re-verified today

`allow_squash_merge=false`, `allow_merge_commit=true`,
`delete_branch_on_merge=true` on all three repositories this lane touches
(eden, libs, .devcontainer).

### Phase 3 GREEN — PR-B (`libs`), MERGED-READY, opened as **libs#40**

Reproduced BY ME, not banked from the subagent, inside `p0-devcontainer`:

- `bash .ci/ctl_test.sh` → **TRUE rc=0**, `18 test(s) hold; 18 of 18 proven able
  to fail`. The `[error] gate (implementation): 2 affected project(s), and NOT
  ONE is gateable` lines are the NEW behaviour firing inside a fixture.
- `shellcheck -S style .ci/ctl.sh` → rc=0
- `bash .ci/ctl.sh validate` → **TRUE rc=0**, identical to the `85ab8ca`
  baseline I measured before any change.
- `bash ctl.sh validate` (the FULL repository gate, not just the CI layer) →
  **TRUE rc=0**: `17 project record(s) hold; 3 mutant(s) caught`, `validate: all
  checks passed`.

**The break-test here is machine-checked and unavoidable.** This harness runs a
second phase that re-applies each test under a COUNTER-STIMULUS and requires it
to FAIL; "18 of 18 proven able to fail" is the suite's own exit condition, not
my assertion about a manual break. That is stronger evidence than the `/dev`
break-test ritual, so it is what I relied on.

Both `TRUE rc=` readings above were taken with `set +e; cmd >file 2>&1; rc=$?;
set -e` after the pipe mistake earlier in this file. No number here was read
through a pipe.

### A SECOND false green, this time in my own monitoring

My first PR-check watcher grepped for the lowercase word `pending`. `gh pr
checks --json state` emits **`QUEUED`**, so the grep never matched and the
watcher announced `ALL CHECKS SETTLED` while both checks were still queued. I
caught it because the printed state line contradicted the verdict on the same
screen.

Twice in one lane, then: a status read through a pipe, and a state matcher that
could not match. Both are the same defect the whole of P0 is about — a check
whose green means nothing — and both were mine while I was building checks
against exactly that. It is recorded rather than quietly fixed, because a lane
that only documents other people's false greens is not credible.

## Blocked

Nothing.

## Next

Phase 2 — red tests for PR-A (.devcontainer) and PR-B (libs), in parallel.
