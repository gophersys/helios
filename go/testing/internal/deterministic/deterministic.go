// Package deterministic holds the virtual-time Clock and seeded entropy engine
// shared by the core (package testing) and the public fakes (package testingtest).
//
// It is internal so the byte/timeline ALGORITHM has exactly one definition site:
// testingtest.FakeClock / FakeRandomSource are thin public wrappers over these
// types, which is what makes "Fakes().Clock is a *testingtest.FakeClock under the
// hood" true without an import cycle (testingtest imports testing; the core cannot
// import testingtest, so the shared algorithm lives below both).
//
// The timeline and byte stream are a FROZEN invariant (contract open question 6):
// identical start/seed + identical call sequence ⇒ identical output forever. A
// change is breaking and may only ship behind a new constructor.
package deterministic

import (
	"context"
	"encoding/binary"
	"io"
	"math/rand/v2"
	"sort"
	"sync"
	"time"
)

// UnixEpoch is the fixed reproducible anchor a zero start/Epoch maps to: never
// time.Now. Stored in UTC so the wire/telemetry representation is stable.
func UnixEpoch() time.Time { return time.Unix(0, 0).UTC() }

// normalizeStart maps the zero time.Time to the Unix epoch; any other instant is
// kept verbatim. This is the single place the zero-start rule is enforced.
func normalizeStart(start time.Time) time.Time {
	if start.IsZero() {
		return UnixEpoch()
	}
	return start
}

// Clock is virtual time: it NEVER advances on its own. Tests drive time explicitly
// via Advance. It implements dependencies.Clock (Now + After); Advance is the
// test-only affordance. Every method is goroutine-safe; Advance releases all After
// channels whose deadline it crosses, in deadline order, before returning.
type Clock struct {
	mu      sync.Mutex
	now     time.Time
	waiters []*waiter
}

type waiter struct {
	deadline time.Time
	ch       chan time.Time
	ctx      context.Context // nil ⇒ never cancellable
}

// NewClock builds a virtual Clock starting at start (zero start → the Unix epoch).
func NewClock(start time.Time) *Clock {
	return &Clock{now: normalizeStart(start)}
}

// Now returns the current virtual instant. It never reads the wall clock.
func (c *Clock) Now() time.Time {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.now
}

// After returns a channel that delivers once virtual time reaches now+d (i.e. when
// an Advance crosses that deadline). It honors ctx cancellation: on cancellation
// the channel is never sent on, mirroring dependencies.Clock.After. A non-positive
// d fires immediately at the current instant.
func (c *Clock) After(ctx context.Context, d time.Duration) <-chan time.Time {
	c.mu.Lock()
	deadline := c.now.Add(d)
	// Already due (d <= 0 or a zero advance): deliver the deadline instant
	// immediately, buffered so the send never blocks and a pre-canceled ctx still
	// wins (the channel is then left empty, never sent on).
	if !deadline.After(c.now) {
		c.mu.Unlock()
		ch := make(chan time.Time, 1)
		if ctx == nil || ctx.Err() == nil {
			ch <- deadline
		}
		return ch
	}
	w := &waiter{deadline: deadline, ch: make(chan time.Time, 1), ctx: ctx}
	c.waiters = append(c.waiters, w)
	c.mu.Unlock()

	if ctx != nil && ctx.Done() != nil {
		// Best-effort prompt removal on cancellation so a blocking receiver unwinds;
		// correctness does NOT depend on this goroutine winning the race with
		// Advance — Advance re-checks ctx.Err() under the lock before sending, so a
		// canceled waiter is never delivered regardless of scheduling.
		go func() {
			<-ctx.Done()
			c.cancel(w)
		}()
	}
	return w.ch
}

func (c *Clock) cancel(target *waiter) {
	c.mu.Lock()
	defer c.mu.Unlock()
	for i, w := range c.waiters {
		if w == target {
			c.waiters = append(c.waiters[:i], c.waiters[i+1:]...)
			return
		}
	}
}

// Advance moves virtual time forward by d and releases every waiter whose deadline
// it crosses, in deadline order, before returning. A non-positive d is a no-op for
// time but still releases any already-due waiters at the current instant.
func (c *Clock) Advance(d time.Duration) {
	c.mu.Lock()
	if d > 0 {
		c.now = c.now.Add(d)
	}
	target := c.now

	// Partition: due (deadline <= target) vs pending, preserving pending order. A
	// waiter whose ctx is already canceled is dropped without delivery — checked
	// HERE under the lock so cancellation is deterministic and never races the
	// cancel goroutine.
	var due []*waiter
	var pending []*waiter
	for _, w := range c.waiters {
		if w.ctx != nil && w.ctx.Err() != nil {
			continue // canceled: drop, never send
		}
		if !w.deadline.After(target) {
			due = append(due, w)
		} else {
			pending = append(pending, w)
		}
	}
	c.waiters = pending
	c.mu.Unlock()

	// Release in deadline order (stable for equal deadlines via the original index
	// captured by the sort being stable on already-ordered-by-insertion input).
	sort.SliceStable(due, func(i, j int) bool { return due[i].deadline.Before(due[j].deadline) })
	for _, w := range due {
		// Buffered cap-1 channel: a non-blocking send; if cancellation already
		// drained/removed it, this still cannot block.
		select {
		case w.ch <- w.deadline:
		default:
		}
	}
}

// Random is a deterministic, reproducible byte stream from a seed. NOT crypto-secure
// — tests only. Read is serialized; identical seed + identical Read sequence ⇒
// identical bytes, forever (the frozen invariant). The underlying generator is
// math/rand/v2's ChaCha8, seeded deterministically from the uint64 seed.
type Random struct {
	mu  sync.Mutex
	src *rand.ChaCha8
}

// NewRandom builds a deterministic entropy stream from seed.
func NewRandom(seed uint64) *Random {
	var key [32]byte
	binary.LittleEndian.PutUint64(key[0:8], seed)
	// Spread the seed across the key so distinct seeds diverge immediately while
	// the mapping stays a pure, frozen function of the seed.
	binary.LittleEndian.PutUint64(key[8:16], seed^0x9e3779b97f4a7c15)
	binary.LittleEndian.PutUint64(key[16:24], seed*0xff51afd7ed558ccd)
	binary.LittleEndian.PutUint64(key[24:32], seed*0xc4ceb9fe1a85ec53)
	return &Random{src: rand.NewChaCha8(key)}
}

// Read fills p completely from the deterministic stream and never errors (the
// io.ReadFull contract crypto/rand guarantees, so the fake interchanges with it).
// It is read through io.ReadFull — the same fill-completely seam the real
// crypto/rand-backed RandomSource adapter uses (dependencies.cryptoRandom) — so the
// fake and the production source are byte-for-byte interchangeable and the
// io.ReadFull error contract is surfaced verbatim, not flattened.
//
//nolint:wrapcheck // contract §3: RandomSource is io.Reader-shaped; io.ReadFull's sentinel errors must stay comparable so the fake interchanges with crypto/rand — wrapping would change their identity (mirrors dependencies.cryptoRandom.Read).
func (r *Random) Read(p []byte) (int, error) {
	r.mu.Lock()
	defer r.mu.Unlock()
	return io.ReadFull(r.src, p)
}
