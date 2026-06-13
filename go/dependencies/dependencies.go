// Package dependencies defines the universal port set — the hexagon's outbound edges
// (ADR-0009 A) — plus the discipline every per-library Deps type obeys.
//
// It is an import-only LEAF: it depends on no other Eden pattern (not configuration,
// not observability, not errors), so the entire library graph can import it without a
// cycle. It owns the SMALL, STABLE ports nearly every Eden library needs — Clock,
// RandomSource, Sink — and the wiring helpers (Resolve, Validate). It does NOT own
// domain ports (Secrets, Models, Platform): those are declared by the pattern that
// consumes them and are added by each library to its OWN Deps struct. This package is
// the floor of the hexagon, not the ceiling.
//
// This package has no New of its own: dependencies is the SECOND ARGUMENT to every
// other library's spine — New(configuration, dependencies) -> (Component, error) — not
// a component with its own constructor. Resolve/Validate are the surface it offers; the
// spine it serves lives in each consuming library.
package dependencies

import (
	"context"
	"crypto/rand"
	"io"
	"time"
)

// ---- Universal ports (each ≤5 methods; accept-interfaces-return-concrete).

// Clock is the universal source of "now" and of time-based waiting. No component may
// call time.Now / time.After / time.Sleep directly; it asks the injected Clock, which
// is what makes every time-dependent component deterministic under a fake.
//
// Implementations must be safe for concurrent use.
type Clock interface {
	// Now returns the current instant. It is monotonic-aware: the returned time
	// carries a monotonic reading per the stdlib time contract. Cannot block, so it
	// takes no context.
	Now() time.Time
	// After returns a channel that delivers once after d has elapsed on this Clock's
	// timeline. It honors ctx cancellation so a blocking select unwinds cleanly on
	// shutdown; on cancellation the channel is never sent on.
	After(ctx context.Context, d time.Duration) <-chan time.Time
}

// RandomSource is the universal entropy port: a stream of cryptographically-suitable
// random bytes for IDs, jitter, sampling, and shuffles. It mirrors io.Reader exactly,
// so *math/rand/v2.ChaCha8, crypto/rand, and a seeded test source are all drop-in with
// zero adapter code.
//
// Read must fill p completely or return a non-nil error (the io.ReadFull contract that
// crypto/rand guarantees), and must be safe for concurrent use.
type RandomSource interface {
	Read(p []byte) (n int, err error)
}

// Sink is the universal "emit one structured record outward" port — the seam the
// observability and logging patterns adapt. dependencies owns only the minimal verb so
// it stays a leaf; the rich Event type lives in the observability library, which
// supplies a Sink adapter over this port. record is typed any ON PURPOSE: typing it as
// observability.Event would force this leaf to import observability and invert the
// graph.
//
// Implementations must be safe for concurrent use.
type Sink interface {
	// Emit hands one record outward. It is best-effort and must NOT block business
	// code on a slow backend; it honors ctx cancellation. A nil error means accepted,
	// not delivered.
	Emit(ctx context.Context, record any) error
}

// Set is the composition-root currency: the bundle of every universal port, assembled
// once at the edge. It is a struct of interfaces, never an interface itself — there is
// no Dependencies interface to bloat. Per-library Deps structs are built BY NARROWING
// this: a component that only needs time declares a Deps holding just a Clock, never
// the whole Set (see §5). Set is shared read-only after assembly.
//
// The zero Set is INVALID by design: a nil port is a wiring bug, not a default.
// Defaulting is an explicit, opt-in step (Resolve), never silent on field access.
type Set struct {
	Clock  Clock
	Random RandomSource
	Sink   Sink
}

// Resolve returns a copy of s with any nil universal port replaced by its real,
// host-backed adapter (system clock, crypto/rand entropy, discard sink). It is one of
// two sanctioned ways to obtain real defaults (RealClock/RealRandom/DiscardSink being
// the per-port form), and it is pure in the constructor-purity sense: it allocates
// adapter VALUES whose methods touch the environment at call time, but Resolve itself
// performs no I/O, reads no clock, and reads no env.
//
// Call Resolve ONLY at the composition root — never inside a component's New. Binding
// defaults inside New would read the wall clock at construction, the exact impurity the
// spine (10 §4) forbids. Resolve never overwrites a non-nil port: explicit wiring
// always wins, so an injected fake Clock survives.
func Resolve(s Set) Set {
	if s.Clock == nil {
		s.Clock = RealClock()
	}
	if s.Random == nil {
		s.Random = RealRandom(nil)
	}
	if s.Sink == nil {
		s.Sink = DiscardSink()
	}
	return s
}

// Validate reports the first nil universal port as a typed error, for composition roots
// (and component Constructors checking the ports they NARROWED in) that prefer to fail
// loudly on an unwired dependency rather than silently default. Returns nil when every
// universal port is non-nil. Pure: no I/O.
func Validate(s Set) error {
	switch {
	case s.Clock == nil:
		return &MissingPortError{Port: "Clock"}
	case s.Random == nil:
		return &MissingPortError{Port: "RandomSource"}
	case s.Sink == nil:
		return &MissingPortError{Port: "Sink"}
	default:
		return nil
	}
}

// MissingPortError reports an unwired universal port. Inspect it structurally via
// errors.AsType[*dependencies.MissingPortError](err) (Go 1.26); component Constructors
// wrap it with %w when reporting a narrowed port.
type MissingPortError struct{ Port string }

func (e *MissingPortError) Error() string { return "dependencies: missing port " + e.Port }

// ---- Real providers: the ONLY place wall-clock / crypto entropy is bound. ----
// Each returns an adapter VALUE; the value's METHODS (not these constructors) touch the
// environment, so calling them is pure. They are invoked by the composition root and
// passed INTO a Set / a library's Deps — NEVER called inside a component's New.
//
// These three return the PORT INTERFACE rather than a concrete type by contract
// (contracts/dependencies.md §2, frozen surface; rationale 5). The real adapters
// systemClock/cryptoRandom/discardSink are deliberately UNEXPORTED so business code has
// no public concrete type to bind against and must go through the injected port — that
// unexported-ness is the load-bearing seam. Returning a concrete type here would force
// exporting the adapter and break the contract. The ireturn "return concrete" rule is
// therefore wrong-for-contract for exactly these three constructors; nolint is scoped to
// each, with the contract as the cited authority.

// RealClock returns a Clock backed by the operating-system wall clock and timers.
//
//nolint:ireturn // contract §2: returns the Clock port; the systemClock adapter is unexported by design (rationale 5).
func RealClock() Clock { return systemClock{} }

// RealRandom returns a RandomSource backed by entropy; a nil entropy reader means
// crypto/rand.
//
//nolint:ireturn // contract §2: returns the RandomSource port; the cryptoRandom adapter is unexported by design (rationale 5).
func RealRandom(entropy io.Reader) RandomSource {
	if entropy == nil {
		entropy = rand.Reader
	}
	return cryptoRandom{entropy: entropy}
}

// DiscardSink returns a Sink that drops every record — the safe default when a component
// is wired without observability (tests, smoke binaries).
//
//nolint:ireturn // contract §2: returns the Sink port; the discardSink adapter is unexported by design (rationale 5).
func DiscardSink() Sink { return discardSink{} }

// systemClock, cryptoRandom, and discardSink are the real adapters, UNEXPORTED on
// purpose: business code has no public type to bind against and must go through the
// injected port, so the real-vs-fake decision has exactly one seam (the providers
// above, called at the composition root).
type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

func (systemClock) After(ctx context.Context, d time.Duration) <-chan time.Time {
	out := make(chan time.Time, 1)
	timer := time.NewTimer(d)
	go func() {
		defer timer.Stop()
		select {
		case t := <-timer.C:
			out <- t
		case <-ctx.Done():
			// On cancellation the channel is never sent on; the receiver's select
			// unwinds via its own ctx.Done() / shutdown path.
		}
	}()
	return out
}

type cryptoRandom struct{ entropy io.Reader }

// Read mirrors io.Reader exactly (contract §2 RandomSource). The io.ReadFull error
// (io.EOF / io.ErrUnexpectedEOF) is returned UNWRAPPED on purpose: an io.Reader caller
// must be able to compare it to io.EOF, which wrapping would defeat — the io.Reader
// contract is the cited authority over wrapcheck here.
//
//nolint:wrapcheck // contract §2: RandomSource is io.Reader-shaped; its sentinel errors must stay comparable, so they pass through unwrapped.
func (c cryptoRandom) Read(p []byte) (int, error) { return io.ReadFull(c.entropy, p) }

type discardSink struct{}

func (discardSink) Emit(ctx context.Context, record any) error { return nil }
