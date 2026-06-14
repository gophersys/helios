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

// TestPublishControl_NilConnGuard is a defense-in-depth check that the typed port is satisfied; the
// real publish round trip is proven over REAL NATS in the integration arm (natscontrol_integration_test).
func TestPublishControl_PortShape(t *testing.T) {
	t.Parallel()
	// A compile-time + runtime assertion that the adapter implements the publisher port shape; the
	// real round trip is the integration arm's job (a real *nats.Conn).
	var _ interface {
		PublishControl(context.Context, agentruntime.ControlMessage) error
	} = (*natscontrol.Adapter)(nil)
}
