//go:build load

package observability_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"
	"time"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/observability"
)

// loadN reads the fan-out width the `load` ctl.sh verb sets (EDEN_LOAD_N, default 500
// in-process; ADR-0020 dimension (e) threshold).
func loadN() int {
	if v := os.Getenv("EDEN_LOAD_N"); v != "" {
		if n, err := strconv.Atoi(v); err == nil && n > 0 {
			return n
		}
	}
	return 500
}

// TestLoad_ConcurrentEmitRaceCleanNoLost fans out N goroutines that each hammer ONE
// shared Provider through all four hot-path methods — Emit, Log, a With child's Emit,
// and a Scope open+close — concurrently under -race. observability documents (contract
// §2 Concurrency) that a Provider is safe for concurrent use from many goroutines; this
// test proves it at fan-out: 0 races, every emitted Event lands EXACTLY ONCE after Flush
// (none lost to a racing buffer append, none duplicated), and goleak asserts the
// goroutine high-water returns to baseline afterward (no orphan worker).
//
//nolint:paralleltest // goleak.VerifyNone(t) observes the WHOLE process goroutine set; running serially keeps the high-water assertion honest.
func TestLoad_ConcurrentEmitRaceCleanNoLost(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	exp := &loadExporter{}
	p, err := observability.New(
		observability.Config{ServiceName: "load-svc", DefaultPlane: observability.PlaneSelf},
		observability.Deps{Exporter: exp, Clock: loadClock{}},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	const (
		emitsPerWorker = 4 // plain Emit
		logsPerWorker  = 2 // Log (one Event each)
		withPerWorker  = 2 // Emit through a With child
		scopePerWorker = 1 // Scope open+close (one span Event each)
		perWorker      = emitsPerWorker + logsPerWorker + withPerWorker + scopePerWorker
	)

	var wg sync.WaitGroup
	wg.Add(n)
	for w := 0; w < n; w++ {
		go func(worker int) {
			defer wg.Done()
			ctx := context.Background()
			tag := observability.Int64("worker", int64(worker))
			for i := 0; i < emitsPerWorker; i++ {
				p.Emit(ctx, observability.Event{
					Name: "emit", Severity: observability.SeverityInfo,
					Fields: []observability.Field{tag, observability.Int64("i", int64(i))},
				})
			}
			for i := 0; i < logsPerWorker; i++ {
				p.Log(ctx, observability.SeverityInfo, "log", tag)
			}
			child := p.With(tag)
			for i := 0; i < withPerWorker; i++ {
				child.Emit(ctx, observability.Event{Name: "with.emit", Severity: observability.SeverityInfo})
			}
			for i := 0; i < scopePerWorker; i++ {
				_, end := child.Scope(ctx, "span", tag)
				end(observability.Outcome{})
			}
		}(w)
	}
	wg.Wait()

	if err := p.Flush(context.Background()); err != nil {
		t.Fatalf("Flush: %v", err)
	}

	recs := exp.snapshot()
	want := n * perWorker
	if len(recs) != want {
		t.Fatalf("after fan-out Flush shipped %d Records, want %d (lost or duplicated under concurrency)", len(recs), want)
	}

	// Every kind must be present its exact expected number of times — proves no Event
	// was silently dropped AND none double-counted by a racing append.
	counts := map[string]int{}
	for _, r := range recs {
		counts[r.Event.Name]++
	}
	wantByName := map[string]int{
		"emit":      n * emitsPerWorker,
		"log":       n * logsPerWorker,
		"with.emit": n * withPerWorker,
		"span":      n * scopePerWorker,
	}
	for name, w := range wantByName {
		if got := counts[name]; got != w {
			t.Errorf("Record %q count = %d, want %d (concurrency lost or duplicated)", name, got, w)
		}
	}
}

// loadExporter captures every shipped batch; safe for concurrent Export (Flush ships from
// one goroutine, but the lock keeps it honest if that ever changes).
type loadExporter struct {
	mu   sync.Mutex
	recs []observability.Record
}

func (e *loadExporter) Export(_ context.Context, records []observability.Record) error {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.recs = append(e.recs, records...)
	return nil
}

func (e *loadExporter) snapshot() []observability.Record {
	e.mu.Lock()
	defer e.mu.Unlock()
	out := make([]observability.Record, len(e.recs))
	copy(out, e.recs)
	return out
}

type loadClock struct{}

func (loadClock) Now() time.Time { return time.Unix(1700000000, 0).UTC() }
