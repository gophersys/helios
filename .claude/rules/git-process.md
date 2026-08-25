# git-process — THE git strategy and development process

Dated 2026-08-25. **Rule of this document: state what EXISTS.** Put what does not
exist in §14 TO BUILD. A document that describes unbuilt machinery as a property
of the system is a green check that verifies nothing.

> ## ⛔ BLOCKED ON MATEO: ADR-0019 conflict, decision pending
>
> **§1 and §2 contradict `docs/architecture/adr/0019-unified-git-workflow-and-merge-agents.md`
> (Status: Accepted, 2026-06-13), its canonical home
> `docs/architecture/13-versioning-and-git-workflow.md`, and `.claude/agents/merge-agent.md`.**
> ADR-0019 decides **fast-forward-only** merges and the branch grammar
> `<class>/<slug>[/run-<id>]`; §1 says one MERGE COMMIT and §2 says
> `<type>/<slug>`. §5 of this file lists "a new or reopened ADR" as Mateo's gate,
> so no agent may resolve this by editing either side.
>
> **§1 and §2 are left AS WRITTEN and are NOT in force where they conflict.**
> Until Mateo decides, ADR-0019 and doc-13 govern. The resolution is either
> conformance to them, or an ADR amendment that supersedes them, exercised with
> verbatim words and a timestamp under §13.

## 1. Model — trunk-based, artifact promotion

- `main` is always releasable. No develop branch, no release branch.
- Each change: a short-lived branch cut from FRESH `origin/main` (fetch first),
  in its OWN worktree. One PR. One MERGE COMMIT. Branch and worktree deleted after.
- Never commit to `main`. Never work in the primary checkout.
- Environments promote by ARTIFACT (image digest + chart pin). An environment is
  an `<env-id>` namespace, never a branch.

## 2. Naming

| thing | rule |
| --- | --- |
| branch | `<type>/<slug>`, type ∈ {feat, fix, chore, docs, ci, test, refactor} |
| slug | kebab-case, short, stable for the life of the branch |
| worktree | `~/code/.worktrees/<repo>-<slug>` |
| commit | Conventional Commits, imperative. Attribution per **§13** — an agent authors as Claude; joint work carries `Co-Authored-By: Claude`. |
| PR title | Conventional Commit form. The REVIEWER reads it. |
| tag | annotated `vX.Y.Z` on tooling and module repos. Eden tags mark releases. |

- **The PR title is not the merge subject.** GitHub writes the subject:
  `Merge pull request #N from <owner>/<branch>` (measured: eden f6790f3).
- **Slug length is a GUIDE, not a gate.** Renaming a head branch closes the PR,
  and a gate must read `GITHUB_HEAD_REF` on CI but `git branch --show-current`
  locally — which breaks the cictl same-verb rule.

## 3. Loss prevention — five rules

1. COMMIT BEFORE ANY DESTRUCTIVE OPERATION — break-test, restore, rebase.
   Uncommitted work is the only work you can kill.
2. PUSH AFTER EVERY COMMIT. The laptop is not a home.
3. Force-push only with `--force-with-lease`, own branch only, never `main`.
4. WIP commits are permitted on a branch. The merge commit keeps `main` clean.
5. Delete a branch only when a COMMAND proves its commits reach `main`.

## 4. Lanes — two, with a hard boundary

**FEATURE lane** — full `/dev`: plan → red tests proven to fail → green →
verify → PR. Two stops (plan, merge) unless `--auto`. Use it for any change of
behaviour, any new code, any contract change.

**LIGHT lane** — branch → PR → checks → review → merge commit. No planner stop,
no red-test phase. Five classes ONLY:

- version-pin bumps (`versions.env`, `CICTL_VERSION`, digest repins)
- submodule pointer bumps
- regeneration of a generated file, with no generator change
- typo fixes and pure-documentation changes
- config VALUE changes (no new key, no schema change)

> **This lane is Mateo's WRITTEN standing waiver, and this line is that waiver.**
> `/dev` phase 2 lets no agent waive red-tests-first for itself. The waiver is
> his; it covers these 5 classes and nothing else. No agent may add a sixth.
> When unsure, it is a FEATURE.

## 5. Merge — conditions merge, Mateo gates

An agent may merge when ALL FOUR hold.

1. **Checks green AND logs read. Name the gate that RAN.** An affected gate that
   selects no task is a NO-OP and is not evidence about content — say so on the
   PR. For a light-lane change the evidence is the REVIEW plus the named checks,
   because a no-op affected gate is the normal result there.
2. **Read the review verdict as its own call.** APPROVE merges. A repo with no
   reviewer merges, and you STATE it has none. **A bare round-limit skip does not
   block.** A review that DIES with no verdict is a failure, never a pass.

   **WHEN THE REPO HAS NO REVIEWER AND THE GATES NO-OP, THE EVIDENCE SET IS
   EMPTY, AND YOU MAY NOT CALL IT SATISFIED.** In eden today both fire at once on
   any doc-only change: there is no `pr-review` workflow, and the affected gates
   select nothing outside an Nx project. So a doc-only eden change rests on a
   NAMED HUMAN or grant-holder who read it — quoted under §13 — and on nothing
   else. Write "no content evidence; merged on <name>'s reading" rather than
   listing four conditions that a no-op satisfies. There is no pretend gate.
3. **No open decision in the PR body** — a line starting `DECISION:`. That
   marker is the whole definition.
4. **`--merge`, never `--squash`. Delete the branch, remove the worktree.** For a
   FEATURE PR the `.dev/<slug>.md` is ARCHIVED then deleted: quote its final
   Proven section into the PR body so the merge commit keeps the record, then
   delete the file in the last commit. **PROVE the removal** —
   `git cat-file -e origin/main:.dev/<slug>.md` must fail — because the deletion
   silently failed once and 161 lines landed on `libs` main. The light lane
   creates no state file: absent because never created is not absent because
   deleted.

**Mateo gates these personally; no agent authority covers them:** production
deploys · repository CRUD (create/rename/archive/delete) · process changes (this
file, `.claude/`, the cictl contract) · a chart or contract PROMISE · a new or
reopened ADR · secrets, backups, terraform state.

A gate in that list is EXERCISED only under §13: quote his verbatim words and a
timestamp, or write "gate not individually exercised".

## 6. Hygiene and currency

- **The sweep runs in the NIGHTLY tier, and on demand.** One cadence.
- It deletes a MERGED remote branch. It may delete a 0-ahead branch ONLY when the
  last push is older than 7 days — a fresh 0-ahead branch is a worktree whose
  work is still uncommitted.
- **It never touches the head branch of an open PR.**
- It flags a PR idle more than 7 days on the status board.
- Rebase onto `origin/main` when behind, and before merge when conflicted;
  `--force-with-lease`, own branch. **A rebase cancels the review in flight** —
  a cancelled review posts no comment and rounds count from posted comments, so
  the money is spent and no round is recorded. Rebase when you must, not by habit.
- Every workflow and agent starts from FRESH `origin/main`.
- Zero stale branches is a BOARD METRIC.

## 7. Actions — the map as the estate really is

| git event | what runs TODAY | cancelled? |
| --- | --- | --- |
| PR open/push | pr tier AND merge tier — the merge tier is the PRIVILEGED substrate lane (docker, k3d, kind, postgres, 45 min) — plus the AI review | YES |
| merge to main | the pr-tier verbs again over `origin/main~1`. Not whole-repo, no image build. | YES |
| nightly | whole-repo gates, soaks, scans, the sweep, the dependency resolver | no |
| tag `v*` | publish artifacts by digest | no |

**Coverage is partial. Measured against the GitHub API on `main`, 2026-08-25:**

| repo | workflows | note |
| --- | --- | --- |
| `.devcontainer` | build-and-push, pr-review, security-nightly, validate, weekly-bumps | **the most complete in the estate, and the ONE repo with the full nightly + tag + merge triple** |
| `eden` | harness-conformance, harness-upgrade-check, on-pr, on-push, release | hand-written. **NO pr-review** — see §8. |
| `libs` | nightly, on-pr, on-push | cictl-generated |
| `infrastructure` | ghcr-retention, pr-review, validate | **has the AI reviewer** |
| `research-ui` | build-ci-image, ci, on-pr | |
| `research-hardware` | build-ci-image, ci | |
| `home` | validate | |
| `cictl` | ci | one hand-written file, by deliberate exception |
| `hnslint`, `review`, `research-embedded` | **none** | zero workflows |

`.devcontainer` is the working example to copy: `security-nightly.yml`
(`cron 0 9 * * *`), `build-and-push.yml` (`tags: ["v*"]` and `push: main`),
`validate.yml` (`push: main`). Every tier writing what it RAN into the job
summary is TO BUILD (§14).

## 8. Submodules — the pointer seam

- A pointer bump is ALWAYS its own PR, never inside a feature.
- To test your own submodule change, bump to YOUR commit alone.
- "Merged" is not "in effect" until the pointer moves. Say which you mean.
- **The auto-dispatch does not exist** — zero lines. TO BUILD (§14).
- **ONE answer on unattended merge, and it is the only one.** An unattended
  pointer-bump PR may merge on a **light-lane APPROVE and on nothing weaker**.
  That cheap review tier does not exist yet (§14 row 3), so **until it does, a
  pointer-bump PR is merged by a human or by a named grant-holder — never
  unattended.** The §5.2 "no reviewer configured" escape does NOT apply to an
  unattended pointer bump; eden has no reviewer, which is exactly where these
  land, and one bump moved 27 commits and made a project affected that nobody
  had touched.

## 9. Dependencies — currency without drag

- Toolchains come from the devcontainer images. A stale pin is a DEFECT.
- **Two resolvers open PRs today**: `.devcontainer` `weekly-bumps.yml` (Monday
  cron, every pin of its table, ONE PR) and eden `harness-upgrade-check.yml`
  (3 harness pins). `cictl updatability` prints a table and opens nothing.
- Automation opens the PR; a human, or the §5 conditions, lands it. Keep that.
- A pin with no resolvable upstream carries a written reason. The reason must be
  TRUE and no static check can tell — measure it against the real upstream.
- **A tracker FROZEN while its upstream moves is a FAILURE.** Proof case:
  `golang/vuln` stopped cutting releases at v1.1.4 and kept tagging to v1.7.0, so
  the row resolved correctly to a dead value for 7 months and no Monday went red.
  A resolver that always answers the same thing looks exactly like a pin that is
  current. The staleness alarm is TO BUILD (§14).

## 10. Enforcement — stated honestly

**No red check blocks a merge anywhere in this org today.** Branch protection
needs GitHub Pro on the 8 private repos (403) and is unset on the public ones
(measured 2026-08-25). Enforcement is therefore **agent-side**: the §5 conditions
bind every agent and session. Never write "the gate fails the PR" about a gate
that cannot fail it.

**One rule has real teeth.** The merge-method guard can never be a PR check — the
method is chosen after every check reports — so it is a repository SETTING.
Verified 11/11 on 2026-08-25: `allow_squash_merge=false`,
`delete_branch_on_merge=true`, `allow_merge_commit=true`.

**The cictl contract cannot carry the rest yet.** One `ci.contract.yaml` exists
(`libs`); eden has none; the schema decodes with `KnownFields(true)`, so a new
key is a hard failure until cictl ships it.

**The reviewer turn cap is 40, and the dollar budget is NOT the only limiter.**
Measured 2026-08-25: `review/review.sh:34` reads
`MAX_TURNS="${REVIEW_MAX_TURNS:-40}"` at cictl `origin/main`, at `v0.5.1` and at
`v0.6.0` — the version `.devcontainer` pins — and no caller anywhere sets
`REVIEW_MAX_TURNS`. At 40 turns the agent is cut off mid-tool-call and the run
dies with NO VERDICT, which is the §5.2 failure mode. Raising it to 500 is a
DIRECTIVE, not a state: §14 row 12, task #134.

## 11. Coherence — docs match reality, or it is a defect

Nothing here exists yet. Both items are TO BUILD (§14).

- **DOC UPDATER** — a specialized agent. It runs after every merged PR and
  updates the documents that the change made stale. **Docs-match-reality is a
  STANDARD; drift is a DEFECT**, not tidying.
- **EDEN COHERENCE REVIEWER** — the org super-architect. It fires on every
  submodule pointer bump, and on a schedule at two separated depths:

| level | cadence | budget | scope |
| --- | --- | --- | --- |
| LIGHT | nightly | cheap sweep | real state vs documented state, submodule cohesion, standards enforced |
| DEEP | weekly | $200 credit | full org architecture review |

  The two levels must keep a CLEAR depth separation — a deep review that only
  repeats the nightly sweep buys nothing. Deep runs parallel coverage with
  DISJOINT file ownership, at the best price per token.
  Outputs: one coherence report, plus fix PRs opened in the correct lane (§4).

## 12. The CI instrumentation contract

**A Claude launched in CI sees ONLY the checked-out repository.** An ephemeral
runner has no `~/.claude`, so no personal rule, skill or agent reaches it.

**Therefore the repository's own `CLAUDE.md` and `.claude/` ARE the CI profile,
and eden's `.claude/` is authoritative inside eden.** A rule that must bind a CI
agent lives in the repo or it does not exist.

- VERIFIED BY IMAGE INSPECTION (not by a runtime probe): the pools run
  `ghcr.io/gophersys/cloud`, built from `.devcontainer`, whose `base/ctl.sh`
  installs Claude with the official installer and copies no personal
  instrumentation.
- ASSUMED, not yet measured: that each repo's committed instrumentation is
  complete enough to stand alone as that profile. Task #136 runs the audit.
- TO BUILD (§14): a verification probe — the CI Claude echoes which
  instrumentation files it loaded into the job summary, and the gate FAILS when
  the expected profile is absent. A profile nobody verifies is the same class as
  a tracker nobody watches (§9).

## 13. Attribution — identity in the record

**Mateo's ruling, 2026-08-25: ATTRIBUTION IS IDENTITY.** This REVERSES the
earlier no-attribution rule, which forbade every AI trailer. The record must say
who did the work. An unattributed agent commit reads as a human's, and that is a
false record.

| case | git author | trailer |
| --- | --- | --- |
| solo agent work | `Claude <claude-agent@gophersys.noreply>` | none |
| joint interactive work | Mateo | `Co-Authored-By: Claude` |

- **An agent NEVER commits, approves or comments as "Mateo".** An agent's PR
  comment identifies itself and NAMES THE AUTHORITY it acts under.
- **A human gate counts as EXERCISED only when the record quotes Mateo's
  VERBATIM words and a TIMESTAMP.** With no quote, the record says
  **"gate not individually exercised"**. Inference, a summary, or "he
  co-designed it" is not an exercised gate. This makes the F27 fix permanent:
  an agent may not certify the human gate on its own change.
- Actor-level separation — a real bot GitHub identity, so the ACTOR and not
  only the commit author carries it — is TO BUILD (§14, task #138).

## 14. TO BUILD — none of this exists yet

| # | item | owner | note |
| --- | --- | --- | --- |
| 1 | pointer-bump dispatch | eden + submodules | needs a cross-repo PAT (`GITHUB_TOKEN` cannot dispatch), sender step, `on: repository_dispatch`, bot identity, commit-range extraction |
| 2 | hygiene sweep | eden | nightly + on demand, honouring §6 exclusions |
| 3 | per-LANE review pricing | cictl | `TierPreset` keys only on governance type, so every pin bump in `libs`/`eden` pays deep opus, $125 worst case |
| 4 | "what I ran" job summary | cictl | §7 |
| 5 | staleness alarm for a frozen tracker | .devcontainer | §9 |
| 6 | contract gates: branch vocabulary, commit format | cictl | struct field + emit + generator + drift |
| 7 | eden `ci.contract.yaml` | eden | eden is hand-written, so 4 and 6 cannot reach it |
| 8 | DOC UPDATER agent | eden | §11 — runs after every merged PR |
| 9 | EDEN COHERENCE REVIEWER | eden | §11 — light nightly / deep weekly, $200 deep budget, disjoint parallel ownership |
| 10 | CI instrumentation probe | cictl | §12 — echo the loaded profile into the job summary; FAIL when it is absent |
| 11 | bot GitHub identity (task #138) | eden + org | §13 — actor-level separation, so the ACTOR carries the agent identity and not only the commit author |
| 12 | raise the reviewer turn cap (task #134) | cictl | §10 — it is **40** today at main, v0.5.1 and v0.6.0; 500/max is the directive, not the state |
| 13 | attribution sync: `.claude/agents/merge-agent.md` §5 | eden | still carries the OLD no-attribution rule, which §13 reversed |
| 14 | attribution sync: `docs/architecture/adr/0010-documentation-scheme.md:34` | **Mateo** | "Conventional Commits with no AI/LLM attribution lines" — §13 reopens ADR-0010, so this is an ADR amendment and his gate, not an agent edit |

A `.dev/` gate is deliberately NOT here: the state file must be PRESENT until the
last commit, so a PR-time check fails every feature PR and a main-tier check
reports the loss after it happens. §5 condition 4 covers it.
