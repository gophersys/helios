package workspaceprovider

import (
	"context"
	"io"
	"strings"
	"sync"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/secrets"
)

// workspace is the concrete Workspace the library hands the consumer. It wraps a live
// adapter Connection and owns the WORKLOAD-plane state machine the contract assigns to
// the library (not the adapter): the one-primary-workload rule, the Ready gate on
// Exec/Run, secret-resolution timing for a Run's credential, and Status normalization.
// Safe for concurrent use (the contract's concurrent-Workspace guarantee).
type workspace struct {
	handle  Handle
	conn    Connection
	clock   dependencies.Clock
	secrets secrets.Provider

	// readOnlyTargets are the absolute mount-target prefixes a Files.Put must NOT write
	// under (the read-only MountInputs clean-room guarantee, 07 §4). The LIBRARY enforces
	// the rejection so it holds on EVERY substrate, not only those whose native mount is
	// read-only (docker tmpfs is writable). Populated at Provision (the spec is known);
	// empty on an Open re-dial (the clean-room flow provisions fresh, never re-dials).
	readOnlyTargets []string

	// states enforces the documented legal State-transition set (types.go State doc) on every
	// Status read: the library — not the adapter — owns the machine, so a substrate Probe that
	// reads an impossible transition (a move OUT of terminal Gone, an edge not in the graph)
	// surfaces an IllegalStateTransitionError rather than corrupting the observed lifecycle.
	states *stateMachine

	mu      sync.Mutex
	running bool // a primary workload is live (the 1-sandbox-per-execution gate, 07 §3)
}

// Static assertion: *workspace satisfies the Workspace port.
var _ Workspace = (*workspace)(nil)

// Handle returns the durable, loggable identity of this workspace. Pure; no I/O.
func (w *workspace) Handle() Handle { return w.handle }

// Run starts the ONE primary workload. A second Run while one is Running is a
// NotReadyError (the 1-sandbox-per-execution rule). The library resolves the workload
// credential server-side and hands the adapter the un-printable Secret; the value never
// enters the RunSpec, a Handle, or a log.
//
//nolint:gocritic,ireturn // contract §2: Run takes spec by value AND returns the Run port; the surface is frozen.
func (w *workspace) Run(ctx context.Context, spec RunSpec) (Run, error) {
	w.mu.Lock()
	if w.running {
		w.mu.Unlock()
		return nil, wrapKind(&NotReadyError{Handle: w.handle, State: StateRunning, Op: "Run"})
	}
	w.running = true
	w.mu.Unlock()

	resolved, cleanup, err := w.resolveWorkload(ctx, &spec)
	if err != nil {
		w.clearRunning()
		return nil, err
	}
	defer cleanup()

	driver, rerr := w.conn.Run(ctx, spec, resolved)
	if rerr != nil {
		w.clearRunning()
		return nil, classify(rerr)
	}
	return &run{driver: driver, onTerminal: w.clearRunning}, nil
}

// Exec runs ONE command to completion. It is the synchronous, result-shaped verb. A
// timeout surfaces as DeadlineError; a context cancellation as the context's Kind.
//
//nolint:gocritic // contract §2 fixes Workspace.Exec's spec by value; the port surface is frozen.
func (w *workspace) Exec(ctx context.Context, spec ExecSpec) (ExecResult, error) {
	result, err := w.conn.Exec(ctx, spec)
	if err != nil {
		return ExecResult{}, classify(err)
	}
	return result, nil
}

// Files returns the per-workspace file accessor (Put/Get/List), wrapped so every error the
// adapter returns carries its stable Kind (the transport boundary maps it without a per-port
// table, 10 §9) AND so a write under a read-only MountInputs target is rejected by the
// library on every substrate (the clean-room guarantee, 07 §4). Pure; no I/O until a Files
// method is called.
//
//nolint:ireturn // contract §2: Files returns the Files port; the surface is frozen.
func (w *workspace) Files() Files {
	return &classifyingFiles{inner: w.conn.Files(), handle: w.handle, readOnly: w.readOnlyTargets}
}

// classifyingFiles wraps an adapter Files so a bare typed error (NotFoundError,
// NotReadyError) is re-wrapped with its Kind, and a write under a read-only target is
// rejected with a NotReadyError BEFORE the adapter is called. The library owns both so an
// adapter returns the plain typed error and the read-only guarantee holds substrate-wide.
type classifyingFiles struct {
	inner    Files
	handle   Handle
	readOnly []string
}

func (f *classifyingFiles) Put(ctx context.Context, path string, content io.Reader, mode FileMode) error {
	for _, prefix := range f.readOnly {
		if underPrefix(path, prefix) {
			return wrapKind(&NotReadyError{Handle: f.handle, State: StateReady, Op: "Files.Put(read-only MountInputs)"})
		}
	}
	return classify(f.inner.Put(ctx, path, content, mode))
}

func (f *classifyingFiles) Get(ctx context.Context, path string) (io.ReadCloser, error) {
	rc, err := f.inner.Get(ctx, path)
	if err != nil {
		return nil, classify(err)
	}
	return rc, nil
}

func (f *classifyingFiles) List(ctx context.Context, path string) ([]FileEntry, error) {
	entries, err := f.inner.List(ctx, path)
	if err != nil {
		return nil, classify(err)
	}
	return entries, nil
}

// Status normalizes the adapter's raw Probe into a Status: the library stamps Since from
// the injected Clock (so New stays pure and the fake is deterministic), enforces the legal
// State-transition machine (rejecting an impossible transition the substrate reported), and
// carries the native phase verbatim in Detail without leaking it into the State/Condition enums.
func (w *workspace) Status(ctx context.Context) (Status, error) {
	probe, err := w.conn.Probe(ctx)
	if err != nil {
		return Status{}, classify(err)
	}
	if w.states != nil && !w.states.observe(probe.State) {
		// The substrate Probe read a State the library's machine forbids transitioning INTO from
		// the last-observed State (a move out of terminal Gone, or an edge not in the documented
		// graph). The library owns the machine, so this is rejected rather than reported as a
		// corrupt lifecycle read.
		return Status{}, wrapKind(&IllegalStateTransitionError{Handle: w.handle, From: w.states.last(), To: probe.State})
	}
	return Status{
		State:      probe.State,
		Conditions: probe.Conditions,
		Usage:      probe.Usage,
		Detail:     probe.Detail,
		Since:      w.clock.Now(),
	}, nil
}

// resolveWorkload resolves a Run's credential reference server-side and returns a
// Resolved carrying only the Workload slot, plus a cleanup that Zeroizes it after Run
// returns.
func (w *workspace) resolveWorkload(ctx context.Context, spec *RunSpec) (Resolved, func(), error) {
	if spec.Credential.IsZero() {
		return Resolved{}, func() {}, nil
	}
	sec, err := w.secrets.Resolve(ctx, spec.Credential)
	if err != nil {
		return Resolved{}, func() {}, classifySecret(err)
	}
	return Resolved{Workload: sec}, sec.Zeroize, nil
}

// underPrefix reports whether path lies at or under the directory prefix (an absolute
// mount target). It guards the read-only inputs targets in Files.Put.
func underPrefix(path, prefix string) bool {
	if path == prefix {
		return true
	}
	if !strings.HasSuffix(prefix, "/") {
		prefix += "/"
	}
	return strings.HasPrefix(path, prefix)
}

// clearRunning releases the one-primary-workload gate (called on Run failure and at a
// workload's terminal status).
func (w *workspace) clearRunning() {
	w.mu.Lock()
	w.running = false
	w.mu.Unlock()
}

// run is the concrete Run the library hands the consumer. It wraps an adapter RunDriver
// and releases the workspace's one-primary-workload gate exactly once at terminal.
type run struct {
	driver     RunDriver
	once       sync.Once
	onTerminal func()
}

// Static assertion: *run satisfies the Run port.
var _ Run = (*run)(nil)

// Status blocks until the next status transition or ctx; ok=false at terminal. At a
// terminal phase it releases the workspace's one-primary-workload gate exactly once.
func (r *run) Status(ctx context.Context) (RunStatus, bool) {
	status, ok := r.driver.Status(ctx)
	if !ok || status.Phase.IsTerminal() {
		r.once.Do(r.onTerminal)
	}
	return status, ok
}

// Logs streams the workload's combined stdout/stderr from cursor.
func (r *run) Logs(ctx context.Context, from LogCursor) (io.ReadCloser, error) {
	rc, err := r.driver.Logs(ctx, from)
	if err != nil {
		return nil, classify(err)
	}
	return rc, nil
}
