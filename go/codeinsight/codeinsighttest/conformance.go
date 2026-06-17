package codeinsighttest

import (
	"context"
	"strings"
	"testing"
	"time"

	"github.com/gophersys/libs/go/codeinsight"
	"github.com/gophersys/libs/go/errors"
)

// HistoryFactory builds a fresh History binding seeded with the canonical conformance history (the
// commits CanonicalSeed describes) plus the repository path the static-metric reads back onto and
// the HEAD hash that binding reports. The fake arm returns a FakeHistory; the real arm returns a
// NewSystemGitHistory over a seeded on-disk repository. A fresh binding per case keeps cases from
// sharing mutable state.
type HistoryFactory func() (history codeinsight.History, repositoryPath, head string)

// RunAnalyzerSuite drives an Analyzer assembled over the History the factory builds through the
// contract's load-bearing invariants (contract §3/§4): the Report is self-describing and stamped,
// the behavioral metrics are mined, hotspots are normalized + ranked, couplings are symmetric and
// gated, ownership + bus factor are well-formed, the per-function maintainability aggregation does
// NOT saturate to a uniform E, and the Views render-plan is present. The SAME suite runs over the
// fake and the real system-git History, so substitutability is EXECUTED.
//
//nolint:thelper // RunAnalyzerSuite IS the suite entrypoint; subtests carry t directly.
func RunAnalyzerSuite(t *testing.T, newHistory HistoryFactory) {
	t.Run("ReportSelfDescribingAndStamped", func(t *testing.T) { assertSelfDescribing(t, newHistory) })
	t.Run("BehavioralMetricsMined", func(t *testing.T) { assertBehavioral(t, newHistory) })
	t.Run("HotspotNormalizedAndRanked", func(t *testing.T) { assertHotspot(t, newHistory) })
	t.Run("CouplingSymmetricAndGated", func(t *testing.T) { assertCoupling(t, newHistory) })
	t.Run("OwnershipAndBusFactorWellFormed", func(t *testing.T) { assertOwnership(t, newHistory) })
	t.Run("MaintainabilityDiscriminates", func(t *testing.T) { assertMaintainability(t, newHistory) })
	t.Run("ViewsRenderPlanPresent", func(t *testing.T) { assertViews(t, newHistory) })
	t.Run("HistoryFaultClassified", func(t *testing.T) { assertHistoryFault(t) })
}

// analyzeCanonical builds an Analyzer over the factory's History and the native Go provider, then
// runs one analysis. It fails the test on any construction/analysis error.
func analyzeCanonical(t *testing.T, newHistory HistoryFactory) *codeinsight.Report {
	t.Helper()
	history, repositoryPath, _ := newHistory()
	analyzer, err := codeinsight.New(
		codeinsight.Config{RepositoryPath: repositoryPath, Identifier: "conformance"},
		codeinsight.Deps{
			History:   history,
			Providers: []codeinsight.MetricProvider{codeinsight.NewGoMetricProvider()},
			Clock:     FixedClock{At: epoch},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	report, err := analyzer.Analyze(context.Background())
	if err != nil {
		t.Fatalf("Analyze: %v", err)
	}
	return report
}

// assertSelfDescribing checks the Report carries its schema version, a stamped repository ref, and a
// window addressed by commit hash.
func assertSelfDescribing(t *testing.T, newHistory HistoryFactory) {
	t.Helper()
	report := analyzeCanonical(t, newHistory)
	if report.SchemaVersion == "" {
		t.Errorf("Report.SchemaVersion is empty")
	}
	if report.Repository.Identifier != "conformance" {
		t.Errorf("Repository.Identifier = %q, want %q", report.Repository.Identifier, "conformance")
	}
	if _, err := time.Parse(time.RFC3339, report.Repository.AnalyzedAt); err != nil {
		t.Errorf("Repository.AnalyzedAt = %q, not RFC3339: %v", report.Repository.AnalyzedAt, err)
	}
	if report.Repository.HeadCommit == "" {
		t.Errorf("Repository.HeadCommit is empty (the snapshot is unaddressable)")
	}
	if report.Window.ToCommit == "" || report.Window.Revisions == 0 {
		t.Errorf("Window not addressed by commit: %+v", report.Window)
	}
	if report.Repository.CommitCount != report.Window.Revisions {
		t.Errorf("CommitCount %d != Window.Revisions %d", report.Repository.CommitCount, report.Window.Revisions)
	}
}

// assertBehavioral checks the mined behavioral metrics: the hot file changed more than once, its
// churn is positive, and its relative churn is derived from line count.
func assertBehavioral(t *testing.T, newHistory HistoryFactory) {
	t.Helper()
	report := analyzeCanonical(t, newHistory)
	hot := findEntity(report, "hot.go")
	if hot == nil {
		t.Fatalf("entity hot.go missing from %d entities", len(report.Entities))
	}
	if hot.ChangeFrequency < 2 {
		t.Errorf("hot.go ChangeFrequency = %d, want >= 2 (it was edited repeatedly)", hot.ChangeFrequency)
	}
	if hot.ChurnAbsolute <= 0 {
		t.Errorf("hot.go ChurnAbsolute = %d, want > 0", hot.ChurnAbsolute)
	}
	if hot.Lines > 0 && hot.ChurnRelative <= 0 {
		t.Errorf("hot.go ChurnRelative = %v, want > 0 when Lines > 0", hot.ChurnRelative)
	}
	if hot.Cyclomatic == 0 {
		t.Errorf("hot.go Cyclomatic = 0, want > 0 (a Go file with branches)")
	}
}

// assertHotspot checks the hotspot score is normalized to 0..1 and the entities are ranked by it,
// descending — the active-development triage order.
func assertHotspot(t *testing.T, newHistory HistoryFactory) {
	t.Helper()
	report := analyzeCanonical(t, newHistory)
	if len(report.Entities) < 2 {
		t.Fatalf("want >= 2 entities to assert ranking, got %d", len(report.Entities))
	}
	last := 1.1
	for i := range report.Entities {
		score := report.Entities[i].HotspotScore
		if score < 0 || score > 1 {
			t.Errorf("entity %q HotspotScore = %v, want in [0,1]", report.Entities[i].Path, score)
		}
		if score > last {
			t.Errorf("entities not ranked by hotspot descending at %d: %v > %v", i, score, last)
		}
		last = score
	}
	if report.Entities[0].HotspotScore != 1 {
		t.Errorf("top entity HotspotScore = %v, want 1 (normalized max)", report.Entities[0].HotspotScore)
	}
}

// assertCoupling checks coupling edges are symmetric (A<B), clear the shared floor, and carry a
// degree in 0..100 sorted descending.
func assertCoupling(t *testing.T, newHistory HistoryFactory) {
	t.Helper()
	report := analyzeCanonical(t, newHistory)
	if len(report.Couplings) == 0 {
		t.Fatalf("no coupling edges: the canonical seed co-changes a file pair repeatedly")
	}
	last := 101.0
	for i := range report.Couplings {
		c := report.Couplings[i]
		if c.EntityA >= c.EntityB {
			t.Errorf("coupling not in canonical order: %q >= %q", c.EntityA, c.EntityB)
		}
		if c.Degree < 0 || c.Degree > 100 {
			t.Errorf("coupling degree %v out of [0,100]", c.Degree)
		}
		if c.Degree > last {
			t.Errorf("couplings not sorted by degree descending at %d", i)
		}
		last = c.Degree
	}
}

// assertOwnership checks each ownership entry's author shares are well-formed and bus factor is at
// least 1; the repo-level bus factor is positive.
func assertOwnership(t *testing.T, newHistory HistoryFactory) {
	t.Helper()
	report := analyzeCanonical(t, newHistory)
	if len(report.Ownership) == 0 {
		t.Fatalf("no ownership entries")
	}
	for i := range report.Ownership {
		assertOwnershipEntry(t, report.Ownership[i])
	}
	if report.Summary.BusFactor < 1 {
		t.Errorf("Summary.BusFactor = %d, want >= 1", report.Summary.BusFactor)
	}
}

// assertOwnershipEntry checks one ownership entry's author shares sum to ~1 and its bus factor is
// at least 1.
func assertOwnershipEntry(t *testing.T, o codeinsight.Ownership) {
	t.Helper()
	sum := 0.0
	for _, share := range o.Authors {
		if share < 0 || share > 1 {
			t.Errorf("%q author share %v out of [0,1]", o.Path, share)
		}
		sum += share
	}
	if sum < 0.99 || sum > 1.01 {
		t.Errorf("%q author shares sum to %v, want ~1.0", o.Path, sum)
	}
	if o.BusFactor < 1 {
		t.Errorf("%q BusFactor = %d, want >= 1", o.Path, o.BusFactor)
	}
}

// assertMaintainability is the design-fix guard: the per-function-aggregated maintainability index
// must DISCRIMINATE — a simple file rates materially higher than a complex one, and the simple
// file's index is not the saturated 0 the whole-file-sum index produced. It checks the simple file's
// index exceeds the complex file's and is strictly positive.
func assertMaintainability(t *testing.T, newHistory HistoryFactory) {
	t.Helper()
	report := analyzeCanonical(t, newHistory)
	simple := findEntity(report, "simple.go")
	complexEntity := findEntity(report, "complex.go")
	if simple == nil || complexEntity == nil {
		t.Fatalf("simple.go/complex.go missing (simple=%v complex=%v)", simple != nil, complexEntity != nil)
	}
	if simple.Maintainability <= complexEntity.Maintainability {
		t.Errorf("maintainability does not discriminate: simple %v <= complex %v",
			simple.Maintainability, complexEntity.Maintainability)
	}
	if simple.Maintainability <= 0 {
		t.Errorf("simple.go maintainability saturated to %v (the PoC's uniform-E bug)", simple.Maintainability)
	}
	if report.Summary.MaintainabilityRating == "" {
		t.Errorf("Summary.MaintainabilityRating is empty")
	}
}

// assertViews checks the render-plan is present and every view names a primitive, a source, and an
// attention point.
func assertViews(t *testing.T, newHistory HistoryFactory) {
	t.Helper()
	report := analyzeCanonical(t, newHistory)
	if len(report.Views) == 0 {
		t.Fatalf("Views render-plan is empty")
	}
	for i := range report.Views {
		v := report.Views[i]
		if v.ID == "" || v.Primitive == "" || v.Source == "" || v.AttentionPoint == "" {
			t.Errorf("view %d is under-specified: %+v", i, v)
		}
	}
}

// assertHistoryFault checks a History-walk failure is surfaced as a classified (KindUnavailable)
// error the caller branches on by Kind — the fault arm, exercised with a fake that fails.
func assertHistoryFault(t *testing.T) {
	t.Helper()
	analyzer, err := codeinsight.New(
		codeinsight.Config{RepositoryPath: "/seed"},
		codeinsight.Deps{
			History:   &FakeHistory{Err: errors.New(errors.KindUnavailable, "git unavailable")},
			Providers: []codeinsight.MetricProvider{codeinsight.NewGoMetricProvider()},
			Clock:     FixedClock{At: epoch},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	_, walkErr := analyzer.Analyze(context.Background())
	if walkErr == nil {
		t.Fatalf("Analyze over a failing History returned nil error")
	}
	if errors.KindOf(walkErr) != errors.KindUnavailable {
		t.Errorf("history fault KindOf = %v, want %v", errors.KindOf(walkErr), errors.KindUnavailable)
	}
}

// findEntity returns the entity whose path ends with suffix, or nil.
func findEntity(report *codeinsight.Report, suffix string) *codeinsight.Entity {
	for i := range report.Entities {
		if strings.HasSuffix(report.Entities[i].Path, suffix) {
			return &report.Entities[i]
		}
	}
	return nil
}
