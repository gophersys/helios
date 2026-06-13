package dependencies_test

import (
	"bytes"
	"context"
	"errors"
	"io"
	"sync"
	"testing"
	"time"

	"github.com/gophersys/libs/go/dependencies"
)

// ---- Set zero-value / wiring discipline (§2 Set, rationale 8).

// The zero Set is INVALID by design: every universal port is nil.
func TestZeroSetIsInvalid(t *testing.T) {
	t.Parallel()
	var s dependencies.Set
	if s.Clock != nil || s.Random != nil || s.Sink != nil {
		t.Fatalf("zero Set must have nil ports, got %+v", s)
	}
	if err := dependencies.Validate(s); err == nil {
		t.Fatal("Validate(zero Set) must return an error, got nil")
	}
}

// ---- Real providers bind real adapters (§2, rationale 4/5).

func TestRealProvidersAreNonNil(t *testing.T) {
	t.Parallel()
	if dependencies.RealClock() == nil {
		t.Fatal("RealClock() returned nil")
	}
	if dependencies.RealRandom(nil) == nil {
		t.Fatal("RealRandom(nil) returned nil")
	}
	if dependencies.DiscardSink() == nil {
		t.Fatal("DiscardSink() returned nil")
	}
}

// RealClock.Now returns a real wall-clock instant carrying a monotonic reading.
func TestRealClockNowMonotonicAware(t *testing.T) {
	t.Parallel()
	c := dependencies.RealClock()
	a := c.Now()
	b := c.Now()
	if b.Before(a) {
		t.Fatalf("Now() went backward: %v then %v", a, b)
	}
	// A real Now carries a monotonic reading. time.Equal ignores the monotonic part by
	// design, so compare the rendered String(): a monotonic time prints a trailing
	// " m=±..." that Round(0) (which strips the reading) does not.
	if a.String() == a.Round(0).String() {
		t.Fatalf("RealClock.Now() must carry a monotonic reading (stdlib time contract); got %q", a.String())
	}
}

// RealClock.After fires after d elapses on the real timeline.
func TestRealClockAfterFires(t *testing.T) {
	t.Parallel()
	c := dependencies.RealClock()
	ch := c.After(context.Background(), 5*time.Millisecond)
	select {
	case <-ch:
		// fired
	case <-time.After(time.Second):
		t.Fatal("RealClock.After did not fire within 1s")
	}
}

// RealClock.After honors ctx cancellation: the channel is never sent on, and the
// select unwinds (we observe it by the channel not delivering).
func TestRealClockAfterRespectsCancellation(t *testing.T) {
	t.Parallel()
	c := dependencies.RealClock()
	ctx, cancel := context.WithCancel(context.Background())
	ch := c.After(ctx, time.Hour) // would never fire on its own in the test window
	cancel()
	select {
	case v, ok := <-ch:
		// On cancellation the channel must NOT carry a tick. Either it is closed
		// (ok==false) or it simply never sends. A delivered time value is a violation.
		if ok {
			t.Fatalf("After channel delivered a value %v after cancellation; must be un-sent", v)
		}
	case <-time.After(time.Second):
		// Acceptable: channel never sent, select would unwind on a real shutdown.
	}
}

// RealRandom fills the buffer completely (io.ReadFull contract).
func TestRealRandomFullRead(t *testing.T) {
	t.Parallel()
	r := dependencies.RealRandom(nil)
	p := make([]byte, 64)
	n, err := r.Read(p)
	if err != nil {
		t.Fatalf("RealRandom.Read error: %v", err)
	}
	if n != len(p) {
		t.Fatalf("RealRandom.Read short read: got %d want %d", n, len(p))
	}
}

// RealRandom honors an explicit entropy reader when one is supplied.
func TestRealRandomUsesSuppliedEntropy(t *testing.T) {
	t.Parallel()
	want := bytes.Repeat([]byte{0xAB}, 32)
	r := dependencies.RealRandom(bytes.NewReader(want))
	got := make([]byte, len(want))
	n, err := r.Read(got)
	if err != nil {
		t.Fatalf("Read error: %v", err)
	}
	if n != len(want) || !bytes.Equal(got, want) {
		t.Fatalf("RealRandom did not use supplied entropy: got %x want %x", got, want)
	}
}

// RealRandom over a short entropy reader must return a non-nil error rather than a
// silent short read (io.ReadFull contract).
func TestRealRandomShortEntropyErrors(t *testing.T) {
	t.Parallel()
	r := dependencies.RealRandom(bytes.NewReader([]byte{0x01, 0x02})) // only 2 bytes
	p := make([]byte, 16)
	_, err := r.Read(p)
	if err == nil {
		t.Fatal("RealRandom over short entropy must return a non-nil error")
	}
}

// DiscardSink accepts and drops every record.
func TestDiscardSinkEmit(t *testing.T) {
	t.Parallel()
	s := dependencies.DiscardSink()
	if err := s.Emit(context.Background(), "anything"); err != nil {
		t.Fatalf("DiscardSink.Emit returned error: %v", err)
	}
	if err := s.Emit(context.Background(), nil); err != nil {
		t.Fatalf("DiscardSink.Emit(nil) returned error: %v", err)
	}
}

// ---- Resolve (§2, §4 Resolve purity & idempotence).

// Resolve fills exactly the nil ports with real adapters.
func TestResolveFillsNilPorts(t *testing.T) {
	t.Parallel()
	got := dependencies.Resolve(dependencies.Set{})
	if got.Clock == nil || got.Random == nil || got.Sink == nil {
		t.Fatalf("Resolve(zero) must fill all ports, got %+v", got)
	}
	if err := dependencies.Validate(got); err != nil {
		t.Fatalf("Resolve(zero) must produce a complete Set, Validate said: %v", err)
	}
}

// Resolve never overwrites a non-nil port: explicit wiring always wins.
func TestResolveNeverOverwrites(t *testing.T) {
	t.Parallel()
	clock := stubClock{}
	random := stubRandom{}
	sink := stubSink{}
	in := dependencies.Set{Clock: clock, Random: random, Sink: sink}
	got := dependencies.Resolve(in)
	if got.Clock != dependencies.Clock(clock) {
		t.Error("Resolve overwrote a non-nil Clock")
	}
	if got.Random != dependencies.RandomSource(random) {
		t.Error("Resolve overwrote a non-nil Random")
	}
	if got.Sink != dependencies.Sink(sink) {
		t.Error("Resolve overwrote a non-nil Sink")
	}
}

// Resolve fills only the nil ports, leaving the wired one untouched (mixed case).
func TestResolveMixed(t *testing.T) {
	t.Parallel()
	clock := stubClock{}
	got := dependencies.Resolve(dependencies.Set{Clock: clock})
	if got.Clock != dependencies.Clock(clock) {
		t.Error("Resolve overwrote the wired Clock")
	}
	if got.Random == nil || got.Sink == nil {
		t.Error("Resolve did not fill the nil Random/Sink")
	}
}

// Resolve is idempotent: Resolve(Resolve(s)) == Resolve(s).
func TestResolveIdempotent(t *testing.T) {
	t.Parallel()
	once := dependencies.Resolve(dependencies.Set{})
	twice := dependencies.Resolve(once)
	if once != twice {
		t.Fatalf("Resolve not idempotent: %+v != %+v", once, twice)
	}
}

// Resolve performs no I/O and reads no clock: it must not mutate its argument
// (it takes Set by value and returns a copy).
func TestResolveDoesNotMutateArgument(t *testing.T) {
	t.Parallel()
	in := dependencies.Set{}
	_ = dependencies.Resolve(in)
	if in.Clock != nil || in.Random != nil || in.Sink != nil {
		t.Fatal("Resolve mutated its by-value argument")
	}
}

// ---- Validate (§2, §4 Validate completeness).

func TestValidateFullSet(t *testing.T) {
	t.Parallel()
	full := dependencies.Set{Clock: stubClock{}, Random: stubRandom{}, Sink: stubSink{}}
	if err := dependencies.Validate(full); err != nil {
		t.Fatalf("Validate(full Set) returned error: %v", err)
	}
}

func TestValidateReportsFirstMissingPort(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name string
		set  dependencies.Set
		want string
	}{
		{"all nil -> Clock first", dependencies.Set{}, "Clock"},
		{"missing Random", dependencies.Set{Clock: stubClock{}}, "RandomSource"},
		{"missing Sink", dependencies.Set{Clock: stubClock{}, Random: stubRandom{}}, "Sink"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			err := dependencies.Validate(tc.set)
			if err == nil {
				t.Fatal("expected error, got nil")
			}
			var missing *dependencies.MissingPortError
			if !errors.As(err, &missing) {
				t.Fatalf("error is not *MissingPortError: %T", err)
			}
			if missing.Port != tc.want {
				t.Fatalf("MissingPortError.Port = %q, want %q", missing.Port, tc.want)
			}
		})
	}
}

// The MissingPortError is recoverable via errors.As (the AsType idiom in §4).
func TestMissingPortErrorMessageAndAsType(t *testing.T) {
	t.Parallel()
	err := dependencies.Validate(dependencies.Set{})
	want := "dependencies: missing port Clock"
	if err.Error() != want {
		t.Fatalf("Error() = %q, want %q", err.Error(), want)
	}
	var missing *dependencies.MissingPortError
	if !errors.As(err, &missing) {
		t.Fatal("Validate error must be recoverable via errors.As")
	}
	if missing.Port != "Clock" {
		t.Fatalf("Port = %q, want Clock", missing.Port)
	}
}

// A component Constructor wraps MissingPortError with %w and it stays inspectable
// (§5 Site 2: engine.New wraps the narrowed Clock port).
func TestMissingPortErrorWrappable(t *testing.T) {
	t.Parallel()
	base := &dependencies.MissingPortError{Port: "Clock"}
	wrapped := errors.Join(errors.New("engine"), base) // any %w-style chain
	var missing *dependencies.MissingPortError
	if !errors.As(wrapped, &missing) {
		t.Fatal("wrapped MissingPortError must remain recoverable via errors.As")
	}
	if missing.Port != "Clock" {
		t.Fatalf("Port = %q, want Clock", missing.Port)
	}
}

// ---- Ports satisfy their interfaces (compile-time, §2).

// TestRealAdaptersSatisfyPorts proves the real providers return values usable as their
// ports. The provider signatures already return the port interface, so a typed-var
// assertion would be redundant (staticcheck QF1011); the meaningful check is that each
// returned value is a live, non-nil port — which is what a narrowing composition root
// relies on.
func TestRealAdaptersSatisfyPorts(t *testing.T) {
	t.Parallel()
	clock := dependencies.RealClock()
	random := dependencies.RealRandom(nil)
	sink := dependencies.DiscardSink()
	if clock == nil || random == nil || sink == nil {
		t.Fatalf("real providers returned a nil port: clock=%v random=%v sink=%v", clock, random, sink)
	}
}

// RandomSource mirrors io.Reader exactly: a *bytes.Reader is a drop-in with zero
// adapter code (§2 RandomSource doc), proving the port is io.Reader-shaped.
func TestRandomSourceIsIOReaderShaped(t *testing.T) {
	t.Parallel()
	var _ dependencies.RandomSource = bytes.NewReader(nil)
	var _ io.Reader = dependencies.RealRandom(nil)
}

// ---- Concurrency: real adapters survive the race detector (§4).

func TestRealAdaptersConcurrent(t *testing.T) {
	t.Parallel()
	set := dependencies.Resolve(dependencies.Set{})
	var wg sync.WaitGroup
	for range 32 {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = set.Clock.Now()
			p := make([]byte, 8)
			if _, err := set.Random.Read(p); err != nil {
				return // a real read error is asserted in TestRealRandomFullRead
			}
			if err := set.Sink.Emit(context.Background(), "rec"); err != nil {
				return // best-effort emit; correctness asserted in TestDiscardSinkEmit
			}
		}()
	}
	wg.Wait()
}

// ---- local stubs (distinct from the canonical fakes; prove substitutability).

type stubClock struct{}

func (stubClock) Now() time.Time { return time.Unix(0, 0) }
func (stubClock) After(ctx context.Context, d time.Duration) <-chan time.Time {
	ch := make(chan time.Time, 1)
	return ch
}

type stubRandom struct{}

func (stubRandom) Read(p []byte) (int, error) { return len(p), nil }

type stubSink struct{}

func (stubSink) Emit(ctx context.Context, record any) error { return nil }
