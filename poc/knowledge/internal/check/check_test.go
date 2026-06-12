package check

import (
	"path/filepath"
	"strings"
	"testing"
)

// TestCheckersAgainstFixtureModule runs every oracle against the testdata
// module, which contains exactly one BAD shape per rule (in bad.go /
// bad_test.go) and the compliant counterpart of each (in good.go /
// good_test.go). Every rule must fire exactly the expected number of times,
// and never on a good file.
func TestCheckersAgainstFixtureModule(t *testing.T) {
	dir, err := filepath.Abs(filepath.Join("testdata", "module"))
	if err != nil {
		t.Fatal(err)
	}
	violations, err := Run(dir, All())
	if err != nil {
		t.Fatalf("Run: %v", err)
	}

	expected := map[string]int{
		"go/benchmark-loop":          1,
		"go/constructor-purity":      1,
		"go/context-first":           1,
		"go/environment-confinement": 1,
		"go/error-wrapping":          2, // %v form + err.Error() concatenation
		"go/errors-astype":           1,
		"go/interface-size":          1,
		"go/return-concrete":         1,
		"go/slog-multihandler":       1,
		"go/waitgroup-go":            1,
	}

	got := map[string]int{}
	for _, v := range violations {
		got[v.Rule]++
		if strings.HasPrefix(filepath.Base(v.Pos), "good") {
			t.Errorf("rule %s fired on a compliant file: %s %s", v.Rule, v.Pos, v.Message)
		}
	}
	for rule, want := range expected {
		if got[rule] != want {
			t.Errorf("rule %s: got %d violations, want %d", rule, got[rule], want)
		}
	}
	for rule, n := range got {
		if _, ok := expected[rule]; !ok {
			t.Errorf("unexpected rule fired: %s (%d times)", rule, n)
		}
	}
}

// TestTransitivePurity: v2 catches the laundered constructor that v1
// (by design) does not, and the defaulting-adapter exception still survives.
func TestTransitivePurity(t *testing.T) {
	dir, err := filepath.Abs(filepath.Join("testdata", "module"))
	if err != nil {
		t.Fatal(err)
	}
	violations, err := RunWithOptions(dir, All(), Options{TransitivePurity: true})
	if err != nil {
		t.Fatalf("RunWithOptions: %v", err)
	}
	purity := 0
	laundered := false
	for _, v := range violations {
		if v.Rule != "go/constructor-purity" {
			continue
		}
		purity++
		if strings.Contains(v.Message, "NewLaundered") {
			laundered = true
		}
		if strings.Contains(v.Message, "NewGoodWidget") {
			t.Errorf("v2 flagged the defaulting-adapter exception: %s %s", v.Pos, v.Message)
		}
	}
	if !laundered {
		t.Error("v2 missed the laundered constructor (New -> stamp -> time.Now)")
	}
	if purity != 2 {
		t.Errorf("v2 purity violations = %d; want 2 (direct + laundered)", purity)
	}
}

// TestRunIsDeterministic asserts byte-identical output across repeated loads —
// the replicability requirement applied to the oracle layer itself.
func TestRunIsDeterministic(t *testing.T) {
	dir, err := filepath.Abs(filepath.Join("testdata", "module"))
	if err != nil {
		t.Fatal(err)
	}
	render := func() string {
		violations, err := Run(dir, All())
		if err != nil {
			t.Fatalf("Run: %v", err)
		}
		var b strings.Builder
		for _, v := range violations {
			b.WriteString(v.Rule + "|" + v.Pos + "|" + v.Message + "\n")
		}
		return b.String()
	}
	first := render()
	for i := 0; i < 3; i++ {
		if next := render(); next != first {
			t.Fatalf("non-deterministic output on iteration %d:\n--- first\n%s\n--- next\n%s", i, first, next)
		}
	}
}
