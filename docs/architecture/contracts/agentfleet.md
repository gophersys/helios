# Contract — agentfleet

> Status: **DRAFT for negotiation** · 2026-08-26 · The kubernetes control surface of the Eden
> agent fleet: two custom resource kinds, one controller, and the reconcile loop that turns a
> declared agent into a running pod with a durable identity.
> This is the 09 §4 step-1/2 artifact for the fleet's CRD leg, reconciled into one document, with
> the unresolved tensions recorded as open forks (§12) rather than settled silently. **It is NOT
> frozen, and no agent may freeze it** — the freeze is Mateo's `.claude/rules/git-process.md` §5
> gate ("a chart or contract PROMISE"), exercised only under §13 rule 4 with his verbatim words
> and a timestamp. §13 is the exact question he must answer. Until he answers it,
> `libs/go/_ctl/lib.sh::_gate_contract_frozen` correctly fails this document, **by design**.
>
> **Authority to design this now.** `docs/plans/eden-rework-blueprint.md:1918` defers the fleet
> leg with the trigger *"Mateo schedules the fleet program"* and states in the same cell:
> *"The architecture is already decided (agent-fleet rulings, 2026-08-18: role-pods, JetStream
> planes, frozen envelope, CRD controller); what is deferred is building it, not designing it."*
> The trigger fired on 2026-08-26, verbatim: *"we can kick off a lot of these things in parallel
> if we do api agreements up front."*
>
> **⚠️ READ §10.1 BEFORE ANY IMPLEMENTATION SLICE.** A precondition of this whole design is
> unproven and outranks it: nobody has executed a real `Spawn` against the deployed
> orchestrator. If the answer is that neither the gateway nor the orchestrator has ever run a
> harness end to end, that finding is larger than this contract and must reach Mateo first.
>
> Epistemic legend (`docs/architecture/README.md` §3): ✅ verified · 🔶 hypothesis · ⚠️ corrected
> · 🧩 design choice. Every ✅ carries a `file:line` or a quoted ruling. **A claim with neither is
> a PROPOSAL and is marked as one.**

---

## 1. Scope

### 1.1 The naming correction — this document wins over the brief

⚠️ **The task brief asked for an "agentpod CRD" contract. There is no `AgentPod` kind.** The
locked design of 2026-08-18 has exactly **two** kinds in group `fleet.eden.gophersys.com`,
version `v1alpha1`: **`Agent`** and **`AgentTeam`**. A third kind, `AgentTemplate`, was
explicitly REFUSED — *"a fourth home for a value that already has three"* — and this document
does not resurrect it. **The document is named for what exists (`agentfleet`), and where the
brief and this document disagree on a name, this document is the authority.**

🧩 Two consequences to carry forward, both mechanical:

- The library/contract name is **`agentfleet`**, not `agentpod`. `contracts/fleetenvelope.md`
  refers to the owner of pod lifecycle and the CRD as **`agentpod`** in four places (✅ its §1
  bullet 2 of the does-not-own list, its `ActorController` comment, and §6). Those are stale
  cross-references to a name that was never created. Fixing them is a one-line edit in that
  document, in whichever change lands second — recorded as fork **F10** so neither lane assumes
  the other did it.
- No manifest, no Go type, no subject token and no label anywhere in this contract contains the
  token `agentpod` or `AgentPod`.

### 1.2 What `agentfleet` owns

`agentfleet` is the **one home of the fleet's declarative control surface**: what an operator or
a parent agent WRITES to make an agent exist, and what the controller WRITES BACK about it. It
owns exactly six things:

1. **The two custom resource kinds** — `Agent` (one pod, one role, 1..N harness sessions) and
   `AgentTeam` (one lead plus its members, one budget scope, one connector scope). §2.
2. **Fleet identity minting** — `status.agentID` and the `metadata.uid` witness. It is the ONE
   minting authority for `AgentID`; every other library validates the shape and mints nothing
   (✅ `contracts/fleetenvelope.md` §6: *"this library validates the shape and never mints one,
   so there is exactly one minting authority"*). §3.
3. **The pod lifecycle state machine** — the eight phases, their legal transitions, and the
   mapping of the five frozen lifecycle verbs onto CR patches rather than onto new API. §4.
4. **The 12-step reconcile loop** — the concrete controller-runtime binding of the frozen
   `orchestrator.Reconciler` semantics. §5.
5. **Admission** — the one place a `MaxConcurrent` ceiling, a team concurrency ceiling, a team
   budget, a `hostToolSet` name and a widening override are refused **before any pod exists**.
   §8.
6. **The REFUSALS** — the closure guard, the split-brain guard, the uid witness, the unknown
   `hostToolSet`. Each is a LOUD typed failure naming the offending value. §11.

### 1.3 What `agentfleet` does NOT own

The consumer must not expect these here.

- **The wire header, identity TYPES, routing, causality, payload discipline** — `fleetenvelope`
  owns them. This contract mints an `AgentID` value and stamps it into a status field; it never
  defines `AgentID`, `MessageID`, `Actor`, `Intent` or `TreeAddress`, and it never renders a
  message.
- **Subjects, streams, consumers, acknowledgement, dedup, backpressure** — `fleetbus` owns the
  transport. Step 5 of the loop *ensures streams match a policy*; it does not define what a
  stream is.
- **Checkpoint composition, segment format, the archive layout** — `fleetcheckpoint` owns those.
  This contract carries two cursors in status (`lastStreamSeq`, `lastCheckpointTurn`) and one
  tombstone (`deleted.json`); it does not compose a checkpoint.
- **The harness Event taxonomy, the agent loop, the permission round-trip** — `agentsession` is
  frozen and owns them. This contract carries `agentsession.RouteKey`, `agentsession.ToolGrant`
  and `agentsession.Budget` verbatim as CR fields and re-taxonomizes nothing.
- **The five orchestrator ports' SEMANTICS** — `contracts/orchestrator.md` is frozen and owns
  them. This contract IMPLEMENTS four of them and REUSES a fifth (§6). **It changes none.**
- **Workspace provisioning mechanism** — `workspaceprovider` owns the kubernetes pod builder.
  Step 7 calls it so the estate keeps ONE pod builder; it does not build a pod itself.
- **Credential storage or minting** — `secrets` + Vault own them. Every credential in §2 is an
  OPAQUE reference string. **No field of any type in this contract may hold a secret value.**
- **NetworkPolicy, ResourceQuota, LimitRange, PriorityClass objects** — the `infrastructure`
  repository owns them. §8 and §10 state the SHAPE this contract depends on and the derivation
  of every number; the manifests land there, not here.
- **The instrumentation profile schema and its renderer** — a live parallel lane owns those
  (`~/code/.worktrees/eden-instrumentation-contracts`). §7 states only the SEAM this contract
  needs. That worktree was deliberately not read.

It **cites, never redefines**: `fleetenvelope.AgentID` / `MessageID` / `SessionID` / `Actor` /
`ActorKind` / `Intent` / `ControlVerb` / `MaxHops` (`contracts/fleetenvelope.md` §2),
`agentsession.RouteKey` / `ToolGrant` / `Budget` / `Spec` / `State` / `PermissionResolution`
(`contracts/agentsession.md`), `orchestrator.Tenancy` / `Status` / `Manager` / `Probe` /
`DesiredStore` / `Watcher` / `Reconciler` / `TemplateStore` / `Telemetry` / `TemplateRef` /
`InvalidRequestError` (`contracts/orchestrator.md` §2, frozen),
`workspaceprovider.Provider` / `Handle` (`contracts/workspaceprovider.md`, frozen),
`objectstorage.ObjectRef` (`contracts/objectstorage.md`, frozen), and
`errors.Kind` / `errors.AsType` (`contracts/errors.md`, frozen).

---

## 2. Contract

### 2.1 Group, version, scope

| property | value | source |
| --- | --- | --- |
| group | `fleet.eden.gophersys.com` | 2026-08-18 synthesis ✅ |
| version | `v1alpha1`, marked `+kubebuilder:storageversion` | 2026-08-18 synthesis ✅ |
| scope | `Namespaced` | 2026-08-18 synthesis ✅ |
| namespace | `eden` | ✅ `infrastructure/apps/eden/00-namespace.yaml`; the release target of ADR-0028 |
| kinds | `Agent` (shortName `ag`), `AgentTeam` (shortName `agt`) | 2026-08-18 synthesis ✅ |
| finalizer | `fleet.eden.gophersys.com/archive-then-delete` | 2026-08-18 synthesis ✅ |
| `Agent` printcolumns | `PHASE` · `ROLE` · `TURN` · `COST` · `LAST-CHECKPOINT` · `AGE` | 2026-08-18 synthesis ✅ |

Labels the controller applies to every owned object:

| label | value | why it exists |
| --- | --- | --- |
| `fleet.eden.gophersys.com/team` | the `AgentTeam` name | subtree selection, budget rollup |
| `fleet.eden.gophersys.com/role` | `spec.role` | role-pod selection; the operator's first filter |
| `fleet.eden.gophersys.com/agent` | `"true"` | **the NetworkPolicy `podSelector`** — §10.2 |

**HNS-1 applies to every field name.** Full words: `configuration`, not `config`; `repository`,
not `repo`; `credentialReference`, not `credRef`; `dependencies`, not `deps`. There is no
`cfg`, no `env`, no `util`, no `common`, no `core` anywhere in this surface.

### 2.2 `Agent.spec`

```yaml
# Agent — ONE pod, ONE role, 1..N harness sessions inside it.
# Every field below is DESIRED state written by an operator, a parent agent, or the AgentTeam
# controller. Nothing here is observed; observation lives in status (§2.3).
apiVersion: fleet.eden.gophersys.com/v1alpha1
kind: Agent
metadata:
  name: supervisor-linkbox            # OPERATOR-AUTHORED. NOT the identity — see §3.
  namespace: eden
  labels:
    fleet.eden.gophersys.com/team: linkbox-build
    fleet.eden.gophersys.com/role: supervisor
    fleet.eden.gophersys.com/agent: "true"
  finalizers:
    - fleet.eden.gophersys.com/archive-then-delete
spec:
  # ── lifecycle ──────────────────────────────────────────────────────────────
  desiredPhase: Running      # Running | Stopped — the ONE field the five lifecycle verbs write (§4.3)

  # ── placement in the fleet ─────────────────────────────────────────────────
  role: supervisor           # -> EDEN_ROLE; the entrypoint mode. A pod runs exactly ONE role.
  parentRef: ""              # THE TREE EDGE. "" == root (parent == the orchestrator).
  teamRef: linkbox-build     # AgentTeam; connector + budget scope
  tenant:                    # orchestrator.Tenancy, VERBATIM — cited, never redefined
    organizationId: gophersys
    projectId: linkbox
  runId: ""                  # engine Run correlation; "" for a chat session

  # ── the ceiling ────────────────────────────────────────────────────────────
  templateRef:               # THE CEILING — every field below may only TIGHTEN it, never widen
    name: supervisor
    version: 1.4.0
  # profileRef: see §7 — a NEW consequence of Mateo's 2026-08-26 instrumentation ruling,
  # layered onto this 2026-08-18 design. Its relationship to templateRef is OPEN (fork F4).

  # ── the sessions ───────────────────────────────────────────────────────────
  sessions:                  # 1..N harness sessions in ONE pod. MinItems 1.
    - name: main             # ^[a-z][a-z0-9-]{1,61}[a-z0-9]$ — STABLE across restarts;
                             # it is also the peerplane address, so renaming it is a new peer.
      routing:               # FROZEN agentsession.RouteKey — cited, never redefined
        phase: implement
        role: supervisor
      harness: claude-code   # claude-code | omp | codex
      workspace:
        repository: https://github.com/gophersys/linkbox.git
        reference: main
        credentialReference: vault://eden/production#github-clone   # OPAQUE
        worktree: true
        # The PATH is NOT carried. It is DERIVED as /state/<name>/workspace (§6.4).
      grants: []                                   # []agentsession.ToolGrant — already DATA
      hostToolSet: supervisor-project-tools        # a NAME into a COMPILE-TIME registry (§6.4)
      permissionResolution: chat-human-then-advisor
      permissionTimeout: 120s
      budget:                                      # agentsession.Budget — the LEAD enforces it at RUNTIME
        maxCostMicros: 2000000
        maxTurns: 400
        maxWall: 4h
      systemHints: ""
      credentialReference: vault://eden/production#anthropic-api-key   # OPAQUE. NEVER a value.
      initialPrompt: ""      # "" == wait for a relay message
      resumeFrom: latest     # latest | none | <checkpoint turn id>

  # ── placement, drain, retention, rewind ────────────────────────────────────
  placement:
    excludeNodes: [k3s-w-0, k3s-w-1, k3s-w-4]   # controller-DEFAULTED, operator-overridable (§8.3)
  drainTimeout: 120s
  retentionDays: null        # null == the fleet default (the controller ConfigMap). Fork F8.
  recoverFrom: ""            # pin an OLDER checkpoint = a DELIBERATE REWIND (§3.4, §5 step 10)
```

#### The load-bearing fields, and why each is shaped this way

**`desiredPhase` is the only lifecycle write.** ✅ It is the CR expression of the frozen
`orchestrator.Desired` type, which the shipped library already models as a closed two-member set
separate from observed `Status` (✅ `libs/go/orchestrator/types.go`, `Desired` — *"Spawn records
DesiredRunning; Stop records DesiredStopped. It is separate from Status (the observed actual) —
the diff between Desired and Status is what each reconcile pass closes by one step"*). Five verbs
collapsing onto one field is what keeps the API surface at zero new endpoints (§4.3).

**`parentRef` is the tree edge, and `""` means root.** 🧩 The alternative — a `depth` field, or a
`TreeAddress` string in spec — was rejected: an address is DERIVED from the parent chain, so
storing it in spec creates a second home for a value the chain already determines, and an
operator editing it would silently re-parent an agent without moving it. `status.depth` on the
`AgentTeam` is OBSERVED for the UI and is **never a wire field** (§2.4).

**`templateRef` is the ceiling; the spec below it is the floor.** ✅ This is the frozen
orchestrator rule restated at the CR layer (`contracts/orchestrator.md` §1 duty 1: *"The template
is the ceiling; a spawn may only tighten"*; `Manager.Spawn` returns `InvalidRequestError` *"for a
malformed request or a widening override"* — ✅ `libs/go/orchestrator/ports.go`, `Spawn` doc
comment). Admission (§8.1) enforces it, not the pod.

**`sessions` is a list because a pod is a role, not a session.** 🧩 One pod hosting 1..N harness
sessions is the 2026-08-18 role-pod decision. `name` is the stability anchor: it survives a
restart, it addresses the peerplane, and it derives the state root and the workspace path. The
regular expression `^[a-z][a-z0-9-]{1,61}[a-z0-9]$` makes a session name a legal DNS-1123 label,
so it can also be a path element and a subject-adjacent token without a second escaping rule.

**`credentialReference` is opaque, at both levels.** ✅ The frozen discipline, restated:
*"No secret value ever enters a `SpawnRequest`, an `Agent`, an `ObservabilityEvent`, the desired
store, an error, or a log"* (`contracts/orchestrator.md` §1). A CR is a kubernetes object readable
by anything with `get agents` — the reference form is not a convenience, it is the only safe form.

**`resumeFrom: latest | none | <checkpoint turn id>` is per-session**, because two sessions in one
pod restart independently. `latest` is the ordinary restart; `none` starts a session clean;
a pinned turn id is a rewind for that session only.

**`recoverFrom` is a POD-level rewind and is deliberately separate from `resumeFrom`.** §3.4
states its identity consequences.

#### Two absences that are decisions, not omissions

**⚠️ Identity is deliberately ABSENT from spec.** There is no `spec.agentID`. The controller mints
it into `status.agentID` (§3). An operator cannot write it, a GitOps re-apply cannot restore it,
and a template cannot default it. That is the whole point of §3.

**⚠️ `Spec.OnPermission` STAYS NIL FOREVER, and there is no CR field for it.**

- ✅ The mechanism: `libs/go/agentsession/pump.go:348-357`, `permissionArm` branches
  `case s.spec.toolGranted(...)` → `case s.spec.OnPermission != nil:` (**line 352**) →
  `case s.spec.PermissionResolution == ResolveAutonomousAdvisor:` (**line 354**) → `default:
  permissionArmHuman`. **`OnPermission` is tested BEFORE `PermissionResolution`.** A second
  precedence site confirms it at `pump.go:423-424`. The documented statement of the same
  precedence is `pump.go:278`.
- Therefore setting `OnPermission` non-nil **short-circuits the chat-human chain** and disables
  the very path obligation **O10** exists to prove.
- ⚠️ **Anchor correction.** The brief cited `pump.go:291`. Line 291 is
  `if raw.Permission == nil {`, the nil guard inside `handlePermissionRequest`. The CLAIM is
  correct; the anchor is `pump.go:352-354`. Recorded so no lane break-tests the wrong line.
- 🧩 Consequence for the CR: `permissionResolution` is a CR field; `OnPermission` is a Go closure
  and is one of the three closures the CLOSURE GUARD refuses outright (§11 O14).

**⚠️ No free-form `Spec.Env map[string]string`.** The per-session harness state root is ONE TYPED
field, `agentsession.Spec.StateRoot string`.

> 🔶 **PROPOSAL, not current state.** `git grep StateRoot origin/main -- go/agentsession` over
> `gophersys/libs` returns **zero hits**. `agentsession.Spec.StateRoot` does not exist today; it
> is a new typed field this contract asks `agentsession` to add. Since `agentsession` is frozen,
> adding it is an additive struct field on an open struct — the same apidiff-additive move
> `SandboxSpec.Entrypoint` already used (✅ `contracts/orchestrator.md` §2: *"B4 additive — a new
> field on the open SandboxSpec struct, apidiff-additive, invisible to the `.apibaseline`'s
> collapse, so NO baseline change"*). It still needs `agentsession`'s owner to accept it.

The reason a map is refused: a map cannot be validated, it admits a second home for values that
already have typed fields, and it lets an operator smuggle an arbitrary key — including a
credential — onto an object anything with `get agents` can read.

### 2.3 `Agent.status` — a subresource

```yaml
status:
  # ── identity (§3) ──────────────────────────────────────────────────────────
  agentID: agent-01jbq7c4v8zk3h2m9xpwq6rtnd   # THE IDENTITY AUTHORITY. Minted once, before any pod.
  agentUID: 3f5a91c2-7d04-4c1e-9b6a-2e8f0d41ab77   # THE UNIQUENESS WITNESS (metadata.uid at minting)

  # ── observed lifecycle ─────────────────────────────────────────────────────
  phase: Running    # Pending|Provisioning|Running|Suspended|Resuming|Stopping|Stopped|Failed
                    # — orchestrator.Status tokens VERBATIM, so Probe/DesiredStore need NO mapping table
  podName: supervisor-linkbox-01jbq7c4
  configMapName: supervisor-linkbox-configuration
  observedGeneration: 7

  # ── the sessions, observed ─────────────────────────────────────────────────
  sessions:
    - name: main
      sessionID: session-claude-code-supervisor-implement-9f3a1c0e   # agentsession-minted
      harnessResumeID: 0f2b...                                       # harness-native, OPAQUE
      state: Running          # agentsession.State, verbatim
      turn: 118
      lastSeq: 918233
      lastCheckpointTurn: 117

  # ── the two cursors ────────────────────────────────────────────────────────
  lastStreamSeq: 918233     # the JETSTREAM cursor — the history<->live STITCH
  lastInboxSeq: 41          # last CONSUMED inbox stream sequence

  # ── the ledger ─────────────────────────────────────────────────────────────
  ledger:
    costMicros: 1443902
    inputTokens: 8812340
    outputTokens: 402118

  # ── liveness and retention ─────────────────────────────────────────────────
  lastHeartbeat: 2026-08-26T19:04:11Z
  retainUntil: 2026-09-25T19:04:11Z   # set BY THE FINALIZER, read BY THE PRUNER (§5 steps 1, REAP)

  # ── the closed condition set (§2.3.1) ──────────────────────────────────────
  conditions:
    - type: Admitted
      status: "True"
      reason: WithinConcurrency
      lastTransitionTime: 2026-08-26T18:02:00Z
  detail: ""   # REDACTED. Never a credential. (orchestrator.Agent.Detail discipline, verbatim.)
```

**`phase` reuses `orchestrator.Status` tokens verbatim, and that is load-bearing.** ✅ The shipped
`orchestrator.Status` has exactly these eight members in this order
(`libs/go/orchestrator/types.go`, `Status` and `statusTokens`; `contracts/orchestrator.md` §2
section 4). Reusing the tokens means the CRD-backed `Probe` and `DesiredStore` bindings (§6) need
**no mapping table**, and a mapping table is where a token silently becomes a different token.

**`lastStreamSeq` is the stitch, and it is why it lives in status rather than in a checkpoint.**
A consumer replaying history from the object store and then attaching to the live stream needs
one number to know where history ends. Status is the object every consumer can already read
without an object-store credential.

**`retainUntil` is written by the finalizer and read by the pruner.** The two never run in the
same pass and never in the same cadence (§5 step 1 and REAP). Writing it at finalize time — not
at delete time — is what makes deletion fast while keeping retention honest.

#### 2.3.1 The condition types — and the discrepancy on the closed set

The NINE condition types this contract names:

| # | type | True means |
| --- | --- | --- |
| 1 | `Admitted` | passed every §8.1 admission check |
| 2 | `PodReady` | the pod exists and reports Ready |
| 3 | `StreamsReady` | the agent's streams exist and match the ConfigMap policy |
| 4 | `SessionLive` | at least one session is in a non-terminal `agentsession.State` |
| 5 | `CheckpointHealthy` | the last checkpoint turn is within the expected lag |
| 6 | `ArchiveReachable` | the object-store bucket + agent prefix are reachable |
| 7 | `CredentialAvailable` | every `credentialReference` resolved |
| 8 | `BudgetExhausted` | the library hard-stopped spend (True is the ALARM, not the health) |
| 9 | `Archived` | the tombstone is written; the finalizer may be removed |

⚠️ **The set is NOT closed yet, and this document does not close it.** The 2026-08-18 design's
prose also contains **`BusAttached`** as a condition type and **`CredentialUnavailable`** as a
reason token. `CredentialUnavailable` reconciles cleanly: step 11 (§5) uses it as the REASON on a
`CredentialAvailable=False` condition, so it is not a tenth type. `BusAttached` does not
reconcile: it is either a duplicate of `StreamsReady` or a distinct fact (the NATS connection is
up, but the streams are not yet ensured). **Recorded as fork F3 — do not treat the nine as
closed.**

### 2.4 `AgentTeam`

```yaml
apiVersion: fleet.eden.gophersys.com/v1alpha1
kind: AgentTeam
metadata:
  name: linkbox-build
  namespace: eden
spec:
  parentRef: ""                        # "" == the orchestrator is the parent
  lead:                                # a SessionSpec — the same shape as Agent.spec.sessions[]
    name: lead
    routing: {phase: implement, role: supervisor}
    harness: claude-code
    hostToolSet: supervisor-project-tools
    permissionResolution: chat-human-then-advisor
    permissionTimeout: 120s
    budget: {maxCostMicros: 2000000, maxTurns: 400, maxWall: 4h}
    credentialReference: vault://eden/production#anthropic-api-key
  members:
    - role: implementer
      templateRef: {name: implementer-go, version: 2.1.0}
      replicas: 3
      session: {name: main, harness: claude-code, routing: {phase: implement, role: implementer}}
    - role: verifier
      templateRef: {name: verifier, version: 1.0.2}
      replicas: 1
      session: {name: main, harness: claude-code, routing: {phase: verify, role: verifier}}
  connectorScope:                      # ⚠️ GATED — see §10.3. An EXTENSION of ADR-0029, not a reading of it.
    organizationRef: gophersys
    teamOverrides:
      - name: github
        reference: eden://connector/gh-linkbox-bot
  budget: {maxCostMicros: 40000000, maxWall: 12h}   # enforced by the LEAD at RUNTIME
  maxConcurrentAgents: 6               # ⚠️ OPEN — fork F1. Do not treat 6 as decided.
  sessionsPerAgent: 2                  # controller-enforced MAXIMUM 3
  maxHop: 32                           # == fleetenvelope.MaxHops (✅ contracts/fleetenvelope.md §2)
  retentionDays: 30                    # precedence vs Agent.retentionDays is OPEN — fork F8
  policy:
    steerDefault: steer-at-safe-point  # == fleetenvelope.IntentSteerAtSafePoint
    relayJudgement: [assign, question] # which Intents demand a MODEL turn AT THIS LEVEL
status:
  members:
    - role: implementer
      ready: 3
      desired: 3
  depth: 2                             # OBSERVED, FOR THE UI. **NEVER a wire field.**
  activeAgents: 4
  budgetSpentMicros: 18220410
  conditions:
    - {type: RootReady, status: "True"}
    - {type: WithinBudget, status: "True"}
    - {type: WithinConcurrency, status: "True"}
```

**Members are reconciled into `Agent` CRs carrying `ownerReferences` to the `AgentTeam`.**
Deleting the team therefore garbage-collects the subtree through kubernetes' own owner-reference
machinery, and each child `Agent`'s finalizer still archives it. This is the only subtree-delete
mechanism; there is no cascade verb.

**The budget split is explicit, and it is not a redundancy.**

| enforcer | what | when | failure mode |
| --- | --- | --- | --- |
| the LEAD (the library, in-pod) | `spec.budget` | at RUNTIME, per turn | hard-stop, then emit `IntentBudgetExhausted` **UP**; **the PARENT decides** (kill / extend / re-scope) |
| the CONTROLLER | `spec.maxConcurrentAgents` | at ADMISSION, **before any pod exists** | a status condition, never a created pod |

✅ The controller half is the frozen fail-cheap rule verbatim: *"`MaxConcurrent` per
`(Tenant, Template)` class is checked at `Spawn` admission, before a workspace is ever
provisioned (fail cheap …)"* (`contracts/orchestrator.md` §1 duty 3). The lead half is the frozen
single-budget-authority rule: *"Per-session budget is not double-enforced"* (same section), with
`IntentBudgetExhausted` already a member of the fleet `Intent` taxonomy — ✅
`contracts/fleetenvelope.md` §2: *"the library hard-stopped spend; the PARENT decides (kill /
extend / re-scope)"*. **The controller does not enforce cost. The lead does not enforce
concurrency.** Two enforcers, two disjoint quantities, two different times.

**`relayJudgement` is the cost lever.** It names which `Intent` values demand a MODEL turn at this
level; everything else relays at Go speed through `fleetenvelope.Factory.Relay`. A team that lists
every Intent pays a model turn per hop.

**`connectorScope` is an EXTENSION of ADR-0029, never a reading of it.** ⚠️ ADR-0029 is
per-user and per-organization and contains **zero** occurrences of the word "team". Nothing in
this contract may be presented as ADR-0029 already permitting a team scope. And it is **GATED**
behind the connectors path first being proven to have a consumer at all — §10.3.

### 2.5 The Go types the controller exposes

**None on any existing libs surface.** ✅ The orchestrator `.apibaseline` delta is **ZERO**
(§6). The kubebuilder API types (`Agent`, `AgentSpec`, `AgentStatus`, `AgentTeam`, …) live in a
new module and are consumed by the controller and by generated clients, not by a libs consumer.

🔶 **PROPOSED, not decided:** the module path `apps/fleet-controller/api/v1alpha1`, mirroring the
existing `apps/agent-runtime` and `apps/agentgateway` shape (✅ both exist in the eden tree). It is
a proposal because no ruling names a location. Fork **F9**.

The four adapter bindings the controller supplies to the frozen orchestrator ports (§6) are
internal to that module and are **not** a second public surface.

---

## 3. Identity and the uid witness

### 3.1 The form, and why this exact form

✅ `AgentID = "agent-" + <lowercase ULID>` — 6 + 26 = **32 characters**, legal AT ONCE as:

| use | constraint | headroom |
| --- | --- | --- |
| a DNS-1123 label (pod name prefix) | ≤ 63 chars, `[a-z0-9-]`, starts alphanumeric | 31 chars spare |
| a NATS subject token | no `.`, no `*`, no `>`, no space | satisfied |
| an S3 key prefix | no `/`, no `..`, no leading slash | satisfied by construction |

One string satisfying three namespaces is the whole reason the form is fixed rather than
convenient. ✅ `contracts/fleetenvelope.md` §2: *"It names the pod, the object-store prefix and
the NATS subject token, and it SURVIVES a restart (canon ruling C4)."*

⚠️ **A cross-contract seam to close.** `contracts/fleetenvelope.md` §6 says `Validate` enforces
*"the prefix and the 26-character Crockford-base32 body"* and does **not** state a case rule.
Canonical ULID text is conventionally UPPERCASE; DNS-1123 forbids uppercase. **Either
`fleetenvelope.Validate` enforces lowercase, or this contract's DNS-1123 guarantee is not
enforced anywhere.** Recorded as fork **F7**; it is a one-line change in `fleetenvelope` and it
must be made in one of the two documents, not neither.

### 3.2 Minted ONCE, by the controller, before any pod exists

The minting happens at **step 3** of the reconcile loop (§5) and the step **RETURNS** — nothing
else may happen in that pass. Identity precedes every side effect: no pod, no ConfigMap, no
stream, no bucket prefix, no message.

✅ There is exactly one minting authority. Every other library validates the shape:
`contracts/fleetenvelope.md` §2 — *"It is minted by the agentpod controller, never by an agent
and never by this library."* (That sentence's `agentpod` is the stale name from §1.1.)

### 3.3 The `metadata.uid` witness — the refusal that makes the id durable

**Mechanism.** At minting, the controller records the live `metadata.uid` into `status.agentUID`.
On every subsequent pass, **if the live `metadata.uid` differs from `status.agentUID`, the
controller REFUSES the object** — it sets `Admitted=False` with a reason naming both uids, creates
nothing, and does not re-mint.

**Why a CRD validation pattern is not enough.** `metadata.name` is operator-authored. A
`+kubebuilder:validation:Pattern` can enforce the SHAPE of a name, but it can never enforce that a
ULID suffix is **FRESH**. So this sequence is legal under any pattern:

```
kubectl delete agent supervisor-linkbox        # the object goes; the checked-in CR does not
git-ops re-apply                               # the SAME CR file returns, same metadata.name
```

and if the id were derived from the name, or restored from the checked-in file, the re-applied
object would **reuse the AgentID and mix two agents' histories on one NATS subject and one
object-store prefix**. That is not a corrupted record; it is two agents' transcripts interleaved
under one identity, indistinguishable after the fact. The uid witness is the only thing that sees
it, because `metadata.uid` is server-generated and cannot be re-applied.

### 3.4 Three distinct identifiers — never conflated

| id | minted by | form | cardinality | where it appears |
| --- | --- | --- | --- | --- |
| **`AgentID`** | THIS controller, step 3 | `agent-<lowercase ulid>`, 32 ch | 1 per `Agent` | subject token · pod name · object-store prefix · `status.agentID` |
| **`SessionID`** | the LIBRARY, ✅ `libs/go/agentsession/identifiers.go:31-41` (`func sessionID`) | `session-<harness>[-role][-phase]-<hex8>` | **1..N per agent** | a FIELD on the message. **NEVER a subject token.** |
| **`HarnessResumeID`** | the harness | opaque, harness-native | 1 per session incarnation | what `--resume` is given. Nothing else reads it. |

✅ The shape is exactly what the shipped code builds:
`"session-" + route.Harness [+ "-" + Routing.Role] [+ "-" + Routing.Phase] + "-" + randomSuffix()`,
with `randomSuffix()` returning 8 hex characters (`identifiers.go:44-51`).

**⚠️ THREE THINGS ARE DELETED BY THIS CONTRACT.**

1. ✅ **The `agent-<n>` in-memory counter** — `libs/go/orchestrator/manager.go:262-265`:
   ```go
   func (p *Pool) newAgentID() AgentID {
       return AgentID("agent-" + strconv.FormatUint(p.idSeq, 10))
   }
   ```
   A process-local monotonic counter cannot survive a restart and collides across replicas.
   Canon ruling C4 (2026-08-18): *"the in-memory `agent-<n>` counter dies."*
2. ✅ **The false doc comment at `libs/go/orchestrator/types.go:251`** —
   `ID       AgentID     // stable handle (== agentsession SessionID once running)`.
   **No code enforces that equality**, and this contract makes it false by construction: one agent
   has 1..N session ids.
3. ✅ **The false doc comment at `apps/agentgateway/internal/gateway/registry.go:11-21`** —
   *"The agentsession SessionID and the orchestrator AgentID are the same join key by contract
   (orchestrator.AgentID 'equals the agentsession SessionID once the session is open')"*. Same
   false equality, asserted a second time, in a second repository layer. ✅ The shipped
   `reconcile.go:159-168` shows how it is currently satisfied — the record stores the AgentID AS
   the SessionRef — which is exactly the conflation being removed.

**`recoverFrom` semantics, stated so nothing hides.** Pinning an older checkpoint keeps the **SAME
`AgentID`**, mints a **NEW `SessionID`**, and **that session's `Seq` restarts at 1**. The restart
is legal because `MessageID` is the `agent/session/seq` composite, so a fresh session's `Seq 1`
can never collide with the prior session's. **An `IntentLifecycle` envelope records the
discontinuity rather than hiding it** — a reader replaying the agent's history sees a marked
rewind, not a silently non-monotonic sequence.

> 🔶 `IntentLifecycle` is not among the five `Intent` members frozen in
> `contracts/fleetenvelope.md` §2 (`IntentDelegate`, `IntentReport`, `IntentSteerAtSafePoint`,
> `IntentSteerPreemptive`, `IntentBudgetExhausted`), and that document's fork **F3** asks
> whether `Intent` is closed at five. **This contract requires a sixth member or an equivalent
> lifecycle-marker mechanism.** Stated as a demand on `fleetenvelope`, not as a fact about it.

### 3.5 The env seam — the mechanical cause of `EDEN_AGENT_ID` being unset

**The defect, measured.** ✅ The pod consumer exists and is strict:

```go
// apps/agent-runtime/internal/composition/composition.go:59
AgentID: os.Getenv("EDEN_AGENT_ID"),
// apps/agent-runtime/internal/composition/composition.go:113-116
if environment.AgentID == "" {
    logger.Error("agent-runtime: EDEN_AGENT_ID is required")
    return 2
}
```

⚠️ **The producer does not exist.** `git grep EDEN_AGENT_ID origin/main` over the whole of
`gophersys/libs` returns **ZERO hits**. `libs/go/orchestrator/fold.go` folds only
`template.Sandbox.Env` (`fold.go:42-54`, via `envToProvider` at `fold.go:121-129`) plus three
workdir-clone keys — `EnvWorkdirRepo` / `EnvWorkdirRepoRef` / `EnvWorkdirRepoCredential`
(`fold.go:171-176`). **Nothing in the orchestrator sets `EDEN_AGENT_ID`.** That absence IS the
mechanical cause of the pod exiting 2, and it is why the fix belongs in this contract.

⚠️ **Anchor correction.** The brief stated `orchestrator.EnvAgentID = "EDEN_AGENT_ID"` as an
existing const folded unconditionally in `fold.go`. It does not exist. It is the FIX. Marked 🔶
throughout.

**The two paths, and the cross-check that binds them:**

| path | who sets `EDEN_AGENT_ID` |
| --- | --- |
| CRD path | the controller builds the pod (through `workspaceprovider`, §5 step 7) and sets it from `status.agentID` |
| orchestrator path | 🔶 a new `orchestrator.EnvAgentID = "EDEN_AGENT_ID"` const, folded **UNCONDITIONALLY** in `fold.go` — the same additive shape as `EnvWorkdirRepo` |

**CROSS-CHECK, and it is the obligation that makes the seam provable.** The controller also writes
`EDEN_POD_NAME` from the downward API, and **the pod asserts the two agree at boot — a mismatch
is exit 2 naming BOTH values.** One of them travels through the folded env; the other travels
through the kubelet. If they disagree, one of the two paths lied, and the pod says which.

**⚠️ The downward API is REFUSED as the SOLE source.** It exists only under kubernetes, so making
it the source would fork identity per substrate — one identity rule for kubernetes, another for
docker, and `contracts/orchestrator.md` §1 explicitly keeps both substrates on one contract
(`SubstrateKubernetes` | `SubstrateDocker`). The downward API is the WITNESS, never the SOURCE.

🧩 **Precision on "the controller builds the pod".** It does not build a pod object directly; it
calls `workspaceprovider.Provider.Provision`, so the estate keeps ONE kubernetes pod builder
(§5 step 7). The env therefore travels as `workspaceprovider.WorkspaceSpec` env vars — the shape
`fold.go:121-129` already produces. "The controller sets `EDEN_AGENT_ID`" means "the controller
puts it in the spec it hands the provider", and any lane reading it as "the controller writes a
`corev1.Pod`" would build a second pod builder.

---

## 4. The lifecycle state machine

### 4.1 The eight phases

✅ Verbatim `orchestrator.Status` tokens (`libs/go/orchestrator/types.go`,
`contracts/orchestrator.md` §2 section 4). Terminal: `Stopped`, `Failed`.

### 4.2 Legal transitions

```
                    ┌──────────── a fault, from ANY non-terminal ──────────┐
                    │                                                      ▼
  (create) ──▶ Pending ──▶ Provisioning ──▶ Running ──▶ Stopping ──▶ Stopped   Failed
                                              │  ▲                    ▲       (TERMINAL)
                                              │  │                    │
                                              ▼  │                    │
                                        Suspended │                   │
                                              │  │                    │
                                              ▼  │                    │
                                          Resuming ┘                  │
                                                                      │
   any non-terminal ─────────── a Stop (desiredPhase: Stopped) ───────┘
```

| edge | trigger | loop step (§5) |
| --- | --- | --- |
| create → `Pending` | the CR exists, identity minted, admitted | 3, 4 |
| `Pending` → `Provisioning` | `desiredPhase: Running`, no pod | 7 |
| `Provisioning` → `Running` | pod Ready **and** heartbeat observed | 12 |
| `Running` → `Suspended` | credential unresolvable (Vault sealed) | **11** |
| `Suspended` → `Resuming` | the credential resolves again | 11 → 7 |
| `Resuming` → `Running` | the session re-attaches at `resumeFrom` | 12 |
| `Running` → `Stopping` | `desiredPhase: Stopped` | 9 |
| `Stopping` → `Stopped` | drain completed, **or** `drainTimeout` elapsed | 9 |
| any non-terminal → `Failed` | a provisioning / spawn / admission-impossible fault | 4, 7 |
| `Running`/`Suspended` → `Provisioning` | the pod is gone or evicted | **8** |

**⚠️ `Suspended` is not `Failed`, and the difference is operational, not cosmetic.** Vault sealing
is EXPECTED on every `vault-0` restart on this cluster. A sealed Vault marking agents `Failed`
would turn a routine restart into a fleet-wide terminal state that no reconcile pass recovers
from — `Failed` is terminal (✅ `Status.Terminal()`, `libs/go/orchestrator/types.go`). `Suspended`
is re-enterable, so the fleet heals itself when Vault unseals.

**At most ONE transition per `Agent` per pass**, and **a per-agent failure never fails the pass**
— ✅ the frozen `Reconciler.Reconcile` contract, verbatim (`libs/go/orchestrator/ports.go`,
`Reconcile` doc comment).

### 4.3 The five lifecycle verbs map to CR changes, not to new API

**This is the reason the API surface delta is zero.**

| verb | CR change | what the loop does |
| --- | --- | --- |
| **start** | create the `Agent` CR (or patch `spec.desiredPhase: Running`) | steps 2→3→4→5→6→7 |
| **resume** | patch `spec.desiredPhase: Running` | step 7 (or step 8 if a pod existed) |
| **stop** | patch `spec.desiredPhase: Stopped` | step 9: `ControlMessage{VerbStop}` → drain → delete the Pod. **THE CR REMAINS.** |
| **delete** | `kubectl delete agent <name>` | step 1: the finalizer archives, then removes itself |
| **recover** | set `spec.recoverFrom: <checkpoint>` — **or do nothing at all** | step 10 for a pinned rewind; **step 8 makes ordinary recovery automatic** |

**`recover` is the interesting one, because most of the time it is not a verb.** Step 8 re-creates
a pod that is gone or evicted, pinned to `status.lastCheckpoint`. **That is recovery, and it needs
no verb.** `recoverFrom` exists only for the case where the operator wants an OLDER checkpoint
than the latest — a deliberate rewind, with the identity consequences of §3.4.

**`stop` leaves the CR.** A stopped agent is a declared agent that is not running; deleting the CR
is a different act with a different consequence (the archive). Conflating them is how an operator
loses a transcript by trying to pause a run.

---

## 5. The 12-step reconcile loop

This is the **frozen `orchestrator.Reconciler` contract** bound to controller-runtime. ✅ Its
three invariants are the frozen ones, quoted: **ONE pass**, **IDEMPOTENT and CONVERGENT**,
**AT MOST ONE transition per agent per pass**, and **a single agent's failure never fails the
pass** (`libs/go/orchestrator/ports.go`, `Reconcile`).

1. **`DeletionTimestamp` set → ARCHIVE.** Publish the terminal lifecycle envelope; seal the last
   segment; write `deleted.json{retainUntil: now + retentionDays}`; delete the Pod;
   `RemoveFinalizer`.
   **⚠️ The finalizer is removed once the TOMBSTONE is written, NOT once the data is deleted.**
   Deletion therefore stays fast (a `kubectl delete` does not block on an object-store sweep) and
   retention stays the pruner's job. Removing the finalizer only after deletion would make every
   delete as slow as the slowest prefix sweep, and a stuck sweep would wedge the object forever.
2. **No finalizer → `AddFinalizer`, requeue.** Before anything else can create state, the thing
   that will archive it must exist.
3. **`status.agentID` empty → MINT the ULID, capture `agentUID`, write status, RETURN.**
   **Nothing else may happen in this pass.** Identity precedes every side effect.
   **If `agentUID` is set and disagrees with the live `metadata.uid` → REFUSE** (§3.3).
4. **ADMIT.** Six checks, in this order, each failing cheap:
   `MaxConcurrent` per `(Tenant, Template)` · team `maxConcurrentAgents` · team budget ·
   unknown `hostToolSet` · a WIDENING override against `templateRef` · ResourceQuota headroom.
   **Any failure is a status condition, NEVER a created pod. FAIL CHEAP.**
5. **Ensure streams match the ConfigMap policy; ensure the object-store bucket + agent prefix.**
   **⚠️ An absent bucket makes the controller NotReady and it admits NOTHING.** An agent that runs
   with nowhere to checkpoint produces a transcript that cannot survive its own pod.
6. **Render / Apply the owned ConfigMap** (`/etc/eden/agent.json`), **schema-validated (Eden
   invariant E2)**. ✅ The estate already carries a schema directory (`schemas/` at the eden root),
   so validation is a binding, not a new mechanism.
7. **`desiredPhase: Running` and no Pod → provision** via `workspaceprovider.Provider`, so the
   estate keeps **ONE** kubernetes pod builder — **then PATCH an `ownerReference` onto the
   deterministic pod name IN THE SAME PASS.**
   **Cost, stated rather than hidden:** a one-pass window in which the pod exists with no
   ownerReference. The finalizer (step 1) covers deletion during that window, because the archive
   path deletes the Pod by name and does not rely on garbage collection.
   **⚠️ This must be PROVEN in the fleet lane, not asserted** — obligation O17.
8. **`desiredPhase: Running` and the Pod is gone or evicted → re-create** with
   `EDEN_CHECKPOINT_RESTORE = status.lastCheckpoint`. **THAT IS RECOVERY, AND IT NEEDS NO VERB.**
9. **`desiredPhase: Stopped` and the Pod is live →** publish `ControlMessage{VerbStop}` → await
   `PhaseDraining → PhaseStopped` **or** `drainTimeout` (a checkpoint is taken at drain) → delete
   the Pod. **THE CR REMAINS.**
   ✅ `VerbStop`, `PhaseDraining` and `PhaseStopped` are frozen `fleetenvelope` members
   (`contracts/fleetenvelope.md` §2, `ControlVerb` and `HealthPhase`) — cited, not redefined.
10. **`recoverFrom != ""` → re-create the Pod pinned to that checkpoint.** Step 8 restores the
    LATEST; step 10 restores a NAMED one. They are the same mechanism with a different pin, which
    is why a rewind is not a separate code path that can drift from the recovery path.
11. **Credential unresolvable → `Suspended` + `CredentialUnavailable`, NEVER `Failed`.**
    ⚠️ Vault sealing is **expected on EVERY `vault-0` restart on this cluster**. §4.2 states why a
    terminal phase here would be a self-inflicted outage.
12. **Observe.** Pod status **plus** the heartbeat-written status subresource → `Probe.Observe`.
    This is the step that makes `Probe`'s frozen promise true: *"a truthful 'actual' independent
    of the desired record — the property that makes reconcile correct after a Pool restart"*
    (✅ `libs/go/orchestrator/ports.go`, `Probe`).

**REAP — a SEPARATE, SLOWER cadence.** ✅ The frozen contract already separates it: *"Separate
from Reconcile so retention runs on its own cadence. Idempotent."* (`ports.go`, `Reap`).

- Delete object-store prefixes past `retainUntil`.
- **AND** delete oldest-first past the hard bucket ceiling — because a retention window alone does
  not bound a bucket; a burst inside one window can fill it.
- **Every pruner action publishes its own `IntentLifecycle` envelope with
  `Actor{Kind: ActorSystem, ID: "retention-pruner"}`** — *"the audit trail records its own
  erasure."* An erasure that leaves no record is indistinguishable from data that never existed.

> ⚠️ `fleetenvelope.ActorKind` is frozen at four members — `ActorAgent`, `ActorHuman`,
> `ActorPolicy`, `ActorController` (✅ `contracts/fleetenvelope.md` §2). **There is no
> `ActorSystem`.** Either the pruner emits as `ActorController` with
> `ID: "retention-pruner"` (recommended — the pruner IS part of the controller), or
> `fleetenvelope` takes an additive fifth member. Recorded as fork **F3b** inside F3.

---

## 6. What the controller implements, and what it does NOT replace

### 6.1 The answer is "nothing, at the contract level" — the opposite of the reflex answer

The reflex answer to "we are adding a kubernetes controller" is "it replaces the orchestrator".
**It does not.** **ZERO orchestrator ports change. `libs/go/orchestrator/ports.go` does not
change. The orchestrator `.apibaseline` delta is ZERO.** ✅ (`go/orchestrator/.apibaseline` exists
on `origin/main` and is the frozen witness.)

| port | methods | verdict |
| --- | --- | --- |
| `DesiredStore` | 3 | **IMPLEMENT** — the CR spec + status **IS** the durable record. `Put`/`Get`/`List` become apply/get/list against the API server. |
| `Probe` | 1 | **IMPLEMENT** — Pod Ready **plus** the Heartbeat on `agent.<id>.health`. **The FIRST consumer that subject has ever had.** |
| `Manager` | 5 | **IMPLEMENT** — `Spawn` = create CR (returns `Pending` immediately); `Stop`/`Resume` = patch `spec.desiredPhase`. **Admission MOVES to the controller** so `MaxConcurrent` binds a hand-applied CR too. ⚠️ See §6.2. |
| `Watcher` | 1 | **IMPLEMENT** — an informer **IS** snapshot-then-tail. ✅ The frozen doc already demands exactly that: *"The first emission per matching agent is its current state (snapshot-then-tail), so a fresh subscriber needs no separate List"* (`ports.go`, `Watch`). |
| `Reconciler` | 2 | **REUSE** — controller-runtime's semantics **ARE** the frozen semantics (one pass, idempotent, convergent, at most one transition, per-agent failures isolated). The existing tests move over unchanged. |
| `TemplateStore` | 1 | **UNCHANGED** |
| `Telemetry` | 1 | **UNCHANGED** |

**`Probe` is the sharpest evidence that the port set was right.** The health subject already
exists on the wire (✅ `contracts/fleetenvelope.md` §2, `Heartbeat` on `agent.<id>.health`) and has
never had a consumer. A port designed for a multi-node future turning out to bind a real cluster
query with no signature change is the desired-vs-actual split doing exactly what
`contracts/orchestrator.md` §1 promised: *"the contract reads identically for the multi-node
version"*.

### 6.2 ⚠️ The one place the SURFACE holds and the SEMANTICS move — and it is not free

**`Manager.Spawn`'s documented behaviour changes even though its signature does not.**

The frozen contract says Spawn *"validates the request against limits BEFORE admitting it (fail
cheap, before any pod): a wrapped `LimitError` (`errors.AsType`, `errors.KindExhausted`) if the
`(Tenant, Template)` `MaxConcurrent` ceiling is met"* — ✅ `libs/go/orchestrator/ports.go`, the
`Spawn` doc comment, verbatim. That is a **SYNCHRONOUS refusal on the caller's goroutine**.

If **admission MOVES to the controller** — which it must, so that a hand-applied CR is also
admitted — then `Spawn` creates a CR and returns `Pending`, and the `LimitError` arrives later as
an `Admitted=False` condition. **A caller that today branches on a returned `LimitError` will
never see one.**

- `.apibaseline` delta: still **ZERO** (a doc comment is not a symbol).
- Behavioural delta: **not zero**, and it is a change to a frozen contract's stated semantics,
  which `contracts/orchestrator.md` §1 governs by revision (ADR-0016 §1), not by silence.
- 🧩 **Recommendation:** the controller-backed `Manager` binding performs a **best-effort
  synchronous pre-check** at `Spawn` and still returns `LimitError` when it can see the ceiling
  already met, while the controller re-checks authoritatively at step 4. That preserves the
  documented behaviour for the common case and keeps the hand-applied CR covered. It is a
  best-effort check, not a guarantee, and saying so is the point.
- **Recorded as fork F5. This document does not decide it**, because it may put a frozen contract
  into revision.

### 6.3 Closure re-homing — the three closures on `SpawnRequest`

The frozen `orchestrator.SpawnRequest` carries values a kubernetes CR cannot carry: a Go func, a
host-tool list, and a workspace path. Each gets a stated answer.

| closure | answer |
| --- | --- |
| `OnPermission func(...)` | **NOT re-homed — NOT USED, and it MUST stay nil** (§2.2). Re-homing it would defeat obligation O10. |
| `HostTool` | **A COMPILE-TIME REGISTRY inside `apps/agent-runtime`, selected BY NAME from the CR** (`hostToolSet`). |
| `Workspace` | **Not carried — DERIVED as `/state/<sessionName>/workspace`.** |

### 6.4 Why `HostTool` must be a compile-time registry, and not data

**Only the process that owns the harness stdio can serve Claude's CLI-initiated MCP handshake.**
The handshake is `initialize → notifications/initialized → tools/list → tools/call` over
`mcp_message` control_requests, and **failing any step BLOCKS `client.connect()`** — the harness
does not degrade, it does not start. A host tool is therefore a live in-process handler, not a
serializable value, and no CR field can carry it.

**The CR carries a NAME. The binary carries the implementations.** An unknown name is a **LOUD
boot-and-admission failure that LISTS WHAT IS REGISTERED**, with `Reason: UnknownHostToolSet`. It
is checked twice on purpose: at admission (step 4, so no pod is created for a typo) and at boot
(so an image that does not carry the named set cannot silently run without its tools).

**`Workspace` is derived, not carried**, so there is one rule producing the path instead of a
field an operator can set inconsistently with the `state` volume mount. The derivation
`/state/<sessionName>/workspace` also makes the session name's DNS-1123 shape do double duty as a
path element.

---

## 7. The profile reference — Mateo's 2026-08-26 instrumentation ruling

### 7.1 The ruling, and that it is NEW

> **Mateo, 2026-08-26:** instrumentation becomes a **central `agentprofile` schema + renderer,
> with commit-time rendered files and a drift gate.**

⚠️ **This is a NEW consequence of a 2026-08-26 ruling layered onto the 2026-08-18 design.** The
2026-08-18 synthesis has `templateRef` and `hostToolSet` and knows nothing of a rendered profile.
Nothing in §2 through §6 should be read as having anticipated this.

### 7.2 The consequence for this contract

**`templateRef` and `hostToolSet` must reference a RENDERED-PROFILE ARTIFACT plus a DIGEST, not a
repository path.**

```yaml
  profileRef:
    name: supervisor
    version: 1.4.0
    digest: sha256:9c1f...   # the RENDERED artifact's content digest. REQUIRED.
```

**The argument, stated so it can be refuted.**

- **A repository path is resolved at pod boot.** Between the moment the profile is rendered at
  commit time and the moment a pod boots — which may be days, and is certainly after any number of
  intervening commits — the path's content can change. The pod then runs an instrumentation
  profile nobody rendered, gated or reviewed, while the CR still claims the reviewed one.
- **A digest cannot drift.** It names one byte sequence. If the artifact is absent or its content
  does not hash to the recorded digest, the controller refuses at admission — cheaply, before any
  pod, which is the §5 step 4 rule already.
- **It is the SAME EVIDENCE DISCIPLINE the estate already uses for image promotion.** ✅ ADR-0028:
  the release workflow *"opens a promotion pull request against `gophersys/infrastructure` that
  pins the digests"*. Instrumentation that decides what an agent is allowed to do deserves at
  least the discipline already applied to the bytes it runs.

**The tension with `templateRef`, recorded rather than resolved.** `templateRef` is THE CEILING
(§2.2): the immutable pin every field may only tighten. `profileRef` would be a second immutable
pin. **Two pins means two ceilings, and nothing in either the 2026-08-18 design or the 2026-08-26
ruling says which wins when they disagree.** Three shapes are possible — fold the digest INTO
`templateRef`; keep `profileRef` separate with a stated precedence; or make `templateRef` resolve
THROUGH `profileRef`. **This document does not choose. Fork F4.**

### 7.3 The seam with the parallel lane

🔶 A live parallel lane is building the `agentprofile` schema and renderer at
`~/code/.worktrees/eden-instrumentation-contracts`. **That worktree was deliberately NOT read and
NOT touched.** The seam this contract needs from it is exactly three things, and nothing more:

1. a **stable artifact name + version** addressing scheme;
2. a **content digest** over the rendered artifact, in a form the controller can verify at
   admission;
3. a statement of **who publishes** the artifact and **where** it is fetched from, so step 4 knows
   what "absent" means.

**Neither lane may assume the other has landed.** Until the seam is agreed, `profileRef` is a
PROPOSAL in this contract and its field shape above is illustrative.

---

## 8. Admission, quota, placement

### 8.1 Admission — the one authority, at step 4, before any pod

The six checks of §5 step 4, and what each refuses:

| # | check | refusal condition | reason token |
| --- | --- | --- | --- |
| 1 | `MaxConcurrent` per `(Tenant, Template)` | `Admitted=False` | `ConcurrencyCeiling` |
| 2 | team `maxConcurrentAgents` | `Admitted=False` | `TeamConcurrencyCeiling` |
| 3 | team budget already exhausted | `Admitted=False` | `TeamBudgetExhausted` |
| 4 | `hostToolSet` unknown | `Admitted=False`, **LISTING what is registered** | `UnknownHostToolSet` |
| 5 | a WIDENING override against `templateRef` | `Admitted=False` | `WideningOverride` |
| 6 | ResourceQuota headroom | `Admitted=False` | `QuotaExhausted` |

**Every one of these creates NOTHING.** ✅ The frozen fail-cheap rule
(`contracts/orchestrator.md` §1 duty 3). A refusal that has already created a pod is not a
refusal; it is a leak with an error message.

### 8.2 Quota — the numbers, with their derivation

Three manifests in `infrastructure`, owned there, not here:
`apps/eden/01-resourcequota.yaml` · `apps/eden/02-limitrange.yaml` · a `PriorityClass`.

**PriorityClass `eden-agent` sits BELOW the platform services.** An agent is preempted before
`agentgateway`, never the reverse. A fleet that can evict its own control plane cannot recover
from its own load.

**ResourceQuota, scopeSelector on that PriorityClass:**

| resource | value |
| --- | --- |
| `count/pods` | 8 ⚠️ (fork F1) |
| `requests.cpu` | 4 |
| `requests.memory` | 8Gi |
| `limits.ephemeral-storage` | 12Gi |

**LimitRange default per agent pod:** cpu **1** · memory **2Gi** · ephemeral-storage request
**1Gi** / limit **2.5Gi** (**DOWN from today's 4Gi**).

**Derivation, so the numbers are auditable rather than believed:**

- 20 worker cores in the pool.
- CI reserves up to 12 and **deliberately holds NO CPU limit** — it is meant to burst.
- eden's standing footprint is ~5.7 cores.
- Agent pods declare `requests == limits`, so they are **throttled to their request** while CI
  bursts freely. 4 cores of agent requests fits the residue without contending with CI's burst.

**Pod volumes:** `state` emptyDir `sizeLimit: 1Gi` → `/state`; `workspace` emptyDir
`sizeLimit: 1Gi` → `/workspace`.

**`emptyDir sizeLimit` IS enforced by the kubelet eviction manager, and that is the entire
reason it is set.** Exceeding it **evicts THE POD** — converting an unattributable node-wide
DiskPressure cascade (which takes down whatever the kubelet picks, including things that are not
agents) into a **bounded, attributable, single-pod eviction that step 8 recovers from a
checkpoint**. The failure is not prevented; it is made small, named, and automatically repaired.

### 8.3 Placement — `excludeNodes: [k3s-w-0, k3s-w-1, k3s-w-4]`

Controller-DEFAULTED, operator-overridable. Each exclusion has a reason:

| node | reason |
| --- | --- |
| `k3s-w-0` | ephemeral-storage limits at **147–149%**, actively evicting |
| `k3s-w-1` | same |
| `k3s-w-4` | **USB passthrough**; already excluded by every CI pool |

**The fleet lands on `k3s-w-2` and `k3s-w-3`.**

**⚠️ A CEILING IS NOT RAISED WITHOUT MEASURING THE `pve-00` THIN POOL.**
`k3s-w-0`, `k3s-w-1` and `k3s-w-2` are **three thin LVs on ONE NVMe**, so exhausting the pool
takes all three at once — including `k3s-w-2`, which this placement lands agents on. The
measurement, before any raise:

```
ssh pve-00 lvs -o lv_name,data_percent,lv_size
```

Recorded as fork **F2**. Do not treat any raise as available until that command has been run and
its output recorded.

---

## 9. Deployment shape

### 9.1 Toolchain — controller-runtime **v0.23.0** (`k8s.io/*` v0.35.0), NOT v0.24.1

⚠️ **The Go-version argument for v0.24.1 was verified WRONG.** A `go` directive is a **MINIMUM,
not a ceiling**; it does not exclude a newer toolchain and is not evidence for a dependency
choice.

**The choice rests PURELY on API skew:**

| candidate | `k8s.io/*` | vs homelab k3s v1.35.5 | vs cloud v1.34.5 |
| --- | --- | --- | --- |
| **v0.23.0** ✅ recommended | v0.35.0 | **exact match** | within one minor |
| v0.24.1 | v0.36.0 | **+1** | **+2** |

Matching the substrate exactly, and staying within one minor of the other, is the whole argument.
Nothing else in the comparison is load-bearing.

### 9.2 The Argo shape — and the failure mode that is silent

**⚠️ `projects/apps.yaml` has `namespaceResourceWhitelist: */*` and NO
`clusterResourceWhitelist`.** ✅ Verified by reading
`infrastructure/platform/services/gitops/registry/projects/apps.yaml` — it declares
`namespaceResourceWhitelist: [{group: "*", kind: "*"}]` and the file ends there.

**Consequence: a CRD placed in the `apps` project does NOT fail loudly.** It sits permanently
**OutOfSync**, with `selfHeal` converging **never** — five weeks on `app-eden` already. A
green-looking Application that has never applied its most important object is exactly the class of
silent no-op the estate's fail-loudly rule exists to prevent.

**The fix, and it is already the estate's proven pattern:**

| Application | project | why |
| --- | --- | --- |
| `app-fleet-crd.yaml` | **platform** | ✅ `projects/platform.yaml` has `clusterResourceWhitelist: [{group: "*", kind: "*"}]` and lists `eden` in `destinations` |
| `app-fleet-rbac.yaml` | **platform** | same; the eden destination comment already reads *"the Eden Namespace (app-eden-namespace) + orchestrator cluster RBAC (app-eden-rbac)"* |
| the controller Deployment | **apps** | a namespaced workload, which is what the `apps` project is for |

✅ **The split is proven three times in the estate**, by reading
`infrastructure/platform/services/gitops/registry/`: `app-eden-namespace` + `app-eden-rbac`
(platform) alongside `app-eden` (apps); `app-workspaces-namespace` + `app-workspaces-rbac`
(platform) alongside `app-workspaces-api`; and `app-embedded-namespace` (platform). This contract
adds a fourth instance of an existing pattern, not a new one.

### 9.3 `ServerSideApply=true` FROM THE FIRST COMMIT

Not later, not on the first failure. The client-side apply path stores the full manifest in the
`kubectl.kubernetes.io/last-applied-configuration` annotation, against a **262144-byte** cap.
Measured CRD precedents run **660 KB / 1.2 MB / 1.4 MB** — two to five times the cap. A CRD that
grows past it fails on the day a field is added, not on the day it is written, which is the worst
possible time to discover it.

✅ The option is already the estate's default: twelve Applications in
`infrastructure/platform/services/gitops/registry/` carry `ServerSideApply=true`, including the
bootstrap `root-app.yaml` and `app-eden-rbac.yaml`.

### 9.4 `argocd.argoproj.io/sync-wave: "-1"` on the CRD Application

The CRD must exist before any `Agent` object can be applied. A negative wave is the ordering
mechanism.

⚠️ **There is ZERO precedent for `sync-wave` in the `infrastructure` repository** — a grep across
the whole repository returns no occurrences. This would be the estate's **first** use of the
annotation. That is not an objection; it is a note that the mechanism is unexercised here, so the
first deploy should verify the ordering rather than assume it. Recorded as fork **F11**.

### 9.5 **NEVER declare `recurse: false`**

The API server **normalises it away** — the field round-trips to absent — so Argo compares a
desired manifest containing `recurse: false` against a live object without it, forever. **The
Application sits OutOfSync permanently.** Omit the key; the default is already what is wanted.

---

## 10. Preconditions owned by other repositories

Each is a PRECONDITION with an executable check, not a footnote.

### 10.1 ⚠️ THE RED FLAG — a real `Spawn` has never been executed, and it outranks this design

**Nobody has ever executed a real `Spawn` against the deployed orchestrator.** Two shipped
artifacts describe incompatible worlds:

- ✅ `deploy/image/agentgateway.Dockerfile:18` — *"The orchestrator role likewise spawns no
  harness in-process (the supervisor runs in a provisioned workspace pod), so it shares this
  minimal base"*. The runtime stage is **distroless**, with no `claude` binary.
- ✅ `libs/go/orchestrator/reconcile.go:159` — `session, err := ports.Sessions.Open(ctx, spec)`.
  **The orchestrator binary opens the session IN-PROCESS**, inside that same distroless image.

Both cannot be true of a working system. Either the session factory bound in production is a
remote-open binding that the Dockerfile comment describes correctly, or the in-process open has
never run and would fail on the missing binary.

**IF THE ANSWER IS "NEITHER HAS EVER RUN END TO END", THAT IS A BIGGER FINDING THAN THIS WHOLE
DESIGN, AND IT MUST REACH MATEO BEFORE ANY IMPLEMENTATION SLICE STARTS.** Every step of §5 that
publishes a control message, awaits a drain, or observes a heartbeat presumes a harness that runs.

**The executable check — run this, do not reason about it:**

```
kubectl -n eden get deploy orchestrator -o jsonpath='{.spec.template.spec.containers[0].image}'
kubectl -n eden exec deploy/orchestrator -- sh -lc 'command -v claude || echo NO-CLAUDE-BINARY'
kubectl -n eden logs deploy/orchestrator --since=720h | grep -c 'session open'
kubectl -n eden get pods -l fleet.eden.gophersys.com/agent=true
```

A zero on the third line, or `NO-CLAUDE-BINARY` on the second, settles it. **Record the actual
output. Do not record an inference.**

### 10.2 NetworkPolicy — owned by `infrastructure`, in ONE change

**(1) The object-store NetworkPolicy gains ONE ingress rule.**

```yaml
# infrastructure/apps/minio/25-networkpolicy.yaml — a FOURTH policy alongside the existing three
  ingress:
    - from:
        - namespaceSelector:
            matchLabels: {kubernetes.io/metadata.name: eden}
          podSelector:
            matchLabels: {fleet.eden.gophersys.com/agent: "true"}
      ports: [{port: 9000, protocol: TCP}]
```

**⚠️ IT IS A `podSelector`, NOT A NAMESPACE RULE, AND THAT IS THE WHOLE POINT.** Debt **D12**
accepts MinIO running as root with a writable root filesystem **BECAUSE it is network-isolated to
two controllers**. ✅ Verified by reading `infrastructure/apps/minio/25-networkpolicy.yaml`: the
existing rules are `default-deny-ingress`, `allow-longhorn-backups` (namespace
`longhorn-system`), `allow-ingress-nginx` (namespace `ingress-nginx`), and `allow-same-namespace`.
**A namespace-wide `eden` rule would let every pod in `eden` reach the object store and would
destroy D12's justification.**

🧩 One mechanical note the manifest must get right: `namespaceSelector` and `podSelector` must be
**two keys of ONE `from` list element** (an AND). Written as two separate list elements they
become an OR — which is exactly the namespace-wide rule this section forbids, arrived at by a
YAML dash.

**(2) IN THE SAME CHANGE, namespace `eden` gets its FIRST NetworkPolicy.** ✅ Verified: `ls
infrastructure/apps/eden/` contains no NetworkPolicy manifest. The set:

- default-deny ingress
- allow ingress-nginx
- allow intra-namespace
- allow egress to: the object store · NATS · the OTLP endpoint · DNS

**⚠️ Shipping the object-store allow ALONE would be a NET SECURITY REGRESSION.** Today the
privileged `dind` CI runners with **deliberately unrestricted egress** can reach `eden` pods —
and after this change those pods hold live harness credentials. Adding a rule that lets agents
out, without adding the rule that keeps CI out, makes the estate strictly less safe than before
the fleet existed.

**(3) REJECTED: the `s3.mateosegura.com` ingress hairpin.** It would add TLS, DNS and an nginx hop
**on every turn boundary**, against 2 CoreDNS replicas whose last incident failed a 40-minute
build. The in-cluster service address avoids all three.

**⚠️ BLAST RADIUS IS OPEN.** Nobody has enumerated what reaches `eden` pods cross-namespace. The
recommendation is **ENUMERATE FIRST, as an added audit step**, before writing the allow list —
because a default-deny written against an unenumerated set breaks whatever was silently depending
on it. Fork **F6**.

### 10.3 The connectors path — an explicitly DEFERRED defect that GATES `connectorScope`

**The production connectors path was never traced to a consumer: "USER CONNECTORS DO NOT WORK IN
THE SHIPPED BINARY AT ALL."**

- Fix site: `main.go:142-160` **plus** `prodserve.go:232-261`.
- **Landing condition:** the fix lands, **with a test asserting that `eden://connector/<id>`
  resolves in the PRODUCTION composition**, BEFORE any per-team connector is claimed to work.

**This GATES `AgentTeam.spec.connectorScope` (§2.4).** A team-scoped connector override on top of
a path with no consumer is a field that reads as working and does nothing. Until the landing
condition is met, `connectorScope` must not be presented as functional in any document, board or
demonstration.

### 10.4 The bucket and the Vault seed

- **The object-store bucket must exist before the controller admits anything** (§5 step 5). An
  absent bucket makes the controller `NotReady`.
- **The Vault seed must carry every `credentialReference` in every `Agent.spec`.** ✅ The estate's
  mechanism already exists — `infrastructure/apps/eden/08-vault-seed-job.yaml` and the four
  imperative secrets documented in `infrastructure/apps/eden/README.md` (ADR-0028). A missing
  reference is `Suspended` + `CredentialUnavailable` (§5 step 11), which is recoverable — but a
  fleet that starts entirely `Suspended` because nobody seeded it is an avoidable outage.

---

## 11. Conformance obligations — each with the break-test that must be seen RED

**Every obligation below is proven by a test that has been SEEN FAILING for the stated reason
before it was made to pass.** A test that has only ever been green proves nothing about the thing
it names. The break-test column says what to change to make the test fail; if the test still
passes after that change, the test is the defect.

| # | obligation | break-test that must be seen RED |
| --- | --- | --- |
| **O1** | `status.agentID` is minted ONCE, before any pod exists | make step 3 fall through instead of returning; assert a pod was created before `agentID` was written |
| **O2** | a `metadata.uid` disagreeing with `status.agentUID` is REFUSED | delete + re-apply the same CR file with `status.agentID` restored; assert the controller refuses and does not adopt the prefix |
| **O3** | `AgentID`, `SessionID`, `HarnessResumeID` are never conflated | set `SessionRef = AgentID` (today's shipped behaviour, `reconcile.go:159-168`); assert a two-session agent breaks the assertion |
| **O4** | the pod receives `EDEN_AGENT_ID`; absent ⇒ exit 2 | remove the env fold; assert the pod exits **2** with `agent-runtime: EDEN_AGENT_ID is required` (✅ `composition.go:113-116`) |
| **O5** | `EDEN_POD_NAME` and `EDEN_AGENT_ID` are cross-checked at boot | set them to disagree; assert exit **2** with an error naming **BOTH** values |
| **O6** | at most ONE transition per Agent per pass; a per-agent failure never fails the pass | make one agent's provision panic; assert the other agents still transitioned and `Reconcile` returned nil |
| **O7** | FAIL CHEAP — an admission failure creates NO pod | breach `MaxConcurrent`; assert `Admitted=False` **and** zero pods created |
| **O8** | an absent bucket makes the controller NotReady and it admits NOTHING | delete the bucket; assert zero admissions and a NotReady controller |
| **O9** | a sealed Vault ⇒ `Suspended` + `CredentialUnavailable`, NEVER `Failed` | seal `vault-0`; assert `phase: Suspended` and that unsealing returns it to `Running` |
| **O10** | the chat-human-then-advisor permission chain is exercised | set `Spec.OnPermission` non-nil; assert the human arm is **NEVER** taken (`pump.go:352` short-circuits — §2.2) |
| **O11** | the finalizer is removed once the TOMBSTONE is written, not once data is deleted | stall the object-store sweep; assert `kubectl delete` still completes promptly and `deleted.json` exists |
| **O12** | every pruner action publishes its own lifecycle envelope | prune a prefix with the publish suppressed; assert the erasure has no audit record and the test fails |
| **O13** | `recoverFrom` keeps the `AgentID`, mints a NEW `SessionID`, restarts `Seq` at 1, and records the discontinuity | reuse the prior `SessionID`; assert the `MessageID` composite collides |
| **O14** | **CLOSURE GUARD** — a non-nil `SpawnRequest.OnPermission`, a non-empty `.HostTools`, or a non-empty `.Workspace` on the kubernetes `Manager` binding is a **loud `InvalidRequestError` NAMING THE FIELD** | **nil the field out instead of erroring, and assert `Spawn` succeeds SILENTLY** — the silent nil-out is the defect this obligation exists to forbid |
| **O15** | **SPLIT-BRAIN GUARD** — binding BOTH the kubernetes `DesiredStore` and the in-process reconcile ticker is a **STARTUP FAILURE naming both** | downgrade it to a warning; assert the process starts with two reconcilers writing one record |
| **O16** | an unknown `hostToolSet` fails LOUDLY, **listing what IS registered** | use an unregistered name; assert `Reason: UnknownHostToolSet` **and** that the message enumerates the registry |
| **O17** | the `ownerReference` is patched onto the pod IN THE SAME PASS as creation | drop the patch; assert an orphan pod survives CR deletion **(this is the step-7 cost — PROVE it, do not assert it)** |
| **O18** | exceeding `emptyDir sizeLimit` evicts THE POD, and step 8 recovers it from a checkpoint | fill `/state` past 1Gi; assert a single-pod eviction (not node DiskPressure) and an automatic checkpoint restore |
| **O19** | the orchestrator `.apibaseline` delta is ZERO | re-record the baseline after the controller lands; assert byte-identical to `origin/main`'s |
| **O20** | there is NO free-form `Spec.Env map[string]string` on any fleet surface | add one; assert the API-shape test refuses it |

**⚠️ O14's break-test is the sharpest one in the table and must not be softened.** The failure mode
being forbidden is not an error with the wrong text — it is **`Spawn` succeeding while silently
discarding a closure the caller supplied**. The caller then believes a permission policy is in
force that is not. A guard that logs and continues is the defect wearing the guard's name.

**⚠️ O15 is a startup failure, never a warning**, for the same reason: two reconcilers writing one
record produce a record that is neither's, intermittently, under load — the hardest class of
defect to attribute after the fact and the cheapest to refuse at startup.

---

## 12. Open forks — what Mateo must rule on, or delegate

**Nothing in this table is decided. The recommendation is listed first and is a recommendation.**

| # | fork | options (recommendation first) | blocks |
| --- | --- | --- | --- |
| **F1** | **The concurrency numbers do not agree.** The §2.4 example shows `maxConcurrentAgents: 6`; the recommendation to Mateo is *"quota 8, team default 4"*. | (a) quota `count/pods 8`, team default `4`, and the example corrected to 4 — the example is illustrative, the recommendation is the reasoned number · (b) team default 6 and quota raised, **only after F2** · (c) measure a real team first and set both from the measurement | the quota manifest; §8.2 |
| **F2** | **The `pve-00` thin pool is unmeasured.** `k3s-w-0/1/2` are three thin LVs on ONE NVMe; exhausting it takes all three at once, including the node the fleet lands on. | (a) **MEASURE FIRST** — `ssh pve-00 lvs -o lv_name,data_percent,lv_size`, record the output, then decide · (b) raise nothing until the fleet has run for a week | any ceiling raise; F1(b) |
| **F3** | **The condition set is not closed.** Nine types are named; the design's prose also contains `BusAttached` (a type) and `CredentialUnavailable` (a reason). **F3b:** the retention pruner needs an actor kind, and `fleetenvelope.ActorKind` is frozen at four with no `ActorSystem`. | (a) `BusAttached` folds into `StreamsReady`; `CredentialUnavailable` is a REASON on `CredentialAvailable=False`; the pruner emits as `ActorController` with `ID: "retention-pruner"` — closing at nine types and requiring no `fleetenvelope` change · (b) ten types, with `BusAttached` distinct · (c) `fleetenvelope` takes an additive fifth `ActorKind` | the status schema; `fleetenvelope`'s freeze |
| **F4** | **`templateRef` vs `profileRef` — two ceilings.** Mateo's 2026-08-26 ruling requires a digest-pinned rendered profile; the 2026-08-18 design makes `templateRef` THE ceiling. Neither says which wins. | (a) **fold the digest INTO `templateRef`** — one pin, one ceiling, no precedence question to get wrong · (b) separate `profileRef` with a written precedence rule · (c) `templateRef` resolves THROUGH `profileRef` | §7; the instrumentation lane's seam |
| **F5** | **`Manager.Spawn`'s synchronous `LimitError` vs admission moving to the controller.** The surface does not change (`.apibaseline` delta zero) but the frozen doc comment's behaviour does. | (a) best-effort synchronous pre-check at `Spawn` **plus** authoritative re-check at step 4, and the doc comment amended to say "best-effort" · (b) admission stays in `Spawn` only — but then a hand-applied CR is never admitted · (c) a contract revision of `orchestrator` under ADR-0016 §1 | §6.2; whether a frozen contract enters revision |
| **F6** | **NetworkPolicy blast radius is unenumerated.** Nobody knows what reaches `eden` pods cross-namespace. | (a) **ENUMERATE FIRST** as an added audit step, then write the allow list from the measurement · (b) ship default-deny and repair what breaks | §10.2; the whole NetworkPolicy change |
| **F7** | **`AgentID` case.** This contract requires lowercase for DNS-1123; `fleetenvelope.md` §6 says "26-character Crockford-base32" with no case rule, and canonical ULID text is uppercase. | (a) `fleetenvelope.Validate` enforces LOWERCASE explicitly — one line, and it makes the DNS-1123 guarantee real · (b) this contract lowercases at minting and `fleetenvelope` stays case-agnostic (the guarantee is then enforced nowhere) | `fleetenvelope`'s freeze |
| **F8** | **`retentionDays` precedence.** `Agent.retentionDays: null` means "the fleet default (controller ConfigMap)"; `AgentTeam.retentionDays: 30` also exists. Which wins for a team member? | (a) Agent explicit > Team > controller ConfigMap — most specific wins, the ordinary rule · (b) Team always wins for a member, so a team's retention cannot be widened per agent | the pruner; §5 step 1 |
| **F9** | **Where the controller module lives.** No ruling names a location. | (a) `apps/fleet-controller/` with `api/v1alpha1`, mirroring `apps/agent-runtime` and `apps/agentgateway` · (b) a top-level `controllers/` · (c) inside `libs/` (**not recommended** — it is a binary, not a library) | the first commit |
| **F10** | **`fleetenvelope.md` cites `agentpod` in four places**, a name that was never created. | (a) whichever contract lands SECOND fixes the four references to `agentfleet` in the same change · (b) fix it now in `fleetenvelope.md` (**not recommended** — a sibling lane owns that file) | nothing; but it must not be forgotten |
| **F11** | **`sync-wave` has zero precedent in `infrastructure`.** This would be the estate's first use. | (a) ship it and **VERIFY the ordering on the first deploy** rather than assuming it · (b) order by two Applications with a manual sync between them | §9.4 |
| **F12** | **`connectorScope` is gated on a defect that has not landed** (§10.3). | (a) ship `AgentTeam` WITHOUT `connectorScope` in v1alpha1 and add it additively once the connectors test passes — an absent field cannot be believed · (b) ship the field marked non-functional (**risk:** a documented non-functional field is still read as functional) | §2.4; any per-team connector claim |

Each fork is also recorded in `docs/architecture/open-decisions.md`, per `CLAUDE.md`'s rule that
an unmade decision lives there and never in prose alone.

---

## 13. THE FREEZE QUESTION — for Mateo, and for nobody else

Freezing this contract is a `.claude/rules/git-process.md` §5 human gate. An agent may not
exercise it, and this document may not be edited to say it is frozen by anything other than
Mateo's own words quoted with a timestamp (§13 rule 4). The question is exactly this:

> **Do you freeze `agentfleet` v1alpha1 at the surface in §2 — two kinds and only two (`Agent`
> and `AgentTeam`, with `AgentTemplate` refused), `spec.desiredPhase` as the single lifecycle
> write that the five verbs patch, `status.agentID` + the `metadata.uid` witness as the ONE
> minting authority with a REFUSAL on disagreement, `Spec.OnPermission` permanently nil, no
> free-form `Spec.Env` map, the 12-step reconcile loop with its separate REAP cadence, and the
> §6 port table in which ZERO orchestrator ports change — accepting that the freeze commits the
> fleet lane to the two LOUD guards of §11 (O14, O15), to the `agentsession.Spec.StateRoot`
> additive field, and to whatever `fleetenvelope` must add for the lifecycle envelope and the
> pruner actor (fork F3)?**
>
> **YES** → the surface is frozen, the fleet lane starts against a fixed target, and the CRD +
> RBAC Applications land under the **platform** project with `ServerSideApply=true` from the
> first commit.
>
> **NO, with changes** → name the forks in §12 you are ruling differently, and the draft is
> amended and re-refuted before the question is asked again.
>
> **Answering also requires ruling F4 and F5, and they cannot be delegated.** F4 decides whether
> your 2026-08-26 instrumentation ruling produces one ceiling or two, which changes §2's schema.
> F5 decides whether a *frozen* contract (`orchestrator`) enters revision, which no agent may
> decide. F1, F2, F3, F6–F12 may be delegated.
>
> **AND — BEFORE ANY OF THE ABOVE — §10.1.** The executable check for whether a real `Spawn` has
> ever run must be executed and its output recorded. **If neither the gateway nor the
> orchestrator has ever run a harness end to end, that finding outranks this contract**, and the
> freeze question should not be answered until you have seen it.

**A second gate rides on the same answer.** The fleet ADR is reserved at **0030** (Batch B+C,
2026-08-18: *"Fleet ADR takes number 0030 (fills the hole; messaging keeps 0032)"*) and does not
exist on disk — `docs/architecture/adr/` runs 0029 → 0031. A new ADR is separately Mateo-gated
(§5), so no agent has written it, and this contract cites the 2026-08-18 and 2026-08-26 rulings
directly rather than citing an ADR that is not there. **Writing ADR-0030 is Mateo's, and it
should land in the same decision as the freeze**, so this contract's authority chain stops
dangling.
