# contracts/ — WS1 contract negotiation drafts

> Status: **Frozen as reconciled** (ADR-0016, 2026-06-12) — ballot rows remain overturnable by
> Mateo; an overturn is a re-negotiation producing a contract revision, never a silent edit.
> Originally: drafts for negotiation — They are the
> 09 §4 step-1/2 artifacts for the six universal patterns: per pattern, a producer-side draft and
> a consumer-side draft were authored independently and reconciled into one document, with
> unresolved tensions recorded as open questions. Freezing happens at the contract-PR gate
> (09 §4 step 3) after Mateo's review; the frozen contract's CODE lands in `libs/go/<pattern>/`
> while the contract DOCUMENT is retained here in place as the living contract text (the original
> "moves to the attic" plan was not adopted — contracts/ is the canonical retained home).

| Draft | Kind | Summary |
|---|---|---|
| [configuration.md](configuration.md) | pattern (10 §4) | Immutable, fully-resolved input IR; parsed once at the edge |
| [dependencies.md](dependencies.md) | pattern (10 §4) | The injected record of ports; the hexagon |
| [errors.md](errors.md) | pattern (10 §4) | Typed, wrappable, redaction-safe error model with stable `Kind` |
| [observability.md](observability.md) | pattern (10 §4) | Structured Event stream, OTel-aligned, secret-safe |
| [secrets.md](secrets.md) | pattern (10 §4) | Reference→value resolution; un-printable `Secret` type |
| [testing.md](testing.md) | pattern (10 §4) | Canonical fakes + adapter≡fake conformance suites |
| [agentsession.md](agentsession.md) | connector (F4, 05 §2) | The agent-session port: one normalized, resumable Event stream + tool grants + permission round-trip + credential seam over any harness (C22, ADR-0008) |
| [gitrepository.md](gitrepository.md) | library (S2 seam) | Local git on a worked repository: clone/fetch, branch + worktree (the swarm primitive), status/diff, per-actor commit, fast-forward-only push; NEVER a merge engine — merges go through gates (C23, ADR-0013) |
| [workspaceprovider.md](workspaceprovider.md) | connector (F1, 05 §2) | The substrate port: provision/teardown isolated workspaces, run/exec workloads, file mounts, declared dial-out egress, resource limits, over docker + any conformant kubernetes (k3d default, kind 2nd target); real-substrate test harnesses live in `workspaceprovidertest` (C23, ADR-0012/0016) |
| [orchestrator.md](orchestrator.md) | service library (S2/S4 seam) | The basic agent orchestrator: resolve an `AgentTemplate` (data, session-scoped) → provision a `Workspace` → open an `agentsession` → track/limit/observe the running set — a desired-vs-actual reconcile loop that reads identically single-node and multi-node; NEVER owns pods (workspaceprovider), the agent loop (agentsession), or credentials (secrets) (C23, C14) |
| [fleetenvelope.md](fleetenvelope.md) **DRAFT** | fleet wire spine (09 §4 step 1/2) | The message header every fleet plane carries: identity, causality (`CausedBy`/`InReplyTo`/`RootID`/`Hop`), the ten-member `Intent` vocabulary, `Actor`, payload spill discipline, and the once-only serialization window. **Has no library of its own** — the surface lands additively inside `libs/go/agentruntime`, so freezing it produces contract revision `agentruntime` R2 + `agentsession` R2. Not frozen; §12 is Mateo's question |
| [fleetbus.md](fleetbus.md) **DRAFT** | fleet transport (09 §4 step 1/2) | The NATS subject taxonomy (`events`/`inbox`/`control`/`health`), the two JetStream stream policies with explicit limits, `MessageID`-keyed dedup, the two sequence spaces and the history↔live stitch cursor, backpressure, and archive-then-publish. Also has no library of its own: the code lands in `agentruntime` + `agentruntime/natsbus`. Not frozen |
| [agentfleet.md](agentfleet.md) **DRAFT** | fleet control plane (09 §4 step 1/2) | The `Agent` and `AgentTeam` CRDs (`fleet.eden.gophersys.com/v1alpha1`), controller-minted identity with the `metadata.uid` witness, the lifecycle state machine, the 12-step reconcile loop, and the demonstration that **zero `orchestrator` ports are replaced**. **There is no `AgentPod` kind** — the document is named for what exists. Not frozen |
| [agentcheckpoint.md](agentcheckpoint.md) **DRAFT** | library (turn-boundary durability) | The turn-boundary checkpoint that IS the archive: the key grammar, the `done`-marker ordering as the atomicity primitive, the manifest, the pure-function path contract, restore, and the pruner. Bound to the **frozen `objectstorage` port**, never to MinIO — the successor store is an open decision. The one NEW library of the program: `libs/go/agentcheckpoint`, so this filename must equal that slug or `phase-gate architecture` can never resolve it. Not frozen |
| [codeinsight.md](codeinsight.md) **DRAFT** | analysis library | Walks an arbitrary git repository → ONE self-describing `Report` (per-entity static + behavioral metrics, logical coupling, ownership, trends, and a `Views` render-plan, every datum commit-hash-stamped). The producer side of the "point Eden at a codebase → dashboards" feature; consumes a new `gitrepository` history-walk surface, feeds `@eden/visualization`. NOT frozen — no lib built yet (research note 06) |

Every draft obeys: HNS-1 naming (10 §5) · the `New(configuration, dependencies)` spine (10 §4) ·
interfaces ≤5 methods, accept-interfaces-return-concrete (10 §9) · `context.Context` first ·
Go 1.26 floor (ADR-0003) · module path `github.com/gophersys/libs/go/<pattern>` (ADR-0009 B) ·
public fakes in `<pattern>test`. `agentsession` is an **F4 connector contract** (05 §2), not a
10 §4 library pattern — it obeys the same construction rules but its adapter seam, capability
manifest, and conformance suite are the connector-family obligations of 05 §1/§3/§6.
