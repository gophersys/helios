package codeinsight

import (
	"go/ast"
	"go/parser"
	"go/token"
	"testing"
)

func TestParseLog_StructuresCommitsAndDeltas(t *testing.T) {
	const rs = "\x1e"
	raw := rs + "abc123\x00Ada <ada@example.com>\x002026-06-17T10:00:00Z\n" +
		"10\t2\tfoo.go\n" +
		"-\t-\timage.png\n" +
		"3\t0\tbar/baz.go\n" +
		rs + "def456\x00Bo <bo@example.com>\x002026-06-16T09:00:00Z\n" +
		"1\t1\tfoo.go\n"

	commits := parseLog([]byte(raw), rs)
	if len(commits) != 2 {
		t.Fatalf("want 2 commits, got %d", len(commits))
	}
	if commits[0].hash != "abc123" || commits[0].authorKey != "Ada <ada@example.com>" {
		t.Errorf("commit[0] header wrong: %+v", commits[0])
	}
	if len(commits[0].changes) != 3 {
		t.Fatalf("want 3 deltas, got %d", len(commits[0].changes))
	}
	if got := commits[0].changes[0]; got.path != "foo.go" || got.added != 10 || got.deleted != 2 {
		t.Errorf("delta[0] = %+v", got)
	}
	if got := commits[0].changes[1]; got.path != "image.png" || got.added != 0 || got.deleted != 0 {
		t.Errorf("binary delta should be zero-churn: %+v", got)
	}
}

func TestNormalizeRenamePath(t *testing.T) {
	cases := map[string]string{
		"foo.go":                   "foo.go",
		"old.go => new.go":         "new.go",
		"pkg/{old => new}/file.go": "pkg/new/file.go",
		"src/{ => sub}/file.go":    "src/sub/file.go",
	}
	for input, want := range cases {
		if got := normalizeRenamePath(input); got != want {
			t.Errorf("normalizeRenamePath(%q) = %q, want %q", input, got, want)
		}
	}
}

func TestCyclomaticComplexity_CountsBranches(t *testing.T) {
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
	fn := firstFunc(t, src)
	// base 1 + if + && + for + 2 case clauses = 6
	if got := cyclomaticComplexity(fn); got != 6 {
		t.Errorf("cyclomatic = %d, want 6", got)
	}
}

func TestCognitiveComplexity_PenalizesNesting(t *testing.T) {
	flat := firstFunc(t, `package p
func f(x int) { if x > 0 { _ = x } }`)
	nested := firstFunc(t, `package p
func f(x int) { if x > 0 { for x > 0 { x-- } } }`)
	if cognitiveComplexity(nested) <= cognitiveComplexity(flat) {
		t.Errorf("nested cognitive (%d) should exceed flat (%d)",
			cognitiveComplexity(nested), cognitiveComplexity(flat))
	}
}

func TestMaintainabilityIndex_ClampedAndMonotone(t *testing.T) {
	if mi := maintainabilityIndex(0, 0, 0); mi != 100 {
		t.Errorf("trivial file MI = %v, want 100", mi)
	}
	low := maintainabilityIndex(50000, 200, 2000)
	if low < 0 || low > 100 {
		t.Errorf("MI must be clamped to 0..100, got %v", low)
	}
	simple := maintainabilityIndex(500, 3, 40)
	if simple <= low {
		t.Errorf("simpler file MI (%v) should exceed complex file MI (%v)", simple, low)
	}
}

func TestSqaleRating_Bands(t *testing.T) {
	cases := []struct {
		ratio float64
		want  string
	}{{0.0, "A"}, {0.049, "A"}, {0.05, "B"}, {0.099, "B"}, {0.10, "C"}, {0.19, "C"}, {0.20, "D"}, {0.49, "D"}, {0.50, "E"}, {0.9, "E"}}
	for _, c := range cases {
		if got := sqaleRating(c.ratio); got != c.want {
			t.Errorf("sqaleRating(%v) = %q, want %q", c.ratio, got, c.want)
		}
	}
}

func TestBusFactor_FewestAuthorsPastHalf(t *testing.T) {
	if got := busFactor([]float64{0.6, 0.3, 0.1}); got != 1 {
		t.Errorf("dominant author → bus factor 1, got %d", got)
	}
	if got := busFactor([]float64{0.34, 0.33, 0.33}); got != 2 {
		t.Errorf("even split → bus factor 2, got %d", got)
	}
}

func TestRecordCoChanges_SymmetricUniquePairs(t *testing.T) {
	pairs := map[pairKey]int{}
	recordCoChanges([]string{"b.go", "a.go", "a.go"}, pairs) // duplicate a.go must not self-pair
	if len(pairs) != 1 {
		t.Fatalf("want 1 unique pair, got %d: %+v", len(pairs), pairs)
	}
	if pairs[makePairKey("a.go", "b.go")] != 1 || makePairKey("a.go", "b.go") != makePairKey("b.go", "a.go") {
		t.Errorf("pair key must be order-independent and counted once")
	}
}

func firstFunc(t *testing.T, src string) *ast.FuncDecl {
	t.Helper()
	fileSet := token.NewFileSet()
	file, err := parser.ParseFile(fileSet, "x.go", src, 0)
	if err != nil {
		t.Fatalf("parse: %v", err)
	}
	for _, decl := range file.Decls {
		if fn, ok := decl.(*ast.FuncDecl); ok && fn.Body != nil {
			return fn
		}
	}
	t.Fatal("no function found")
	return nil
}
