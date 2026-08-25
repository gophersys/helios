# git-process — THE git strategy and development process

Co-designed Mateo + orchestrator, 2026-08-25, three interview rounds, all
answers locked. Destination: `eden/.claude/rules/git-process.md` (submodules
get a 5-line pointer rule). Machine-checkable parts move into the cictl
contract. This process is followed every time we work on eden, and it is the
foundation of the processes built INTO eden itself.

## 1. Model — trunk-based, artifact promotion

- `main` is always releasable. No develop or release branches.
- Every change: a short-lived branch cut from FRESH `origin/main` (fetch
  first, always) in its OWN worktree, one PR, one MERGE COMMIT (never
  squash), branch + worktree deleted after.
- Never commit to `main`. Never work in the primary checkout.
- Environments promote by ARTIFACT (image digest + chart pin), never by
  branch. Env branches never exist — envs are `<env-id>` namespaces.

## 2. Naming — machine-checked at the PR gate

| thing | rule |
| --- | --- |
| branch | `<type>/<slug>`, type ∈ {feat, fix, chore, docs, ci, test, refactor} |
| slug | kebab-case, ≤4 words, stable for the branch's life |
| worktree | `~/code/.worktrees/<repo>-<slug>` |
| commit | Conventional Commits, imperative, no AI/LLM attribution, no Co-Authored-By |
| PR title | = the merge commit's first line |
| tag | annotated `vX.Y.Z` on tooling/module repos; eden tags mark promoted releases only |

A wrong name fails the PR gate (cictl contract rule), not a code review.

## 3. Loss prevention — the five rules

1. COMMIT BEFORE ANY DESTRUCTIVE OP — break-tests, restores, rebases.
   Uncommitted work is the only killable work.
2. PUSH AFTER EVERY COMMIT — the laptop is not a home.
3. Force-push = `--force-with-lease`, own feature branch only, never `main`.
4. WIP commits are allowed on branches; merge commits keep `main` clean.
5. A branch is deletable only when its commits are PROVEN reachable from
   `main` — a command, not a memory.

## 4. Lanes — two, with a hard boundary

- FEATURE lane = full /dev: plan → red tests proven failing → green →
  verify → PR. Two stops (plan approval, merge approval) unless `--auto`.
  For anything that changes behavior, adds code, or touches a contract.
- LIGHT lane = branch → PR → gates → review → merge commit. No planner
  stop, no red-test phase. ONLY for this written list:
  - version-pin bumps (versions.env, CICTL_VERSION, digest repins)
  - submodule pointer bumps
  - generated-file regeneration (callers, sidecars) with no generator change
  - typo and pure-documentation fixes
  - config VALUE changes (no new keys, no schema change)
- When unsure, it is a feature. The list changes only by process change
  (a Mateo gate, §5).

## 5. Merge — conditions merge, humans gate three things

Any agent may merge when ALL four conditions hold:

1. Checks green AND logs read — the gate RAN this change (a fast green is
   not a green).
2. The review APPROVE verdict read as its own call — or no reviewer is
   configured, and that is stated.
3. No open decision in the PR body.
4. `--merge`, never `--squash`; branch deleted; worktree removed;
   `.dev/<slug>.md` deleted in the last commit before merge.

Mateo personally gates exactly three classes — no agent authority covers
them: production deploys, repository CRUD (create/rename/archive/delete),
and process changes (this file, `.claude/`, the cictl contract).

## 6. Hygiene and currency — clean is a metric

- A scheduled hygiene sweep per repo (weekly Actions + on-demand): deletes
  remote branches merged or 0-ahead, prunes worktrees, flags PRs idle >7
  days on the status board.
- PR currency: rebase onto `origin/main` when behind, and before merge when
  conflicted. `--force-with-lease`, own branch only.
- Every workflow and agent starts from FRESH `origin/main`.
- Zero stale branches is a BOARD METRIC, not an aspiration.

## 7. Actions — the event→pipeline map

| git event | pipeline | properties |
| --- | --- | --- |
| PR open/push | FAST — affected-only gates + AI review | concurrency-cancel supersedes older runs |
| merge to main | FULL — whole-repo gates, race detectors, image builds | never cancelled |
| nightly | DEEP — soaks, real-model tests, scans, hygiene sweep, dependency resolver | |
| tag `v*` | RELEASE — publish artifacts by digest | |

Every tier writes what it RAN into the job summary — the mechanical defense
against a green that checked nothing.

## 8. Submodules — the pointer seam

- A submodule merge to its main auto-opens a LIGHT-lane pointer-bump PR in
  eden (repository-dispatch), carrying the exact commit list it moves.
- Pointer bumps are ALWAYS their own PR — never inside a feature.
- Testing your own submodule change = bump to YOUR commit alone.
- "Merged" is not "in effect" until the pointer moves; the report must say
  which.

## 9. Dependencies — currency without drag

- Toolchains come from the devcontainer images; a stale pin is a defect.
- Every pin with a resolvable upstream is on the auto-resolver; automation
  opens the PR (light lane), a human or the merge conditions land it.
- A tracker frozen while upstream moves is a FAILURE (staleness alarm) —
  the govulncheck releases-vs-tags freeze is the proof case.

## 10. Enforcement — rules for agents, gates for truth

Moves into the cictl contract (violations fail the PR, not the review):
branch-name vocabulary, Conventional Commit format, merge-method guard,
`.dev/` file absent on main. The hygiene sweep and pointer-bump dispatch
are Actions. Everything else in this file binds every agent and session
that touches eden.
