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

Mateo's four design rulings, 2026-08-26, decision prompt, interactive session f9c810a8:

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
obligation has **no subject in this repository**: this change adds no executable surface, and
eden's affected gates select nothing outside an Nx project. That is STATED, never waived — no
agent may waive §4/phase 2 for itself. The executable proof of the `agentprofile` agreement is
the sibling `gophersys/libs` pull request (`feat/agentprofile`), whose conformance suite is
red-first and whose `phase-gate qa` runs in the devcontainer.

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

**`bash .ci/ctl.sh graph-guard` — rc=0, and it RAN:**

```
[info]  graph-guard: .nxignore covers all 36 required patterns
[info]  graph-guard: resolving the nx project graph
[info]  graph-guard: the graph resolves and holds 49 project(s)
[info]  graph-guard: the graph matches the roster exactly (49 project(s))
[ok]    graph-guard: OK — 49 project(s) resolved, 0 rooted in a submodule fixture tree
[info]  graph-guard: 8 project-shaped file(s) sit under a submodule fixture directory and produced no project
```

**`NX_BASE=origin/main bash .ci/ctl.sh affected-check` — rc=0, output `NX   No tasks were run`.**

That second line is a **NO-OP and is not evidence about content** (git-process §5.1). A docs-only
change selects nothing, and the structural reason is measurable: there is no `project.json`
anywhere under `docs/`, and `.ci/graph-roster.txt` carries no `docs` row. eden also has **no
`pr-review` workflow** (§7's own table). So on this pull request BOTH §5.2 conditions fire at once
and **the content-evidence set is EMPTY.** That is stated on the PR, not papered over — and it is
one of the reasons this branch is not merged by an agent.

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
  `fleetenvelope` draft. The supersession of `OTelContext` by typed `TraceParent`/`TraceState` is
  `fleetenvelope` §9's business, on the sibling branch, and is Mateo's to freeze.
- **No `oteladapter` is written**, and no infrastructure manifest gains an OTLP endpoint. Both are
  named lanes in the parallelization map, and both are the reason a telemetry claim cannot be
  proven today. `fleettelemetry` states that rather than describing a pipeline that does not run.
- **The content-evidence set on this pull request is EMPTY** and I will not call it satisfied. The
  gate that RAN is `graph-guard` (rc=0, 49 projects, roster match); `affected-check` selected
  nothing (`NX   No tasks were run`), and eden has no `pr-review` workflow. Under §5.2 that means a
  named human read is the only evidence available here.

## Blocked

Empty.

## Next

Read the research findings, then author `agentprofile` first — the libs lane builds against it.
