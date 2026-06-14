//go:build load

package dependencies_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"
	"time"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/dependencies/dependenciestest"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500 in-process;
// ADR-0020 dimension (e) threshold).
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_SharedRealPortsRaceClean fans out N goroutines that hammer a SINGLE resolved Set's
// ports concurrently (the §2 "safe for concurrent use" guarantee, ADR-0020 dimension (e)). The
// crypto/rand-backed Random, the systemClock, and the discard Sink are all shared, so -race
// exercises true concurrent access to one adapter value each. goleak asserts the goroutine
// high-water returns to baseline (0 leaked) afterward.
func TestLoad_SharedRealPortsRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	set := dependencies.Resolve(dependencies.Set{}) // one shared instance of each real port
	var wg sync.WaitGroup
	wg.Add(n)
	for i := range n {
		go func(i int) {
			defer wg.Done()
			_ = set.Clock.Now()
			p := make([]byte, 16)
			if _, err := set.Random.Read(p); err != nil {
				t.Errorf("worker %d: shared Random.Read error: %v", i, err)
				return
			}
			if err := set.Sink.Emit(context.Background(), i); err != nil {
				t.Errorf("worker %d: shared Sink.Emit error: %v", i, err)
			}
		}(i)
	}
	wg.Wait()
}

// TestLoad_AfterBridgeReapsUnderFanout fans out N After timers — each spawning a ctx-bridge
// goroutine — and cancels every one, proving the bridge reaping (dimension (c)/(e) intersection)
// holds under concurrency: all N goroutines are reaped, none deadlocks, and goleak confirms the
// high-water returns to baseline. A bridge that failed to observe cancellation would leak N
// goroutines here and goleak would fail.
func TestLoad_AfterBridgeReapsUnderFanout(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	c := dependencies.RealClock()
	ctx, cancel := context.WithCancel(t.Context())

	var wg sync.WaitGroup
	wg.Add(n)
	chans := make([]<-chan time.Time, n)
	var mu sync.Mutex
	for i := range n {
		go func(i int) {
			defer wg.Done()
			ch := c.After(ctx, time.Hour) // far-future: only cancellation ends it
			mu.Lock()
			chans[i] = ch
			mu.Unlock()
		}(i)
	}
	wg.Wait()

	cancel() // teardown every bridge at once

	// Drain: each channel must be un-sent (cancellation leaves it empty). We do not block on a
	// tick (there is none); a short, bounded read confirms no stale value was delivered.
	deadline := time.After(2 * time.Second)
	for i := range n {
		select {
		case v, ok := <-chans[i]:
			if ok {
				t.Fatalf("bridge %d delivered %v after cancel; must be un-sent", i, v)
			}
		case <-deadline:
			// No tick is the expected outcome; stop draining and let goleak prove reaping.
			i = n
		default:
			// un-sent and empty — fine.
		}
	}
}

// TestLoad_ConcurrentResolveRaceClean fans out N independent Resolve calls (the composition-root
// op) under -race. Resolve is pure and allocates fresh adapter values, so N concurrent calls must
// be race-clean and each must yield a complete, valid Set (dimension (e)).
func TestLoad_ConcurrentResolveRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	var wg sync.WaitGroup
	wg.Add(n)
	for range n {
		go func() {
			defer wg.Done()
			got := dependencies.Resolve(dependencies.Set{})
			if err := dependencies.Validate(got); err != nil {
				t.Errorf("concurrent Resolve produced an incomplete Set: %v", err)
			}
		}()
	}
	wg.Wait()
}

// TestLoad_FakeClockConcurrentAdvance fans out N goroutines that Advance and read a SHARED fake
// clock concurrently (the fake's §3 "safe for concurrent use" guarantee under load). -race proves
// the internal mutex serializes correctly; the final Now reflects the full additive advance.
func TestLoad_FakeClockConcurrentAdvance(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	start := time.Unix(0, 0).UTC()
	c := dependenciestest.NewClock(start)
	var wg sync.WaitGroup
	wg.Add(n)
	for range n {
		go func() {
			defer wg.Done()
			c.Advance(time.Millisecond)
			_ = c.Now()
		}()
	}
	wg.Wait()
	if got, want := c.Now(), start.Add(time.Duration(n)*time.Millisecond); !got.Equal(want) {
		t.Fatalf("after %d concurrent Advance(1ms): Now()=%v, want %v", n, got, want)
	}
}
