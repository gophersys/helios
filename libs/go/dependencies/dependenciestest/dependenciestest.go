// Package dependenciestest provides the canonical, controllable fakes for every
// universal port (the testing pattern, 10 §4), plus a one-call Fakes() helper. Every
// library's test wires THESE shared fakes — never ad-hoc local ones — so "fake ≡ real"
// is provable by the single shared conformance suite (§4). Fakes ship WITH the frozen
// contract (09 §4), before any consumer implements.
//
// This package is the LEAF home of the virtual-time and seeded-entropy ENGINE: Clock
// and Random are THE single definition of the timeline algorithm and the byte-stream
// algorithm for the whole library graph (one concept, one home — 10 §9). It sits below
// every consumer (it imports only dependencies), so a downstream <pattern>test fake
// ALIASES these types instead of re-implementing the algorithm — there is exactly one
// timeline, one byte stream, and one bug surface, asserted identical by the shared
// RunPortSuite running over the single fake. The timeline and byte stream are a FROZEN
// invariant: identical start/seed + identical call sequence ⇒ identical output forever;
// a change is breaking and may only ship behind a new constructor.
package dependenciestest

import (
	"context"
	"math/rand/v2"
	"sync"
	"time"

	"github.com/gophersys/libs/go/dependencies"
)

// Compile-time proof the fakes implement the production ports.
var (
	_ dependencies.Clock        = (*Clock)(nil)
	_ dependencies.RandomSource = (*Random)(nil)
	_ dependencies.Sink         = (*RecordingSink)(nil)
)

// Clock is a manually-advanced fake clock — the single virtual-time engine. Now is
// frozen until Advance is called; After channels fire when Advance crosses their
// deadline. Use NewClock for a chosen epoch (a zero start anchors at UnixEpoch). Safe
// for concurrent use.
type Clock struct {
	mu      sync.Mutex
	now     time.Time
	pending []*timer
}

type timer struct {
	deadline time.Time
	ch       chan time.Time
	fired    bool
}

// UnixEpoch is the fixed, reproducible anchor a zero start maps to — never time.Now.
// Stored in UTC so the wire/telemetry representation is stable across hosts. It is the
// single named home of the engine's default instant; a zero-start fake begins here.
func UnixEpoch() time.Time { return time.Unix(0, 0).UTC() }

// normalizeStart maps the zero time.Time to UnixEpoch; any other instant is kept
// verbatim. This is the single place the zero-start rule is enforced, so every entry
// point onto the engine (NewClock, Fakes) anchors a zero start identically.
func normalizeStart(start time.Time) time.Time {
	if start.IsZero() {
		return UnixEpoch()
	}
	return start
}

// NewClock returns a fake Clock frozen at start; a zero start anchors at UnixEpoch.
func NewClock(start time.Time) *Clock { return &Clock{now: normalizeStart(start)} }

// Now returns the current frozen instant. It does not advance on its own.
func (c *Clock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.now
}

// After returns a channel that fires when the fake timeline reaches now+d (driven by
// Advance). It honors ctx cancellation: a canceled ctx leaves the channel un-sent.
func (c *Clock) After(ctx context.Context, d time.Duration) <-chan time.Time {
	c.mu.Lock()
	t := &timer{deadline: c.now.Add(d), ch: make(chan time.Time, 1)}
	// A non-positive duration is already due relative to the current instant. Deliver
	// the DEADLINE instant (now+d), exactly as the Advance path delivers t.deadline —
	// "After channels fire when Advance crosses their deadline", so an already-due
	// timer carries its own deadline, not the current instant. This keeps the engine's
	// fired-value invariant uniform across the due-on-After and due-on-Advance paths.
	if !t.deadline.After(c.now) {
		t.fired = true
		t.ch <- t.deadline
	} else {
		c.pending = append(c.pending, t)
	}
	c.mu.Unlock()

	if ctx.Done() == nil {
		return t.ch
	}

	// Bridge cancellation: if ctx is canceled before the timer fires, never deliver a
	// tick. The returned channel mirrors t.ch on a real fire and stays un-sent on cancel.
	// Cancellation takes priority: if Advance and cancel race, the cancel wins (the
	// receiver's select unwinds via its own ctx.Done()), so a canceled timer can never
	// deliver a stale tick.
	out := make(chan time.Time, 1)
	go func() {
		select {
		case <-ctx.Done():
			c.cancel(t)
		case v, ok := <-t.ch:
			// Re-check cancellation before forwarding so a cancel that raced with a
			// fire still suppresses the tick.
			if !ok || ctx.Err() != nil {
				return
			}
			out <- v
		}
	}()
	return out
}

// cancel marks a pending timer so a later Advance will not fire it.
func (c *Clock) cancel(t *timer) {
	c.mu.Lock()
	defer c.mu.Unlock()
	t.fired = true
	for i, p := range c.pending {
		if p == t {
			c.pending = append(c.pending[:i], c.pending[i+1:]...)
			break
		}
	}
}

// Advance moves now forward by d and fires every timer whose deadline the new instant
// has reached.
func (c *Clock) Advance(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.now = c.now.Add(d)
	remaining := c.pending[:0]
	for _, t := range c.pending {
		if t.fired {
			continue
		}
		if !t.deadline.After(c.now) {
			t.fired = true
			t.ch <- t.deadline
			continue
		}
		remaining = append(remaining, t)
	}
	c.pending = remaining
}

// Random is a deterministic, seedable entropy source (math/rand/v2.ChaCha8 under the
// hood) so randomized code paths are reproducible — the single byte-stream engine. NOT
// crypto-secure: tests only; production binds crypto/rand. Identical seed + identical
// Read sequence ⇒ identical bytes, forever (the frozen invariant). Safe for concurrent
// use.
type Random struct {
	mu  sync.Mutex
	src *rand.ChaCha8
}

// NewRandom returns a deterministic entropy source seeded by seed.
func NewRandom(seed [32]byte) *Random {
	return &Random{src: rand.NewChaCha8(seed)}
}

// Read fills p from the deterministic stream. It always fills p completely (the ChaCha8
// stream never runs short) and returns a nil error.
//
//nolint:wrapcheck // contract §3: this fake mirrors the io.Reader-shaped RandomSource; rand.ChaCha8.Read never errors, and its return must stay io.Reader-comparable, so it passes through unwrapped.
func (r *Random) Read(p []byte) (int, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	return r.src.Read(p) //nolint:wrapcheck // see method doc: io.Reader-shaped, passes through unwrapped.
}

// RecordingSink captures every emitted record for assertions. Records returns a snapshot
// copy. Safe for concurrent Emit.
type RecordingSink struct {
	mu      sync.Mutex
	records []any
}

// Emit appends record to the captured log. It honors ctx cancellation: a canceled ctx
// drops the record (best-effort, like the real Sink) and returns ctx.Err().
//
//nolint:wrapcheck // contract §3: Emit returns ctx.Err() verbatim so callers can errors.Is it against context.Canceled/DeadlineExceeded; wrapping would deviate from the pinned return.
func (s *RecordingSink) Emit(ctx context.Context, record any) error {
	if err := ctx.Err(); err != nil {
		return err //nolint:wrapcheck // see method doc: ctx.Err() returned verbatim per contract §3.
	}
	s.mu.Lock()
	defer s.mu.Unlock()
	s.records = append(s.records, record)
	return nil
}

// Records returns a snapshot copy of every captured record (never the internal slice).
func (s *RecordingSink) Records() []any {
	s.mu.Lock()
	defer s.mu.Unlock()
	out := make([]any, len(s.records))
	copy(out, s.records)
	return out
}

// Fakes returns a dependencies.Set with every universal port populated by a fake —
// pinned to a fixed instant and seed — plus handles to each fake so a test can drive it.
// The test analog of dependencies.Resolve; callers override individual fields as
// needed.
func Fakes() (set dependencies.Set, clock *Clock, random *Random, sink *RecordingSink) {
	clock = NewClock(UnixEpoch())
	random = NewRandom([32]byte{})
	sink = &RecordingSink{}
	return dependencies.Set{Clock: clock, Random: random, Sink: sink}, clock, random, sink
}
