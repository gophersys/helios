# Contract — agentcheckpoint

> Status: **DRAFT for negotiation** — NOT frozen, and no agent may freeze it · 2026-08-26 · The
> durable-state library of the Eden agent fleet: what a pod writes at every turn boundary so that
> a `kill -9` costs at most one turn and no instruction at all. This is the 09 §4 step-1/2
> artifact — the producer-side and consumer-side obligations of ONE checkpoint format, reconciled
> into one document, with the unresolved tensions recorded as open forks (§14) rather than settled
> silently. The freeze is Mateo's `.claude/rules/git-process.md` §5 gate ("a chart or contract
> PROMISE"), exercised only under §13 rule 4 with his verbatim words and a timestamp. §15 is the
> exact question he must answer. Until he answers it, `bash ./ctl.sh phase-gate architecture` in
> `libs/go/agentcheckpoint` is RED **by design** — `libs/go/_ctl/lib.sh::_gate_contract_frozen`
> requires a `Status: … Frozen` header (✅ `lib.sh:1216`), and a draft correctly fails it.
>
> **THE NAME IS MECHANICAL, NOT COSMETIC.** The fleet brief called this library `fleetcheckpoint`;
> the canonical locked design names it **`agentcheckpoint`**, and the document filename must equal
> the library slug or the architecture gate can never pass — ✅ `libs/go/_ctl/lib.sh:1182-1184`
> resolves the contract as `contract="$(_eden_monorepo_root)/docs/architecture/contracts/${slug}.md"`
> with `local slug="${EDEN_LIB_NAME}"`, and `_gate_run "contract frozen header" _gate_contract_frozen
> "$contract"` reads exactly that path. A contract filed under any other name is not a missing
> header — it is a document the gate can never find.
>
> Epistemic legend (`docs/architecture/README.md` §3): ✅ verified · 🔶 hypothesis · ⚠️ corrected ·
> 🧩 design choice. Every ✅ carries a `file:line`, a quoted ruling, or a measurement taken for this
> document. A claim with neither is a PROPOSAL and is marked as one.
>
> **Citation discipline for the spine.** `contracts/fleetenvelope.md` is being authored
> concurrently with this document. Every citation of it here names a TYPE and a SECTION, never a
> line number, because its line numbers are moving under this text.

## 1. Scope

`agentcheckpoint` is the **one home of the fleet's durable state**: what is written, in what
order, to what keys, so that an agent pod that dies mid-flight comes back knowing who it was, what
it had said, what it had done to its worktree, and where in the stream it had got to. 🔶

It owns exactly six things:

1. **The key grammar** (§5) — the object-store layout under one `AgentID`, and the rule that the
   `done` marker is written LAST.
2. **The ordering / atomicity primitive** (§5.2) — object storage has no multi-object transaction
   and the frozen port has no transaction verb, so ORDER is the primitive. This is the property
   the whole library is built on.
3. **The manifest** (§6) — the one mutable object, its JSON Schema, and its field semantics.
4. **The composition of a checkpoint** (§4) — which four artifacts a turn produces, and the
   `EventTurnEnd` cadence that produces them.
5. **Restore** (§8) — the seven steps, the path assertion that fails the pod, and the digest chain
   that must verify.
6. **Retention and the pruner** (§10) — the two bounds, and the rule that the pruner publishes its
   own erasure.

It explicitly does **not** own (the consumer must not expect these here):

- **The wire header, identity, causality, intent, the spilled-artifact VALUE type** —
  `contracts/fleetenvelope.md`. This document cites `AgentID`, `MessageID`, `Actor`, `Intent` and
  `ArtifactRef` and never redefines one of them. In particular the manifest's `turn` field is the
  home `fleetenvelope` §4.1 explicitly delegates to it ✅ (*"There is no turn ordinal on the
  header … it lives on `agentsession.Event.Turn` / `Event.TurnID`, on `SessionHealth.Turn`, on
  `Agent.status.sessions[].turn`, **on the checkpoint manifest**, and as the OTel attributes"*).
- **Blob put/get/delete/presign/list** — `contracts/objectstorage.md`, FROZEN (ADR-0016). This
  library speaks that five-method port and nothing below it (§11).
- **Local git** — `contracts/gitrepository.md`, FROZEN (ADR-0016). Provisioning, inspection and
  authoring ride that port. Bundle CREATION has no verb there, and that gap is open fork F5 (§14),
  named rather than assumed away.
- **Subjects, streams, consumers, acknowledgement, redelivery** — `fleetbus`. This library is
  handed a cursor and hands one back; it never opens a connection.
- **Pod lifecycle, the CRD, `Agent.status`, the health condition surface** — `agentpod`. This
  library RAISES a condition's cause; it does not own the condition type.
- **The harness Event taxonomy and the session port** — `contracts/agentsession.md`, FROZEN. A
  checkpoint transports `agentsession.Event` verbatim inside `segment.jsonl`; it never re-spells
  the taxonomy.
- **Bucket lifecycle.** Creating the `eden-agents` bucket is an OPERATOR concern, because the
  frozen port deliberately excludes it (§11.3).
- **Encryption, signing, secret material.** No field of any type in §2 holds a secret value. The
  store credential is a `secrets.Reference` resolved at the composition root (§11.4).

## 2. Contract

```go
// Package agentcheckpoint is the durable-state library of the Eden agent fleet: at every turn
// boundary it writes the turn's verbatim event segment, the harness transcript delta, the harness
// sidecar set and an incremental git bundle of the worktree, then a manifest — in that order — so
// a pod that dies loses at most one turn's WORK and no INSTRUCTION at all.
//
// Module: github.com/gophersys/libs/go/agentcheckpoint  (go 1.26)
//
// THE ARCHIVE IS THE CHECKPOINT. segment.jsonl in the turn directory IS the sealed archive
// segment. There is no separate tiering component, and a failed archive write is a FAILED
// CHECKPOINT — loud, per turn (R8, 2026-08-18).
//
// THE ORDER IS THE ATOMICITY PRIMITIVE. Object storage has no multi-object transaction and the
// frozen objectstorage port has no transaction verb, so: payload objects first, the `done` marker
// last within the turn, manifest.json last overall. A torn checkpoint has NO done marker and is
// IGNORED. Latest prefers the highest turn carrying a done marker, which makes restore
// self-healing and idempotent EVEN IF the manifest PUT itself was lost.
//
// It depends ONLY on the frozen objectstorage and gitrepository ports and adds NO edge to
// agentruntime or agentsession. It never imports github.com/minio/minio-go/v7: that SDK is
// confined to objectstorage/minioadapter (contracts/objectstorage.md §1).
//
// Concurrency: New is PURE (no I/O, no clock read, no env read). A constructed *Checkpointer is
// safe for concurrent use; Write for one (agent, session) is serialized by the caller — the turn
// boundary is already serial by definition (§4).
//
// Zero value: a zero Manifest is INVALID. Validate reports the first violated rule.
package agentcheckpoint

// ── The port (4 methods, under the 5-method ceiling — 10 §9) ──────────────────

// Store is the load-bearing surface. Four methods, because a fifth would be a verb the caller can
// already build from these: "list my checkpoints" is Latest plus the manifest's previousTurn
// chain, and "delete one turn" is a Prune with a tight bound.
type Store interface {
	// Write composes and stores ONE turn's checkpoint in the ORDER §5.2 fixes, and returns the
	// Ref that addresses it. It is the whole write path: a partial Write leaves NO done marker
	// and is therefore invisible to Latest — never a half-visible checkpoint.
	Write(ctx context.Context, checkpoint Checkpoint) (Ref, error)

	// Latest returns the manifest of the highest turn that CARRIES A DONE MARKER for this
	// (agent, session). It is deliberately not "the manifest object", because the manifest PUT
	// is the last write and may be the one that was lost; Latest reconstructs from the marker
	// set and prefers the marker over the manifest whenever the two disagree (§5.2).
	// NotFoundError when the agent/session prefix holds no completed turn.
	Latest(ctx context.Context, agent fleetenvelope.AgentID, session string) (Manifest, error)

	// Restore materializes ref into the pod's Layout: the transcript reassembled from its base
	// plus its delta chain, the sidecar set unpacked, the worktree cloned to the manifest's
	// commit. It VERIFIES every digest, and it ASSERTS manifest.WorkspacePath against the
	// Layout's derived workspace path FIRST. A mismatch is a PathMismatchError naming both
	// paths, and the caller FAILS THE POD (§8 step 3). Restore is idempotent.
	Restore(ctx context.Context, ref Ref, into Layout) error

	// Prune deletes every completed turn prefix of this agent whose retainUntil is before the
	// given instant, and publishes one lifecycle envelope per deletion (§10). It is built from
	// the frozen port's List + Delete, deliberately (§11.3), and it NEVER deletes a prefix whose
	// done marker is absent — an in-flight turn is not garbage.
	Prune(ctx context.Context, agent fleetenvelope.AgentID, before time.Time) (PruneReport, error)
}

// ── The constructor spine (10 §4) — PURE ──────────────────────────────────────

// New is the constructor spine. PURE: no I/O, no clock read, no env read, no bucket probe, no git
// invocation. It validates Config and Deps and returns the concrete *Checkpointer. The first
// object-store call is the first Store method. A missing dependency or an invalid retention bound
// is a ConfigError naming the field.
//
// (Config and Deps are the idiomatic Go exported type names HNS-1 rule 11 sanctions, and they are
// spelled EXACTLY so: hnslint fails a library that spells them Configuration/Dependencies.)
func New(configuration Config, dependencies Deps) (*Checkpointer, error)

// Checkpointer is the concrete handle New returns; it implements Store. Immutable after
// construction. The zero value is unusable.
type Checkpointer struct{ /* unexported */ }

// Config is the immutable, fully-resolved input (the configuration pattern: parsed at the edge,
// frozen). It holds NO live handles and NO secret values.
type Config struct {
	Bucket        string        // the fleet bucket, e.g. "eden-agents". This library never CREATES it (§11.3).
	Agent         fleetenvelope.AgentID // the pod's durable identity; prefixes every key
	StateRoot     string        // the per-pod harness state root the Layout is derived from (§7)
	WorkspaceRoot string        // the per-pod workspace root the Layout is derived from (§7)
	Retention     time.Duration // the TIME bound; 0 is a ConfigError, never a silent default (§10)
	MaxBucketBytes int64        // the SIZE bound, the second and independent ceiling (§10)
	Harness       Harness       // WHICH harness this pod runs: claude-code | omp | codex. Data, not a port.
}

// Deps is the injected hexagon (ADR-0009 A). Every field is required; a nil port is a New-time
// ConfigError. Note what is ABSENT: no agentruntime, no agentsession, no minio-go, no fleetbus
// client. The library is handed ports, never clients.
type Deps struct {
	Objects    objectstorage.ObjectStore  // THE FROZEN FIVE-METHOD PORT (§11). The only store edge.
	Provision  gitrepository.Provisioner  // Clone — the restore half of the workspace (§8 step 5)
	Inspect    gitrepository.Inspector    // Status — HEAD commit + clean flag at the turn boundary
	Author     gitrepository.Author       // Commit(AllowEmpty) — the marker commit (§4.3)
	Bundles    Bundler                    // git bundle create/apply. OPEN FORK F5 (§14).
	Files      HarnessFiles               // the local-filesystem port over the harness state root
	Lifecycle  LifecyclePublisher         // where a pruner deletion is announced (§10)
	Clock      Clock                      // the library's ONLY time source
}

// ── The consumer-defined ports (each ≤5 methods, each the SHAPE OF THE NEED) ──

// HarnessFiles is the local-filesystem port over ONE pod's harness state. It is consumer-defined
// and narrow because the checkpoint's job is to move bytes, not to know a harness's layout — the
// layout is DeriveLayout's pure function (§7), not this port's business. Four methods.
type HarnessFiles interface {
	// ReadRange opens [from, to) of path. It is the byte-range DELTA primitive that makes an
	// every-turn cadence affordable at all (§4.2), and it is why the transcript is never tarred.
	ReadRange(ctx context.Context, path string, from, to int64) (io.ReadCloser, error)

	// Digest reports sha256 over the FIRST prefix bytes of path, plus path's current full size.
	// The prefix digest is the P-CKPT-1 guard (§4.4): a mismatch on the next turn means the
	// harness REWROTE its file, and the writer escalates to a full upload, loudly.
	Digest(ctx context.Context, path string, prefix int64) (Digest, error)

	// Archive streams the named directories as one tar.zst. Used for the sidecar set only —
	// never for the transcript, which is a delta (§4.2).
	Archive(ctx context.Context, directories []string) (io.ReadCloser, error)

	// Extract unpacks an Archive stream under into. Used only on the restore path.
	Extract(ctx context.Context, body io.Reader, into string) error
}

// Bundler is the git-bundle port. TWO methods, and it exists because the FROZEN gitrepository
// surface has no bundle verb — Provisioner is Clone/AddWorktree/RemoveWorktree, Inspector is
// Status/Diff/Branches/Worktrees, Author is Stage/Commit/Fetch/Push, and Backend is already AT the
// 5-method ceiling (✅ contracts/gitrepository.md §2). This is open fork F5 (§14); the
// recommendation follows codeinsight's precedent of owning a narrow local port with its own
// system-git adapter rather than revising a frozen baseline (✅ contracts/codeinsight.md §2).
type Bundler interface {
	// Create writes an INCREMENTAL bundle of (basis, tip] for worktree at path into.
	// basis == "" produces a FULL bundle. The bundle MUST be created against a NAMED ref, never
	// a bare rev-range — see the false-green in §13.4.
	Create(ctx context.Context, worktree string, basis, tip gitrepository.CommitID, into string) (BundleInfo, error)

	// Apply fetches one bundle into an existing checkout and returns the tip it brought. It
	// asserts the tip is REACHABLE afterwards; it never trusts an exit code (§13.4).
	Apply(ctx context.Context, bundlePath string, into string) (gitrepository.CommitID, error)
}

// LifecyclePublisher is where a pruner deletion is announced. ONE method, so the library gains no
// bus dependency: the composition root binds it to the fleet write plane, and a test binds it to a
// recorder. The audit trail records its own erasure (§10).
type LifecyclePublisher interface {
	PublishLifecycle(ctx context.Context, actor fleetenvelope.Actor, intent fleetenvelope.Intent, body string) error
}

// Clock is the injected time source. The library never reads the wall clock (spine purity, 10 §4).
type Clock interface{ Now() time.Time }

// ── The values ────────────────────────────────────────────────────────────────

// Checkpoint is ONE turn's input to Write: everything the caller knows that the library cannot
// derive. It carries no bytes — the library reads those through HarnessFiles and Bundler.
type Checkpoint struct {
	Session        string    // the eden session name; the key segment and the Layout selector
	Turn           int       // the session's turn ordinal; 1-based, monotonic
	PreviousTurn   int       // 0 == this is the first checkpoint of the session
	Reason         Reason    // ReasonTurnEnd | ReasonDrain | ReasonOperator
	HarnessResumeID string   // the harness-native session id Spec.ResumeFrom will be set to (§8 step 6)
	Segment        []byte    // the VERBATIM envelopes of this turn, newline-delimited JSON
	Cursor         Cursor    // the stream/inbox/per-session positions to resume from (§6)
	Ledger         Ledger    // this turn's cost and token accounting
}

// Reason is the closed taxonomy of why a checkpoint was written. Append-only (10 §9).
type Reason uint8

const (
	ReasonTurnEnd  Reason = iota // the ONLY routine cause: agentsession.EventTurnEnd (§4.1)
	ReasonDrain                  // a graceful shutdown drained the in-flight turn
	ReasonOperator               // a human or a policy asked for one out of band
)

// Ref addresses ONE completed checkpoint: an agent, a session and a turn. It is loggable (no
// credential, no payload) and comparable. The zero value is invalid; NewRef validates the shape.
type Ref struct{ /* unexported: agent, session, turn */ }

// NewRef constructs a validated Ref. Pure; no I/O.
func NewRef(agent fleetenvelope.AgentID, session string, turn int) (Ref, error)

// ObjectRef renders one of this checkpoint's keys as the FROZEN objectstorage value type. It is
// the ONE place the key grammar of §5 becomes a store address, so the grammar has one home.
// Pure; no I/O. It is also how a fleetenvelope.ArtifactRef is turned into an objectstorage.ObjectRef
// — the seam contracts/fleetenvelope.md §5 delegates here.
func (r Ref) ObjectRef(bucket string, part Part) (objectstorage.ObjectRef, error)

// Part names one artifact of a turn. Closed, append-only.
type Part uint8

const (
	PartSegment    Part = iota // turns/<turn:08d>/segment.jsonl
	PartTranscript             // turns/<turn:08d>/transcript.delta
	PartSidecar                // turns/<turn:08d>/sidecar.tar.zst
	PartBundle                 // turns/<turn:08d>/workspace.bundle
	PartDone                   // turns/<turn:08d>/done          — the completeness marker
)

// Layout is the pod's derived, PINNED filesystem shape for one session. It is produced by
// DeriveLayout and it is a PURE FUNCTION of (stateRoot, workspaceRoot, session) — which is what
// makes --resume find its session after a restore onto a different node (§7).
type Layout struct {
	Session       string
	HarnessRoot   string // <stateRoot>/<session>/harness
	WorkspacePath string // <workspaceRoot>/<session>/workspace   — the REQUIRED manifest field
	TranscriptPath string // the harness's append-only transcript, derived per harness (§7)
	SidecarDirs   []string // the harness's per-session state directories (§7)
}

// DeriveLayout is THE PATH CONTRACT, made executable. PURE: no I/O, no env read, no clock read.
// Identical inputs give identical paths in every pod on every node, which is the property §7's
// false-green depends on. An invalid session name or a relative root is an InvalidError.
func DeriveLayout(stateRoot, workspaceRoot, session string, harness Harness) (Layout, error)

// Harness names WHICH harness a pod runs. Closed taxonomy, append-only. It selects the transcript
// path and the sidecar set inside DeriveLayout, and it is recorded in the manifest so a restore
// into a pod running a different harness FAILS rather than half-works.
type Harness uint8

const (
	HarnessClaudeCode Harness = iota // claude-code
	HarnessOmp                       // omp
	HarnessCodex                     // codex
)

// Digest is a sha256 witness plus the size it was taken over. Never a payload, never a credential.
type Digest struct {
	SHA256     string // "sha256:<lowercase-hex>"
	SizeBytes  int64  // the FULL current size of the file the digest was taken from
	PrefixBytes int64 // the prefix the SHA256 covers; == SizeBytes for a whole-file digest
}

// PruneReport is what Prune returns and what the escalation envelope carries. Counts and bytes,
// never a key list of unbounded length — the per-deletion detail rides the lifecycle envelopes.
type PruneReport struct {
	PrefixesDeleted int
	BytesReclaimed  int64
	BytesRemaining  int64
	SizeForced      bool // true == the SIZE bound fired and deleted inside the retention period
}

// ── Errors (typed, errors.AsType-first, aligned with contracts/errors.md) ─────
//
// Each is a distinct type carrying the offending value — never a payload, never a credential —
// and each maps to a stable errors.Kind from the canonical set, so a caller branches on TYPE and
// never on a message substring (contracts/errors.md; 10 §9 rule 12).
type (
	// ConfigError reports an invalid Config or a nil Deps field.            -> errors.KindInvalid
	ConfigError struct{ Field string }

	// TornError reports a turn prefix whose done marker is absent or whose object set is
	// incomplete. It is the ORDER primitive's typed voice (§5.2).          -> errors.KindConflict
	TornError struct {
		Turn    int
		Missing string // the key that was expected and is not there
	}

	// PathMismatchError reports manifest.workspacePath != the pod's derived workspace path. It
	// NAMES BOTH, because the operator's next question is always "which one is wrong?". This is
	// the §8 step 3 refusal — the single most important line in the restore path.
	//                                                                      -> errors.KindConflict
	PathMismatchError struct{ Expected, Actual string }

	// DigestMismatchError reports a restored object whose bytes do not match the manifest's
	// witness. A restore that cannot verify its digest chain FAILS THE POD. -> errors.KindConflict
	DigestMismatchError struct{ Key, Expected, Actual string }

	// PrefixRewrittenError reports that the harness transcript's prefix digest changed — the
	// P-CKPT-1 escape (§4.4). It is RAISED, COUNTED and then HANDLED by a full upload; it is
	// never swallowed, because a silent full upload hides that the append-only assumption broke.
	//                                                                      -> errors.KindConflict
	PrefixRewrittenError struct {
		Path      string
		BaseBytes int64
	}

	// NotFoundError reports an agent/session prefix with no completed turn. -> errors.KindNotFound
	NotFoundError struct{ Agent, Session string }

	// BudgetExceededError reports that the HARD bucket ceiling was reached and the pruner had to
	// delete inside the retention period (§10).                           -> errors.KindExhausted
	BudgetExceededError struct{ Bytes, Ceiling int64 }
)
```

The `errors.Kind` values above are the canonical set from `contracts/errors.md` ✅ (`KindCanceled`,
`KindConflict`, `KindDeadline`, `KindExhausted`, `KindInternal`, `KindInvalid`, `KindNotFound`,
`KindPermission`, `KindUnauthenticated`, `KindUnauthorized`, `KindUnavailable`, `KindUnknown`).
No new `Kind` is introduced by this contract.

## 3. THE ARCHIVE IS THE CHECKPOINT — ruling R8

> ✅ **R8 (2026-08-18), verbatim:** *"There is no separate tiering component. `segment.jsonl` in the
> turn directory IS the sealed archive segment, written at the turn boundary the fleet already
> proves. **A failed archive write is a failed checkpoint — loud, per turn.**"*

This dissolves a component rather than building one, and that is the point. A separate archiver is
a background process with its own cadence, its own failure mode and its own silence: it rots
because nothing on the hot path notices when it stops. Folding the archive INTO the checkpoint
makes the archive's health identical to the checkpoint's health, and the checkpoint's health is
already load-bearing — a pod that cannot checkpoint cannot survive a restart, so it fails loudly
by construction. One health signal instead of two, and the weaker of the two cannot go quiet.

**Three shapes were REFUSED outright** ✅ (2026-08-18), and each refusal is recorded here so it is
not rediscovered:

| Refused | Why |
| --- | --- |
| a JetStream object-store transit bucket | *"couples checkpoint backpressure to the audit PVC"* — the checkpoint would stall on the audit plane's disk pressure, which is a failure of one subsystem propagating into the survival of another |
| a per-turn tar of the harness store | *"REFUTED by measurement"* — see §4.2; the numbers are reproduced there because a refusal without its measurement is an opinion |
| Longhorn for anything | 🧩 ruled out for the fleet. (Adjacent ✅: Longhorn was REMOVED as a MinIO consumer on 2026-08-19 — `infrastructure/apps/minio/README.md`.) |

**Consequence for `Write`.** There is no partial success. If the segment object does not land, the
turn is not checkpointed, and `Write` returns an error the pod surfaces — it does not log-and-
continue. This is FAIL-NOT-SKIP at the library boundary: a checkpoint that quietly did nothing is
worse than no checkpoint, because it is believed.

## 4. Cadence and composition

### 4.1 The cadence is `EventTurnEnd`, per session

> ✅ **The ruling (2026-08-18), verbatim:** *"The ONLY event that means 'the harness is idle and the
> turn is authoritative'. At the turn boundary the harness is quiescent by definition, no process is
> mid-write, and omp's sqlite WAL is consistent. **The checkpoint is written BEFORE the turn is
> acknowledged upward.**"*

⚠️ **CORRECTION to the fleet brief.** The brief states that `EventTurnEnd` *"arrives from the
messaging program's PR-1a"* and that the fleet is sequenced after it. Measured against libs
`origin/main`, **`EventTurnEnd` already exists today** ✅:

- `go/agentsession/types.go:260` declares it — *"a TURN reached a clean end: carries that turn's
  authoritative `TokenLedger` and final text, and parks the session in `StateAwaitingInput` — NOT a
  session terminal"*;
- `go/agentsession/claudeadapter/normalize.go:538` emits it from the claude result line;
- `go/agentruntime/runtime.go:140` already branches on `event.Kind == agentsession.EventTurnEnd`.

So the cadence event is **not** a dependency the fleet waits on. What PR-1a adds is the json-tag /
`MarshalText` serialization work `contracts/fleetenvelope.md` §8 records as `agentsession` revision
R2 — invisible to `.apibaseline` and therefore recorded by hand. The checkpoint hook can be
authored against a member that is already on the wire.

**Why the checkpoint precedes the acknowledgement.** If the turn were acked first and the pod died
before the write, the instruction that produced the turn would be gone from the inbox AND the
turn's state would be gone from the store — the one combination that loses work with no record.
Writing first inverts the failure: the worst case is a turn that is REPLAYED, never one that
VANISHES (§9).

### 4.2 Two measured facts decide the shape

**(a) The claude transcript is APPEND-ONLY, so the checkpoint is a byte-range DELTA, not a tar.**

The transcript lives at `$HOME/.claude/projects/<cwd-slug>/<harnessSessionID>.jsonl`.

> ✅ **The design's measurement (2026-08-18), verbatim:** *"1.8 GB across 12 sessions; the largest
> single .jsonl is 141 MB"*, the next four being 27/22/15/13 MB — and *"At 141 MB x 40 turns a
> per-turn tar is 5.6 GB of writes for ONE session… **THE DELTA IS NOT AN OPTIMISATION — it is the
> only shape that fits an every-turn cadence at all.**"*

✅ **RE-MEASURED for this document on this machine, 2026-08-26** — the argument holds and has grown
stronger, and two of the design's incidental numbers are corrected:

```
TOTAL              2.0 GB under ~/.claude/projects        (design said 1.8 GB — it grew)
LARGEST .jsonl     167,739,465 B  = 160 MiB               (design said 141 MB — it grew)
NEXT FOUR          119.6 MB · 22.6 MB · 22.2 MB · 19.8 MB
CWD-SLUG DIRS      42                                     (design said "12 sessions" — that count
                                                           is SESSIONS; the directory axis is 42)
IMPLIED WORST CASE 160 MiB x 40 turns = 6.4 GiB of writes for ONE session, per-turn-tar
```

The conclusion is unchanged and the margin is wider: a per-turn tar of a 160 MiB transcript is
~6.4 GiB of writes per session per day, against a ~40 KiB delta. 🔶 The delta is the only shape
that fits.

**(b) The workspace is ONE git worktree, so the workspace checkpoint is git-native.**

The frozen `gitrepository` contract already anticipates exactly this use: ✅
`CommitOptions.AllowEmpty` is documented *"permit a commit with an empty index (rare; **e.g. a
checkpoint/marker commit**)"* (`contracts/gitrepository.md` §2). So the turn boundary can always
produce a commit — even a turn that changed nothing — and the incremental bundle's size is the
diff, not the tree.

⚠️ **Gitignored files are deliberately NOT captured, and that is a decision, not an oversight.**
A git-native workspace checkpoint captures exactly what git tracks. Build outputs, `node_modules`,
`.venv`, downloaded caches and `.env` files are therefore lost on restore. Three reasons make that
the right call rather than a gap: (i) they are reproducible from what IS captured, and a restore
that reproduces them is a restore that proves they were reproducible; (ii) capturing them would
put untracked, unreviewed and possibly SECRET-BEARING bytes into a durable audit store, which is
exactly the material `contracts/secrets.md` exists to keep out of surfaced artifacts; (iii) it
would silently uncap the budget of §12, since `.gitignore` is where a repository puts the things
that are large. 🧩 The cost is stated so nobody discovers it during an incident: **a restored pod
must re-run its build.**

### 4.3 What one turn writes

| Artifact | Content | Source | Mutability |
| --- | --- | --- | --- |
| `segment.jsonl` | the VERBATIM envelopes of this turn | `Checkpoint.Segment`, zstd | immutable |
| `transcript.delta` | bytes `[prevOffset..now]` of the harness `.jsonl` | `HarnessFiles.ReadRange` | immutable |
| `sidecar.tar.zst` | the `<sessionID>/` + `file-history/` dirs | `HarnessFiles.Archive` | immutable |
| `workspace.bundle` | git bundle since the previous commit | `Bundler.Create` after `Author.Commit(AllowEmpty)` | immutable |
| `done` | the completeness marker | written LAST within the turn | immutable |
| `manifest.json` | the pointer to all of the above | written LAST overall | **the only mutable object** |

### 4.4 P-CKPT-1 is a LANDING CONDITION, not a note

The probe *"is the claude transcript strictly append-only under all conditions"* came back
**INCONCLUSIVE**. ⚠️ It is therefore RUN as an exit criterion of the implementation slice, not
carried as an assumption.

**The design does not depend on the answer, and this is the model for how to depend on an unproven
measurement safely.** The manifest records, for the transcript, `{baseBytes, basePrefixDigest}` —
a sha256 over the first `baseBytes` of the file. On the NEXT turn the writer re-digests that same
prefix before reading the new range:

- **prefix matches** → the file is still append-only at that offset; write a `transcript.delta`.
- **prefix MISMATCHES** → the harness REWROTE its file. The writer raises
  `PrefixRewrittenError`, **increments a counter, raises a health condition, and falls back to a
  FULL UPLOAD** — loudly. The checkpoint still succeeds; what changes is that the estate now knows
  the assumption broke, with a number attached, on the turn it broke.

🔶 The pattern generalizes: *depend on a measurement only where a cheap witness can detect that it
stopped being true, and make the detection LOUD rather than the fallback silent.* A design that
merely assumed append-only would degrade into corruption; this one degrades into cost, with an
alarm.

## 5. The key grammar and the ordering / atomicity primitive

### 5.1 The grammar

```
eden-agents/agents/<agentID>/sessions/<sessionID>/
  turns/<turn:08d>/segment.jsonl        the VERBATIM envelopes of this turn      immutable
  turns/<turn:08d>/transcript.delta     bytes [prevOffset..now] of the .jsonl    immutable
  turns/<turn:08d>/sidecar.tar.zst      the <sessionID>/ + file-history/ dirs    immutable
  turns/<turn:08d>/workspace.bundle     git bundle since the previous commit     immutable
  turns/<turn:08d>/done                 the completeness marker, written LAST    immutable
  artifacts/sha256-<hex>                spilled payloads (content-addressed)     immutable
  manifest.json                         THE ONLY MUTABLE OBJECT (atomic PUT)
  deleted.json                          written by the finalizer; carries retainUntil
```

Notes that are load-bearing:

- **`<turn:08d>` is zero-padded to eight digits** so lexical order IS numeric order. The frozen
  port's `List(ctx, bucket, prefix)` returns objects by key; without the padding, `Latest` would
  have to parse and sort every key rather than reading the tail.
- **`agentID` is `fleetenvelope.AgentID`**, cited, never redefined. It is controller-minted and
  restart-surviving, which is exactly why it can prefix a durable key.
- **`sessionID` is the eden session name**, not the harness-native id. The harness-native id is a
  manifest FIELD (`harnessResumeId`), because it is the harness's business and it changes shape
  per harness.
- **`deleted.json` is a tombstone, not a deletion record for the audit trail.** The audit record of
  an erasure is the published lifecycle envelope (§10); `deleted.json` is the finalizer's own
  bookkeeping so a re-run of the pruner is idempotent.

⚠️ **The `artifacts/` prefix shown above is SESSION-level, and the design contradicts itself.**
The same design places spilled artifacts at `agents/<agentID>/artifacts/sha256-<hex>` in one
section and under `.../sessions/<sessionID>/artifacts/` in another. **This document adopts the
AGENT-level form** — `agents/<agentID>/artifacts/sha256-<hex>` — because content-addressing only
dedups across sessions if the prefix is SHARED, and an agent that spills the same 300 KiB tool
result in four sessions should store it once. The session-level form stores it four times and
calls it content-addressing. **The adoption is normative in this document and it is ALSO open fork
F1 (§14)**, because the design does not settle it and the freeze is where Mateo settles it.

⚠️ **A THIRD spelling exists and is not the same string.** `docs/plans/eden-rework-blueprint.md`'s
deferred object-store leg names *"content-addressed `artifact/<sha256>`"* ✅ — singular directory,
bare hex, no `sha256-` prefix. Fork F1 must close on ONE spelling across the fleet grammar, the
`fleetenvelope.ArtifactRef.Reference` value and the blueprint's product grammar, or three documents
will describe three different keys for one object.

### 5.2 THE ORDER IS THE ATOMICITY PRIMITIVE

Object storage has no multi-object transaction, and the frozen `objectstorage.ObjectStore` has no
transaction verb — its five methods are `Put`, `Get`, `Delete`, `Presign`, `List` ✅
(`contracts/objectstorage.md` §2). A checkpoint is five objects plus a manifest. So atomicity
cannot be bought; it must be CONSTRUCTED, and the only material available is ORDER.

**The rule, and it has no exceptions:**

```
1..4   the payload objects        segment · transcript.delta · sidecar.tar.zst · workspace.bundle
5      the `done` marker          LAST WITHIN THE TURN
6      manifest.json              LAST OVERALL (a single atomic PUT of a small object)
```

Three properties fall directly out of that order, and the third is the elegant one:

1. **A torn checkpoint has NO `done` marker, and is IGNORED.** Any crash during steps 1-4 leaves a
   turn prefix with some objects and no marker. `Latest` never returns it; `Restore` refuses it
   with `TornError` naming the missing key; `Prune` never deletes it, because an unmarked prefix
   may be an IN-FLIGHT turn rather than garbage. Torn state is inert, not dangerous.

2. **`Latest` prefers the highest turn carrying a `done` marker** — it reads the MARKER SET, not
   the manifest. The marker is a zero-or-few-byte object whose mere existence is the whole
   assertion, so the window in which it can be half-written is as small as the store allows.

3. **RESTORE IS SELF-HEALING AND IDEMPOTENT EVEN IF THE MANIFEST PUT ITSELF WAS LOST.**
   This is the single most valuable property of the design, and it is worth stating as a
   theorem. Suppose the pod dies between step 5 and step 6 of turn N. The manifest still points at
   turn N-1. Naively, turn N is lost. But `Latest` does not read the manifest to decide WHICH turn
   is current — it reads the marker set, sees turn N marked done, and rebuilds turn N's manifest
   from the objects the marker guarantees are all present. **The manifest is therefore a CACHE of
   a fact the key space already carries, not the fact itself.** A cache that can be lost without
   losing the fact is a cache you never have to make transactional — which is precisely why this
   design needs no transaction verb and therefore needs no revision of the frozen port.

   🔶 The corollary is a constraint on every future change: **the manifest may never become the
   sole home of anything.** The moment a field exists only in `manifest.json` and cannot be
   recomputed from the turn prefix, property 3 dies quietly and nothing tests for it. §13 makes
   that a conformance property, not a comment.

## 6. The manifest

```json
{
  "agentId": "agent-01jbq7...", "sessionId": "session-claude-code-implementer-a1b2c3d4",
  "turn": 12, "previousTurn": 11, "writtenAt": "2026-08-18T22:31:05Z",
  "reason": "turn-end",                        // turn-end | drain | operator
  "workspacePath": "/state/main/workspace",    // REQUIRED
  "harness": "claude-code",                    // claude-code | omp | codex
  "harnessResumeId": "0f3d...",
  "cursor": {
    "streamSeq": 918233,                       // the JetStream RESUME cursor
    "inboxSeq": 41,                            // last CONSUMED inbox stream seq
    "perSession": {"session-...": 4471}        // the per-session transcript offsets
  },
  "state": [
    {"kind":"append-delta","key":"turns/00000012/transcript.delta",
     "baseBytes":2546964,"length":41220,
     "basePrefixDigest":"sha256:1e60d7fb...","sha256":"sha256:aa12..."},
    {"kind":"file-set","key":"turns/00000012/sidecar.tar.zst","sha256":"sha256:bb34..."}
  ],
  "workspace": {"bundleKey":"turns/00000012/workspace.bundle",
                "commit":"9a1c...", "basis":"7d2e...",     // "" == a full bundle
                "sha256":"sha256:cc56..."},
  "ledger": {"costMicros":412300,"inputTokens":918233,"outputTokens":41221}
}
```

### 6.1 Field semantics

| Field | Required | Meaning, and what a wrong value costs |
| --- | --- | --- |
| `agentId` | ✅ | `fleetenvelope.AgentID`, cited. Restoring into a pod with a different `AgentID` is a different agent wearing this one's memory; `Restore` refuses. |
| `sessionId` | ✅ | the eden session name. It selects the `Layout`, so it is also a PATH input (§7). |
| `turn` / `previousTurn` | ✅ | the delta chain's links. `previousTurn == 0` means the chain starts here. A gap in the chain is a `TornError` on restore, never a silent skip. |
| `writtenAt` | ✅ | the injected `Clock` instant, UTC. It is the input to `retainUntil` (§10), so it is never a wall-clock read inside the library. |
| `reason` | ✅ | `turn-end` \| `drain` \| `operator`. Present so an operator reading the store can tell a routine checkpoint from a shutdown from a manual one. |
| `workspacePath` | ✅ **REQUIRED** | the absolute worktree path this checkpoint was taken at. It is the field §7's false-green depends on, and §8 step 3 asserts it before anything else. |
| `harness` | ✅ | `claude-code` \| `omp` \| `codex`. It selects the transcript path and sidecar set in `DeriveLayout`, so restoring into a pod running a different harness fails rather than half-works. |
| `harnessResumeId` | ✅ | the value `agentsession.Spec.ResumeFrom` is set to on reopen ✅ (`libs/go/agentsession/agentsession.go`, `Spec.ResumeFrom` — *"harness-native session id to re-attach (empty == fresh)"*). Empty means the session cannot be resumed and the pod must say so, not start fresh silently. |
| `cursor.streamSeq` | ✅ | the JetStream RESUME cursor for the read plane. |
| `cursor.inboxSeq` | ✅ | the last CONSUMED inbox stream seq. It is what makes the un-acked instruction redeliver rather than duplicate (§9). |
| `cursor.perSession` | ✅ | per-session transcript offsets. A pod hosts 1..N sessions; one cursor per session. |
| `state[]` | ✅ | the artifacts and their digests. See §6.2 — the closed set of `kind` is NOT settled. |
| `workspace.commit` | ✅ | the worktree tip this checkpoint restores to. |
| `workspace.basis` | ✅ (may be `""`) | the bundle's prerequisite. `""` means a FULL bundle, which is how a chain starts and how it recovers. |
| `ledger` | ✅ | the turn's cost/token accounting, carried so the cost record survives the pod. |

**Schema.** `$id` is `eden://protocol/agentfleet/v1/checkpoint-manifest`, generated from the Go
types into `libs/protocols/agentfleet/v1/checkpoint-manifest.schema.json` and drift-gated by the
`schema` dimension `contracts/fleetenvelope.md` §8 adds to `phase-gate architecture`. There is no
`schemaVersion` FIELD, consistent with that document's ruling that the version lives in the `$id`
and the `v1` path segment.

⚠️ **`libs/protocols/` does NOT exist on libs `origin/main`** and must be created by the first lane
that writes a schema. Measured 2026-08-26: `git -C libs ls-tree origin/main --name-only` lists
`go plugins templates typescript` and no `protocols`; the directory's `.gitkeep` survives only at
the STALE submodule pin `50940e1` (301 commits behind `origin/main`), where it was later deleted.
A sibling contract records the directory as *"today holds only `.gitkeep` ✅"*, which is true of the
stale working tree and false of `origin/main` — the exact trap of reading a 301-commit-stale
submodule instead of `git show origin/main:<path>`.

### 6.2 ⚠️ OPEN — the closed set of `state[].kind` is not settled

Only two values appear in the design — `append-delta` and `file-set` — while §4.4's prefix-mismatch
fallback produces an artifact that is neither: a FULL transcript upload, with no `baseBytes` and no
`basePrefixDigest`, that a restorer must NOT try to append to a base. Encoding it as `append-delta`
with `baseBytes: 0` would work mechanically and would be the wrong shape, because the restorer
would then distinguish two genuinely different artifacts by inspecting a numeric field rather than
by reading a name — the `Intent(0)` default-on-unknown mistake in a different costume.

Recorded as **open fork F2 (§14)** with the recommendation: **three members —
`append-delta` · `full-upload` · `file-set`** — closed at three, a fourth being a contract revision.

## 7. The pod filesystem and the PURE-FUNCTION PATH CONTRACT

```
/state/<sessionName>/harness/     -> the per-session harness state root
/state/<sessionName>/workspace/   -> the git worktree, and the omp session store
```

**PER-SESSION SUBDIRECTORIES ARE STRUCTURAL, NOT TIDY.** 1..N sessions share a pod. Two sessions
that share one directory share one state store, and a shared state store is where one session's
`--resume` re-attaches another session's conversation.

> **THE PATH IS A PURE FUNCTION AND IT IS PART OF THE CONTRACT.**
> `workspace = /state/<sessionName>/workspace` -> `cwd-slug = "-state-<sessionName>-workspace"`

✅ **The `<cwd-slug>` rule is directly MEASURED, not inferred.** `~/.claude/projects/` on this
machine, 2026-08-26, holds directories named `-Users-mateo`, `-Users-mateo-code-eden` and
`-Users-mateo-Music` — the absolute start directory with `/` replaced by `-`. The slug is a pure
function of the CWD, which is why pinning the CWD pins the transcript directory.

### 7.1 The false-green this prevents

Restore a session onto a pod whose workspace path differs by one character, and `--resume` does not
error. It starts a FRESH conversation. Then: the pod boots, the session opens, the heartbeat
reports `Running`, the CR goes `Running`, the dashboard is green — **and the agent has no memory of
anything it did.** Every signal the estate has says healthy; the one thing that mattered is gone.
This is the same class as `.claude/rules/git-process.md` §12's unverified CI profile and §9's
frozen tracker: a check that cannot fail, believed because it is green.

The refusal is mechanical: `workspacePath` is a **REQUIRED** manifest field, and §8 step 3 asserts
it before any byte is restored, failing the pod with `PathMismatchError` naming both paths.

### 7.2 Harness state, measured — and two corrections

**CLAUDE.** `$HOME/.claude/projects/<cwd-slug>/<harnessSessionID>.jsonl` (append-only, subject to
P-CKPT-1) + the `.../<harnessSessionID>/` sidecar directory + `$HOME/.claude/file-history/
<harnessSessionID>/`. The documented relocation lever is **`CLAUDE_CONFIG_DIR`**.

⚠️ **CORRECTION — the lever is not wired, and there is no per-session seam for it today.**
Measured against libs `origin/main`: `CLAUDE_CONFIG_DIR` appears in **zero** Go files, and
`claudeadapter/spawn.go:38` builds the child environment as `injectEnvironment(os.Environ(), cred)`
— the adapter scrubs and injects exactly the credential variable and passes everything else
through. There is likewise **no `StateRoot` field on `agentsession.Spec`** ✅ (`agentsession.go:92`
— the fields are `Workspace`, `Routing`, `Grants`, `HostTools`, `Credential`, `Budget`,
`ResumeFrom`, `SystemHints`, `OnPermission`, `PermissionResolution`, `PermissionTimeout`, `Name`,
`Parent`). The brief's `agentsession.Spec.StateRoot` does not exist. This is open fork F6 (§14).

**OMP.** ⚠️ **Two corrections, both measured at `libs origin/main`:**

- The store root is **`.omp`**, not `.omp-session` ✅ (`ompadapter.go:34`:
  `const sessionStoreDir = ".omp"`, with the comment *"the store ROOT the adapter names inside the
  provisioned workspace. Only the root: the layout below it is omp's"*). It is placed via
  `PI_CODING_AGENT_DIR` ✅ (`ompadapter.go:30`). It is **WORKSPACE-relative, not HOME-relative** —
  confirmed.
- **omp is structurally UNRESUMABLE today, and `CapResume=Full` is OVER-CLAIMED.** ✅
  `ompadapter.go:196-201`:

  ```go
  func sessionArguments(resumeFrom string) []string {
      if resumeFrom != "" { return []string{"--resume", resumeFrom} }
      return []string{"--no-session"}
  }
  ```

  The FIRST run always has `resumeFrom == ""`, so it emits `--no-session` and persists nothing —
  and there is therefore never an id for a later run to resume from. Meanwhile
  ✅ `ompadapter.go:111` declares `agentsession.CapResume: agentsession.CapFull`. The capability
  manifest asserts a capability the code cannot deliver. **Fixing it is a LANDING CONDITION on the
  omp half of this library: without it, `agentcheckpoint`'s omp recovery obligation is vacuous** —
  a restore would faithfully replace an `.omp` directory that was never written, and O3 would pass
  over an agent that starts fresh every time.

**CODEX.** A third subdirectory under the same state root. The manifest's `harness` enum is
`claude-code | omp | codex`.

### 7.3 ⚠️ The isolation axis, stated more precisely than the brief

The brief attributes O9 to per-session STATE ROOTS. Measured, the mechanism is finer and the
conclusion is stronger:

- For **claude**, the isolation axes are `(cwd-slug, harnessSessionID)`. Two sessions with distinct
  WORKSPACES already land in distinct `projects/<cwd-slug>/` directories even inside one
  `CLAUDE_CONFIG_DIR`, and the transcript file is keyed by harness session id inside that.
- For **omp**, the store is workspace-relative (`<workspace>/.omp`) and there is **no id axis at
  all**, because `--no-session` persists none.

**Therefore the structural requirement is ONE WORKSPACE PER SESSION, and it is driven by omp, not
by claude.** Sharing a workspace collapses omp's only isolation axis entirely. A per-session
harness state root is desirable (it makes the checkpoint's `sidecar.tar.zst` a clean per-session
set) but it is the WEAKER of the two requirements, and it is the one that currently has no seam.
🔶 That distinction is what makes fork F6's recommended option — one pod-level `CLAUDE_CONFIG_DIR`
plus per-session workspaces — sufficient for O9 without revising a frozen contract.

## 8. Restore — the seven steps

1. **The pod boots with `EDEN_CHECKPOINT_RESTORE=<ref>`.** Absent, the pod starts fresh; present
   and unresolvable, the pod FAILS — never a silent fresh start.
2. **`Latest` (or the pinned ref)** → **prefer the highest turn carrying a `done` marker** (§5.2).
3. **ASSERT `manifest.workspacePath` == the pod's derived workspace path. A mismatch FAILS THE POD,
   naming both.** This is the single most important line in the restore path, and it runs BEFORE
   any byte is fetched — a restore that has already written half a transcript before discovering it
   is in the wrong pod has made the failure more expensive without making it more visible.
4. **Reassemble the transcript** from the base plus the delta chain, **verifying every digest**;
   unpack the sidecar set; place both under the pinned state root. A `full-upload` member (fork F2)
   RESETS the chain rather than appending to it.
5. **Restore the workspace** by applying the bundle chain up to `workspace.commit`, then asserting
   the tip is reachable.
6. **ONLY THEN open the session** with `Spec.ResumeFrom = harnessResumeId`. Opening earlier races
   the harness against the restore: claude would create a fresh transcript at the very path step 4
   is writing.
7. **Resume the streams**: publish at `perSession[sessionID]+1`; the read plane at `streamSeq+1`;
   the inbox consumer at `inboxSeq+1`.

**A restore that cannot verify its digest chain FAILS THE POD.** There is no degraded restore, no
best-effort partial, no "restore what verifies and log the rest". An agent operating on a
half-restored memory is the failure mode this library exists to prevent, and a partial restore
produces exactly it while reporting success.

**What rides the frozen `gitrepository` port, and what does not** — stated because the brief says
the workspace half "rides this port" and the frozen surface only half-supports that:

| Step | Verb | On the frozen port? |
| --- | --- | --- |
| turn-boundary marker commit | `Author.Commit(..., CommitOptions{AllowEmpty: true})` | ✅ yes, and explicitly anticipated |
| turn-boundary tip + clean flag | `Inspector.Status` | ✅ yes |
| restore into a fresh checkout | `Provisioner.Clone(ctx, remote, dir, options)` | ✅ yes — a bundle FILE PATH is a valid `remote` (proven, §13.4) |
| **bundle CREATION** | — | ❌ **NO VERB EXISTS.** Open fork F5 (§14) |
| **applying a bundle CHAIN** | `Author.Fetch` cannot, in practice | ❌ `FetchOptions.Remote` is a logical name from `Config.Remotes`, fixed at `New`; an N-bundle chain of run-time paths cannot be pre-declared |

🧩 The recommendation keeps the chain in ONE home: `Bundler` does both `Create` and `Apply`, even
though `Clone` could do the first hop. Splitting the chain across two ports to save one method
would put half of a single mechanism behind a frozen contract and half behind a local one.

## 9. THE RECOVERY FLOOR

> **AT MOST ONE TURN'S WORK IS LOST. NO INSTRUCTION IS LOST.**

Four statements make that floor honest rather than aspirational:

- **WORK.** Neither claude nor omp exposes a mid-turn state handle, so the in-flight turn cannot be
  resumed. This is **STRUCTURAL, not a shortcut** — and it is exactly why the cadence is the turn
  boundary (§4.1). A finer cadence would not buy a finer floor; it would only write more objects
  for the same guarantee.
- **INSTRUCTION.** The message that started the lost turn sits UN-ACKED on the durable inbox stream
  and is REDELIVERED to the restored pod, because the checkpoint precedes the acknowledgement.
  *"So the honest floor is ONE TURN REPLAYED, never silently dropped."*
- **RECORD.** Every event already published survives on the events plane, so the RECORD of the lost
  turn exists even though the harness's MEMORY of it does not. Those are different things and
  conflating them is how "we lost the turn" becomes "we have no idea what happened".
- **RECONCILIATION.** A resumed agent is told, **by a synthetic `IntentAnswer` injected before its
  first new turn**, that its last turn was interrupted. ✅ `IntentAnswer` is a member of
  `fleetenvelope.Intent` (`contracts/fleetenvelope.md` §2), cited here, not invented. *"Without
  that note it re-runs work it cannot remember but whose side effects (files, commits) already
  exist."* 🔶 This is the one place the recovery floor depends on the AGENT reading a message
  rather than on a mechanism, and it is recorded as such: the mechanism guarantees the note is
  DELIVERED; it cannot guarantee the note is HEEDED.

## 10. Retention and the pruner

**ONE fleet configuration value** in the controller ConfigMap, **default 30 days**, overridable per
`AgentTeam` and per `Agent` (tighten or extend only — an override may not remove the bound).

**TWO BOUNDS, because a period alone does not bound a runaway:**

| Bound | Rule | What it catches |
| --- | --- | --- |
| **TIME** | delete every completed turn prefix past `retainUntil` | ordinary growth |
| **SIZE** | a **HARD 20 GiB bucket ceiling**; past it the pruner deletes oldest-first **REGARDLESS of period** and publishes an escalation | a runaway that fills the disk in three days, which the period alone would not notice until day 31 |

The SIZE bound returns `PruneReport{SizeForced: true}` and a `BudgetExceededError` to the caller.
It is not a silent adjustment: deleting data inside its stated retention period is a policy
violation the estate must SEE, even when it is the correct emergency action.

**Every pruner action publishes its own `IntentLifecycle` envelope** with
`Actor{Kind: ActorSystem, ID: "retention-pruner"}` naming the prefix and the byte count —
**"the audit trail records its own erasure."** 🔶 This is the property that makes retention
auditable rather than merely automatic: without it, the difference between "the pruner deleted
turn 40" and "turn 40 was never written" is invisible after the fact.

⚠️ **`ActorSystem` and `IntentLifecycle` must be verified against the frozen `fleetenvelope`
taxonomies at freeze.** As of this drafting, `fleetenvelope`'s `ActorKind` set and its `Intent` set
are themselves in DRAFT and moving. If neither member exists, the pruner rides the nearest existing
members and this sentence becomes the record of why — it is a PROPOSAL, not a fact.

**OD-9 stays OPEN, and it rules the VALUE, not the MECHANISM.** ✅ The register reads:
*"OD-9 | **Transcript retention & privacy policy** (per-project retention, redaction verification) |
needs ruling before any non-Mateo user exists. | L4"* (`docs/architecture/open-decisions.md:21`).
The fleet closes OD-9 **only for the agent-transcript retention class** and leaves the human-data /
redaction-verification half explicitly open. Mateo is asked to confirm 30 days (90 would also fit
the §12 budget) — recorded as **open fork F3 (§14)**, not settled here.

⚠️ **A SECOND HOME RISK, named rather than absorbed.** `docs/plans/eden-rework-blueprint.md`
defers **`objectStore.retentionDays`** as a CHART key, reopening when *"the object-store leg brings
the first non-barman writer"* ✅ — and this library IS that writer. The same row warns: *"a second
key would be a second home for one policy."* Putting retention in the controller ConfigMap while
the chart grows `objectStore.retentionDays` creates exactly that. **Open fork F4 (§14).**

## 11. Binding to the FROZEN `objectstorage` port — and why not MinIO

### 11.1 The port is the guarantee; the vendor is not

`agentcheckpoint` speaks ONLY the frozen five-method `objectstorage.ObjectStore` port — `Put`,
`Get`, `Delete`, `Presign`, `List` ✅ (`contracts/objectstorage.md` §2, at the 5-method ceiling).
It never imports `github.com/minio/minio-go/v7`; that SDK is imported in EXACTLY ONE compilation
unit, `objectstorage/minioadapter` ✅ (same contract, §1: *"The SDK … is imported in EXACTLY ONE
place, the `minioadapter` sub-package; the root package is SDK-free"*).

**Every store-facing statement in this document is a statement about the PORT.** The word "MinIO"
appears only where today's operational binding or the successor risk is being described — never as
a guarantee.

The reason is a measured fact with a ruling attached: MinIO's upstream is **ARCHIVED**
(`archived=true`, last push 2026-04-24) and the successor is an **OPEN DECISION** ✅
(Mateo, 2026-08-18 Batch A: *"MinIO proceed v1 behind the frozen objectstorage port + successor
decision opened separately"*). A contract that named MinIO as a guarantee would have to be revised
the day the successor is chosen; one that names the port does not. That is not caution — it is the
difference between a contract revision and a `Deps` change.

⚠️ **Drift found in the frozen contract while binding to it.** `contracts/objectstorage.md` §2
writes `func New(configuration Config, dependencies Deps) (*Store, error)` and calls the concrete
type `*Store`, while the mechanically-recorded freeze witness says otherwise: ✅
`libs/go/objectstorage/.apibaseline` (read at `origin/main`) lists
`func New(configuration Config, dependencies Deps) (*Client, error)` and `type Client struct{ ... }`.
There is no exported `Store` type. **This document binds to `*Client` and to the `ObjectStore`
INTERFACE, which is the name both agree on.** The contract text is stale against its own baseline;
correcting it is `objectstorage`'s change, not this one, and is flagged here rather than silently
worked around.

### 11.2 Today's operational binding, stated as a binding

MinIO runs at `minio.minio.svc:9000`, `hostPath /mnt/media/minio` on the NVMe of `k3s-w-1`, single
replica, `strategy: Recreate` ✅ (`infrastructure/apps/minio/README.md`). Its README today reads
*"It has **1** consumer"* — music-studio's restic repository. The fleet makes two, and that README
is stale the moment this library ships. 🔶 The successor risk is therefore concrete and small: the
fleet's dependency is one `Deps.Objects` binding and one bucket, and a successor swaps the adapter.

### 11.3 The pruner is DELIBERATELY our code, and bucket CREATION stays an operator concern

✅ The frozen contract states the exclusion: *"It does **not** provide: bucket lifecycle
(create/delete bucket), policy/ACL management, multipart-upload orchestration, server-side-
encryption key management, or versioning — those are operator/adapter concerns off the consumer
port."*

Two consequences, and both are the RIGHT call rather than a workaround:

- **The pruner is built from `List` + `Delete`.** Object lifecycle policies are a per-vendor
  feature with per-vendor semantics; expressing retention through one would make the fleet's
  deletion behaviour depend on which store is behind the port — the precise coupling §11.1 exists
  to prevent. Building it from the two verbs the port DOES guarantee makes retention identical on
  MinIO, on a successor, and on the in-memory fake, which is also what makes it TESTABLE (§13).
  It costs a few hundred lines and buys vendor-independence and a fake binding; a lifecycle policy
  costs zero lines and buys an untestable behaviour that changes with the vendor.
- **Bucket CREATION stays with the operator.** `eden-agents` is created once, by the same hand that
  creates the scoped user and the quota. A library that creates its own bucket has to hold a
  credential that CAN create buckets, and that credential is strictly more powerful than the one
  §11.4 scopes. Keeping creation out is what lets the fleet's credential be read-write on ONE
  bucket and nothing else.

Neither is a port revision, and neither should become one.

### 11.4 The credential route

A scoped store user **`eden-fleet`**, **read-write on the `eden-agents` bucket ONLY**, seeded into
the eden Vault by extending `infrastructure/apps/eden/08-vault-seed-job.yaml`, and resolved through
the **FROZEN `secrets.Provider`** ✅ (`contracts/secrets.md` §2 — one method, `Resolve(ctx,
Reference) (*Secret, error)`, the value never entering a `Config`, a log or an error) as
`vault://eden/production#minio-access-key` / `#minio-secret-key`. The shape matches the frozen
reference grammar ✅ (`contracts/secrets.md`: *"raw is the canonical form, e.g.
`vault://eden/connectors/github#token`"*).

**The root `minio-creds` never leaves its own namespace.** ✅ Measured: `minio-creds` is a Secret in
namespace `minio` (`infrastructure/apps/minio/10-deployment.yaml:11,37`). The eden namespace never
holds it, and no eden pod can read it. The fleet gets a user it can be revoked without touching the
store's root.

✅ Measured: `08-vault-seed-job.yaml` today seeds JWT signing keys, the connectors KEK, the database
DSNs and the optional harness fields, and **mentions MinIO nowhere** — a `grep -n minio` over it
returns nothing. Extending it is additive, and it must follow the job's own only-if-absent
discipline so a reseed never rotates a live credential.

**Presigned-PUT is RECORDED as the named escape hatch, not taken now.** The port has `Presign`, so
the seam exists the day a payload is large enough that streaming it through the pod is the wrong
shape. Taking it now would add a URL-expiry lifetime, a clock-skew failure mode and a second
credential path for zero measured benefit at the §12 volumes.

⚠️ **A tension with the blueprint, named rather than resolved by silence.**
`docs/plans/eden-rework-blueprint.md` defers *"eden's remaining Vault surface — the connectors KEK,
harness credentials, the per-team connector store (ADR-0029), and the `vault://eden/<stage>#<field>`
reference shape"*, reopening when *"the fleet leg lands. It is the fleet's credential plumbing, and
it migrates to the `secrets` contract (ESO/Bitwarden) **with** it rather than half-now."* ✅ So the
fleet leg is simultaneously the trigger for seeding this credential into Vault AND the trigger for
migrating that whole surface OFF Vault. **Open fork F8 (§14)**, with the recommendation that
seeding behind the frozen `secrets.Provider` makes the migration a BINDING change rather than a
contract change — which is the whole reason the reference is opaque.

## 12. The storage budget

Reproduced because it is what makes the ceilings falsifiable. A ceiling with no budget behind it is
a number somebody liked.

```
PER TURN, PER SESSION  transcript delta ~40 KiB · sidecar ~20 KiB · incremental bundle ~50 KiB
                       · segment (40 events x 4 KiB, zstd) ~35 KiB · manifest ~2 KiB
                       ~150 KiB typical · ~600 KiB p95
RATE                   N pods x 12 turns/h x 8 h/day
AT N=4                 384 turns/day => ~60 MiB/day typical, ~245 MiB/day worst
AT 30 DAYS             1.8 GiB typical · 7.2 GiB worst
CEILINGS               eden-agents 20 GiB HARD, against 82 GiB measured free (4x at the ceiling,
                       45x at typical) · Node ephemeral 2.5 GiB per pod
```

🔶 What the budget is FALSIFIED BY, stated so the numbers can be checked rather than believed:

- a measured per-turn total above ~600 KiB p95 at N=4 breaks the 30-day worst case;
- a P-CKPT-1 prefix mismatch turns one turn's ~40 KiB delta into a full transcript upload —
  at today's largest measured transcript (160 MiB, §4.2) a single fallback is **~270 times** the
  typical daily volume for one pod. The counter §4.4 raises is therefore also a BUDGET alarm, not
  only a correctness alarm, and that is a second reason it may not be silent;
- ⚠️ the *"82 GiB measured free"* figure is a property of the `k3s-w-1` NVMe behind
  `hostPath /mnt/media/minio` ✅ and is NOT re-verified in this document. It is carried as the
  design's measurement, and it is the one number here that a cluster change can invalidate without
  anything noticing.

## 13. Fake and conformance

### 13.1 The two-binding suite

`agentcheckpointtest` is the public fake package (10 §4, `contracts/testing.md`). The exported
suite follows the house signature exactly ✅ — `objectstoragetest.RunStoreSuite(t *testing.T,
newStore func() objectstorage.ObjectStore, ...)`, read from `libs/go/objectstorage/.apibaseline`
at `origin/main`:

```go
func RunStoreSuite(t *testing.T, newStore func() agentcheckpoint.Store, ...)
```

It runs the SAME property set over an in-memory fake `objectstorage.Backend` ✅
(`objectstoragetest.NewBackend() *Backend`, which already exists) AND, in the
`//go:build integration` lane, over the real store. **The fake weakens the SOURCE of bytes, never
the contract.**

The properties, each stated as a refutation rather than a happy path:

1. `Write` then `Latest` returns THIS turn's manifest, and `Restore` reproduces every byte.
2. **A `Write` interrupted before the `done` marker is INVISIBLE to `Latest`** — asserted by
   injecting a Backend that fails the marker `Put`, not by inspecting a success.
3. **A `Write` interrupted before the MANIFEST `Put` is still returned by `Latest`** — the §5.2
   property 3 theorem, tested directly. This is the property that would rot silently otherwise.
4. Every field of the manifest is RECOMPUTABLE from the turn prefix — the §5.2 corollary, asserted
   by deleting `manifest.json` and requiring `Latest` to return an identical value.
5. A delta chain with a missing link is `TornError` naming the missing key, never a partial restore.
6. A corrupted object is `DigestMismatchError`, and `Restore` leaves the target UNTOUCHED.
7. A `workspacePath` mismatch is `PathMismatchError` naming BOTH paths, raised BEFORE any write.
8. A prefix-digest mismatch produces a full upload AND increments the counter AND raises the
   condition — all three, because any one alone is a silent degrade.
9. `Prune` never deletes an unmarked prefix, and publishes exactly one lifecycle envelope per
   deleted prefix.
10. The SIZE bound deletes inside the period AND sets `SizeForced` AND returns
    `BudgetExceededError`.
11. `DeriveLayout` is pure and total: same inputs, same paths, no panic on adversarial session
    names (a `rapid` property).
12. No surfaced error, no manifest and no log contains the seeded credential canary ✅
    (`objectstoragetest.SeededCredentialCanary`).

### 13.2 The three conformance obligations, each with its break-test

Each must be seen RED first. A property that has never failed is a property nobody has tested.

| # | Obligation | Break-test that must turn it RED |
| --- | --- | --- |
| **O3** | checkpoint → `kill -9` → recover loses AT MOST ONE TURN | move the hook off `EventTurnEnd` → turn N-1 is lost |
| **O9** | two sessions in ONE pod, interleaved, each replayable, neither state store collides | share one StateRoot **and one workspace** → session B's `--resume` attaches session A (see §7.3 — the workspace is the axis that actually collapses) |
| **O13** | restore into a DIFFERENT absolute path FAILS LOUDLY, never silently starts fresh | unpin `workspacePath` → `--resume` starts fresh, with everything green |

These run on a **REAL claude session AND a REAL omp session** in a `fleet-live` lane.
**FAIL-NOT-SKIP is absolute: a missing live credential FAILS and NAMES the variable. NO SKIP PATH
EXISTS.** A `t.Skip` here would produce a green lane that proved nothing about the only three
properties that matter — the exact defect `.claude/rules/git-process.md` §10 and §12 catalogue.

⚠️ **O3 and O9 cannot pass for omp until §7.2's landing condition lands.** Stated here so the lane
is not authored, run, and believed against a harness that persists nothing.

### 13.3 A conformance obligation the suite must ADD

**O-BUNDLE: an incremental bundle restore must assert the RESTORED COMMIT, never the exit code.**
See §13.4 — this is not a hypothetical.

### 13.4 ✅ EXECUTION-PROVEN, and it found a false-green

Run on this machine, 2026-08-26, in a scratch repository:

- `git clone <full.bundle> <dir>` restores a repository from a bundle. **A bundle file path is a
  valid `remote` argument**, which is what lets restore's first hop ride the frozen
  `gitrepository.Provisioner.Clone` verb unchanged.
- `git fetch <incremental.bundle> '+refs/heads/main:refs/remotes/bundle/main'` replays an
  incremental bundle onto it: `* [new branch] main -> bundle/main`, and the commit count goes
  1 → 2.
- ⚠️ **THE FALSE-GREEN.** A bundle created from a bare rev-range — `git bundle create inc.bundle
  <base>..HEAD` — records its ref as `HEAD`, not as `refs/heads/<branch>`. Fetching it with a
  `refs/heads/*` refspec then **exits 0, prints nothing, and adds zero commits**, while
  `git bundle verify` reports *"is okay"*. Two green signals over a restore that restored nothing.
  Creating the bundle against a NAMED ref — `git bundle create inc.bundle <base>..refs/heads/main`
  — fixes it, and `git bundle list-heads` then shows `refs/heads/main`.

  This is precisely the failure class §7.1 describes, discovered in the mechanism itself rather
  than in the design. It is why `Bundler.Create` REQUIRES a named ref and `Bundler.Apply` asserts
  reachability of the returned tip — and why O-BUNDLE exists.

## 14. Open forks — what Mateo must rule on, or delegate

| # | Fork | Options (recommendation first) | Blocks |
| --- | --- | --- | --- |
| **F1** | **The spilled-artifact prefix, and its spelling.** Agent-level vs session-level; and three spellings exist across three documents — `agents/<agentID>/artifacts/sha256-<hex>` (this design), `.../sessions/<sessionID>/artifacts/...` (the same design, elsewhere), `artifact/<sha256>` (blueprint + the `fleetenvelope` seam). | (a) **AGENT-level, one spelling, closed across all three documents** — content-addressing only dedups across sessions if the prefix is SHARED; a session-level prefix stores one payload N times and still calls itself content-addressed · (b) session-level, accepting per-session duplication for a simpler lifecycle | the spill seam; the pruner's byte accounting; `fleetenvelope`'s F5 |
| **F2** | **Is `state[].kind` closed at two?** Only `append-delta` and `file-set` appear, while §4.4's fallback produces a third artifact. | (a) **three members — `append-delta` · `full-upload` · `file-set`**, closed at three; a fourth is a contract revision · (b) two members, encoding a full upload as `append-delta` with `baseBytes: 0` — rejected here because it makes a restorer distinguish two different artifacts by a numeric field rather than by a name | the manifest schema; the restore reader |
| **F3** | **The retention VALUE.** OD-9 rules the value, not the mechanism. | (a) **30 days** (the §12 budget: 1.8 GiB typical / 7.2 GiB worst at N=4, comfortably under the 20 GiB ceiling) · (b) 90 days (5.4 GiB typical / 21.6 GiB worst — the worst case EXCEEDS the ceiling, so 90 requires either a higher ceiling or accepting that the SIZE bound routinely fires) | closing the agent-transcript half of OD-9 |
| **F4** | **Retention's HOME.** Controller ConfigMap vs the chart's deferred `objectStore.retentionDays`, which the blueprint reopens on exactly this library. | (a) **the controller ConfigMap is the ONE home; the chart key is not introduced**, and the blueprint row is closed pointing here · (b) the chart key is the home and the controller reads it · (c) both — rejected: the blueprint's own words are *"a second key would be a second home for one policy"* | the controller's config surface; the chart |
| **F5** | **`git bundle create` has NO verb on the FROZEN `gitrepository` port**, and `Backend` is already AT its 5-method ceiling. | (a) **an `agentcheckpoint`-owned `Bundler` port (2 methods) with a `systemgitbundler` adapter** — the exact precedent `codeinsight` set with its own `History` port + `SystemGitHistory` adapter, keeping the frozen `.apibaseline` untouched, at the cost of a second place that shells `git` · (b) a `gitrepository` contract revision (ADR-0016 §1) adding a bundle op kind and re-recording its `.apibaseline` — cleaner long-term, but it puts a FROZEN contract into revision on this library's critical path | the whole workspace half |
| **F6** | **The per-session harness state root has NO seam.** `agentsession.Spec` has no `StateRoot`; `CLAUDE_CONFIG_DIR` appears in zero Go files; `claudeadapter/spawn.go:38` passes `os.Environ()` through. | (a) **ONE pod-level `CLAUDE_CONFIG_DIR` + per-session WORKSPACES** — sufficient for O9 (§7.3: the workspace is omp's only isolation axis and claude's slug axis), and requires NO frozen-contract change · (b) add `Spec.StateRoot` → an `agentsession` contract revision + re-recorded `.apibaseline` · (c) a per-session env seam on the adapter, below the frozen surface | O9's shape; the sidecar key set |
| **F7** | **Two bucket grammars.** The fleet's `agents/<agentID>/sessions/<sessionID>/...` vs the blueprint's deferred PRODUCT grammar `org/<id>/project/<id>/run/<id>/segment-NNNNNN.jsonl` — reopening on *"the fleet lands and needs sealed segments"*, i.e. now. | (a) **two disjoint top-level prefixes in ONE `eden-agents` bucket**, with this contract owning `agents/` and the product leg owning `org/` · (b) two buckets, two quotas, two credentials · (c) one grammar for both — rejected: the fleet key is agent-scoped and the product key is tenant-scoped, and forcing one on the other loses a dimension | the object-store leg's reopening |
| **F8** | **The credential route's direction.** The fleet leg is the trigger to SEED this credential into eden Vault and, per the blueprint, the trigger to MIGRATE that whole surface off Vault to ESO/Bitwarden. | (a) **seed Vault now behind the frozen `secrets.Provider`** — the reference is opaque, so the migration is a `Deps` binding change, not a contract change · (b) wait for the ESO/Bitwarden migration and block this library on it · (c) skip Vault and go direct to ESO for this one credential — rejected: it splits one credential plane in two | the composition root; `08-vault-seed-job.yaml` |
| **F9** | **Presigned-PUT for large payloads.** | (a) **RECORD it, do not take it** — the port has `Presign`, so the seam exists when a measurement demands it; taking it now adds a URL-expiry lifetime and a clock-skew failure mode for zero benefit at §12 volumes · (b) take it now for `artifacts/` | nothing (it is additive) |

Each fork is also recorded in `docs/architecture/open-decisions.md`, per `CLAUDE.md`'s rule that an
unmade decision lives there and never in prose alone.

**Two LANDING CONDITIONS, which are not forks — they are work that must land or an obligation is
vacuous:**

- **P-CKPT-1** — the append-only probe is RUN as an exit criterion of the implementation slice
  (§4.4). The design does not depend on the answer; the estate depends on knowing it.
- **omp `CapResume`** — `ompadapter.go:196-201` must persist a session on the first run, or
  `CapResume=Full` (`ompadapter.go:111`) stays an over-claim and O3/O9 pass over an agent that
  starts fresh every time (§7.2).

## 15. THE FREEZE QUESTION — for Mateo, and for nobody else

Freezing this contract is a `.claude/rules/git-process.md` §5 human gate. An agent may not exercise
it, and this document may not be edited to say it is frozen by anything other than Mateo's own
words quoted with a timestamp (§13 rule 4). The question is exactly this:

> **Do you freeze `agentcheckpoint` v1 at the surface in §2 — the four-method `Store` port
> (`Write` / `Latest` / `Restore` / `Prune`), the key grammar of §5 with the `done` marker written
> LAST within the turn and `manifest.json` LAST overall, `workspacePath` as a REQUIRED manifest
> field asserted before any byte is restored, the `EventTurnEnd` per-session cadence with the
> checkpoint written BEFORE the turn is acknowledged upward, the recovery floor of AT MOST ONE
> TURN'S WORK AND NO INSTRUCTION, and a binding to the FROZEN five-method `objectstorage` port
> rather than to any store — accepting that the freeze commits the fleet to building its own
> pruner over `List` + `Delete` and to landing a bundle seam that the frozen `gitrepository`
> surface does not provide?**
>
> **YES** → the surface is frozen, `.apibaseline` is recorded as the freeze witness,
> `phase-gate architecture` goes green, and the checkpoint lane starts against a fixed target.
>
> **NO, with changes** → name the forks in §14 you are ruling differently, and the draft is amended
> and re-refuted before the question is asked again.
>
> **Answering also requires ruling F1, F2 and F5**, because all three change §2's surface: F1 fixes
> a key the `ObjectRef` method renders, F2 fixes the closed set the manifest schema generates from,
> and F5 decides whether a FROZEN contract (`gitrepository`) goes into revision. **F3 and F4 may be
> delegated only together**, because they are one policy with two candidate homes. F6, F7, F8 and
> F9 may be delegated.

**A second gate rides on the same answer.** The fleet ADR is reserved at **0030** ✅ (Batch B+C,
2026-08-18: *"Fleet ADR takes number 0030 (fills the hole; messaging keeps 0032)"*) and does not
exist on disk — `docs/architecture/adr/` runs 0029 → 0031. A new ADR is separately Mateo-gated
(§5), so no agent has written it, and this contract cites the 2026-08-18 rulings directly rather
than citing an ADR that is not there. **Writing ADR-0030 is Mateo's, and it should land in the same
decision as the freeze**, so this contract's authority chain stops dangling.
