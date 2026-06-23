// Package workspaceprovidertest is the canonical public fake + the conformance suite +
// the REAL-SUBSTRATE harnesses for workspaceprovider (the testing pattern, 10 §4 / 08 §2).
// It owns the three things C23 demands as a deliverable, in one package so a consumer
// imports one thing:
//
//	(a) a deterministic in-memory FAKE Adapter (and a one-call FakeProvider) — no daemon,
//	    no cluster — so ANY consumer (S2's orchestrator, the F4 agentsession adapter, the
//	    engine's clean-room harness, the chat editor backend) unit-tests its logic against
//	    the port in microseconds without a substrate;
//
//	(b) the ONE conformance ProviderSuite every adapter runs against a REAL substrate
//	    (ADR-0016 — never a mock); the fake runs it too (the fake ≡ adapter closure, 08 §2); and
//
//	(c) the REAL-SUBSTRATE HARNESSES (the C23 deliverable, ruling Q3): EphemeralContainer
//	    (spins one throwaway container on the docker daemon), K3dCluster (the DEFAULT distro)
//	    and KindCluster (the SECOND conformance target), each returning a live Adapter bound
//	    to its substrate and reaping everything on t.Cleanup.
package workspaceprovidertest

import (
	"bytes"
	"context"
	"io"
	"sort"
	"strings"
	"sync"
	"time"

	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// Adapter is a deterministic in-memory workspaceprovider.Adapter. It models the State
// machine for real (so a SUT exercises ordering, idempotency, NotFound-after-Teardown),
// mounts (an in-memory FS), egress (records allowlists for assertion), resource limits
// (records them; can be told to OOMKill a run), and the credential seam (records which
// secrets.References were injected — refs ONLY, never values). Spawns NO process and
// dials NO substrate, so a consumer test runs in microseconds. Configurable manifest for
// graceful-degradation tests. Safe for concurrent use. Deterministic.
type Adapter struct {
	// Capabilities is the manifest the adapter reports (set via NewAdapter's varargs, or
	// overridden directly for graceful-degradation tests).
	Capabilities workspaceprovider.CapabilityManifest
	// Provisioned is an append-only log of the WorkspaceSpecs Create saw — for "was a
	// workspace with this egress/limits/tenancy-key requested?" assertions.
	Provisioned []workspaceprovider.WorkspaceSpec
	// Destroyed records the Handles torn down (idempotency + leak assertions).
	Destroyed []workspaceprovider.Handle
	// InjectedRefs records every secrets.Reference injected (refs only) — the
	// carries-refs-never-values guarantee, runnable.
	InjectedRefs []secrets.Reference

	mu         sync.Mutex
	clock      func() time.Time
	state      map[string]*fakeWorkspace // keyed by Handle.String()
	failNext   error
	oomNext    bool
	deniedHost map[string]bool
	watchSinks []chan workspaceprovider.WatchEvent // live Watch streams (supervision conformance)
	failWatch  error                               // when set, Watch errors immediately (the partial-failure-reap test)
}

// fakeWorkspace is the in-memory native object the fake Adapter models.
type fakeWorkspace struct {
	handle    workspaceprovider.Handle
	spec      workspaceprovider.WorkspaceSpec
	createdAt time.Time
	files     map[string][]byte
	readOnly  map[string]bool // path prefix -> read-only (MountInputs)
	running   bool
	oomKilled bool // the workload-pod (Entrypoint) OOM-kill the supervised Probe surfaces (OD-15-a)

	// editorRealized records whether the adapter co-located the READ-ONLY editor sidecar for a
	// workspace whose spec.Editor was non-nil (ADR-0027). It is the fake's observable analog of the
	// real adapters adding the editor container + the read-only workdir mount (kubernetes) / the
	// `--volumes-from …:ro` sibling (docker). Create sets it from realizeEditor(spec); the
	// conformance case asserts it so a spec.Editor that is silently dropped is a FAILURE, not a
	// fake pass. (TDD: false until the Create body realizes the sidecar — the RED-before-green seam.)
	editorRealized bool

	// forcedStates is a scripted sequence of native States the Probe returns one-per-call (the
	// LAST entry sticks once exhausted). It lets a conformance case drive the workspace through an
	// ILLEGAL transition (e.g. Gone -> Ready) so the LIBRARY's State-machine guard is exercised —
	// the doc-claimed legal-transition invariant turned into an executed test (finding #5).
	forcedStates []workspaceprovider.State
}

// Static assertions: *Adapter is a workspaceprovider.Adapter; *fakeWorkspace's connection
// is a Connection.
var (
	_ workspaceprovider.Adapter    = (*Adapter)(nil)
	_ workspaceprovider.Connection = (*fakeConnection)(nil)
)

// NewAdapter builds a ready, empty in-memory Adapter declaring caps as CapFull (and every
// other capability CapAbsent). Pass the capabilities the fake should model; omit one to
// drive a graceful-degradation (Skip) path in the conformance suite.
func NewAdapter(caps ...workspaceprovider.Capability) *Adapter {
	manifest := workspaceprovider.CapabilityManifest{
		Capabilities: map[workspaceprovider.Capability]workspaceprovider.CapStatus{},
		Distro:       "in-memory fake",
	}
	for _, c := range caps {
		manifest.Capabilities[c] = workspaceprovider.CapFull
	}
	return &Adapter{
		Capabilities: manifest,
		clock:        time.Now,
		state:        map[string]*fakeWorkspace{},
		deniedHost:   map[string]bool{},
	}
}

// defaultCaps is the full capability set a vanilla fake declares — everything CapFull, so
// the conformance suite exercises every gated case against the fake by default.
func defaultCaps() []workspaceprovider.Capability {
	return []workspaceprovider.Capability{
		workspaceprovider.CapExecPTY,
		workspaceprovider.CapPersistentVolume,
		workspaceprovider.CapBindMount,
		workspaceprovider.CapEgressPolicy,
		workspaceprovider.CapResourceLimits,
		workspaceprovider.CapLogStream,
		workspaceprovider.CapMultiTenant,
		workspaceprovider.CapReattach,
		workspaceprovider.CapSupervise,
		workspaceprovider.CapWorkloadPod,
		workspaceprovider.CapEditorSidecar,
	}
}

// Create provisions an in-memory native object. It records the spec, the injected refs
// (refs only), and honors a forced failure. ROLLBACK is trivial here (nothing is left on
// a failure). It returns a HandleData whose Connection drives Run/Exec/Files/Status.
//
//nolint:gocritic // contract §3/§2 fixes Adapter.Create's spec/resolved by value; the port surface is frozen.
func (a *Adapter) Create(_ context.Context, spec workspaceprovider.WorkspaceSpec, resolved workspaceprovider.Resolved) (workspaceprovider.HandleData, error) {
	a.mu.Lock()
	defer a.mu.Unlock()

	a.Provisioned = append(a.Provisioned, spec)
	a.recordRefs(&spec, resolved)

	if a.failNext != nil {
		err := a.failNext
		a.failNext = nil
		return workspaceprovider.HandleData{}, err
	}

	handle := a.handleFor(&spec)
	ws := &fakeWorkspace{
		handle:    handle,
		spec:      spec,
		createdAt: a.clock(),
		files:     map[string][]byte{},
		readOnly:  map[string]bool{},
	}
	for i := range spec.Mounts {
		if spec.Mounts[i].ReadOnly || spec.Mounts[i].Kind == workspaceprovider.MountInputs {
			ws.readOnly[spec.Mounts[i].Target] = true
		}
	}
	// Model the credential seam: write each resolved MountSecret's VALUE into the in-memory FS
	// at its Target (mirroring the real adapters, which write a 0600 file / mount a 0400 secret
	// volume). The value is read via Secret.Use (the sole read path) and stored ONLY as the
	// file's bytes — never echoed into a recorded Spec/Handle/ref (the no-leak scan covers
	// those), so caseMountSecret can `cat` the Target and the no-leak assertion still holds.
	a.writeMountSecrets(ws, &spec, resolved)
	// Realize the read-only editor sidecar where the spec requested one (ADR-0027). TDD-RED: the
	// realization body lands in the implementation phase; until then realizeEditor reports
	// not-yet-realized, so caseEditorSidecar (which asserts the sidecar IS realized) is RED.
	ws.editorRealized = realizeEditor(&spec)
	a.state[handle.String()] = ws
	return workspaceprovider.HandleData{Handle: handle, Connection: a.connFor(ws)}, nil
}

// realizeEditor reports whether the fake co-located the read-only editor sidecar for spec (the
// observable caseEditorSidecar asserts, mirroring the real adapters' editor container + read-only
// workdir mount, ADR-0027). It is the RED-before-green seam: it returns false for now (the editor
// sidecar is NOT yet realized), so a spec.Editor request is observably unsatisfied and the
// conformance case FAILS — the implementation phase replaces this body with the real realization.
func realizeEditor(_ *workspaceprovider.WorkspaceSpec) bool {
	return false
}

// EditorRealized reports whether the fake realized the read-only editor sidecar for the workspace
// named by handle (ADR-0027). The conformance caseEditorSidecar reads it so a dropped spec.Editor
// is a FAILURE, not a fake pass. False for an unknown handle.
func (a *Adapter) EditorRealized(handle workspaceprovider.Handle) bool {
	a.mu.Lock()
	defer a.mu.Unlock()
	if ws, ok := a.state[handle.String()]; ok {
		return ws.editorRealized
	}
	return false
}

// writeMountSecrets stores each resolved MountSecret's value at its Target in the in-memory FS,
// reading the value via Secret.Use (the sole read path). It models the real adapters' write of
// the secret material into the workspace at the mount Target.
//
//nolint:gocritic // resolved mirrors the frozen Resolved seam; spec is pointer-passed for its Mounts.
func (a *Adapter) writeMountSecrets(ws *fakeWorkspace, spec *workspaceprovider.WorkspaceSpec, resolved workspaceprovider.Resolved) {
	for i := range spec.Mounts {
		if spec.Mounts[i].Kind != workspaceprovider.MountSecret {
			continue
		}
		secret := resolved.Mounts[spec.Mounts[i].Target]
		if secret == nil {
			continue
		}
		_ = secret.Use(func(plaintext []byte) error { //nolint:errcheck // the fake stores a copy; Use only fails on a zeroized secret, which the library never hands here.
			ws.files[spec.Mounts[i].Target] = append([]byte(nil), plaintext...)
			return nil
		})
	}
}

// Dial re-attaches to an existing in-memory workspace. NotFoundError if gone.
func (a *Adapter) Dial(_ context.Context, handle workspaceprovider.Handle) (workspaceprovider.HandleData, error) {
	a.mu.Lock()
	defer a.mu.Unlock()
	ws, ok := a.state[handle.String()]
	if !ok {
		return workspaceprovider.HandleData{}, &workspaceprovider.NotFoundError{Handle: handle}
	}
	return workspaceprovider.HandleData{Handle: handle, Connection: a.connFor(ws)}, nil
}

// List enumerates the in-memory workspaces matching selector's tenancy labels.
func (a *Adapter) List(_ context.Context, selector workspaceprovider.Selector) ([]workspaceprovider.Descriptor, error) {
	a.mu.Lock()
	defer a.mu.Unlock()
	out := make([]workspaceprovider.Descriptor, 0, len(a.state))
	for _, ws := range a.state {
		if !matchesLabels(ws.spec.Labels, selector.Labels) {
			continue
		}
		state := workspaceprovider.StateReady
		if ws.running {
			state = workspaceprovider.StateRunning
		}
		out = append(out, workspaceprovider.Descriptor{
			Handle:    ws.handle,
			Name:      ws.spec.Name,
			Substrate: ws.handle.Substrate(),
			State:     state,
			Labels:    ws.spec.Labels,
			CreatedAt: ws.createdAt,
		})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out, nil
}

// Destroy removes the in-memory workspace. IDEMPOTENT (absent == nil).
func (a *Adapter) Destroy(_ context.Context, handle workspaceprovider.Handle) error {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.Destroyed = append(a.Destroyed, handle)
	delete(a.state, handle.String())
	return nil
}

// Manifest reports the configured capability manifest.
func (a *Adapter) Manifest() workspaceprovider.CapabilityManifest { return a.Capabilities }

// FailProvisionWith forces the NEXT Create to return err (a typed workspaceprovider error,
// e.g. &QuotaExceededError{} / &IsolationError{} / &ImageError{}), then resets.
func (a *Adapter) FailProvisionWith(err error) *Adapter {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.failNext = err
	return a
}

// FailWatchWith makes every Watch return err (starting no goroutine), so a Provider fanned over a
// HEALTHY adapter + this one exercises the library's partial-failure reap: the healthy adapter's
// already-started watcher must be canceled, not leaked (finding #6). Stays set (a watch fault is
// persistent until cleared).
func (a *Adapter) FailWatchWith(err error) *Adapter {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.failWatch = err
	return a
}

// OOMKillRun makes the next Run terminate as RunKilled / ConditionOOMKilled (the
// after-delay is modeled as "at the terminal transition"), so a consumer drives the
// runaway-agent path without a real substrate. The delay argument is accepted for
// signature parity with the contract's §3 sketch; the fake applies it at terminal.
func (a *Adapter) OOMKillRun(_ time.Duration) *Adapter {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.oomNext = true
	return a
}

// DenyEgressTo records host as default-denied so a workload "dialing" it surfaces
// ConditionEgressDenied in the modeled Status.
func (a *Adapter) DenyEgressTo(host string) *Adapter {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.deniedHost[host] = true
	return a
}

// MarkOOMKilled flags the workspace named by handle as OOM-killed so its supervised Probe surfaces
// ConditionOOMKilled (the workload-pod / Entrypoint discriminator the OD-15-a model delivers — on
// the fake the kill attaches to the readable workspace, mirroring the kubelet's reason on a real
// Entrypoint pod). A no-op for an unknown handle.
func (a *Adapter) MarkOOMKilled(handle workspaceprovider.Handle) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if ws, ok := a.state[handle.String()]; ok {
		ws.oomKilled = true
	}
}

// ForceStateSequence scripts the native States the workspace's Probe returns, one per Status call
// (the last entry sticks once the sequence is exhausted). It exists so a conformance/unit test can
// drive the workspace through an ILLEGAL transition (e.g. Ready then Gone then Ready — a move OUT of
// terminal Gone) and assert the LIBRARY's State-machine guard rejects it, turning the documented
// legal-transition invariant into an executed test (finding #5). A no-op for an unknown handle.
func (a *Adapter) ForceStateSequence(handle workspaceprovider.Handle, states ...workspaceprovider.State) {
	a.mu.Lock()
	defer a.mu.Unlock()
	if ws, ok := a.state[handle.String()]; ok {
		ws.forcedStates = append([]workspaceprovider.State(nil), states...)
	}
}

// AssertNoSecretMaterial fails t if canary (a seeded credential plaintext) appears in ANY
// recorded Spec/Env/Handle/Descriptor/Status/log — the carries-refs-never-values
// guarantee, runnable.
func (a *Adapter) AssertNoSecretMaterial(t TestingT, canary string) {
	t.Helper()
	if canary == "" {
		return
	}
	a.mu.Lock()
	defer a.mu.Unlock()
	var b strings.Builder
	for i := range a.Provisioned {
		writeSpecText(&b, &a.Provisioned[i])
	}
	for _, h := range a.Destroyed {
		b.WriteString(h.String())
	}
	for _, r := range a.InjectedRefs {
		b.WriteString(r.String())
	}
	for _, ws := range a.state {
		b.WriteString(ws.handle.String())
		writeSpecText(&b, &ws.spec)
	}
	if strings.Contains(b.String(), canary) {
		t.Errorf("secret material leaked: canary %q appears in a recorded spec/handle/ref", canary)
	}
}

// recordRefs appends every secrets.Reference the spec/resolved bundle carried to
// InjectedRefs (refs only, never values).
func (a *Adapter) recordRefs(spec *workspaceprovider.WorkspaceSpec, _ workspaceprovider.Resolved) {
	if !spec.ImagePull.IsZero() {
		a.InjectedRefs = append(a.InjectedRefs, spec.ImagePull)
	}
	for i := range spec.Mounts {
		if !spec.Mounts[i].Ref.IsZero() {
			a.InjectedRefs = append(a.InjectedRefs, spec.Mounts[i].Ref)
		}
	}
	for i := range spec.Egress {
		if !spec.Egress[i].Ref.IsZero() {
			a.InjectedRefs = append(a.InjectedRefs, spec.Egress[i].Ref)
		}
	}
}

// handleFor builds the fake's native Handle for a spec via the library's parse round-trip
// so it carries the same canonical shape an adapter would assign. The fake encodes the
// substrate + name + a "/workspace" workdir; the library re-stamps tenancy.
func (a *Adapter) handleFor(spec *workspaceprovider.WorkspaceSpec) workspaceprovider.Handle {
	substrate := spec.Substrate
	if substrate == "" {
		substrate = workspaceprovider.SubstrateDocker
	}
	workDir := "/workspace"
	for i := range spec.Mounts {
		if spec.Mounts[i].Kind == workspaceprovider.MountBind || spec.Mounts[i].Kind == workspaceprovider.MountInputs {
			workDir = spec.Mounts[i].Target
			break
		}
	}
	raw := string(substrate) + "://" + strings.Join([]string{
		"", // namespace (library re-stamps)
		spec.Labels[workspaceprovider.LabelOrganization],
		spec.Labels[workspaceprovider.LabelProject],
		spec.Name,
		strings.ReplaceAll(workDir, "/", "%2F"),
	}, "/")
	h, err := workspaceprovider.ParseHandle(raw)
	if err != nil {
		// A name is guaranteed non-empty by the library's validateSpec before Create, so
		// this only fires on a programming error in the fake itself.
		panic("workspaceprovidertest: fake produced a malformed handle: " + err.Error())
	}
	return h
}

// connFor builds the Connection over an in-memory workspace (returned concrete per
// accept-interfaces/return-concrete, 10 §9).
func (a *Adapter) connFor(ws *fakeWorkspace) *fakeConnection {
	return &fakeConnection{adapter: a, ws: ws}
}

// matchesLabels reports whether all of want's entries are present-and-equal in have.
func matchesLabels(have, want map[string]string) bool {
	for k, v := range want {
		if have[k] != v {
			return false
		}
	}
	return true
}

// writeSpecText flattens a spec's loggable fields into b for the leak scan.
func writeSpecText(b *strings.Builder, spec *workspaceprovider.WorkspaceSpec) {
	b.WriteString(spec.Name)
	b.WriteString(spec.Image)
	b.WriteString(spec.ImagePull.String())
	for _, e := range spec.Env {
		b.WriteString(e.Name)
		b.WriteString(e.Value)
	}
	for k, v := range spec.Labels {
		b.WriteString(k)
		b.WriteString(v)
	}
	for i := range spec.Mounts {
		b.WriteString(spec.Mounts[i].Target)
		b.WriteString(spec.Mounts[i].Ref.String())
	}
	for i := range spec.Egress {
		b.WriteString(spec.Egress[i].Host)
		b.WriteString(spec.Egress[i].Ref.String())
	}
}

// fakeConnection is the in-memory Connection: Run/Exec/Files/Status over a fakeWorkspace.
type fakeConnection struct {
	adapter *Adapter
	ws      *fakeWorkspace
}

// Run models a primary workload. An OOM injection makes the run terminate
// RunKilled/ConditionOOMKilled; otherwise it succeeds.
//
//nolint:gocritic,ireturn // contract §2: Run takes spec/resolved by value AND returns the RunDriver port; the surface is frozen.
func (c *fakeConnection) Run(_ context.Context, spec workspaceprovider.RunSpec, resolved workspaceprovider.Resolved) (workspaceprovider.RunDriver, error) {
	c.adapter.mu.Lock()
	defer c.adapter.mu.Unlock()
	if !spec.Credential.IsZero() {
		c.adapter.InjectedRefs = append(c.adapter.InjectedRefs, spec.Credential)
	}
	_ = resolved
	c.ws.running = true
	oom := c.adapter.oomNext
	c.adapter.oomNext = false
	cmd := strings.Join(spec.Command, " ")
	return &fakeRun{oom: oom, command: cmd}, nil
}

// Exec runs a modeled command synchronously. A command of the form ["false"] exits 1;
// everything else exits 0. The clean-room go-test idiom returns 0 with the command echoed
// in Detail.
//
//nolint:gocritic // contract §2 fixes Connection.Exec's spec by value; the port surface is frozen.
func (c *fakeConnection) Exec(_ context.Context, spec workspaceprovider.ExecSpec) (workspaceprovider.ExecResult, error) {
	// Model `cat <path>` by returning the in-memory file content, so a case that reads a
	// MountSecret-injected file (caseMountSecret) gets the real value on the fake too.
	if out, exit, ok := c.modelCat(spec.Command); ok {
		if spec.Stdout != nil {
			_, _ = spec.Stdout.Write(out) //nolint:errcheck // caller-owned sink; bytes also ride ExecResult.Stdout.
		}
		return workspaceprovider.ExecResult{ExitCode: exit, Stdout: out, Detail: "fake cat"}, nil
	}
	out := []byte(strings.Join(spec.Command, " ") + "\n")
	if spec.Stdout != nil {
		_, _ = spec.Stdout.Write(out) //nolint:errcheck // caller-owned sink; bytes also ride ExecResult.Stdout.
	}
	exit := 0
	if len(spec.Command) > 0 && spec.Command[0] == "false" {
		exit = 1
	}
	return workspaceprovider.ExecResult{ExitCode: exit, Stdout: out, Detail: "fake exec"}, nil
}

// modelCat models `cat <path>` (and `sh -c "cat <path>"`) against the in-memory FS: it returns
// the file's bytes + exit 0 when present, empty + exit 1 when absent, and ok=false when the
// command is not a cat (so Exec falls through to its echo model).
func (c *fakeConnection) modelCat(command []string) (out []byte, exit int, ok bool) {
	path := catTarget(command)
	if path == "" {
		return nil, 0, false
	}
	c.adapter.mu.Lock()
	defer c.adapter.mu.Unlock()
	data, present := c.ws.files[path]
	if !present {
		return nil, 1, true
	}
	return append([]byte(nil), data...), 0, true
}

// catTarget extracts the path argument of a `cat <path>` (direct or wrapped in `sh -c`), else "".
func catTarget(command []string) string {
	if len(command) == 2 && command[0] == "cat" {
		return command[1]
	}
	if len(command) == 3 && command[0] == "sh" && command[1] == "-c" {
		fields := strings.Fields(command[2])
		if len(fields) == 2 && fields[0] == "cat" {
			return fields[1]
		}
	}
	return ""
}

// Files returns the in-memory file accessor.
//
//nolint:ireturn // contract §2: Connection.Files returns the Files port; the surface is frozen.
func (c *fakeConnection) Files() workspaceprovider.Files {
	return &fakeFiles{adapter: c.adapter, ws: c.ws}
}

// Probe reports the modeled lifecycle. A running workload is StateRunning; otherwise
// StateReady. A denied egress host surfaces ConditionEgressDenied.
func (c *fakeConnection) Probe(_ context.Context) (workspaceprovider.Probe, error) {
	c.adapter.mu.Lock()
	defer c.adapter.mu.Unlock()
	// A scripted state sequence (ForceStateSequence) overrides the modeled lifecycle so a test can
	// drive an ILLEGAL transition past the library's State-machine guard. The next entry is consumed
	// per Probe; the last entry sticks once the sequence is exhausted.
	if len(c.ws.forcedStates) > 0 {
		next := c.ws.forcedStates[0]
		if len(c.ws.forcedStates) > 1 {
			c.ws.forcedStates = c.ws.forcedStates[1:]
		}
		return workspaceprovider.Probe{State: next, Detail: "fake forced state " + next.String()}, nil
	}
	probe := workspaceprovider.Probe{State: workspaceprovider.StateReady, Detail: "fake ready"}
	if c.ws.running {
		probe.State = workspaceprovider.StateRunning
	}
	if c.ws.oomKilled {
		// The workload-pod (Entrypoint) OOM-kill attaches to the readable workspace container —
		// the supervised Probe surfaces the discriminator natively (OD-15-a).
		probe.State = workspaceprovider.StateDegraded
		probe.Detail = "OOMKilled"
		probe.Conditions = append(probe.Conditions, workspaceprovider.ConditionOOMKilled)
	}
	for i := range c.ws.spec.Egress {
		if c.adapter.deniedHost[c.ws.spec.Egress[i].Host] {
			probe.Conditions = append(probe.Conditions, workspaceprovider.ConditionEgressDenied)
		}
	}
	return probe, nil
}

// fakeRun is the in-memory RunDriver: it transitions Running -> terminal once. oom forces
// the terminal transition to be a RunKilled/ConditionOOMKilled (the runaway-agent path).
type fakeRun struct {
	oom     bool
	command string
	step    int
}

// Status walks the modeled lifecycle: first call reports Running (ok=true); the second
// reports a terminal phase (ok=false) — Succeeded, or Killed/OOMKilled if oom was set.
func (r *fakeRun) Status(_ context.Context) (workspaceprovider.RunStatus, bool) {
	r.step++
	if r.step == 1 {
		return workspaceprovider.RunStatus{Phase: workspaceprovider.RunRunning}, true
	}
	if r.oom {
		return workspaceprovider.RunStatus{
			Phase:     workspaceprovider.RunKilled,
			Condition: workspaceprovider.ConditionOOMKilled,
			Detail:    "OOMKilled (fake)",
		}, false
	}
	return workspaceprovider.RunStatus{Phase: workspaceprovider.RunSucceeded, ExitCode: 0}, false
}

// Logs streams the modeled command as the workload's raw log.
func (r *fakeRun) Logs(_ context.Context, _ workspaceprovider.LogCursor) (io.ReadCloser, error) {
	return io.NopCloser(bytes.NewBufferString(r.command + "\n")), nil
}

// fakeFiles is the in-memory Files seam.
type fakeFiles struct {
	adapter *Adapter
	ws      *fakeWorkspace
}

// Put writes content to the in-memory FS. A write under a read-only mount target is a
// NotReadyError (the clean-room declared-inputs guarantee).
func (f *fakeFiles) Put(_ context.Context, p string, content io.Reader, _ workspaceprovider.FileMode) error {
	f.adapter.mu.Lock()
	defer f.adapter.mu.Unlock()
	for prefix, ro := range f.ws.readOnly {
		if ro && strings.HasPrefix(p, prefix) {
			return &workspaceprovider.NotReadyError{Handle: f.ws.handle, State: workspaceprovider.StateReady, Op: "Files.Put(read-only)"}
		}
	}
	data, err := io.ReadAll(content)
	if err != nil {
		return &workspaceprovider.NotReadyError{Handle: f.ws.handle, State: workspaceprovider.StateReady, Op: "Files.Put(read)"}
	}
	f.ws.files[p] = data
	return nil
}

// Get reads a path back. NotFoundError if absent.
func (f *fakeFiles) Get(_ context.Context, p string) (io.ReadCloser, error) {
	f.adapter.mu.Lock()
	defer f.adapter.mu.Unlock()
	data, ok := f.ws.files[p]
	if !ok {
		return nil, &workspaceprovider.NotFoundError{Handle: f.ws.handle, Path: p}
	}
	return io.NopCloser(bytes.NewReader(data)), nil
}

// List enumerates the (shallow) entries under path.
func (f *fakeFiles) List(_ context.Context, p string) ([]workspaceprovider.FileEntry, error) {
	f.adapter.mu.Lock()
	defer f.adapter.mu.Unlock()
	prefix := strings.TrimSuffix(p, "/") + "/"
	seen := map[string]bool{}
	var entries []workspaceprovider.FileEntry
	for path, data := range f.ws.files {
		if !strings.HasPrefix(path, prefix) {
			continue
		}
		rest := strings.TrimPrefix(path, prefix)
		name, _, isDir := strings.Cut(rest, "/")
		if seen[name] {
			continue
		}
		seen[name] = true
		entries = append(entries, workspaceprovider.FileEntry{
			Name:  name,
			IsDir: isDir,
			Size:  int64(len(data)),
			Mode:  0o644,
		})
	}
	sort.Slice(entries, func(i, j int) bool { return entries[i].Name < entries[j].Name })
	return entries, nil
}

// TestingT is the minimal testing surface the assertions need (satisfied by *testing.T).
type TestingT interface {
	Helper()
	Errorf(format string, args ...any)
}
