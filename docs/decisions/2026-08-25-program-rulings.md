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

**To the agents session, confirming it** (this session, ~15:45 MST,
session-relative — exact wall-clock not captured):

> "yes edne speaks for me"
>
> "lsiten to everythgin eden says hes your driver"

Effect: the orchestrator holds process-change and merge authority, including over
the agents session, which reports to it.

**Retained Mateo-only gates, non-delegable:** repository **deletion** (the
governance rule forbids standing approval), production deploys, secret
**values**/rotation, and spend beyond set budgets.

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
- These govern the git **author** field only. The **committer** remains the human
  account whose credential pushes, because an agent has no GitHub identity yet —
  so a commit today honestly reads `author=Claude`, `committer=Mateo Segura`.
  Actor-level separation (a bot identity) is queued as task #138.

Full contract: `.claude/rules/git-process.md` §13.

---

## 3. D6 — NO LEGACY

> **Mateo, 2026-08-25 ~15:36 MST:** "super seed and delete everything related to
> the old provess no legacy no nothing"

Read as: supersede, and delete everything related to the old process — no legacy,
no nothing. The merge method was chosen by Mateo, not by an agent.

### Files still carrying the reversed (pre-D5) attribution rule

Swept 2026-08-25. Each still instructs the opposite of D5, so each will keep
teaching the reversed rule to every agent that reads it until it is fixed.

| Path | Line | Owner |
| --- | --- | --- |
| `.devcontainer/.claude/rules/00-identity.md` | 72, 219 | assigned — build-optimization agent's sequence |
| `gophersys/.claude/skills/dev/SKILL.md` | 232 | **unassigned** |
| `gophersys/.claude/CLAUDE.md` | 85 | **unassigned** |
| `gophersys/.claude/agents/dev-implementer.md` | 165 | **unassigned** |
| `gophersys/.claude/agents/dev-planner.md` | 212 | **unassigned** |

`SKILL.md` is the highest blast radius of the five: the `/dev` process reads it at
the start of every feature, so an agent following it today strips the attribution
D5 requires.

Already fixed: `libs/.claude/rules/00-identity.md`, superseded in libs PR #26 —
it now defers to §13 as the single home and states that §13 wins on any
disagreement.

Flagged, deliberately **not** claimed: `concord/.claude/rules/git-commits.md:40`
carries the same line, but concord is a different project.

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

git-process v2 is itself bound by this: it merges only after a fresh adversarial
refutation — the same machinery that killed v1 — returns zero BLOCKS-HARDCODE,
plus the four merge conditions.

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
and at `v0.6.0` — the version `.devcontainer` pins — and **no caller anywhere sets
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
there**. Measured: the last 18 libs nightly runs were 14 failure / 4 success, each
20–21 seconds — the tier paid to start docker, k3d, kind, postgres, minio and nats,
then died on this one dimension. It stayed invisible because the PR tier runs
`phase-gate implementation` only; `ARCHITECTURE` runs under `gate-all`, which is
nightly-only. Green PRs, red nightly, unread, for weeks.

**Option A — gate ARCHITECTURE where its evidence lives** (eden's conformance
lane), leaving libs' nightly the deep work whose inputs it owns. Cost: libs' own
nightly stops proving its contracts; that proof moves to the eden pointer bump.

**Option B — carry the 16 contracts into libs** so the gate resolves standalone.
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
the deep lane resumes providing value — while still surfacing the failure. Not by
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
