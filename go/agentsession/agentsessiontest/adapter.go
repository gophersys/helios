// Package agentsessiontest is the canonical public fake (the testing pattern,
// 10 §4 / 08 §2) plus the one conformance suite and the integration harness for the
// agentsession F4 port. The fake is a SCRIPTED, REACTIVE harness Adapter: a test feeds
// it a sequence of Events to emit and asserts over the Commands it received, so the
// kernel (engine, chat backend) tests lifecycle, ordering, Seq-replay, grant-linkage,
// budget-abort, the permission round-trip, and the credential seam WITHOUT spawning a
// real claude/omp process. An in-memory Transcript is provided so Seq/replay are real.
package agentsessiontest

import (
	"context"
	"sync"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/secrets"
)

// Adapter is a scripted, reactive agentsession.Adapter. Script is the Event sequence
// the next Spawned session emits in order; the fake drives the FULL normalized path
// (deltas, thinking, tool start/end, permission request, usage ticks, lifecycle
// transitions) with no real subprocess. It is REACTIVE: a Steer or a permission-answer
// control frame injects the matching scripted reaction so a test observes mid-stream
// effects deterministically.
//
// Concurrency: Adapter is safe for concurrent use; its recorded Commands/refs are
// appended under a mutex. One Spawn produces one *fakeConn (one session).
type Adapter struct {
	mu sync.Mutex

	script       []agentsession.Event
	capabilities agentsession.CapabilityManifest
	spawnErr     error
	nonReadying  bool

	// received records every Command the SUT sent (Prompt/Steer/Abort) across all conns.
	received []agentsession.Command
	// injectedRefs records which secrets.Reference each Spawn was asked to inject —
	// refs ONLY, never values — for the credential-flow assertions.
	injectedRefs []secrets.Reference
	// resolvedReaction is the extra script emitted after a permission answer frame
	// (the EventPermissionResolved + the continuation), keyed by request id.
	reactions map[string][]agentsession.Event
	// steerReactions is the extra script emitted after a Steer frame whose text matches
	// the key (so a test pins an observable mid-stream steer effect).
	steerReactions map[string][]agentsession.Event
}

// New returns a scripted fake whose next Spawn emits the given events in order. By
// default it declares every capability CapFull so the conformance suite exercises the
// full surface; use WithManifest to test graceful degradation.
func New(script ...agentsession.Event) *Adapter {
	return &Adapter{
		script:         script,
		capabilities:   fullManifest(),
		reactions:      make(map[string][]agentsession.Event),
		steerReactions: make(map[string][]agentsession.Event),
	}
}

// WithManifest overrides the declared capability manifest (to test CapAbsent/CapPartial
// degradation). Fluent.
func (a *Adapter) WithManifest(manifest agentsession.CapabilityManifest) *Adapter {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.capabilities = manifest
	return a
}

// OnPermissionAnswer pins the events the fake emits after the SUT answers the permission
// request requestID (the EventPermissionResolved record + any continuation). Fluent.
func (a *Adapter) OnPermissionAnswer(requestID string, events ...agentsession.Event) *Adapter {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.reactions[requestID] = events
	return a
}

// OnSteer pins the events the fake emits after a Steer frame whose text equals trigger
// (so a test observes a mid-stream steer effect deterministically). Fluent.
func (a *Adapter) OnSteer(trigger string, events ...agentsession.Event) *Adapter {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.steerReactions[trigger] = events
	return a
}

// FailSpawnWith forces the next Spawn to return err (e.g. agentsession.AuthError) — for
// the spawn-failure path (the harness process never starts). Fluent.
func (a *Adapter) FailSpawnWith(err error) *Adapter {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.spawnErr = err
	return a
}

// SpawnNonReadying makes the next Spawn SUCCEED but return a conn whose event stream
// closes WITHOUT ever emitting the Ready handshake — the silent-bad-token shape (a harness
// that starts but whose auth fails silently, exiting before confirming readiness). Unlike
// FailSpawnWith (a Spawn-error shortcut), this drives the library pump's GENUINE
// no-ready->AuthError synthesis path, so the conformance case is non-vacuous. Fluent.
func (a *Adapter) SpawnNonReadying() *Adapter {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.nonReadying = true
	return a
}

// Received returns a copy of every Command the SUT sent across all conns, under lock —
// the race-safe accessor for "did the SUT steer/abort/prompt?" assertions.
func (a *Adapter) Received() []agentsession.Command {
	a.mu.Lock()
	defer a.mu.Unlock()
	out := make([]agentsession.Command, len(a.received))
	copy(out, a.received)
	return out
}

// InjectedRefs returns a copy of the secrets.References each Spawn was asked to inject
// (refs only, never values), under lock.
func (a *Adapter) InjectedRefs() []secrets.Reference {
	a.mu.Lock()
	defer a.mu.Unlock()
	out := make([]secrets.Reference, len(a.injectedRefs))
	copy(out, a.injectedRefs)
	return out
}

// Spawn launches a scripted session. It records the injected credential reference (NOT
// the value), then starts the reactive conn that streams the script and reacts to
// control frames. It returns the forced spawn error when one is set.
//
//nolint:gocritic,ireturn // contract §2/§3: Spec is the frozen copyable input and Spawn returns the HarnessConn port — the fake mirrors the frozen seam.
func (a *Adapter) Spawn(_ context.Context, spec agentsession.Spec, _ agentsession.Route, cred agentsession.InjectedCredential) (agentsession.HarnessConn, error) {
	a.mu.Lock()
	if a.spawnErr != nil {
		err := a.spawnErr
		a.mu.Unlock()
		return nil, err
	}
	a.injectedRefs = append(a.injectedRefs, spec.Credential)
	script := make([]agentsession.Event, len(a.script))
	copy(script, a.script)
	reactions := cloneReactions(a.reactions)
	steerReactions := cloneReactions(a.steerReactions)
	nonReadying := a.nonReadying
	a.mu.Unlock()

	// The credential is resolved server-side; a real adapter would place it via
	// Secret.Use at the injection site. The fake reads NOTHING from it (it never needs
	// the value), which is exactly the credential-never-leaks guarantee: the value has
	// no path into the script, the Commands, or any emitted Event.
	_ = cred

	conn := newFakeConn(script, reactions, steerReactions, a.recordCommand)
	conn.nonReadying = nonReadying
	conn.start()
	return conn, nil
}

// Manifest reports the adapter's declared capabilities.
func (a *Adapter) Manifest() agentsession.CapabilityManifest { return a.capabilities }

// recordCommand appends a Command the SUT sent (called by the conn), under lock.
func (a *Adapter) recordCommand(command agentsession.Command) {
	a.mu.Lock()
	a.received = append(a.received, command)
	a.mu.Unlock()
}

// cloneReactions deep-copies a reaction map so each conn owns its own script.
func cloneReactions(in map[string][]agentsession.Event) map[string][]agentsession.Event {
	out := make(map[string][]agentsession.Event, len(in))
	for key, events := range in {
		copied := make([]agentsession.Event, len(events))
		copy(copied, events)
		out[key] = copied
	}
	return out
}

// fullManifest declares every capability CapFull (the default for the conformance
// suite's positive arm).
func fullManifest() agentsession.CapabilityManifest {
	return agentsession.CapabilityManifest{Capabilities: map[agentsession.Capability]agentsession.CapStatus{
		agentsession.CapSteer:              agentsession.CapFull,
		agentsession.CapResume:             agentsession.CapFull,
		agentsession.CapThinkingEvents:     agentsession.CapFull,
		agentsession.CapHostTools:          agentsession.CapFull,
		agentsession.CapNativeBudget:       agentsession.CapFull,
		agentsession.CapPermissionPrompt:   agentsession.CapFull,
		agentsession.CapPartialToolResults: agentsession.CapFull,
	}}
}

// compile-time assertion: *Adapter is an agentsession.Adapter.
var _ agentsession.Adapter = (*Adapter)(nil)
