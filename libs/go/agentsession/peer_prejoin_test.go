package agentsession_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/agentsession/agentsessiontest"
	"github.com/gophersys/libs/go/errors"
)

// The PRE-JOIN window, which no public path can reach.
//
// Pool.Open calls Spawn (pool.go:81) BEFORE joinPeer (pool.go:95). The host tools must therefore
// be injected into the Spec the adapter receives while the PeerLink does not yet exist — so
// every peer host-tool handler is, for a window, holding a nil link. Nothing in the public API
// can observe that window: by the time Open returns, Join has happened, and if Join FAILS Open
// returns an error and no session exists to call a tool on.
//
// A window that cannot be observed is a window that ships unproven. PeerHostToolsForTest
// (export_test.go) is the white-box seam that opens it, and this is what it must guarantee.

// TestPeerHostTool_BeforeJoinIsTypedUnavailable is test 8, the pre-Join arm. A handler invoked
// with no link must return a TYPED errors.KindUnavailable — the Kind a caller branches on for
// "not ready yet, retry" — and must not panic.
//
// FALSIFICATION: dereferencing the nil link panics INSIDE the harness's host-tool router, where
// a panic is not a failed tool but a broken transport: claude's mcp_message never gets its
// control_response and the CLI's client.connect() blocks forever, omp's #pendingCalls entry is
// never resolved and the model waits on a tool that already died. Neither surfaces as an error
// anyone can read.
func TestPeerHostTool_BeforeJoinIsTypedUnavailable(t *testing.T) {
	t.Parallel()
	plane := agentsessiontest.NewPeerPlane()

	tools := agentsession.PeerHostToolsForTest("impl-a", plane, nil)
	if len(tools) == 0 {
		t.Fatalf("peerHostTools returned nothing for a named session on a live plane")
	}

	for _, tool := range tools {
		t.Run(tool.Name, func(t *testing.T) {
			t.Parallel()
			if tool.Handler == nil {
				t.Fatalf("%s was built with a nil Handler: a tool the model can call and nothing can serve", tool.Name)
			}
			defer func() {
				if recovered := recover(); recovered != nil {
					t.Fatalf("%s PANICKED with no link (%v). A panic inside a host-tool handler is a broken transport, not a failed tool: the harness never receives its result frame and the model waits forever",
						tool.Name, recovered)
				}
			}()
			result, err := tool.Handler(context.Background(), []byte(`{"to":"review-c","body":"too early"}`))
			if err == nil {
				t.Fatalf("%s answered %q before Join; a session that is not on the plane cannot send or list, and saying it can is the silent non-membership this design removes",
					tool.Name, result)
			}
			if errors.KindOf(err) != errors.KindUnavailable {
				t.Errorf("%s returned KindOf=%v, want %v — the Kind a caller branches on for \"not ready yet\"",
					tool.Name, errors.KindOf(err), errors.KindUnavailable)
			}
		})
	}
}

// TestPeerHostTool_NoPlaneMeansNoTools proves the other end of the same gate: with no plane
// injected there is nothing to send over and nothing to list, so the set is EMPTY. A tool
// offered to a model that can never succeed is worse than an absent one — the model spends
// turns on it and the transcript fills with failures that were structurally guaranteed.
func TestPeerHostTool_NoPlaneMeansNoTools(t *testing.T) {
	t.Parallel()
	if tools := agentsession.PeerHostToolsForTest("impl-a", nil, nil); len(tools) != 0 {
		t.Errorf("peerHostTools with no plane returned %d tools, want 0", len(tools))
	}
	if tools := agentsession.PeerHostToolsForTest("", agentsessiontest.NewPeerPlane(), nil); len(tools) != 0 {
		t.Errorf("peerHostTools with no Spec.Name returned %d tools, want 0: an unaddressable session has no peer identity to send FROM", len(tools))
	}
}
