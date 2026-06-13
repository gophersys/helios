package observabilitytest_test

import (
	"context"
	stderrors "errors"
	"testing"
	"time"

	"github.com/gophersys/libs/go/observability"
	"github.com/gophersys/libs/go/observability/observabilitytest"
)

// TestFakeConformance runs the shared contract conformance suite (§4) against the
// fake package's own Deps-aware double, proving the fake satisfies the same
// substitutability properties the real adapter does (08 §2).
func TestFakeConformance(t *testing.T) {
	t.Parallel()
	observabilitytest.RunFakeConformance(t)
}

// ── kernel-injection fake behavior (the *Provider obtained from New) ────────.

func fixedClock() time.Time { return time.Unix(1700000000, 0).UTC() }

func TestFakeRecordsEvents(t *testing.T) {
	t.Parallel()
	p := observabilitytest.New(fixedClock)
	ctx := context.Background()
	p.Emit(ctx, observability.Event{Name: "phase.start", Plane: observability.PlaneAgent, Severity: observability.SeverityInfo})
	p.Emit(ctx, observability.Event{
		Name: "gate.decision", Plane: observability.PlaneAgent, Severity: observability.SeverityInfo,
		Fields: []observability.Field{observability.Bool("gate.passed", true)},
	})

	events := p.Events()
	if len(events) != 2 {
		t.Fatalf("Events() len = %d, want 2", len(events))
	}
	if events[0].Name != "phase.start" || events[1].Name != "gate.decision" {
		t.Errorf("events out of order: %q, %q", events[0].Name, events[1].Name)
	}
}

func TestFakeFindByName(t *testing.T) {
	t.Parallel()
	p := observabilitytest.New(fixedClock)
	ctx := context.Background()
	p.Emit(ctx, observability.Event{Name: "phase.start", Severity: observability.SeverityInfo})
	p.Emit(ctx, observability.Event{Name: "cost.ledger", Severity: observability.SeverityInfo})
	p.Emit(ctx, observability.Event{Name: "cost.ledger", Severity: observability.SeverityInfo})

	if got := len(p.Find("cost.ledger")); got != 2 {
		t.Errorf("Find(cost.ledger) len = %d, want 2", got)
	}
	if got := len(p.Find("phase.start")); got != 1 {
		t.Errorf("Find(phase.start) len = %d, want 1", got)
	}
	if got := len(p.Find("missing")); got != 0 {
		t.Errorf("Find(missing) len = %d, want 0", got)
	}
}

func TestFakeDefaultPlaneOnUnset(t *testing.T) {
	t.Parallel()
	p := observabilitytest.New(fixedClock)
	// An Event emitted as PlaneUnset must land on the fake's default (PlaneSelf),
	// never stay PlaneUnset.
	p.Emit(context.Background(), observability.Event{Name: "e", Severity: observability.SeverityInfo})
	got := p.Events()[0].Plane
	if got != observability.PlaneSelf {
		t.Errorf("unset Event Plane = %v, want PlaneSelf", got)
	}
}

func TestFakeWithInheritanceAndParentUnaffected(t *testing.T) {
	t.Parallel()
	p := observabilitytest.New(fixedClock)
	ctx := context.Background()
	child := p.With(observability.String("run.id", "r-1"))
	child.Emit(ctx, observability.Event{
		Name: "child", Severity: observability.SeverityInfo,
		Fields: []observability.Field{observability.String("phase", "implement")},
	})
	p.Emit(ctx, observability.Event{Name: "parent", Severity: observability.SeverityInfo})

	events := p.Events()
	var childEvent, parentEvent observability.Event
	for _, e := range events {
		switch e.Name {
		case "child":
			childEvent = e
		case "parent":
			parentEvent = e
		}
	}
	if len(childEvent.Fields) != 2 {
		t.Fatalf("child Fields = %d, want 2 (inherited + call-site)", len(childEvent.Fields))
	}
	if childEvent.Fields[0].Key != "run.id" || childEvent.Fields[1].Key != "phase" {
		t.Errorf("child Fields order = %q,%q; want run.id,phase", childEvent.Fields[0].Key, childEvent.Fields[1].Key)
	}
	for _, f := range parentEvent.Fields {
		if f.Key == "run.id" {
			t.Error("With leaked the child's inherited field onto the parent")
		}
	}
}

func TestFakeScopeStampsDuration(t *testing.T) {
	t.Parallel()
	// A step clock lets the close func compute a deterministic duration.
	now := time.Unix(1700000000, 0).UTC()
	clock := func() time.Time { return now }
	p := observabilitytest.New(clock)
	ctx := context.Background()
	_, end := p.Scope(ctx, "phase.start", observability.String("phase", "implement"))
	now = now.Add(2 * time.Second) // advance the clock before closing
	end(observability.Outcome{})

	span := p.Find("phase.start")
	if len(span) != 1 {
		t.Fatalf("Scope emitted %d span Events, want 1", len(span))
	}
	var dur time.Duration
	var sawOK bool
	for _, f := range span[0].Fields {
		switch f.Key {
		case "duration":
			if d, ok := f.Value.TelemetryValue().(time.Duration); ok {
				dur = d
			}
		case "ok":
			sawOK = true
		}
	}
	if dur != 2*time.Second {
		t.Errorf("span duration = %v, want 2s", dur)
	}
	if !sawOK {
		t.Error("span Event missing the ok outcome field")
	}
}

func TestFakeScopeRecordsOutcomeError(t *testing.T) {
	t.Parallel()
	p := observabilitytest.New(fixedClock)
	_, end := p.Scope(context.Background(), "phase.start")
	end(observability.Outcome{Err: stderrors.New("phase failed")})

	span := p.Find("phase.start")[0]
	var ok bool
	for _, f := range span.Fields {
		if f.Key == "ok" {
			if b, isBool := f.Value.TelemetryValue().(bool); isBool {
				ok = b
			}
		}
	}
	if ok {
		t.Error("a failed Outcome recorded ok=true")
	}
}

func TestFakeLogIsAView(t *testing.T) {
	t.Parallel()
	p := observabilitytest.New(fixedClock)
	p.Log(context.Background(), observability.SeverityWarn, "disk low",
		observability.String("mount", "/data"))
	events := p.Events()
	if len(events) != 1 {
		t.Fatalf("Log produced %d Events, want 1", len(events))
	}
	if events[0].Severity != observability.SeverityWarn {
		t.Errorf("Log Event Severity = %v, want SeverityWarn", events[0].Severity)
	}
}

func TestFakeLedgersRoundTrip(t *testing.T) {
	t.Parallel()
	p := observabilitytest.New(fixedClock)
	led := observability.Ledger{
		RunID: "run-7", PhaseID: "verify", Model: "claude", Harness: "claudecode",
		TokensIn: 800, TokensOut: 400, CacheHits: 100, CostMicros: 4242,
		Retries: 3, WallTime: 9 * time.Second,
	}
	p.Emit(context.Background(), observability.LedgerEvent(time.Time{}, led))

	got := p.Ledgers()
	if len(got) != 1 {
		t.Fatalf("Ledgers() len = %d, want 1", len(got))
	}
	if got[0] != led {
		t.Errorf("Ledgers()[0] = %+v, want %+v", got[0], led)
	}
}

func TestFakeAssertNoSecrets(t *testing.T) {
	t.Parallel()
	p := observabilitytest.New(fixedClock)
	const canary = "s3cr3t"
	// A redacting Valuer never renders the canary → AssertNoSecrets holds.
	p.Emit(context.Background(), observability.Event{
		Name: "e", Severity: observability.SeverityInfo,
		Fields: []observability.Field{observability.Any("token", redacting{canary})},
	})
	if err := p.AssertNoSecrets(canary); err != nil {
		t.Errorf("AssertNoSecrets failed on a redacting Valuer: %v", err)
	}

	// A leaking Valuer renders the canary → AssertNoSecrets reports it.
	p.Emit(context.Background(), observability.Event{
		Name: "leak", Severity: observability.SeverityInfo,
		Fields: []observability.Field{observability.Any("token", leaking{canary})},
	})
	if err := p.AssertNoSecrets(canary); err == nil {
		t.Error("AssertNoSecrets did not catch a leaking Valuer")
	}
}

func TestFakeLedgersSurvivesNilValuerField(t *testing.T) {
	t.Parallel()
	// A cost.ledger Event carrying Any("tokens.in", nil) used to nil-deref in
	// decodeLedger (helpers.go) when Ledgers() walked its Fields. Any() now
	// substitutes a no-value Valuer and decodeLedger guards a nil Value, so the
	// inspection path can no longer crash on a poison Field.
	p := observabilitytest.New(fixedClock)
	p.Emit(context.Background(), observability.Event{
		Name:     "cost.ledger",
		Severity: observability.SeverityInfo,
		Fields: []observability.Field{
			observability.Any("tokens.in", nil),
			observability.String("run.id", "run-nil"),
		},
	})
	// Must not panic.
	got := p.Ledgers()
	if len(got) != 1 {
		t.Fatalf("Ledgers() len = %d, want 1", len(got))
	}
	if got[0].RunID != "run-nil" {
		t.Errorf("Ledgers()[0].RunID = %q, want %q (decode continued past the nil-valued field)", got[0].RunID, "run-nil")
	}
}

func TestFakeFlushNoError(t *testing.T) {
	t.Parallel()
	p := observabilitytest.New(fixedClock)
	if err := p.Flush(context.Background()); err != nil {
		t.Errorf("fake Flush returned error: %v", err)
	}
}

func TestFailingExporterReturnsErr(t *testing.T) {
	t.Parallel()
	want := stderrors.New("wire down")
	exp := observabilitytest.FailingExporter{Err: want}
	got := exp.Export(context.Background(), nil)
	if !stderrors.Is(got, want) {
		t.Errorf("FailingExporter.Export = %v, want %v", got, want)
	}
}

func TestFakeConcurrentEmit(t *testing.T) {
	t.Parallel()
	p := observabilitytest.New(fixedClock)
	const n = 200
	done := make(chan struct{})
	for i := 0; i < n; i++ {
		go func() {
			p.Emit(context.Background(), observability.Event{Name: "e", Severity: observability.SeverityInfo})
			done <- struct{}{}
		}()
	}
	for i := 0; i < n; i++ {
		<-done
	}
	close(done)
	if got := len(p.Events()); got != n {
		t.Errorf("concurrent Emit recorded %d Events, want %d", got, n)
	}
}

// redacting models a Valuer whose projection never exposes the raw canary.
type redacting struct{ raw string }

func (redacting) TelemetryValue() any { return "secrets.Secret(REDACTED)" }

// leaking models a buggy Valuer whose projection exposes the canary, which
// AssertNoSecrets must catch.
type leaking struct{ raw string }

func (l leaking) TelemetryValue() any { return l.raw }
