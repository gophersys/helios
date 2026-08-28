package dependencies_test

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"testing"
	"time"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
)

// The `property` ctl.sh verb runs `go test ./... -race` with RAPID_CHECKS set in the process
// environment (default 1000 iterations/property, ADR-0020 dimension (a) threshold); rapid reads
// it directly.

// portMask draws which of the three universal ports are wired (non-nil) in a Set, so a property
// can exercise every one of the 2^3 nil/non-nil combinations. A wired port is one of the local
// stubs (substitutability is the contract — any implementation of the port is acceptable).
func drawSet(rt *rapid.T) (set dependencies.Set, hasClock, hasRandom, hasSink bool) {
	hasClock = rapid.Bool().Draw(rt, "hasClock")
	hasRandom = rapid.Bool().Draw(rt, "hasRandom")
	hasSink = rapid.Bool().Draw(rt, "hasSink")
	if hasClock {
		set.Clock = stubClock{}
	}
	if hasRandom {
		set.Random = stubRandom{}
	}
	if hasSink {
		set.Sink = stubSink{}
	}
	return set, hasClock, hasRandom, hasSink
}

// TestProperty_ResolveFillsExactlyNilPorts asserts the core Resolve invariant over the WHOLE
// nil/non-nil lattice (§2 Resolve, §4 ResolvePurityAndIdempotence): a wired port is NEVER
// overwritten, every nil port is filled with a real adapter, and the result always validates.
func TestProperty_ResolveFillsExactlyNilPorts(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		in, hasClock, hasRandom, hasSink := drawSet(rt)
		// Capture the wired identities BEFORE Resolve so we can prove they survive untouched.
		wantClock, wantRandom, wantSink := in.Clock, in.Random, in.Sink

		got := dependencies.Resolve(in)

		// Every port is non-nil after Resolve, regardless of input.
		if got.Clock == nil || got.Random == nil || got.Sink == nil {
			rt.Fatalf("Resolve left a nil port: %+v", got)
		}
		if err := dependencies.Validate(got); err != nil {
			rt.Fatalf("Resolve must produce a complete Set, Validate said: %v", err)
		}
		// A wired port is the SAME value after Resolve (never overwritten); a nil port is now
		// a freshly-bound real adapter (differs from the zero nil).
		if hasClock && got.Clock != wantClock {
			rt.Fatal("Resolve overwrote a wired Clock")
		}
		if hasRandom && got.Random != wantRandom {
			rt.Fatal("Resolve overwrote a wired Random")
		}
		if hasSink && got.Sink != wantSink {
			rt.Fatal("Resolve overwrote a wired Sink")
		}
	})
}

// TestProperty_ResolveIdempotent asserts Resolve(Resolve(s)) == Resolve(s) for every input
// (the idempotency invariant, §4): the second pass binds nothing new because the first already
// filled every nil, and a comparable Set means equality is exact.
func TestProperty_ResolveIdempotent(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		in, _, _, _ := drawSet(rt)
		once := dependencies.Resolve(in)
		twice := dependencies.Resolve(once)
		if once != twice {
			rt.Fatalf("Resolve not idempotent: %+v != %+v", once, twice)
		}
	})
}

// TestProperty_ResolveDoesNotMutateArgument asserts Resolve performs no I/O and takes its Set by
// value: whatever the input, the caller's argument is unchanged after the call (§4 purity).
func TestProperty_ResolveDoesNotMutateArgument(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		in, _, _, _ := drawSet(rt)
		before := in
		_ = dependencies.Resolve(in)
		if in != before {
			rt.Fatalf("Resolve mutated its by-value argument: %+v -> %+v", before, in)
		}
	})
}

// TestProperty_ValidateReportsFirstNilInFixedOrder asserts Validate names the first nil port in
// the FIXED precedence Clock → RandomSource → Sink for every subset (§2 Validate). The port name
// is the contract; this pins it across the whole lattice so a reordering regression is caught.
func TestProperty_ValidateReportsFirstNilInFixedOrder(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		in, hasClock, hasRandom, hasSink := drawSet(rt)
		err := dependencies.Validate(in)

		// Determine the expected first-missing port by the documented precedence.
		var want string
		switch {
		case !hasClock:
			want = "Clock"
		case !hasRandom:
			want = "RandomSource"
		case !hasSink:
			want = "Sink"
		default:
			want = "" // complete set → nil error
		}

		if want == "" {
			if err != nil {
				rt.Fatalf("Validate(complete) = %v, want nil", err)
			}
			return
		}
		var missing *dependencies.MissingPortError
		if !errors.As(err, &missing) {
			rt.Fatalf("Validate error is not *MissingPortError: %T (%v)", err, err)
		}
		if missing.Port != want {
			rt.Fatalf("first missing port = %q, want %q (set: clock=%v random=%v sink=%v)",
				missing.Port, want, hasClock, hasRandom, hasSink)
		}
	})
}

// TestProperty_MissingPortErrorSurvivesWrapping asserts a MissingPortError remains structurally
// recoverable through any number of %w wraps (§4 — a narrowing Constructor wraps it with %w and
// it stays AsType-inspectable). The Port name is the stable, inspectable contract.
func TestProperty_MissingPortErrorSurvivesWrapping(t *testing.T) {
	t.Parallel()
	ports := []string{"Clock", "RandomSource", "Sink"}
	rapid.Check(t, func(rt *rapid.T) {
		port := ports[rapid.IntRange(0, len(ports)-1).Draw(rt, "port")]
		depth := rapid.IntRange(0, 6).Draw(rt, "wrapDepth")
		var err error = &dependencies.MissingPortError{Port: port}
		for i := range depth {
			err = fmt.Errorf("layer-%d: %w", i, err)
		}
		var missing *dependencies.MissingPortError
		if !errors.As(err, &missing) {
			rt.Fatalf("MissingPortError lost through %d wraps: %T", depth, err)
		}
		if missing.Port != port {
			rt.Fatalf("Port drifted through wrapping: got %q want %q", missing.Port, port)
		}
	})
}

// TestProperty_RealRandomFullRead asserts the io.ReadFull contract over arbitrary buffer sizes
// (§2 RandomSource): the default crypto/rand-backed adapter fills p COMPLETELY and returns a nil
// error — never a short read with err==nil. This is the entropy port's load-bearing guarantee.
func TestProperty_RealRandomFullRead(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		size := rapid.IntRange(1, 4096).Draw(rt, "size")
		r := dependencies.RealRandom(nil)
		p := make([]byte, size)
		n, err := r.Read(p)
		if err != nil {
			rt.Fatalf("RealRandom.Read(%d) error: %v", size, err)
		}
		if n != size {
			rt.Fatalf("RealRandom.Read(%d) short read with nil err: got n=%d", size, n)
		}
	})
}

// TestProperty_RealRandomUsesSuppliedEntropy asserts that when an entropy reader holds AT LEAST
// the requested bytes, RealRandom returns exactly that prefix verbatim (§2: io.Reader-shaped,
// zero adapter code). Over arbitrary byte content + size this pins the "drop-in io.Reader"
// guarantee the contract rests on.
func TestProperty_RealRandomUsesSuppliedEntropy(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		want := rapid.SliceOfN(rapid.Byte(), 1, 512).Draw(rt, "entropy")
		r := dependencies.RealRandom(bytes.NewReader(want))
		got := make([]byte, len(want))
		n, err := r.Read(got)
		if err != nil {
			rt.Fatalf("Read error: %v", err)
		}
		if n != len(want) || !bytes.Equal(got, want) {
			rt.Fatalf("RealRandom did not return supplied entropy verbatim: got %x want %x", got, want)
		}
	})
}

// TestProperty_RealRandomShortEntropyErrors asserts that when the entropy reader holds FEWER
// bytes than requested, Read returns a non-nil error rather than a silent short read (the
// io.ReadFull contract, §2). Over arbitrary (have < want) pairs this pins the no-silent-short
// guarantee.
func TestProperty_RealRandomShortEntropyErrors(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		have := rapid.IntRange(0, 64).Draw(rt, "have")
		extra := rapid.IntRange(1, 64).Draw(rt, "extra")
		want := have + extra // strictly more than the reader can supply
		r := dependencies.RealRandom(bytes.NewReader(bytes.Repeat([]byte{0x5A}, have)))
		p := make([]byte, want)
		if _, err := r.Read(p); err == nil {
			rt.Fatalf("Read(want=%d) over %d-byte entropy must error, got nil", want, have)
		}
	})
}

// TestProperty_FakeClockAfterFiresIffDeadlineCrossed asserts the fake Clock's central timing
// invariant over arbitrary deadline/advance pairs (§3 fake Clock, §4): After(d) fires iff the
// cumulative advance reaches d. This is the determinism the port exists to provide — a regression
// in the deadline comparison (>= vs >) is caught across the whole space.
func TestProperty_FakeClockAfterFiresIffDeadlineCrossed(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		deadlineMs := rapid.IntRange(1, 1000).Draw(rt, "deadlineMs")
		advanceMs := rapid.IntRange(0, 1000).Draw(rt, "advanceMs")
		c := dependenciestest.NewClock(time.Unix(0, 0).UTC())
		ch := c.After(context.Background(), time.Duration(deadlineMs)*time.Millisecond)
		c.Advance(time.Duration(advanceMs) * time.Millisecond)

		fired := false
		select {
		case <-ch:
			fired = true
		default:
		}
		want := advanceMs >= deadlineMs
		if fired != want {
			rt.Fatalf("After(%dms) after Advance(%dms): fired=%v, want %v",
				deadlineMs, advanceMs, fired, want)
		}
	})
}

// TestProperty_FakeClockAdvanceIsAdditive asserts the fake Clock's Now is the exact sum of its
// advances over an arbitrary advance sequence (§3): time is a pure accumulator, never drifting.
func TestProperty_FakeClockAdvanceIsAdditive(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		start := time.Unix(0, 0).UTC()
		c := dependenciestest.NewClock(start)
		steps := rapid.SliceOfN(rapid.IntRange(0, 1000), 0, 20).Draw(rt, "steps")
		total := time.Duration(0)
		for _, ms := range steps {
			d := time.Duration(ms) * time.Millisecond
			c.Advance(d)
			total += d
		}
		if !c.Now().Equal(start.Add(total)) {
			rt.Fatalf("fake clock drifted: Now()=%v, want %v", c.Now(), start.Add(total))
		}
	})
}

// TestProperty_FakeRandomDeterministic asserts the seedable fake is reproducible over arbitrary
// seeds and read sizes (§3 Random): identical seed + identical read pattern → identical bytes.
// Reproducibility is the property randomized code paths rely on for determinism under test.
func TestProperty_FakeRandomDeterministic(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		var seed [32]byte
		copy(seed[:], rapid.SliceOfN(rapid.Byte(), 0, 32).Draw(rt, "seed"))
		size := rapid.IntRange(1, 1024).Draw(rt, "size")

		a := dependenciestest.NewRandom(seed)
		b := dependenciestest.NewRandom(seed)
		pa := make([]byte, size)
		pb := make([]byte, size)
		if _, err := a.Read(pa); err != nil {
			rt.Fatalf("a.Read: %v", err)
		}
		if _, err := b.Read(pb); err != nil {
			rt.Fatalf("b.Read: %v", err)
		}
		if !bytes.Equal(pa, pb) {
			rt.Fatal("same seed must yield the same byte stream")
		}
	})
}
