package natscontrol_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/agentruntime"
	"github.com/gophersys/libs/go/errors"

	"github.com/gophersys/eden/apps/agentgateway/internal/natscontrol"
)

// TestNew_RequiresConn proves a nil *nats.Conn is a construction error (KindInvalid) — the adapter
// dials nothing; the composition root supplies a dialed connection.
func TestNew_RequiresConn(t *testing.T) {
	t.Parallel()
	if _, err := natscontrol.New(nil); errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("nil conn kind = %s, want invalid", errors.KindOf(err))
	}
}

// TestPublishControl_MarshalFault proves a marshal failure is wrapped on the Eden errors seam as
// KindInternal (an invariant we own broken). The marshal seam is swapped white-box (export_test.go)
// because a valid ControlMessage (string/uint8/map fields) can never make json.Marshal fail through
// the public surface; the arm returns before the connection is touched, so a nil-conn adapter is
// sufficient. Not t.Parallel(): it mutates the package-level marshal seam.
func TestPublishControl_MarshalFault(t *testing.T) {
	restore := natscontrol.SetMarshalControl(func(any) ([]byte, error) {
		return nil, errors.New(errors.KindInternal, "natscontrol: forced marshal fault")
	})
	t.Cleanup(restore)

	adapter := natscontrol.NewForTest()
	err := adapter.PublishControl(context.Background(), agentruntime.ControlMessage{AgentID: "agent-x", Verb: agentruntime.VerbStop})
	if errors.KindOf(err) != errors.KindInternal {
		t.Fatalf("marshal-fault kind = %s, want internal", errors.KindOf(err))
	}
}
