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

(to be written after research lands)

## Proven

(populated only with commands run and output read)

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

## Blocked

Empty.

## Next

Read the research findings, then author `agentprofile` first — the libs lane builds against it.
