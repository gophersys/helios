package ompadapter_test

import (
	"context"
	"io"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/ompadapter"
)

// TestRPC_DenyOnAdapterTimeoutWhenNobodyResolves is F1 TIMEOUT: the adapter's OWN bounded fallback
// answers Deny when the library never resolves a dialog.
//
// omp's `select` carries no timeout field and omp arms no timer (rpc-mode.ts:640), so an
// unanswered dialog stalls the turn forever — q3-probe5 measured 45s and no agent_end. Under the
// routed contract the adapter no longer decides inline; it surfaces the ask and waits for the
// library. If nothing comes back within the adapter's bounded window (the library is wedged, the
// session is being torn down, the decision Send failed), the adapter must answer Deny itself, so a
// missing resolution fails SAFE rather than hanging omp.
//
// Two properties, together: the adapter must NOT answer before the window (it is waiting, not
// deciding inline — the deleted grant-derived behavior), and it MUST answer Deny after it.
//
// Today the adapter answers inline the instant the dialog arrives, so the "no answer before the
// window" half is RED, and there is no fallback path at all.
func TestRPC_DenyOnAdapterTimeoutWhenNobodyResolves(t *testing.T) {
	t.Parallel()
	const fallback = 200 * time.Millisecond
	harness := newRPCHarnessWithFallback(t, agentsession.Spec{}, fallback)
	harness.completeHandshake()

	// The captured no-timeout select (rpc-17.3.7-approval-select.jsonl[1]).
	harness.emit(rpcFixture(t, approvalFixture)[1])

	// It must be WAITING, not deciding: nothing is written before the fallback fires.
	time.Sleep(fallback / 2)
	if frame, found := harness.stdin.find(hasType("extension_ui_response")); found {
		t.Fatalf("the adapter answered the dialog inline (%v) before waiting for a resolution — the deleted grant-deciding path", frame)
	}

	answer := harness.waitFrame("the fallback deny", hasType("extension_ui_response"))
	assertLegalDialogAnswer(t, answer)
	if id := stringField(answer, "id"); id != selectFrameID {
		t.Errorf("fallback answer id = %q, want the dialog id %q", id, selectFrameID)
	}
	if value := stringField(answer, "value"); !strings.EqualFold(value, "Deny") {
		t.Errorf("adapter fallback answer = %q, want Deny — a dialog nobody resolved must fail safe, never stall and never auto-approve", value)
	}
}

// newRPCHarnessWithFallback builds the shared rpc harness over a conn with an injected
// deny-on-timeout window, so the fallback fires in milliseconds instead of the production default.
// It mirrors newRPCHarness (rpc_test.go) but for the conn constructor.
//
//nolint:gocritic // contract §2: Spec is the frozen copyable session input; the seam mirrors Spawn's by-value port.
func newRPCHarnessWithFallback(t *testing.T, spec agentsession.Spec, fallback time.Duration) *rpcHarness {
	t.Helper()
	reader, writer := io.Pipe()
	harness := &rpcHarness{t: t, stdout: writer, stdin: &recordingStdin{}, drained: make(chan struct{})}
	harness.conn = ompadapter.RPCConnWithFallbackForTest(spec, reader, harness.stdin, fallback)
	go harness.drain()
	t.Cleanup(func() {
		_ = harness.conn.Close(context.Background()) //nolint:errcheck // best-effort reap; Close is idempotent.
		_ = writer.Close()                           //nolint:errcheck // releases any test-side write still blocked on the conn's reader.
		_ = reader.Close()                           //nolint:errcheck // ends the conn's read pump if Close did not.
		select {
		case <-harness.drained:
		case <-time.After(rpcDeadline):
			t.Errorf("the conn's event channel was still open %s after Close: the pump outlives the session", rpcDeadline)
		}
	})
	return harness
}
