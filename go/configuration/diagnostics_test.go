package configuration_test

import (
	"testing"

	"github.com/gophersys/libs/go/configuration"
)

// Section: Path.
func TestPath_Child(t *testing.T) {
	t.Parallel()
	var root configuration.Path // empty == root
	got := root.Child("engine")
	if got != "engine" {
		t.Fatalf("root.Child(engine) = %q, want %q", got, "engine")
	}
	got = got.Child("models")
	if got != "engine.models" {
		t.Fatalf("Child chained = %q, want %q", got, "engine.models")
	}
}

func TestPath_Index(t *testing.T) {
	t.Parallel()
	p := configuration.Path("engine.models").Index(0).Child("auth")
	if p != "engine.models[0].auth" {
		t.Fatalf("Index/Child chain = %q, want %q", p, "engine.models[0].auth")
	}
}

func TestPath_ChildOnRootHasNoLeadingDot(t *testing.T) {
	t.Parallel()
	if got := configuration.Path("").Child("a"); got != "a" {
		t.Fatalf("empty.Child(a) = %q, want %q (no leading dot)", got, "a")
	}
}

// Section: Diagnostics: zero value.
func TestDiagnostics_ZeroValueIsEmptyUsableSink(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	if d.HasError() {
		t.Fatal("zero Diagnostics.HasError() = true, want false")
	}
	if got := d.All(); got != nil {
		t.Fatalf("zero Diagnostics.All() = %v, want nil", got)
	}
}

func TestDiagnostics_Append(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	d.Append(configuration.Diagnostic{Severity: configuration.SeverityWarning, Summary: "w"})
	if d.HasError() {
		t.Fatal("warning-only HasError() = true, want false")
	}
	d.Append(configuration.Diagnostic{Severity: configuration.SeverityError, Summary: "e"})
	if !d.HasError() {
		t.Fatal("after error Append HasError() = false, want true")
	}
	if got := len(d.All()); got != 2 {
		t.Fatalf("All() len = %d, want 2", got)
	}
}

func TestDiagnostics_AppendVariadic(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	d.Append(
		configuration.Diagnostic{Severity: configuration.SeverityWarning, Summary: "a"},
		configuration.Diagnostic{Severity: configuration.SeverityError, Summary: "b"},
	)
	if got := len(d.All()); got != 2 {
		t.Fatalf("variadic Append len = %d, want 2", got)
	}
	if !d.HasError() {
		t.Fatal("variadic Append HasError() = false, want true")
	}
}

// All() returns a copy: mutating it must not affect the sink.
func TestDiagnostics_AllReturnsCopy(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	d.Append(configuration.Diagnostic{Severity: configuration.SeverityError, Summary: "x"})
	got := d.All()
	got[0].Summary = "MUTATED"
	if d.All()[0].Summary != "x" {
		t.Fatal("mutating All() result leaked back into the sink")
	}
	// Appending to the returned slice must not grow the sink either.
	got = append(got, configuration.Diagnostic{Summary: "extra"}) //nolint:staticcheck // SA4010: the appended-to slice is deliberately unused; this asserts the append cannot reach back into the sink.
	_ = got
	if len(d.All()) != 1 {
		t.Fatal("appending to All() result grew the sink")
	}
}

// Diagnostics has value semantics on copy: copying the struct then appending to
// the copy must not affect the original (Append is the only mutator, *D).
func TestDiagnostics_ValueSemanticsOnCopy(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	d.Append(configuration.Diagnostic{Severity: configuration.SeverityError, Summary: "orig"})
	cp := d
	cp.Append(configuration.Diagnostic{Severity: configuration.SeverityError, Summary: "added"})
	if len(d.All()) != 1 {
		t.Fatalf("appending to a copy mutated original: original len = %d, want 1", len(d.All()))
	}
}

// Value-semantics-on-copy must hold EVEN when the original carries spare backing
// capacity at copy time — the only case a naive in-place append can corrupt a
// sibling. The amortized Append (which keeps spare capacity to stay O(1)) must
// still clone-on-write across a copy so the copy's append cannot overwrite a slot
// the original would later fill, and the original's own next append cannot stomp
// the copy.
//
// Weaken-to-confirm: replace Append's body with a bare
// `d.findings = append(d.findings, findings...)` (drop the owner-sentinel
// clone-on-write). The original here is grown to a capacity strictly greater than
// its length, so cp aliases the original's spare slot; cp.Append then writes
// "cp-added" into that shared slot, and d.Append("orig-added") overwrites it (or
// vice versa) — the cross-check below then fails. The single-element original in
// TestDiagnostics_ValueSemanticsOnCopy cannot catch this (cap==len after its
// first append), which is exactly why this case exists.
func TestDiagnostics_ValueSemanticsOnCopyWithSpareCapacity(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	// Append several so the amortized backing array grows past its length,
	// leaving spare capacity that a copy could otherwise alias.
	for i := range 6 {
		d.Append(configuration.Diagnostic{Severity: configuration.SeverityWarning, Summary: "base", Detail: string(rune('a' + i))})
	}
	cp := d

	cp.Append(configuration.Diagnostic{Severity: configuration.SeverityError, Summary: "cp-added"})
	d.Append(configuration.Diagnostic{Severity: configuration.SeverityError, Summary: "orig-added"})

	// The original must NOT see the copy's appended finding, and vice versa.
	for _, dg := range d.All() {
		if dg.Summary == "cp-added" {
			t.Fatal("original observed the copy's appended finding: backing array was aliased")
		}
	}
	for _, dg := range cp.All() {
		if dg.Summary == "orig-added" {
			t.Fatal("copy observed the original's appended finding: backing array was aliased")
		}
	}
	// Each chain saw exactly its own added finding (6 base + 1).
	if got := len(d.All()); got != 7 {
		t.Fatalf("original len = %d, want 7", got)
	}
	if got := len(cp.All()); got != 7 {
		t.Fatalf("copy len = %d, want 7", got)
	}
	if !d.HasError() {
		t.Fatal("original must carry its own orig-added SeverityError")
	}
}

// All() is ordered by At.Source then At.Position.
func TestDiagnostics_AllOrderedBySourceThenPosition(t *testing.T) {
	t.Parallel()
	var d configuration.Diagnostics
	d.Append(
		configuration.Diagnostic{At: configuration.Position{Source: "b.yaml", Line: 1}, Summary: "b1"},
		configuration.Diagnostic{At: configuration.Position{Source: "a.yaml", Line: 9}, Summary: "a9"},
		configuration.Diagnostic{At: configuration.Position{Source: "a.yaml", Line: 2, Column: 5}, Summary: "a2c5"},
		configuration.Diagnostic{At: configuration.Position{Source: "a.yaml", Line: 2, Column: 1}, Summary: "a2c1"},
	)
	got := d.All()
	want := []string{"a2c1", "a2c5", "a9", "b1"}
	if len(got) != len(want) {
		t.Fatalf("All() len = %d, want %d", len(got), len(want))
	}
	for i := range want {
		if got[i].Summary != want[i] {
			t.Fatalf("All()[%d].Summary = %q, want %q (order: %v)", i, got[i].Summary, want[i], summaries(got))
		}
	}
}

func summaries(ds []configuration.Diagnostic) []string {
	out := make([]string, len(ds))
	for i, d := range ds {
		out[i] = d.Summary
	}
	return out
}

// Diagnostic is a comparable value type (the contract calls it comparable).
func TestDiagnostic_IsComparable(t *testing.T) {
	t.Parallel()
	a := configuration.Diagnostic{Severity: configuration.SeverityError, Path: "x", At: configuration.Position{Source: "s", Line: 1}, Summary: "sum", Detail: "det"}
	b := a
	if a != b { //nolint:staticcheck // intentional comparability assertion
		t.Fatal("identical Diagnostics compared unequal; type must be comparable")
	}
}

func TestSeverity_Ordering(t *testing.T) {
	t.Parallel()
	if configuration.SeverityWarning >= configuration.SeverityError {
		t.Fatalf("SeverityWarning (%d) must order before SeverityError (%d)", configuration.SeverityWarning, configuration.SeverityError)
	}
}
