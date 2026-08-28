// Internal (white-box) tests for the AssertResult decision core. A failing subtest
// unavoidably fails its parent, so the fail/skip routing is unit-tested against the
// pure resultReport helper instead of through a live *testing.T (TDD discipline).
package testingtest

import (
	"strings"
	"testing"

	testingpkg "github.com/gophersys/libs/go/testing"
)

func TestResultReport_FailingCaseProducesFailLine(t *testing.T) {
	t.Parallel()
	r := testingpkg.Result{
		Suite:  "secrets.SecretProvider",
		Passed: 1,
		Failed: 1,
		Cases: []testingpkg.CaseResult{
			{Name: "ok", Outcome: testingpkg.Pass},
			{Name: "bad", Outcome: testingpkg.Fail, Messages: []string{"want X got Y"}},
		},
	}
	lines := resultReport(r)
	if len(lines) != 1 {
		t.Fatalf("a pass+fail Result should yield exactly 1 (fail) line; got %d", len(lines))
	}
	if !lines[0].fail {
		t.Fatal("a failing case must produce a fail line")
	}
	if !strings.Contains(lines[0].text, "bad") || !strings.Contains(lines[0].text, "want X got Y") {
		t.Fatalf("fail line should name the case and its messages; got %q", lines[0].text)
	}
}

func TestResultReport_PanicCaseProducesPanicFailLine(t *testing.T) {
	t.Parallel()
	r := testingpkg.Result{
		Suite:  "x",
		Failed: 1,
		Cases:  []testingpkg.CaseResult{{Name: "boom", Outcome: testingpkg.Fail, Panic: "kaboom"}},
	}
	lines := resultReport(r)
	if len(lines) != 1 || !lines[0].fail {
		t.Fatalf("a panicking case must produce one fail line; got %+v", lines)
	}
	if !strings.Contains(lines[0].text, "PANICKED") || !strings.Contains(lines[0].text, "kaboom") {
		t.Fatalf("panic line should surface the panic text; got %q", lines[0].text)
	}
}

func TestResultReport_SkipIsInformationalNotFail(t *testing.T) {
	t.Parallel()
	r := testingpkg.Result{
		Suite:   "x",
		Skipped: 1,
		Cases:   []testingpkg.CaseResult{{Name: "gated", Outcome: testingpkg.Skip, Messages: []string{"cap absent"}}},
	}
	lines := resultReport(r)
	if len(lines) != 1 {
		t.Fatalf("a skip should yield one (informational) line; got %d", len(lines))
	}
	if lines[0].fail {
		t.Fatal("a skip must NOT be a fail line (skips do not fail t)")
	}
}

func TestResultReport_AllPassYieldsNoLines(t *testing.T) {
	t.Parallel()
	r := testingpkg.Result{
		Suite:  "x",
		Passed: 3,
		Cases: []testingpkg.CaseResult{
			{Name: "a", Outcome: testingpkg.Pass},
			{Name: "b", Outcome: testingpkg.Pass},
			{Name: "c", Outcome: testingpkg.Pass},
		},
	}
	if lines := resultReport(r); len(lines) != 0 {
		t.Fatalf("an all-pass Result must produce no diagnostic lines; got %+v", lines)
	}
}
