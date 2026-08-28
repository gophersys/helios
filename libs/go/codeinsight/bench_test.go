package codeinsight_test

import (
	"testing"
	"time"

	"github.com/gophersys/libs/go/codeinsight"
)

// sink keeps the compiler from eliding the benchmarked work.
var sink any

// BenchmarkNew measures the pure construction spine (validation + the defensive provider copy) — the
// hot path a per-request edenhttp handler pays before any I/O.
func BenchmarkNew(b *testing.B) {
	provider := codeinsight.NewGoMetricProvider()
	history := codeinsight.NewSystemGitHistory()
	clock := benchClock{}
	configuration := codeinsight.Config{RepositoryPath: "/some/repository", Identifier: "bench"}
	b.ReportAllocs()
	for b.Loop() {
		analyzer, err := codeinsight.New(configuration, codeinsight.Deps{
			History:   history,
			Providers: []codeinsight.MetricProvider{provider},
			Clock:     clock,
		})
		if err != nil {
			b.Fatalf("New: %v", err)
		}
		sink = analyzer
	}
}

// BenchmarkParseLog measures the git-log stream parser over a representative multi-commit numstat
// stream — the per-commit hot path the behavioral spine pays for every analysis.
func BenchmarkParseLog(b *testing.B) {
	const rs = "\x1e"
	raw := []byte(
		rs + "abc123\x00Ada <ada@example.com>\x002026-06-17T10:00:00Z\n" +
			"10\t2\tfoo.go\n3\t0\tbar/baz.go\n-\t-\timage.png\n" +
			rs + "def456\x00Bo <bo@example.com>\x002026-06-16T09:00:00Z\n" +
			"1\t1\tfoo.go\n5\t5\tqux.go\n",
	)
	b.ReportAllocs()
	for b.Loop() {
		sink = codeinsight.ParseLogForTest(raw)
	}
}

// benchClock is a no-op Clock for the New benchmark.
type benchClock struct{}

func (benchClock) Now() time.Time { return time.Time{} }
