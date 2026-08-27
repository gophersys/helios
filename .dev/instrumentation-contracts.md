# instrumentation-contracts

phase:    intake
repo:     gophersys/eden
branch:   docs/instrumentation-contracts
worktree: ~/code/.worktrees/eden-instrumentation-contracts
pr:       -
attempt:  0/2

## Goal

Author the two DRAFT contract documents that let the observability + agent-instrumentation
program run as parallel lanes against written API agreements instead of against each other:

- **`agentprofile`** — the central schema (role × harness matrix) that is the single source of
  truth for agent instrumentation, the renderer that emits each harness's native files, the
  determinism guarantee, the commit-time drift-gate semantics, and how a rendered profile is
  addressed by a pod (artifact + digest, which the AgentPod CRD's `profileRef` points at).
- **`fleettelemetry`** — the message-kind → OTel mapping table, task-as-trace semantics, the
  durable-consumer read pattern that never competes with delivery consumers, and the UI
  streaming read model that platformgateway serves from the same consumer.

Status stays **DRAFT for negotiation**. Freezing is Mateo's §5 gate and no agent exercises it.
Each document ends with the exact freeze question Mateo must answer.

## Authority

Mateo's four design rulings, 2026-08-26, decision prompt, interactive session f9c810a8.

> ⚠️ **These are the rulings AS RELAYED TO THIS LANE, not a transcript.** They are recorded in this
> lane's own words and are NOT presented as Mateo's verbatim wording — `git-process.md` §13 rule 4
> reserves "verbatim" for a quote with a timestamp, and this lane does not hold the transcript. The
> refutation caught two different renderings of ruling 4 on one branch, which is precisely the
> hazard: at most one could have been verbatim, and neither was marked as a paraphrase. Where a
> document needs Mateo's exact words, it must get them from him.

1. Instrumentation source of truth = **central schema + renderer** — one agentprofile schema
   (role × harness matrix: claude/omp/codex) in eden; a renderer emits each harness's native
   files (CLAUDE.md, .claude/rules, skills, settings; omp/codex equivalents).
2. **Commit-time rendering + drift gate** — rendered files are committed; CI fails on drift,
   following the estate's existing generated-file pattern.
3. Telemetry = **bus consumer** — one service consumes the fleet's JetStream messages → OTel;
   the same consumer feeds UI streaming (platformgateway SSE). No in-process exporters in
   agentsession.
4. **Task = trace across the whole tree** — the message header carries a task id and a W3C
   traceparent.

Plus the standing program directives of the same day: *"we can kick off a lot of these things
in parallel if we do api agreements up front"* and *"i want u to make bigger code changes and
test locally before submitting a pr, avoid submitting smaller code, and try to implement
features completely"*.

## Lane

FEATURE lane (`.claude/rules/git-process.md` §4 — "any contract change"). Phase 2's red-test
obligation has **no subject in this repository**: this change adds no executable surface. That is
STATED, never waived — no agent may waive §4/phase 2 for itself.

> ⚠️ **Corrected — an earlier revision of this line was a claim I had not measured.** It read: *"The
> executable proof of the `agentprofile` agreement is the sibling `gophersys/libs` pull request
> (`feat/agentprofile`), whose conformance suite is **red-first** and whose `phase-gate qa` runs in
> the devcontainer."* Both halves were false when written and the refutation caught it:
> `find …/libs-agentprofile/go/agentprofile -name '*_test.go' | wc -l` → **0** at the time, and
> `phase-gate qa` had never been run, let alone passed. It was a PLAN written in the present tense
> in a section whose whole rule is that only executed commands belong there.
>
> The true statement, recorded in the sibling lane's own state file: **TDD order was NOT followed
> for that library.** The phase-1 agent implemented working behaviour alongside the skeleton, so the
> conformance cases could not be written red-first. Only Mateo may waive red-tests-first and no
> agent may waive it for itself; that lane is not waiving it, it is REPORTING it, and compensating
> per-test with mandatory break-probes — plus three slices (`Tree.Stat`/`List`, the `NN-` ordering
> prefix, and the `settings.json` emission) that are genuinely unimplemented and therefore DO get
> real red-first treatment. This entry says so rather than quietly renaming a break-probe as a red.

## Plan

SELF-APPROVED. Two DRAFT contracts, plus the two registrations a new contract owes.

Files this branch touches:
1. `docs/architecture/contracts/agentprofile.md` — new, DRAFT.
2. `docs/architecture/contracts/fleettelemetry.md` — new, DRAFT.
3. `docs/architecture/contracts/README.md` — one table row each. A contract that is not in the
   index is a document nobody finds.
4. `docs/architecture/README.md` §4 — one cohesion-contract row each. Today that table has NO row
   for observability, for the agent fleet, for the message spine, or for agent profiles; four homes
   are unclaimed, and a contract that claims a home without writing it there has claimed nothing.
5. `.dev/instrumentation-contracts.md` — this file, deleted in the last commit before any merge.

### The one risk weighed

Two contracts at once risks one of them drifting from the rulings, and risks colliding with the
parallel `docs/fleet-contracts` lane. Mitigation: every normative statement carries its source; the
two documents are authored by agents with DISJOINT single-file ownership; and the fleet lane's
`fleetenvelope` draft is CONSUMED rather than re-derived — see the coordination note below. An
adversarial claims-vs-sources refutation runs before the pull request opens.

### Coordination with the parallel fleet-contracts lane — resolved, not assumed

The lane exists and has landed its first draft: eden branch `docs/fleet-contracts`, commit
`9773347`, `docs/architecture/contracts/fleetenvelope.md`, 672 lines, DRAFT for negotiation. It
owns `fleetenvelope`, `fleetbus`, `agentpod` and `fleetcheckpoint`. I read it; I never edit it.

It has since added `fleetbus.md` (944 lines, DRAFT), whose **§9 is titled "The telemetry consumer
— Mateo's ruling of 2026-08-26"** and already owns the read pattern. Its §9.3 states the invariant
in the form that can actually fail: *"For a telemetry consumer T attached to stream S, and a
delivery consumer D on the same stream: for every message M published to S, D receives M — and T's
attachment changes neither the set nor the count of messages D receives"*, with
`ConsumerPolicy.QueueGroup` empty as the mechanism. Its §3 owns the four subjects and three
durability classes, §5 owns `MsgId` and dedup, §6 owns the two sequence spaces and the
history↔live stitch, §7 backpressure, §8 archive-then-publish.

So `fleettelemetry` §5 shrank to a citation plus the ONE thing genuinely its own and absent from
`fleetbus`: **what the consumer does when the OTLP export fails.** At-least-once redelivery means a
span can be emitted twice, so the contract must say whether the emission is idempotent, and if it
is not, what that costs and who decides. Fail loudly; never a silent drop. A section that
re-derives a sibling contract is the second home the cohesion contract forbids.

It has already ANSWERED the question this lane was told to pose. Its §4.2 makes `TaskID` a
first-class required field and `TraceParent` / `TraceState` typed fields that SUPERSEDE
`agentruntime`'s `OTelContext map[string]string`, with the reason given: a map cannot be validated,
admits a second home for the same two W3C keys, and lets a producer smuggle an arbitrary key onto
an audited wire. Its §4.3 quotes the same bus-consumer ruling and hands the durable-consumer
mechanics to `fleetbus`. So `fleettelemetry` CITES that header and owns only the mapping and the
read model. The boundary is written into `fleettelemetry` §1 as an explicit NOT-list.

## The parallelization map — what can start when

| # | lane | repo | starts | blocked on |
| --- | --- | --- | --- | --- |
| 1 | **agentprofile renderer library** | libs `feat/agentprofile` | **NOW — in flight** | nothing to build; only the FREEZE waits on Mateo |
| 2 | **`oteladapter`** — the missing `observability.Exporter` binding | libs | **NOW** | nothing. The `Exporter` seam is already frozen and `slogadapter` is the only binding, so no span can leave a process today. This is the single highest-value unblocked lane. |
| 3 | **infrastructure: OTLP endpoint + egress + datasource** | infrastructure | **NOW** | nothing. Zero eden workloads set `OTEL_EXPORTER_OTLP_ENDPOINT` (measured: no match across 13 manifests); the cloud Grafana has no Tempo datasource. Until this lands, every telemetry claim is unprovable. |
| 4 | **drift gate wiring** — a libs `phase-gate` dimension and/or an eden `.ci` verb | libs + eden | after lane 1's `drift` verb exists | lane 1. Freeze question 2 decides WHICH. |
| 5 | **telemetry bus consumer** | libs or apps | after `fleetenvelope` + `fleetbus` freeze | the sibling lane, and Mateo's freeze |
| 6 | **gateway SSE read model on the same consumer** | apps | after lane 5 | lane 5; and freeze question on which app serves it |
| 7 | **`profileRef` on the AgentPod CRD** | eden + infrastructure | after `agentpod` is drafted AND agentprofile's digest is frozen | the sibling lane's `agentpod`, and this lane's §7 |

Lanes 1, 2 and 3 are mutually independent and all start immediately. That is the whole point of
writing the agreements first.

## Proven

(populated only with commands run and output read)

### Gates — RUN, in the devcontainer, with the exit status read from the command itself

A second container off `ghcr.io/gophersys/base:latest` mounts `/Users/mateo/code` at its own
absolute path, so this worktree is visible inside it. `git submodule update --init --recursive`
(rc=0) first — a fresh worktree has EMPTY submodules, and without them the yarn workspace cannot
resolve `@eden/primitives` (which lives in `libs/typescript/`). Then `yarn install --immutable`,
rc=**0**.

**`bash .ci/ctl.sh graph-guard` — rc=0, and it RAN. Note the ENVIRONMENT, because it decides the
result:** this was run INSIDE the container, which is where the repository governance rule says a
gate must run. An independent refutation re-ran it on the macOS host and got **rc=1** —
`TypeError: (0, native_1.isAiAgent) is not a function`, an nx native-binding failure under the
host's node v25.9.0, with `GOPHERSYS_DEVCONTAINER` unset. That is not a contradiction of the result
below; it is the reason the rule exists. A host run of this gate proves nothing either way.

```
[info]  graph-guard: .nxignore covers all 36 required patterns
[info]  graph-guard: resolving the nx project graph
[info]  graph-guard: the graph resolves and holds 49 project(s)
[info]  graph-guard: the graph matches the roster exactly (49 project(s))
[ok]    graph-guard: OK — 49 project(s) resolved, 0 rooted in a submodule fixture tree
[info]  graph-guard: 8 project-shaped file(s) sit under a submodule fixture directory and produced no project
```

**`NX_BASE=origin/main bash .ci/ctl.sh affected-check` — rc=0, output `NX   No tasks were run`.**

**Both Status lines classify correctly under the merged gate's OWN parse**, run here rather than
reasoned about — `grep -c '^> Status:'` is exactly **1** in each file (so `grep -m1` cannot silently
take a different line), and after `tr -d '*'` each parses to `> Status: DRAFT for negotiation · …`,
which does not match `"> Status: Frozen"*` and does match the draft arm. Neither is
UNCLASSIFIABLE, which is the third way that gate exits 1.

**`node docs/tools/check-mermaid.mjs` — rc=0**, `10 blocks, 0 failing` over the whole docs tree.
Both new contracts contain **zero** mermaid blocks, so this proves the tree is unbroken rather than
that the new files were checked. **No docs tool is wired into any gate** — a grep over `.ci/ctl.sh`,
`.github/workflows/` and `scripts/` finds no reference to `render-html`, `check-mermaid`,
`render-atlas` or `render-documents`. A docs defect in this repository is caught by a reader, not
by CI, and that bears directly on how much the greens above are worth.

### ⚠️ TWO STALE CLAIMS IN `git-process.md` — reported, NOT edited

`.claude/rules/git-process.md` says in §5.2: *"In eden today both fire at once on any doc-only
change: there is no `pr-review` workflow, and the affected gates select nothing outside an Nx
project"*, and its §7 table row for `eden` reads *"hand-written. **NO pr-review** — see §8."*

**Both were true when written. Neither is true now.** `.github/workflows/pr-review.yml` is on
`origin/main`, added by `9d3553d ci: give eden the pull request reviewer it never had` and pinned to
cictl `v0.7.0` by `9ee462c`. `git ls-tree origin/main .github/workflows/` lists it.

**This pull request is the counter-example.** PR #24 triggered THREE checks — `affected-gate (fast)`,
`pinned-harness conformance`, and `review`. Not zero.

**I have not edited `git-process.md`.** §5 names "process changes (this file, `.claude/`, the cictl
contract)" as gated personally by Mateo, with no agent authority covering them. The correction is
reported to him and named in the final report; making it is his call. This matters beyond tidiness:
§5.2's empty-evidence-set escape is the rule an agent would reach for to merge a doc-only eden
change on nothing, and it now rests on a false premise in the agent's favour — the most dangerous
direction for a stale rule to be wrong in.

### ⚠️ CORRECTION — "the evidence set is EMPTY" was true of the OLD main and is FALSE of the new one

An earlier revision of this file said a docs-only eden change has no content evidence, citing §5.2.
That was measured against `bc84ea2`, the commit this branch was cut from. **`origin/main` has since
moved 12 commits (now `142c997`), and one of them repeals the claim.**

`703e5a1 ci: let harness-conformance trigger on itself and on the contracts it gates` added this
path to the workflow's `pull_request` filter, with its reason in the file:

```yaml
      # The frozen-contract step iterates these, so adding or removing one CHANGES WHAT IS GATED.
      # A new contract with no matching library, or a deleted contract that silently shrinks the
      # set, must be caught here rather than by a later reader noticing the count moved.
      - "docs/architecture/contracts/**"
```

This pull request adds two files under that path, so **`harness-conformance` is expected to run on
it** — and that job is the opposite of a no-op: it installs the pinned harnesses and runs the live
adapter suite against a real provider, and its own header says it "NEVER RUNS IN A DEGRADED MODE"
because "an input it cannot verify is a FAILURE, never a skip".

Two consequences, and both are stated on the PR:
- The evidence set is **not** empty. The affected gates still no-op, and `graph-guard` still passes,
  but the real gate here is `harness-conformance`. **Its actual check run is read before any merge
  is proposed** — expected-to-run is not ran, and this lane does not bank a prediction as evidence.
- It is an EXPENSIVE and CREDENTIAL-DEPENDENT lane that this change does not otherwise touch. If it
  reds for a live-credential or peer-messaging reason, that is **surfaced, not caused**, and the
  same-job-on-a-branch-without-this-change check settles which.

Branch state measured: 13 ahead, 12 behind, `git merge-tree` reports **0 conflict markers**, and
none of the 12 commits touches `docs/architecture/README.md` or `docs/architecture/contracts/`. No
rebase is taken — §6 says rebase when you must, not by habit.

That NX line is a **NO-OP and is not evidence about content** (git-process §5.1). A docs-only
change selects nothing, and the structural reason is measurable: there is no `project.json`
anywhere under `docs/`, and `.ci/graph-roster.txt` carries no `docs` row.

**But §5.2's SECOND condition does NOT fire, and an earlier version of this paragraph said it did.**
It read: *"eden also has **no `pr-review` workflow** (§7's own table). So on this pull request BOTH
§5.2 conditions fire at once and the content-evidence set is EMPTY."* That re-asserted, as live
evidence, the very claim this file had already recorded as stale twenty lines above — the file
contradicted its own correction, and the refutation caught it. `.github/workflows/pr-review.yml` is
on `origin/main` and PR #24 triggered a `review` check.

So the honest position is the opposite of the earlier one: **only ONE §5.2 condition fires (the
affected gates no-op), the evidence set is NOT empty, and the real evidence is the `review` verdict
plus `harness-conformance`.** Both are read as their own tool calls before any merge is proposed.
This branch is still not merged by an agent, but the reason is Mateo's §5 contract-PROMISE gate,
not an absence of evidence.

**The lesson, recorded because it is the second time this exact shape appeared in this file:** a
correction written in one section does not repeal the claim in another. When a fact changes, sweep
EVERY place it is used, not just the place it is defined — which is the same rule `git-process.md`
§14 states after the ADR-0032 sweep missed the root `CLAUDE.md` twice.

### The reviewer exists, it ran, and it returned REQUEST_CHANGES — read as its own call

eden PR **#24**. `review` reported **FAILURE**; the verdict comment ends **`REQUEST_CHANGES`**. Per
§5.2 the verdict is read as its own call, and it is not treated as blocked-by-a-red-badge: the
badge and the verdict agree here, and the verdict is what governs. Two findings, both real, both in
`fleettelemetry`:

1. **§9's intro says "Six questions" and then enumerates Q1–Q8.** The status header already says
   eight, and the closing line makes Q1, Q4, Q5 and Q8 mandatory — so "six" is not even the
   mandatory subset. The reviewer's reason is the right one: *"§9 is the decision surface: it is the
   whole reason the document exists in DRAFT, and the freeze gate turns on it."*
2. **The transport citations DANGLE ON `main` AFTER MERGE.** `fleetenvelope.md` and `fleetbus.md`
   exist only on the sibling branch. *"After merge, `main` carries `fleettelemetry.md` and a README
   pointer chain whose targets do not exist in the repository"* — and this pull request itself
   measured that no docs tool is wired into any gate, so *"nothing catches the dangling references;
   they ship silently"*. It also names the deeper point: the stated freeze order
   `fleetenvelope → fleetbus → fleettelemetry` now governs the DOCUMENTATION TREE as well, and
   merging the dependent document first inverts it.

**Finding 2 is a defect neither the refutation nor this lane caught**, and it is a distinct axis
from the one we did catch. The earlier concern was citing UNCOMMITTED bytes; the sibling fixed that
by committing at `70a979f`. This is the next axis out: **committed on a BRANCH is still not present
on `main`.** A citation can be valid in a worktree today and dangle the moment the document lands on
trunk. Three states have to be told apart, not two — on `main`, committed-off-trunk, and
does-not-exist — and only the first and third were being distinguished.

The two index rows are corrected here; §1's dependency table is corrected in the document. The
reviewer explicitly cleared `agentprofile.md`: *"its citations (`orchestrator.md`,
`agentsession.md`, ADR-0026) are all already on `main`."*

### The refutation was right that the count was wrong, and wrong about the count

`fleettelemetry` §3.2 claimed the mapping table was exhaustive over `agentsession.EventKind` and
said there were **sixteen** members. The refutation caught that and reported **seventeen**. Counting
the const block by command gives **twenty**:

```sh
start=$(grep -n 'EventSessionState' libs/go/agentsession/types.go | head -1 | cut -d: -f1)
awk -v s="$start" 'NR>=s' libs/go/agentsession/types.go | awk '/^\)/{exit} {print}' | grep -cE '^\s+Event[A-Z]'
# 20
```

Four members are missing, not one: `EventTurnEnd`, `EventPeerMessage`, `EventPeerSent` and
`EventSubagentMessage`. The last three are the intra-harness message plane — the peer and subagent
messaging the harness program added — and they matter to a telemetry contract more than most:
`EventPeerMessage` carries *"UNTRUSTED foreign prose"* (a redaction and cardinality surface at
once), `EventPeerSent` has an `Accepted == false` with **four** distinct meanings that a single
failure attribute would erase, and `EventSubagentMessage` is documented as *"a DISTINCT function
from peer messaging, never in the tree roster"* — so it must not share a span shape with peer
messaging or the telemetry re-conflates exactly what the frozen contract separated.

**Three independent counts, three different answers, none of them from counting.** The document
inherited sixteen, the refutation reported seventeen, and both were assertions. This is the
`/dev` rule about not accepting a review finding without checking it — *"The reviewer has been
wrong, and so have you"* — and it is the second time in this lane that running the command beat
reading the claim. The fix carries the command that produces the number, so the next reader
re-derives it instead of trusting it.

### An operational cost I incurred, worth writing down

`harness-conformance.yml` and the review workflow both declare
`concurrency: … cancel-in-progress: true`. **Every push to an open pull request cancels the runs in
flight and starts them again.** This lane pushed after almost every commit — correct under §3 rule 2
("PUSH AFTER EVERY COMMIT. The laptop is not a home"), but expensive here, because §6 states the
consequence precisely: *"a cancelled review posts no comment and rounds count from posted comments,
so the money is spent and no round is recorded."* Several reviewer starts were paid for and
recorded nothing.

The two rules are not actually in conflict; the resolution is to keep pushing while a pull request
is not yet OPEN, and to BATCH pushes once it is. This lane opened the pull request as a GitHub
DRAFT early — which was right for getting `harness-conformance` running against a real branch, and
wrong in that it armed the reviewer before the refutation findings were applied. From the point the
refutation landed, commits were batched into one push.

### A masking defect I hit myself, in this lane, and the correction

The first attempt ran `yarn install --immutable 2>&1 | tail -20`. Yarn FAILED
(`Error: @eden/primitives@workspace:*: Workspace not found`) and the pipeline still reported
**exit code 0**, because `tail` was the last command in the pipe and its status is the pipeline's.
The green was mine, not yarn's. Every command above was re-run in the form the process requires —
`set +e; cmd; rc=$?; set -e`, or `${pipestatus[1]}` where a pipe was genuinely wanted — and the
numbers quoted are those. This is the same class as `cmd | head -5 || true` followed by `rc=$?`,
which the `/dev` skill names explicitly; it is worth recording that the rule caught a real defect
here rather than a hypothetical one.

### Research reads — the facts that constrain both documents

Every line below was read out of the file named, in this worktree at `origin/main` (bc84ea2).

- **Where a contract goes.** `docs/architecture/contracts/<slug>.md`, slug = one lowercase HNS-1
  word matching the future `libs/go/<slug>`. NOT the `NN-` series — `docs/architecture/README.md`
  states the next unused canonical-spec slot is 20 and that 15 is a deliberate gap.
- **The header grammar.** `# Contract — <slug>` then a blockquote `> Status: …`. The draft form is
  `contracts/codeinsight.md`: `# Contract — codeinsight (DRAFT)` over
  `> Status: **DRAFT for negotiation** · <date> · …`.
- **Freeze questions live in `## 7. Open questions`** — a 5-column table
  `| # | question / conflict | producer position | consumer position | reconciler resolution 🧩 |`.
- **Registration is part of the change**: a row in `contracts/README.md`
  (`| Draft | Kind | Summary |`) and a row in the §4 cohesion-contract table of
  `docs/architecture/README.md`. There is no row today for observability, the agent fleet, the
  message envelope, or agent profiles — those homes are unclaimed.
- **The message envelope ALREADY EXISTS and is FROZEN**, under a different name and a different
  owner: `contracts/agentruntime.md` §4.1 `EventEnvelope` (+ `ControlMessage`, `Heartbeat`),
  realized in `libs/go/agentruntime/protocol.go`. Subjects `agent.<id>.events|control|health`,
  one stream `EventsStreamName = "EDEN_AGENT_EVENTS"`, `MsgId == Seq` so a consumer replays
  gap-free from any `Seq`. `libs/go/envelope` is the UNRELATED AES envelope-encryption leaf
  (ADR-0029). **Neither of my documents may redefine either.**
- **Ruling 4 splits cleanly in two, and only ONE half needs a contract revision.** Verified by
  command against `libs/go/agentruntime/`:
  - `type OTelContext map[string]string` (protocol.go:51) is already a field on `EventEnvelope`
    (protocol.go:58-64), `ControlMessage` and `Heartbeat`. The key `"traceparent"` is already the
    carrier the library's OWN tests assert on — `asserts_test.go:62 const keyTraceParent =
    "traceparent"`, `property_test.go:107`, `runtime_test.go:178` against
    `agentruntimetest.TraceParent`. So the **traceparent half needs no schema change at all**: it
    needs a real propagator and an `oteladapter`, not a new field.
  - **A task id has no field anywhere in the protocol** (grep for `taskid|task_id|"task"` over
    `libs/go/agentruntime/*.go` returns nothing but the traceparent hits above). So the **task
    half is a contract REVISION of `agentruntime.md`** — ADR-0016 §1 ceremony plus a re-record of
    `libs/go/agentruntime/.apibaseline`. That is Mateo's §5 gate, not mine, and it is the freeze
    question the fleettelemetry document must ask rather than answer.
- **`agentruntime/otelobserver` is not the OTel SDK.** Its `Inject`/`Extract` move an in-process
  `map[string]string` under a private context key and never encode a real W3C `traceparent`. So
  "OTel on every message" is a propagation SEAM today, not a working distributed trace.
- **No `oteladapter` exists.** The only `observability.Exporter` implementation is `slogadapter`
  (stdout), so no span can leave a process today. No eden workload sets
  `OTEL_EXPORTER_OTLP_ENDPOINT` — grepping `infrastructure/apps/eden/*.yaml` returns zero matches
  across all 13 manifests. The homelab observability chart (`eden-observability`: alloy gateway +
  alloy logs + loki + tempo + grafana + prometheus) exists with a homelab values file and is NOT
  installed.
- **The UI streaming half already exists and is EPHEMERAL**: `libs/go/edenhttp/natssse` opens an
  ephemeral JetStream consumer per request from a caller-supplied start sequence and frames
  `EventEnvelope` onto SSE with `id: <Seq>`, so a browser resumes by echoing `Last-Event-ID`;
  `apps/agentgateway/internal/stateless/events.go` serves `GET /sessions/{id}/events`.
  `apps/platformgateway` owns the connectors domain and carries NO agent-event surface — so
  ruling 3's "platformgateway SSE" names an app that does not serve that today.
- **Nothing named agentprofile exists**: zero hits repo-wide for `agentprofile`, `profileRef`,
  `harness matrix`, or CLAUDE.md generation. There is no AgentPod CRD and no Eden-owned CRD at
  all; the agent pod is plain YAML at `infrastructure/apps/eden/58-agent-runtime.yaml`.
- **The adjacent, RESERVED home is `agentconfiguration`** — `10-library-system.md:350` gives it
  "compiles to harness formats", and frozen `contracts/orchestrator.md` says `AgentTemplate.Skills
  []SkillRef` / `Rules []RuleRef` are resolved by "agentconfiguration" into "harness-native
  files". The library does not exist. This is the cohesion question the agentprofile contract must
  settle rather than step around.
- **Open decisions that touch this work**: OD-7 (agentconfiguration open items, incl. "harness
  plugin model"), OD-11 (S6 observability stack composition — de-facto settled by the pinned
  infrastructure chart and unrecorded), OD-13 (fleet deployment architecture). Next free ADR
  number is **0033** (0030 is a silent gap, referenced by nothing — do not reuse it).

### The agentconfiguration boundary, settled by measurement rather than by argument

The worry was that `agentprofile` would be a SECOND home for a concept `agentconfiguration`
already owns. Measured over the upstream design in this worktree, with the counts run here:

- `grep -ci CLAUDE.md docs/upstream/build-system/agentcfg-architecture.md` → **0**. Its claudecode
  emitter writes `.claude/settings.json`, `.claude/agents/<name>.md`, an optional
  `~/.claude-code-router/config.json` and `.mcp.json`. It never writes a `CLAUDE.md`.
- `grep -ci` for `drift` → **0**, `byte-identical` → **0**, `determinism` → **0** in the same file.
  It ships purity, a `FileSet.Diff(root)` primitive and golden tests — the ingredients — but no
  determinism guarantee and no gate. A `Diff` you can call is not a check that fails.
- Line 1041, verbatim: *"- **No agent framework.** No tool-loop, no scratchpad, no skills. This is
  the layer below your agent loop."* Skills are an upstream NON-GOAL, in its own words.
- Its entire instruction-content model is two scalar paths —
  `docs/upstream/build-system/portable-agent-config-2026-06.md:165-167`: `rules:` /
  `global: AGENTS.md` / `per_mode_root: rules/`. No bodies, no composition, no precedence, no
  overlays.

So **determinism, the commit-time drift gate, and the composition/precedence/overlay of
instruction content are genuinely unowned.** That, not a turf claim, is what justifies a contract.

Three collisions the draft must resolve rather than avoid, each verified here:

1. **`contracts/orchestrator.md:129-131` (FROZEN) leaves the owner AMBIGUOUS** — *"capability
   modules the agentconfiguration/TemplateStore resolves into harness-native artifacts"*. The
   slash is the seam. It may be claimed, but only explicitly and with that line quoted.
2. **`contracts/agentsession.md:477-480` (FROZEN) already owns the word "role"** —
   `type RouteKey struct { Phase string; Role string }`. A bare role × harness matrix silently
   DROPS the `Phase` axis the frozen contract carries.
3. **`adr/0026-…:59` already declares `.claude` rules a *template-managed* path** synced by 3-way
   merge, which "re-applies upstream changes while preserving local edits". That is mutually
   exclusive with a drift gate on the same path: a path cannot both preserve local edits and fail
   CI on any diff. ADR-0026's machinery is stated as to-be-built, so this pre-empts rather than
   breaks — but it must be written down.

The naming warrant is already in the repository: `.claude/rules/git-process.md` §12 rules that
*"the repository's own `CLAUDE.md` and `.claude/` ARE the CI profile"*, and records as ASSUMED,
not measured, that each repository's committed instrumentation is complete enough to stand alone.
A schema plus a drift gate is what makes that assumption mechanical. It is a DIFFERENT gate from
§12's own TO-BUILD probe (§14 row 10, owner `cictl`), which asks whether the CI agent LOADED the
profile, not whether the committed render MATCHES the schema.

## A defect this work SURFACED but did not cause — `natssse` conflates two sequence spaces

Found while writing the `fleettelemetry` read model, then verified by reading the source directly
in `libs/go/edenhttp/natssse/natssse.go` at libs `origin/main` (8683fea):

- `forward` frames each event with `ID: envelope.Seq` (`natssse.go:179-182`).
- `openConsumer` takes that same number back from `Last-Event-ID` and passes it as
  `nats.StartSequence(lastSeq+1)` (`natssse.go:157-168`).

**Those are two different numbering spaces.** `agentruntime.EventEnvelope.Seq` is documented at
`protocol.go:60` as *"the agentsession transcript offset"* — per session. `nats.StartSequence`
takes a JetStream **stream** sequence, and `EventsStreamName = "EDEN_AGENT_EVENTS"` captures
`agent.*.events` as ONE stream, subject-filtered per agent. So the stream sequence counts messages
across every agent while `Seq` counts within one session. **They are equal only when exactly one
agent with one session has ever published** — which is precisely the shape of a single-agent
fixture.

The conflation is written down in the code's own comment, which asserts both meanings at once:
`Seq // the agentsession transcript offset; the JetStream replay key`. The consequence is a
browser reconnect that resumes at the wrong stream position — replaying or skipping events, with
nothing to say so.

**Not caused by this change, and not fixed by it.** It belongs to `edenhttp`/`natssse`. What this
change does is refuse to inherit it: the `fleettelemetry` contract states the two spaces as
separate numbers and forbids the telemetry consumer from treating one as the other.

**The follow-up is OPEN, not promised: `gophersys/libs` issue #39**, filed with the two file:line
citations, the reason no current test can catch it, and — the part that matters — the reason the
obvious test is VACUOUS: `natssse.go:112` already subject-filters the consumer per agent, so "two
agents interleaved on one stream" passes with the bug fully intact. A non-vacuous assertion needs
two SESSIONS inside ONE agent, or a no-gap-and-no-duplicate check across a reconnect.

## ⚠️ A SEQUENCING CONSTRAINT this change creates, found by reading the gate that merged today

eden PR #18 merged at 2026-08-27T03:07:19Z (merge `b4ff75cb1`) — AFTER this branch was cut. It
added a "Frozen-contract gate" step to `harness-conformance.yml` that iterates
`docs/architecture/contracts/*.md` and, for each one, does this:

```bash
[ -f "libs/go/$lib/ctl.sh" ] || continue
status="$(grep -m1 '^> Status:' "$contract" | tr -d '*')"
if [[ "$status" == "> Status: Frozen"* ]]; then …
elif [[ "$status" == *[Dd]"raft"* ]] || [[ "$status" == *"DRAFT"* ]]; then
  if grep -qw "$lib" <<<"$DRAFT_REGISTER"; then … registered debt, warning …
  else
    echo "::error::contract $lib is DRAFT and not in DRAFT_REGISTER — freeze it or register it with its pending-decision citation" >&2
    exit 1
```

and `DRAFT_REGISTER=""` — **empty since 2026-08-26**, with the comment that it "MAY ONLY SHRINK".

**Merging THIS pull request alone is safe**, and the reason is the `continue` on the second line:
neither contract has a matching `libs/go/<lib>/ctl.sh` in the PINNED libs submodule today, so the
loop skips both and the lane stays green. `fleettelemetry` has no library at all.

**The red arrives later, at the POINTER BUMP.** The moment `gophersys/libs` `feat/agentprofile`
merges and eden's libs pointer moves, `libs/go/agentprofile/ctl.sh` exists, the contract is still
DRAFT, and the whole conformance lane exits 1. Two ways out, and BOTH are Mateo's §5 gate:

1. He freezes `agentprofile.md` before the pointer bump; or
2. `agentprofile` is added to `DRAFT_REGISTER` with its pending-decision citation — which the
   register's own comment calls a process change, and which sits awkwardly against "may only
   shrink".

This is stated on both pull requests and in the freeze question. It is not a reason to delay the
contract; it is a reason the ORDER matters, and the order is: contract merges → Mateo rules →
library merges → pointer bumps. Landing the pointer bump before he rules is what reds the lane.

## Deliberately NOT in this change — say it plainly, so the review is against what is true

- **Nothing is frozen.** Both documents carry `Status: **DRAFT for negotiation**`. Freezing is
  Mateo's `git-process.md` §5 gate ("a chart or contract PROMISE") and no agent exercises it. Each
  document ends with the exact question he must answer.
- **No ADR is opened.** The agentprofile boundary probably needs one — `docs/architecture/README.md`
  §1 rules that where the canonical set and the upstream corpus conflict, "this set wins and must
  record the supersession as an ADR". Opening a new or reopened ADR is also a §5 Mateo gate. The
  contract PROPOSES the ADR; it does not write it. Next free number is 0033.
- **No `.claude/` file is rendered or changed by this branch.** Rendering into `.claude/` touches a
  surface §5 names as personally gated ("process changes (this file, `.claude/`, the cictl
  contract)"). This change specifies the renderer; it does not run it against the estate.
- **No drift gate is wired.** The library's `drift` verb exists on the sibling branch; deciding
  whether the gate is a libs `phase-gate` dimension, an eden `.ci` verb, or both is freeze
  question 2. Nothing in this change makes CI fail on anything.
- **The `agentruntime` contract is NOT revised.** `fleettelemetry` maps from the sibling lane's
  `fleetenvelope` draft, whose §9 owns the `OTelContext` question on the sibling branch. Note that
  the sibling REVERSED itself there at `9fd66d9`: the typed `TraceParent`/`TraceState` fields were
  withdrawn and the `OTel` map kept, and the resulting fork was routed to this lane by name. It is
  Mateo's to freeze either way.
- **No `oteladapter` is written**, and no infrastructure manifest gains an OTLP endpoint. Both are
  named lanes in the parallelization map, and both are the reason a telemetry claim cannot be
  proven today. `fleettelemetry` states that rather than describing a pipeline that does not run.
- **The evidence set is NOT empty, and an earlier version of this bullet said it was.** ⚠️ Corrected:
  the gate that ran locally is `graph-guard` (rc=0, 49 projects, roster match, in the container);
  `affected-check` selected nothing (`NX   No tasks were run`) and that half remains a NO-OP; but
  eden HAS a `pr-review` workflow now, and PR #24 triggered `review`, `pinned-harness conformance`
  and `affected-gate (fast)`. **Each check's own log and the review VERDICT are read as their own
  tool calls before any merge is proposed** — a triggered check is not a passed check, and this lane
  banks neither a prediction nor a badge.

## Blocked

Empty.

## Next

Read the research findings, then author `agentprofile` first — the libs lane builds against it.
