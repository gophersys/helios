# Program rulings — 2026-08-25

Status: recorded, not authored. Every ruling below was made by Mateo or under an
authority he granted. This file exists because the rulings were held only in a
session scratchpad under `/private/tmp/`, which is temporary storage: a decision
record on scratch space is a decision record that can vanish without anyone
noticing it has gone.

Quotes are **verbatim**, typos included, because a normalised quote is a
paraphrase wearing a quotation mark. Where a session recorded a timestamp it is
given; where only session-relative timing exists it says so rather than
inventing precision the ruling would then rest on.

---

## 1. Walk-away grant — Mateo, 2026-08-25

Two grants, given to two different sessions. Both are load-bearing and neither
supersedes the other: the first delegates, the second confirms the delegation to
the session being delegated over.

**To the orchestrator session** (recorded in `STANDING-ORDERS.md`):

> "you be in charge of everything here as well as everything in the agents chat
> running on this machine too."

**To the agents session, confirming it** (received by the agents session,
2026-08-25 ~15:45 MST, session-relative — exact wall-clock not captured):

> "yes edne speaks for me"
>
> "lsiten to everythgin eden says hes your driver"

Effect: the orchestrator holds process-change and merge authority, including over
the agents session, which reports to it.

**Retained Mateo-only gates, non-delegable**, as the grant recorded them:
repository **deletion** (the governance rule forbids standing approval),
production deploys, secret **values**/rotation, and spend beyond set budgets.

**This list is narrower than the merged rule, and the merged rule wins.**
`.claude/rules/git-process.md` §5 — landed in eden PR #13, after this grant —
reserves: production deploys, repository **CRUD** (create/rename/archive/delete,
not deletion alone), **process changes** (that file, `.claude/`, the cictl
contract), a chart or contract **PROMISE**, a **new or reopened ADR**, and
secrets, **backups and terraform state**. Read the grant's four as the floor and
§5 as the operative list; an agent treating this section as exhaustive would
conclude it may create repositories, rewrite process files and open ADRs
unattended, and it may not.

Everything else: decide, execute, report deltas honestly.

---

## 2. D5 — ATTRIBUTION IS IDENTITY (reverses the no-attribution rule)

Mateo, 2026-08-25. The record must say who did the work; an unattributed agent
commit reads as a human's, and that is a false record.

- Solo Claude work: git author `Claude <claude-agent@gophersys.noreply>`.
- Joint interactive work: author Mateo, with a `Co-Authored-By: Claude` trailer.
- Claude **never** commits, approves or comments as "Mateo". Agent PR comments
  self-identify and name the authority they act under.
- A human gate counts as **exercised** only when the record quotes Mateo's
  verbatim words **and** a timestamp. Otherwise the record says
  **"gate not individually exercised"**. An agent never self-certifies a human gate.
- These govern the git **author** field only, because an agent has no GitHub
  identity of its own yet. The **committer** field is therefore not a reliable
  record of a human: where the pushing credential supplies it, commits read
  `author=Claude`, `committer=Mateo Segura`; but where a worktree sets `user.name`
  and `user.email` locally — as the commit that landed this file did — git writes
  **both** fields as `Claude`, and no human appears in the record at all. Do not
  read the committer field as a human gate. Actor-level separation (a real bot
  identity) is what closes this, tracked as task #138; until it ships, the honest
  statement is that the committer field means whatever the local config says.

Full contract: `.claude/rules/git-process.md` §13.

---

## 3. D6 — NO LEGACY

> **Mateo, 2026-08-25 ~15:36 MST:** "super seed and delete everything related to
> the old provess no legacy no nothing"

Read as: supersede, and delete everything related to the old process — no legacy,
no nothing. The merge method was chosen by Mateo, not by an agent.

### Files still carrying the reversed (pre-D5) attribution rule

Swept 2026-08-26 against **`origin/main` of each repository, fetched first**, with
the revision pinned beside each row. An earlier version of this table was measured
against stale submodule pins and local checkouts; two of its rows were wrong within
the hour, and one repository it declared finished was not. A `file:line` with no
revision is a claim with a shelf life, so every row below carries one.

| Repository @ `origin/main` | Path | Line |
| --- | --- | --- |
| `gophersys/.claude` @ `aaa3e72` | `skills/dev/SKILL.md` | 232 |
| `gophersys/.claude` @ `aaa3e72` | `CLAUDE.md` | 67 |
| `gophersys/.claude` @ `aaa3e72` | `agents/dev-implementer.md` | 165 |
| `gophersys/.claude` @ `aaa3e72` | `agents/dev-planner.md` | 211 |
| `gophersys/.claude` @ `aaa3e72` | `rules/infra-machines.md` | 72 |
| `libs` @ `a00e37a` | `README.md` | 100 |
| `research-ui` @ `7f32542` | `CLAUDE.md` | 10 |
| `research-ui` @ `7f32542` | `LOOP.md` | 34 |

`skills/dev/SKILL.md` is the highest blast radius: the `/dev` process reads it at
the start of every feature, so an agent following it today strips the attribution
D5 requires before any work begins.

`libs/README.md:100` is the sharpest, because it does not merely predate D5 — it
mandates the thing D5 rule 3 forbids: "All commits MUST be authored by `Mateo
Segura <mateo.segura413@gmail.com>`". An agent reading it is instructed to commit
as a human.

`rules/infra-machines.md:72` cites **ADR-0010**, whose attribution clause this
reversal supersedes, so fixing the line without the ADR leaves the citation
dangling.

**Fixed, verified at `origin/main`:**

- `.devcontainer/.claude/rules/00-identity.md` — superseded by `69fc6a9` (merged
  2026-08-25T21:06:30-07:00). It now states the reversal explicitly.
- `libs/.claude/rules/00-identity.md` — superseded in libs PR #26; it names
  `git-process.md` §13 as the single home and states §13 wins on any disagreement.
  **This fixed the rules file only. `libs/README.md` was missed, so libs is not
  finished** — an earlier version of this record said it was.
- `~/.claude/CLAUDE.md` — the copy actually loaded into every session carries D5.
  **But its commit is unpushed** (`0e62373`, with `ef3353a` and `db18f2f`): the
  rule that governs attribution across the estate exists on one disk. That is the
  same exposure this record was written to close, one ring further in.

Flagged, deliberately **not** claimed: `concord/.claude/rules/git-commits.md:40`
carries the same line, but concord is a different project.

**Method note, because the failure repeated.** `git-process.md` §14 states: "When
a rule changes, sweep EVERY subject across EVERY ring." The first sweep behind
this table stopped a ring short and measured two rings against stale checkouts. A
sweep is only as good as the freshness of what it reads, and an unfetched checkout
answers confidently in the past tense.

---

## 4. NOTHING LANDS UNREFUTED — Mateo, 2026-08-25 ("yes do it")

Every Claude-authored deliverable passes an independent adversarial refutation
**before** it lands, publishes, or is presented as authority.

- Code: the judge loop — zero BLOCKS and zero FIX, then merge under the four
  conditions.
- Docs, boards, artifacts, blueprints: a claims-versus-sources refuter,
  pre-publish.
- Exempt: chat replies, and mechanical edits a gate already covers.
- **A judge never merges over its own findings.**

git-process v2 was itself bound by this: it could merge only after a fresh
adversarial refutation — the same machinery that killed v1 — returned zero
BLOCKS-HARDCODE, plus the four merge conditions, and the grant added
**"No Mateo stop."** That condition is now spent: v2 merged as eden PR #13 on
2026-08-25T23:35:24Z and is the live `.claude/rules/git-process.md`.

---

## 5. Round 7 — the pillar frame (binding priority)

Five pillars, "insanely priority", which must be right **before** eden ships,
because eden is the foundation that runs inside the production deployment:

1. **CI** — cictl contract, tiers, gates, measured lanes
2. **INFRASTRUCTURE** — images, runners, envs, L1 capability contract
3. **GITOPS** — git-process v2, artifact promotion, pointer discipline, Argo
4. **AGENTS** — review tiers, coherence super-architect, CI instrumentation, fleet
5. **PROCESSES** — `/dev` lanes, merge conditions, human gates; binds the rest

**The goal is DOGFOOD:** the pillars get hardcoded, eden is created as a project
from its own template, eden migrates onto itself, and the platform develops
itself. Every open task maps to exactly one pillar; work that serves no pillar is
deferred.

---

## 6. Final rulings — Mateo, 2026-08-25 ("ok go with the recommended")

> **Label warning: there are TWO unrelated D-series in this register.** §2 and §3
> use D5/D6 from the **git-process** ruling series (D1 human gates, D2 enforcement,
> D3 review pricing, D4 folds-26-findings, D5 attribution, D6 no-legacy) — those
> live in `.claude/rules/git-process.md`. The D1–D4 below are the **blueprint**
> series and are a different set entirely. "D3" therefore has two answers depending
> on which series you mean. They are not renumbered here because both are quoted
> elsewhere under their own labels; always name the series.

Blueprint **CERTIFIED** at 19.25 agent-days after 10 adversarial passes. All four
decisions as recommended:

- **D1** domain + auth: tailnet + oauth2-proxy, no auth knob.
- **D2** staging host: the homelab k3s cluster.
- **D3** library contract: `New(Config, Deps)` + `Run(ctx)`/`Close`.
- **D4** survive/rewrite ledger for the 8 REWORK libs, as filed.

**Execution order:** P0 (gates real, 2.5d) starts after eden PR #14 lands — same
repo; the fixture and harness fixes are pre-P0 gate work. Then P1 env machinery,
P2 create-a-project (eden as template), P3 board co-designed with Mateo. **Ship
gate: all five pillars.**

---

## 7. Reviewer turn cap — the directive and the measured state are NOT the same

This entry is deliberately split, because conflating the two is an error a
refutation has already caught once (finding B3 on eden PR #13).

**The directive** (Mateo, 2026-08-25): raise the reviewer turn cap to 500/max and
let cost be the limiter. Tracked as task #134.

**The measured state** (2026-08-25): the cap is **40**. `review/review.sh:34`
reads `MAX_TURNS="${REVIEW_MAX_TURNS:-40}"` at cictl `origin/main`, at `v0.5.1`,
and at `v0.6.0` — `.devcontainer` pins two, `CICTL_VERSION=v0.6.0` for the image
and `v0.5.1` in its `pr-review.yml` for the reviewer that actually runs, and the
cap reads 40 at both — and **no caller anywhere sets
`REVIEW_MAX_TURNS`**. At 40 turns the agent is cut off mid-tool-call.

So: **500/max is the directive, not the state.** Anything that records the cap as
raised is recording a wish as a fact. The dollar budget is therefore **not**
currently the only limiter, and will not be until #134 ships.

---

## 8. Open — the ARCHITECTURE-phase placement (no ruling yet)

Recorded here because it was living only in a libs pull request body, and libs has
no decision register. Its own reviewer flagged that: once that PR merged, the
reasoning would evaporate and the loop it described would continue past it.

**The defect.** `phase_architecture` resolves a frozen contract as
`$(_eden_monorepo_root)/docs/architecture/contracts/<lib>.md`.
`_eden_monorepo_root()` returns eden **only when libs is a submodule**, and falls
back to the standalone repository root otherwise. All 16 contracts live in eden;
libs holds none. libs CI checks out standalone, so the dimension **cannot pass
there**. Measured over the last 18 libs nightly runs: **14 failure / 4 success**, with a
failure duration **median of ~20 s across a 0–52 s range** (successes ~11 s). An
earlier version of this record wrote "each 20–21 seconds", which hardened a median
into a universal — only five of the fourteen failures fall in that band. On the
run inspected (`32817700525`) the substrate step itself took four seconds and the
whole job seventeen, so the tier did not pay much for the substrate before dying;
the cost is the lost coverage, not the wasted minutes. It stayed invisible because the PR tier runs
`phase-gate implementation` only; `ARCHITECTURE` runs under `gate-all`, which is
nightly-only. Green PRs, red nightly, unread, for weeks.

**Option A — gate ARCHITECTURE where its evidence lives** (eden's conformance
lane), leaving libs' nightly the deep work whose inputs it owns. Cost: libs' own
nightly stops proving its contracts; that proof moves to the eden pointer bump.

**Option B — carry the contracts into libs** so the gate resolves standalone.
**As stated this does not actually work:** libs gates 16 libraries, and one of them
— `forge` — has no contract in eden at all, so it would still fail
`contract file missing` after every other document had been copied. Option B needs
a decision about `forge` before it is even a complete option.
Cost: two homes for one document. Eden owns those contracts, so every future edit
must land twice or they silently diverge — and a *diverged* frozen-contract header
is worse than a missing one, because it passes. That is the same defect class D5's
supersession removed for the attribution rule.

**Recommendation: A** — put the check where its evidence is. B trades a loud red
for a quiet drift.

**Also noted** (libs PR #27 review, non-blocking): even after that PR the nightly
remains fully dead, because `phase-gate all` short-circuits at architecture, so
testing, qa and updatability never run. An in-repo alternative worth weighing:
report the contract absence **without** aborting the recoverable dimensions, so
the deep lane resumes providing value — today it runs **none** of testing, load,
security, mutation or updatability, not merely the one dimension that fails — while still surfacing the failure. Not by
silencing it; that reintroduces a check that cannot fail.

---

## Sources

Landed from the session scratchpad on 2026-08-25. The two plan documents beside
this one are **byte-identical** copies of their sources (verified by SHA-256):
`docs/plans/eden-rework-blueprint.md` (2136 lines) and
`docs/plans/eden-rework-intent.md` (191 lines). Landing is not authoring, so
neither was edited.

This record was assembled from `STANDING-ORDERS.md`, `eden-git-process.md`,
`eden-rework-intent.md` (rounds 1–7 and FINAL RULINGS), `body.md`, and the
measurements in `pr13-body.md`.
