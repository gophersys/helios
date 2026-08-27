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

- **47 of 49 projects are OFF-CLASS** — they owe a target of their class and do
  not declare it (44 miss `validate`, 14 miss `test`, 2 client-go projects miss
  all four). Building that half is ~60 new targets that must REALLY run across
  four repositories; a `validate` that no-ops is exactly the ~200 no-op greens
  §4.2 bans. **It is a phase of its own, not a P0 item.**
- **7 targets are declared outside their class and GENUINELY RUN** — the six
  `.devcontainer` image units declare `build` (docker build) and
  `repository-scripts` declares `lint` (shellcheck). Reading "declares nothing
  it cannot run" through the class table would red all seven falsely. It is a
  DIFFERENT clause from "declares what its class owes", and conflating them is
  refuted by these seven measurements.
- **R-BODY is already 100% clean**: 0 of the closed-set targets carry anything
  but `bash ./ctl.sh <verb>`. `verbs --check` holds that property rather than
  repairing it.

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
| B | `libs` `fix/empty-gate-set-fails` | `.ci/ctl.sh` — a NON-EMPTY affected set that yields zero gateable projects is a FAILURE. The adjacent `:181-184` early return stays 0 deliberately: an empty affected set is a true statement about the diff; the blueprint's named defect is the second arm, and `.ci/`-only changes land there. |
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

## Blocked

Nothing.

## Next

Phase 2 — red tests for PR-A (.devcontainer) and PR-B (libs), in parallel.
