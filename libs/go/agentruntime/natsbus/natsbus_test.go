package natsbus_test

import (
	"context"
	"testing"

	"github.com/nats-io/nats.go"

	"github.com/gophersys/libs/go/agentruntime/natsbus"
	"github.com/gophersys/libs/go/errors"
)

// recordingJetStream is a nats.JetStreamContext that records whether the two provisioning calls
// (AddStream / StreamInfo) were invoked. Every OTHER method comes from the embedded nil interface, so
// a stray call panics — which is exactly the assertion: New must touch NONE of them. It is NOT a NATS
// protocol mock (the real wire behavior is the //go:build integration lane); it is the narrow probe
// that proves the New spine is pure — the I/O lives only behind the explicit EnsureStream step.
type recordingJetStream struct {
	nats.JetStreamContext // nil embedded: any unstubbed call panics (a New-time I/O attempt is caught)

	addStreamCalls  int
	streamInfoCalls int
	streamConfig    *nats.StreamConfig
}

// AddStream records the provisioning attempt and returns a benign StreamInfo (the success path).
func (r *recordingJetStream) AddStream(configuration *nats.StreamConfig, _ ...nats.JSOpt) (*nats.StreamInfo, error) {
	r.addStreamCalls++
	r.streamConfig = configuration
	return &nats.StreamInfo{Config: *configuration}, nil
}

// StreamInfo records the lookup attempt (the name-in-use tolerance path).
func (r *recordingJetStream) StreamInfo(_ string, _ ...nats.JSOpt) (*nats.StreamInfo, error) {
	r.streamInfoCalls++
	return &nats.StreamInfo{}, nil
}

// TestNew_DoesNoNetworkIO is the New-purity conformance (rule 10 — the New(configuration,
// dependencies) spine does no I/O): constructing the adapter must invoke NO method on the injected
// JetStream handle, in particular NOT AddStream/StreamInfo. The recording fake counts every
// provisioning call; New must leave both counters at zero. (The connection handle is a non-nil but
// unconnected *nats.Conn — New only stores it and nil-checks it, never dials, so an unconnected conn
// proves the constructor performs no network round-trip on either handle.)
func TestNew_DoesNoNetworkIO(t *testing.T) {
	t.Parallel()
	jetStream := &recordingJetStream{}
	adapter, err := natsbus.New(natsbus.Config{}, natsbus.Deps{Conn: &nats.Conn{}, JetStream: jetStream})
	if err != nil {
		t.Fatalf("New over unconnected handles errored (it must be pure, not dial): %v", err)
	}
	if adapter == nil {
		t.Fatal("New returned a nil adapter without an error")
	}
	if jetStream.addStreamCalls != 0 {
		t.Errorf("New called AddStream %d times — the constructor is not pure (I/O must live in EnsureStream)", jetStream.addStreamCalls)
	}
	if jetStream.streamInfoCalls != 0 {
		t.Errorf("New called StreamInfo %d times — the constructor is not pure (I/O must live in EnsureStream)", jetStream.streamInfoCalls)
	}
}

// TestEnsureStream_PerformsTheProvisioningIO is the paired half: the AddStream I/O was MOVED out of
// New, not deleted. EnsureStream(ctx) must perform exactly the provisioning round-trip New no longer
// does — AddStream on the events stream capturing agent.*.events. This pins the refactor: purity of
// New AND a live, explicit provisioning step.
func TestEnsureStream_PerformsTheProvisioningIO(t *testing.T) {
	t.Parallel()
	jetStream := &recordingJetStream{}
	adapter, err := natsbus.New(natsbus.Config{}, natsbus.Deps{Conn: &nats.Conn{}, JetStream: jetStream})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if err := adapter.EnsureStream(context.Background()); err != nil {
		t.Fatalf("EnsureStream: %v", err)
	}
	if jetStream.addStreamCalls != 1 {
		t.Errorf("EnsureStream called AddStream %d times, want exactly 1 (the provisioning round-trip)", jetStream.addStreamCalls)
	}
	if jetStream.streamConfig == nil {
		t.Fatal("EnsureStream did not pass a StreamConfig")
	}
	if jetStream.streamConfig.Name != natsbus.StreamName {
		t.Errorf("EnsureStream provisioned stream %q, want %q", jetStream.streamConfig.Name, natsbus.StreamName)
	}
	if len(jetStream.streamConfig.Subjects) != 1 || jetStream.streamConfig.Subjects[0] != "agent.*.events" {
		t.Errorf("EnsureStream subjects = %v, want [agent.*.events]", jetStream.streamConfig.Subjects)
	}
}

// TestNew_NilHandlesAreConfigErrors keeps the pure-validation contract covered: a nil Conn or
// JetStream is a typed KindInvalid construction error (the only thing New does besides wiring).
func TestNew_NilHandlesAreConfigErrors(t *testing.T) {
	t.Parallel()
	if _, err := natsbus.New(natsbus.Config{}, natsbus.Deps{JetStream: &recordingJetStream{}}); errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("nil Conn: err = %v, want KindInvalid", err)
	}
	if _, err := natsbus.New(natsbus.Config{}, natsbus.Deps{Conn: &nats.Conn{}}); errors.KindOf(err) != errors.KindInvalid {
		t.Errorf("nil JetStream: err = %v, want KindInvalid", err)
	}
}
