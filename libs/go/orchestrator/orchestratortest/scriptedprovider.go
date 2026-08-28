package orchestratortest

import (
	"context"
	"sync"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// wrapConflict builds the wrapped workspaceprovider.ConflictError a settling re-Provision
// surfaces (KindConflict in the chain), so the orchestrator's driveResume conflict branch
// (errors.KindOf(err) == errors.KindConflict) recognizes it the same way the real provider's
// fingerprint-mismatch conflict would.
func wrapConflict(name string) error {
	return errors.Wrap(errors.KindConflict, "orchestratortest: workspace settling (scripted)",
		&workspaceprovider.ConflictError{Name: name})
}

// scriptedProvider decorates a real workspaceprovider.Provider so a conformance case can
// drive the orchestrator's driveResume RECOVERY branches deterministically against the SAME
// frozen seam (workspaceprovider.Provider), never a re-implemented stub:
//
//   - failOpensN: the next N Open calls return a transient miss (the recorded handle's pod is
//     still settling after a node-recycle), so driveResume falls through to re-provision.
//   - conflictNextProvision: the next Provision returns a workspaceprovider.ConflictError
//     (the workspace actually EXISTS and is settling), so driveResume takes the conflict-readopt
//     branch — re-Open the recorded handle rather than duplicate-provision.
//
// Everything not armed passes straight through to the wrapped Provider, so the REAL Provision/
// Open/Teardown/idempotency logic is exercised. Safe for concurrent use.
type scriptedProvider struct {
	inner workspaceprovider.Provider

	mu                    sync.Mutex
	failOpensN            int
	failOpenErr           error
	conflictNextProvision bool
	blockProvision        bool // when set, Provision blocks until ctx is Done (the hung-provision / timeout path)

	// reprovisions counts Provision calls that reached the inner provider's Create path while a
	// conflict was NOT armed (the genuine re-provision the pod-gone branch makes), so a case can
	// assert exactly one NEW provision with the re-adopted Name.
	provisions int
}

// newScriptedProvider wraps inner.
func newScriptedProvider(inner workspaceprovider.Provider) *scriptedProvider {
	return &scriptedProvider{inner: inner}
}

// FailNextOpens arms the next n Open calls to return err (a transient re-attach miss). A nil
// err defaults to a workspaceprovider.NotFoundError. Fluent.
func (s *scriptedProvider) FailNextOpens(n int, err error) *scriptedProvider {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.failOpensN = n
	s.failOpenErr = err
	return s
}

// ConflictNextProvision arms the next Provision to return a workspaceprovider.ConflictError
// (the workspace exists and is settling — the orchestrator must re-adopt, not duplicate).
// Fluent.
func (s *scriptedProvider) ConflictNextProvision() *scriptedProvider {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.conflictNextProvision = true
	return s
}

// BlockProvision makes every Provision block until its ctx is canceled (a hung provider), so a
// test proves Config.ProvisionTimeout bounds the call and marks the agent Failed rather than
// wedging it in Provisioning forever. Fluent.
func (s *scriptedProvider) BlockProvision() *scriptedProvider {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.blockProvision = true
	return s
}

// Provisions returns how many Provision calls fell through to the wrapped provider (the
// genuine re-provisions, excluding the armed-conflict short-circuit).
func (s *scriptedProvider) Provisions() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.provisions
}

// Provision returns a ConflictError when armed (consuming the arm), else delegates and counts
// the genuine provision.
//
//nolint:gocritic,ireturn // WorkspaceSpec is the frozen copyable input; Provision returns the frozen Workspace port.
func (s *scriptedProvider) Provision(ctx context.Context, spec workspaceprovider.WorkspaceSpec) (workspaceprovider.Workspace, error) {
	s.mu.Lock()
	if s.conflictNextProvision {
		s.conflictNextProvision = false
		s.mu.Unlock()
		return nil, wrapConflict(spec.Name)
	}
	block := s.blockProvision
	s.provisions++
	s.mu.Unlock()
	if block {
		// Hang until the ctx (bounded by Config.ProvisionTimeout in reconcile) is canceled, so
		// the orchestrator's provisionContext deadline is what ends the call.
		<-ctx.Done()
		return nil, errors.Wrap(errors.KindDeadline, "orchestratortest: provision deadline (scripted hang)", ctx.Err())
	}
	return s.inner.Provision(ctx, spec) //nolint:wrapcheck // the wrapped provider's typed error passes through for assertion.
}

// Open returns a transient miss while armed (consuming one arm), else delegates.
//
//nolint:ireturn // Open returns the frozen Workspace port.
func (s *scriptedProvider) Open(ctx context.Context, handle workspaceprovider.Handle) (workspaceprovider.Workspace, error) {
	s.mu.Lock()
	if s.failOpensN > 0 {
		s.failOpensN--
		err := s.failOpenErr
		s.mu.Unlock()
		if err == nil {
			err = &workspaceprovider.NotFoundError{Handle: handle}
		}
		return nil, err
	}
	s.mu.Unlock()
	return s.inner.Open(ctx, handle) //nolint:wrapcheck // the wrapped provider's typed error passes through for assertion.
}

// Teardown delegates straight through.
func (s *scriptedProvider) Teardown(ctx context.Context, handle workspaceprovider.Handle) error {
	return s.inner.Teardown(ctx, handle) //nolint:wrapcheck // the wrapped provider's typed error passes through for assertion.
}

// List delegates straight through.
func (s *scriptedProvider) List(ctx context.Context, selector workspaceprovider.Selector) ([]workspaceprovider.Descriptor, error) {
	return s.inner.List(ctx, selector) //nolint:wrapcheck // the wrapped provider's typed error passes through for assertion.
}

// compile-time assertion: *scriptedProvider is a workspaceprovider.Provider.
var _ workspaceprovider.Provider = (*scriptedProvider)(nil)
