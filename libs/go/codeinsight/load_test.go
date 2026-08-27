//go:build load

package codeinsight_test

import (
	"context"
	"os"
	"strconv"
	"sync"
	"testing"

	"go.uber.org/goleak"

	"github.com/gophersys/libs/go/codeinsight"
	"github.com/gophersys/libs/go/codeinsight/codeinsighttest"
)

// TestLoad_ConcurrentAnalyzeRaceClean is the load/scale conformance (ADR-0020 dimension (e)): N
// concurrent Analyze calls share one immutable Analyzer over a seeded on-disk repository and must all
// complete race-clean, each producing an identical, well-formed Report, with the goroutine
// high-water returning to baseline (every git child reaped). The `load` verb sets EDEN_LOAD_N
// (default 500 in-process). The Analyzer is documented safe for concurrent Analyze; this proves it
// under `-race`.
//
//nolint:paralleltest // goleak.VerifyNone observes the whole-process goroutine set; this test owns the fan-out and must not run beside a sibling spawning git children.
func TestLoad_ConcurrentAnalyzeRaceClean(t *testing.T) {
	defer goleak.VerifyNone(t)

	n := loadN()
	dir := codeinsighttest.NewRealRepo(t, codeinsighttest.CanonicalSeed())
	analyzer, err := codeinsight.New(
		codeinsight.Config{RepositoryPath: dir, Identifier: "load"},
		codeinsight.Deps{
			History:   codeinsight.NewSystemGitHistory(),
			Providers: []codeinsight.MetricProvider{codeinsight.NewGoMetricProvider()},
			Clock:     codeinsighttest.FixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	ctx := context.Background()
	var wg sync.WaitGroup
	var mu sync.Mutex
	var failures int
	entityCounts := make([]int, n)

	wg.Add(n)
	for i := 0; i < n; i++ {
		go func(index int) {
			defer wg.Done()
			report, analyzeErr := analyzer.Analyze(ctx)
			if analyzeErr != nil {
				mu.Lock()
				failures++
				mu.Unlock()
				return
			}
			entityCounts[index] = len(report.Entities)
		}(i)
	}
	wg.Wait()

	if failures != 0 {
		t.Fatalf("%d of %d concurrent Analyze calls failed", failures, n)
	}
	// Every concurrent Analyze of an immutable analyzer over a fixed repo must agree on the entity
	// count — a divergence would mean a data race corrupted a per-call result.
	want := entityCounts[0]
	if want == 0 {
		t.Fatalf("first Analyze produced 0 entities")
	}
	for i, got := range entityCounts {
		if got != want {
			t.Fatalf("Analyze %d produced %d entities, want %d (a concurrent divergence)", i, got, want)
		}
	}
}

// loadN reads the fan-out width from EDEN_LOAD_N (set by the `load` verb), defaulting to a modest
// in-process width when unset.
func loadN() int {
	if raw := os.Getenv("EDEN_LOAD_N"); raw != "" {
		if n, err := strconv.Atoi(raw); err == nil && n > 0 {
			return n
		}
	}
	return 500
}
