# p0-gates-real

phase:    intake
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

plan: pending

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

Delegate phase 1 to `dev-planner`.
