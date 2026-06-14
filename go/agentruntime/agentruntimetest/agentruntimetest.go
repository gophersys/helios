// Package agentruntimetest is the canonical public test harness for the agentruntime sidecar (the
// testing pattern, 10 §4 / 08 §2): a fake agentruntime.Bus that records every published EventEnvelope
// and Heartbeat and lets a test INJECT control messages (the orchestrator side), a fake Observer that
// records the W3C trace carrier so OTel-on-every-message is asserted without a real collector, a
// deterministic Clock, and a builder that wires a Runtime over a REAL agentsession.Pool driving the
// agentsessiontest scripted fake harness. The fake Bus is NOT a NATS-protocol mock — it is the
// consumer-side fake of the agentruntime.Bus PORT (the real NATS behavior is proven separately by
// the //go:build integration lane against a real embedded nats-server + a real nats container).
package agentruntimetest

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/gophersys/libs/go/agentruntime"
)

// TraceParent is the canonical W3C traceparent the FakeObserver injects on every publish so a test
// asserts OTel context rode the message (the ADR-0022 invariant). It is a syntactically valid
// traceparent; the assertion only needs a stable, recognizable needle.
const TraceParent = "00-0af7651916cd43dd8448eb211c80319c-b7ad6b7169203331-01"

// FakeBus is the consumer-side fake of agentruntime.Bus. It records published events + heartbeats
// (for the sidecar→bus assertions) and delivers test-injected control messages to the subscribed
// handler (for the orchestrator→sidecar round-trip). Safe for concurrent use.
type FakeBus struct {
	mu         sync.Mutex
	events     []agentruntime.EventEnvelope
	heartbeats []agentruntime.Heartbeat
	publishErr error

	handler  func(agentruntime.ControlMessage)
	subReady chan struct{}
}

// NewFakeBus constructs an empty fake bus whose subscription becomes ready once the sidecar calls
// SubscribeControl (a test waits on Subscribed before injecting a verb).
func NewFakeBus() *FakeBus {
	return &FakeBus{subReady: make(chan struct{})}
}

// FailPublishWith makes the next and all subsequent PublishEvent/PublishHealth return err (to drive
// the sidecar's publish-error path: logged, never dropped, pump continues). Fluent.
func (b *FakeBus) FailPublishWith(err error) *FakeBus {
	b.mu.Lock()
	defer b.mu.Unlock()
	b.publishErr = err
	return b
}

// PublishEvent records the envelope (or returns the seeded publish error).
//
//nolint:gocritic // contract: EventEnvelope is the frozen, copyable message value; the Bus port takes it by value.
func (b *FakeBus) PublishEvent(_ context.Context, envelope agentruntime.EventEnvelope) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.publishErr != nil {
		return b.publishErr
	}
	b.events = append(b.events, envelope)
	return nil
}

// PublishHealth records the heartbeat (or returns the seeded publish error).
//
//nolint:gocritic // contract: Heartbeat is the frozen, copyable message value; the Bus port takes it by value.
func (b *FakeBus) PublishHealth(_ context.Context, heartbeat agentruntime.Heartbeat) error {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.publishErr != nil {
		return b.publishErr
	}
	b.heartbeats = append(b.heartbeats, heartbeat)
	return nil
}

// SubscribeControl installs the handler and blocks until ctx is canceled (mirroring the real adapter
// keeping the subscription alive for the agent's life). It signals readiness so a test injects a verb
// only after the sidecar is subscribed.
func (b *FakeBus) SubscribeControl(ctx context.Context, _ agentruntime.AgentID, handle func(agentruntime.ControlMessage)) error {
	b.mu.Lock()
	b.handler = handle
	ready := b.subReady
	b.mu.Unlock()
	close(ready)
	<-ctx.Done()
	return nil
}

// Subscribed returns a channel closed once the sidecar has subscribed (a test waits on it before
// Inject so the control message is not dropped on the floor before the handler exists).
func (b *FakeBus) Subscribed() <-chan struct{} {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.subReady
}

// Inject delivers one control message to the subscribed handler (the orchestrator publishing to
// agent.<id>.control). It is a no-op if no handler is installed yet — call after <-Subscribed().
//
//nolint:gocritic // ControlMessage is the frozen, copyable message value; the injector takes it by value, mirroring the wire.
func (b *FakeBus) Inject(message agentruntime.ControlMessage) {
	b.mu.Lock()
	handler := b.handler
	b.mu.Unlock()
	if handler != nil {
		handler(message)
	}
}

// Events returns a copy of every published EventEnvelope, in publish order, under lock.
func (b *FakeBus) Events() []agentruntime.EventEnvelope {
	b.mu.Lock()
	defer b.mu.Unlock()
	out := make([]agentruntime.EventEnvelope, len(b.events))
	copy(out, b.events)
	return out
}

// Heartbeats returns a copy of every published Heartbeat, in publish order, under lock.
func (b *FakeBus) Heartbeats() []agentruntime.Heartbeat {
	b.mu.Lock()
	defer b.mu.Unlock()
	out := make([]agentruntime.Heartbeat, len(b.heartbeats))
	copy(out, b.heartbeats)
	return out
}

// compile-time assertion: *FakeBus is an agentruntime.Bus.
var _ agentruntime.Bus = (*FakeBus)(nil)

// FakeObserver is the consumer-side fake of agentruntime.Observer. Inject always returns a carrier
// with TraceParent (so a publish always carries OTel context); Extract stores the carried trace so a
// round-tripped Inject returns it. It records log lines + flush calls for the shutdown assertions.
type FakeObserver struct {
	mu       sync.Mutex
	logs     []string
	flushed  int
	lastSeen agentruntime.OTelContext
}

// NewFakeObserver constructs an empty fake observer.
func NewFakeObserver() *FakeObserver { return &FakeObserver{} }

// Logf records the formatted line (without I/O).
func (o *FakeObserver) Logf(_ context.Context, format string, args ...any) {
	o.mu.Lock()
	defer o.mu.Unlock()
	o.logs = append(o.logs, fmt.Sprintf(format, args...))
}

// Inject returns the carried trace if Extract stored one, else a fresh carrier with TraceParent — so
// EVERY published message carries OTel context (the invariant).
func (o *FakeObserver) Inject(ctx context.Context) agentruntime.OTelContext {
	if carried, ok := ctx.Value(fakeCarrierKey{}).(agentruntime.OTelContext); ok && len(carried) > 0 {
		out := make(agentruntime.OTelContext, len(carried))
		for key, value := range carried {
			out[key] = value
		}
		return out
	}
	return agentruntime.OTelContext{"traceparent": TraceParent}
}

// Extract records the carried trace and stores it on a child ctx so a later Inject round-trips it.
func (o *FakeObserver) Extract(ctx context.Context, carrier agentruntime.OTelContext) context.Context {
	if len(carrier) == 0 {
		return ctx
	}
	o.mu.Lock()
	o.lastSeen = carrier
	o.mu.Unlock()
	return context.WithValue(ctx, fakeCarrierKey{}, carrier)
}

// Flush records a flush call (the shutdown OTel-flush assertion).
func (o *FakeObserver) Flush(_ context.Context) error {
	o.mu.Lock()
	defer o.mu.Unlock()
	o.flushed++
	return nil
}

// FlushCount returns how many times Flush was called (>=1 proves the shutdown flush ran).
func (o *FakeObserver) FlushCount() int {
	o.mu.Lock()
	defer o.mu.Unlock()
	return o.flushed
}

// LastExtracted returns the carrier last passed to Extract (proves a consumed control verb's trace
// was extracted — the OTel-on-control-message half).
func (o *FakeObserver) LastExtracted() agentruntime.OTelContext {
	o.mu.Lock()
	defer o.mu.Unlock()
	return o.lastSeen
}

// fakeCarrierKey is the private context key the fake observer round-trips a carrier under.
type fakeCarrierKey struct{}

// compile-time assertion: *FakeObserver is an agentruntime.Observer.
var _ agentruntime.Observer = (*FakeObserver)(nil)

// FixedClock is a deterministic agentruntime.Clock so heartbeat stamps + EmitTime are reproducible.
type FixedClock struct{}

// Now returns a fixed instant.
func (FixedClock) Now() time.Time { return time.Date(2026, time.June, 14, 12, 0, 0, 0, time.UTC) }
