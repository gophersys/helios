package codeinsight_test

import (
	"testing"

	"github.com/gophersys/libs/go/codeinsight"
)

func TestParseLog_StructuresCommitsAndDeltas(t *testing.T) {
	t.Parallel()
	const rs = "\x1e"
	raw := rs + "abc123\x00Ada <ada@example.com>\x002026-06-17T10:00:00Z\n" +
		"10\t2\tfoo.go\n" +
		"-\t-\timage.png\n" +
		"3\t0\tbar/baz.go\n" +
		rs + "def456\x00Bo <bo@example.com>\x002026-06-16T09:00:00Z\n" +
		"1\t1\tfoo.go\n"

	commits := codeinsight.ParseLogForTest([]byte(raw))
	if len(commits) != 2 {
		t.Fatalf("want 2 commits, got %d", len(commits))
	}
	if commits[0].Hash != "abc123" || commits[0].Author != "Ada <ada@example.com>" {
		t.Errorf("commit[0] header wrong: %+v", commits[0])
	}
	if len(commits[0].Changes) != 3 {
		t.Fatalf("want 3 deltas, got %d", len(commits[0].Changes))
	}
	if got := commits[0].Changes[0]; got.Path != "foo.go" || got.Added != 10 || got.Deleted != 2 {
		t.Errorf("delta[0] = %+v", got)
	}
	if got := commits[0].Changes[1]; got.Path != "image.png" || got.Added != 0 || got.Deleted != 0 {
		t.Errorf("binary delta should be zero-churn: %+v", got)
	}
}

func TestNormalizeRenamePath(t *testing.T) {
	t.Parallel()
	cases := map[string]string{
		"foo.go":                   "foo.go",
		"old.go => new.go":         "new.go",
		"pkg/{old => new}/file.go": "pkg/new/file.go",
		"src/{ => sub}/file.go":    "src/sub/file.go",
	}
	for input, want := range cases {
		if got := codeinsight.NormalizeRenamePathForTest(input); got != want {
			t.Errorf("normalizeRenamePath(%q) = %q, want %q", input, got, want)
		}
	}
}

func TestCyclomaticComplexity_CountsBranches(t *testing.T) {
	t.Parallel()
	src := `package p
func f(x int) int {
	if x > 0 && x < 10 { // +1 if, +1 &&
		for i := 0; i < x; i++ { // +1 for
			switch i { // case clauses below count
			case 1: // +1
			case 2: // +1
			}
		}
	}
	return x
}`
	// base 1 + if + && + for + 2 case clauses = 6
	if got := codeinsight.CyclomaticForTest(t, src); got != 6 {
		t.Errorf("cyclomatic = %d, want 6", got)
	}
}

func TestCognitiveComplexity_PenalizesNesting(t *testing.T) {
	t.Parallel()
	flat := codeinsight.CognitiveForTest(t, `package p
func f(x int) { if x > 0 { _ = x } }`)
	nested := codeinsight.CognitiveForTest(t, `package p
func f(x int) { if x > 0 { for x > 0 { x-- } } }`)
	if nested <= flat {
		t.Errorf("nested cognitive (%d) should exceed flat (%d)", nested, flat)
	}
}

func TestMaintainabilityIndex_ClampedAndMonotone(t *testing.T) {
	t.Parallel()
	if mi := codeinsight.MaintainabilityIndexForTest(0, 0, 0); mi != 100 {
		t.Errorf("trivial file MI = %v, want 100", mi)
	}
	low := codeinsight.MaintainabilityIndexForTest(50000, 200, 2000)
	if low < 0 || low > 100 {
		t.Errorf("MI must be clamped to 0..100, got %v", low)
	}
	simple := codeinsight.MaintainabilityIndexForTest(500, 3, 40)
	if simple <= low {
		t.Errorf("simpler file MI (%v) should exceed complex file MI (%v)", simple, low)
	}
}

func TestSqaleRating_Bands(t *testing.T) {
	t.Parallel()
	cases := []struct {
		ratio float64
		want  string
	}{{0.0, "A"}, {0.049, "A"}, {0.05, "B"}, {0.099, "B"}, {0.10, "C"}, {0.19, "C"}, {0.20, "D"}, {0.49, "D"}, {0.50, "E"}, {0.9, "E"}}
	for _, c := range cases {
		if got := codeinsight.SqaleRatingForTest(c.ratio); got != c.want {
			t.Errorf("sqaleRating(%v) = %q, want %q", c.ratio, got, c.want)
		}
	}
}

func TestBusFactor_FewestAuthorsPastHalf(t *testing.T) {
	t.Parallel()
	if got := codeinsight.BusFactorForTest([]float64{0.6, 0.3, 0.1}); got != 1 {
		t.Errorf("dominant author → bus factor 1, got %d", got)
	}
	if got := codeinsight.BusFactorForTest([]float64{0.34, 0.33, 0.33}); got != 2 {
		t.Errorf("even split → bus factor 2, got %d", got)
	}
}

func TestRecordCoChanges_SymmetricUniquePairs(t *testing.T) {
	t.Parallel()
	pairCount, abCount := codeinsight.RecordCoChangesForTest([]string{"b.go", "a.go", "a.go"}, "a.go", "b.go")
	if pairCount != 1 {
		t.Fatalf("want 1 unique pair, got %d", pairCount)
	}
	if abCount != 1 {
		t.Errorf("pair (a.go,b.go) must be counted once, got %d", abCount)
	}
}

func TestNew_ValidatesInputs(t *testing.T) {
	t.Parallel()
	provider := codeinsight.NewGoMetricProvider()
	clock := fixedClock{}
	history := &stubHistory{}

	cases := []struct {
		name          string
		configuration codeinsight.Config
		dependencies  codeinsight.Deps
	}{
		{"empty path", codeinsight.Config{}, codeinsight.Deps{History: history, Providers: []codeinsight.MetricProvider{provider}, Clock: clock}},
		{"nil history", codeinsight.Config{RepositoryPath: "/r"}, codeinsight.Deps{Providers: []codeinsight.MetricProvider{provider}, Clock: clock}},
		{"no providers", codeinsight.Config{RepositoryPath: "/r"}, codeinsight.Deps{History: history, Clock: clock}},
		{"nil clock", codeinsight.Config{RepositoryPath: "/r"}, codeinsight.Deps{History: history, Providers: []codeinsight.MetricProvider{provider}}},
		{"negative coupling floor", codeinsight.Config{RepositoryPath: "/r", CouplingMinShared: -1}, codeinsight.Deps{History: history, Providers: []codeinsight.MetricProvider{provider}, Clock: clock}},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			t.Parallel()
			if _, err := codeinsight.New(c.configuration, c.dependencies); err == nil {
				t.Errorf("New(%s) returned nil error, want an InvalidInputError", c.name)
			}
		})
	}
}

func TestNew_PureConstructor(t *testing.T) {
	t.Parallel()
	analyzer, err := codeinsight.New(
		codeinsight.Config{RepositoryPath: "/some/repo"},
		codeinsight.Deps{
			History:   &stubHistory{},
			Providers: []codeinsight.MetricProvider{codeinsight.NewGoMetricProvider()},
			Clock:     fixedClock{},
		},
	)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	if analyzer.RepositoryPath() != "/some/repo" {
		t.Errorf("RepositoryPath() = %q, want %q", analyzer.RepositoryPath(), "/some/repo")
	}
}
