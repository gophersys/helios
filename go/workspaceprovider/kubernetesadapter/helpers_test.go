//go:build integration

package kubernetesadapter_test

import (
	"context"
	"io"
	"testing"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
	"github.com/gophersys/libs/go/secrets/secretstest"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// newProvider wires a real *workspaceprovider.Provisioner over the kubernetes adapter the
// harness bound to the ephemeral cluster, with a fake secrets.Provider (no real vault) and a
// deterministic Clock — the LIBRARY-owned state machine, idempotency, Handle stamping, and
// credential seam are under test exactly as a consumer sees them.
func newProvider(t *testing.T, adapter workspaceprovider.Adapter) *workspaceprovider.Provisioner {
	t.Helper()
	prov, err := workspaceprovider.New(
		workspaceprovider.Config{Default: workspaceprovider.SubstrateKubernetes},
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{workspaceprovider.SubstrateKubernetes: adapter},
			Secrets:  secretsForTest(),
			Clock:    clockForTest(),
		},
	)
	if err != nil {
		t.Fatalf("New provider over real kubernetes adapter: %v", err)
	}
	return prov
}

// secretsForTest returns a fake secrets.Provider for integration wiring (no real vault).
func secretsForTest() *secretstest.Provider { return secretstest.New(nil) }

// clockForTest returns a deterministic Clock for integration wiring.
//
//nolint:ireturn // the fake Clock is the dependencies.Clock port the Deps hexagon takes; returning the port is the injection shape.
func clockForTest() dependencies.Clock {
	set, _, _, _ := dependenciestest.Fakes()
	return set.Clock
}

// drainRun ranges a Run.Status to its terminal transition and returns the last RunStatus seen.
func drainRun(ctx context.Context, run workspaceprovider.Run) workspaceprovider.RunStatus {
	var last workspaceprovider.RunStatus
	for {
		status, ok := run.Status(ctx)
		last = status
		if !ok || status.Phase.IsTerminal() {
			return last
		}
	}
}

// listContains reports whether descs includes the workspace named by handle.
func listContains(descs []workspaceprovider.Descriptor, handle workspaceprovider.Handle) bool {
	for i := range descs {
		if descs[i].Handle.String() == handle.String() {
			return true
		}
	}
	return false
}

// readAll drains and closes rc.
func readAll(rc io.ReadCloser) ([]byte, error) {
	defer func() { _ = rc.Close() }() //nolint:errcheck // closing a fully-read stream has no actionable error.
	return io.ReadAll(rc)
}
