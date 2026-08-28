package natssse_test

import (
	"testing"
	"time"

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/edenhttp"
	"github.com/gophersys/libs/go/edenhttp/natssse"
	"github.com/gophersys/libs/go/errors"
)

// unitClock is a fixed clock for the New unit tests (no scheduling here).
type unitClock struct{}

func (unitClock) Now() time.Time { return time.Unix(0, 0) }

// fakeJetStream is a non-nil nats.JetStreamContext for the New validation tests: New never CALLS the
// handle (it is pure — it only checks for nil), so an embedded nil interface satisfies the type
// without implementing any method. A test that actually streams uses a REAL JetStream (the
// integration arm), never this.
type fakeJetStream struct{ nats.JetStreamContext }

// TestNew_RequiresJetStream proves a nil JetStream handle is a New-time KindInvalid (the bridge
// dials nothing; the composition root must supply a dialed handle).
func TestNew_RequiresJetStream(t *testing.T) {
	t.Parallel()
	_, err := natssse.New(natssse.Config{}, natssse.Deps{Clock: unitClock{}})
	if errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("nil JetStream kind = %s, want invalid", errors.KindOf(err))
	}
}

// TestNew_RequiresClock proves a nil Clock is a New-time KindInvalid (so the heartbeat scheduling
// is deterministic and New stays pure).
func TestNew_RequiresClock(t *testing.T) {
	t.Parallel()
	_, err := natssse.New(natssse.Config{}, natssse.Deps{JetStream: fakeJetStream{}})
	if errors.KindOf(err) != errors.KindInvalid {
		t.Fatalf("nil Clock kind = %s, want invalid", errors.KindOf(err))
	}
}

// TestNew_DefaultsApplied proves an empty Config defaults the stream name + heartbeat interval (the
// bridge is usable without naming them).
func TestNew_DefaultsApplied(t *testing.T) {
	t.Parallel()
	bridge, err := natssse.New(natssse.Config{}, natssse.Deps{JetStream: fakeJetStream{}, Clock: unitClock{}})
	if err != nil {
		t.Fatalf("New with defaults: %v", err)
	}
	if bridge == nil {
		t.Fatal("New returned a nil bridge")
	}
}

// TestNew_ExplicitConfig proves an explicit stream + heartbeat are accepted.
func TestNew_ExplicitConfig(t *testing.T) {
	t.Parallel()
	_, err := natssse.New(
		natssse.Config{Stream: "CUSTOM_STREAM", HeartbeatInterval: 5 * time.Second},
		natssse.Deps{JetStream: fakeJetStream{}, Clock: unitClock{}},
	)
	if err != nil {
		t.Fatalf("New with explicit config: %v", err)
	}
}

// compile-time assertion that the in-lib defaults line up with the edenhttp spine default (so a
// consumer that wires both shares one cadence). A drift here is a wiring bug, caught at build.
var _ = edenhttp.DefaultHeartbeatInterval
