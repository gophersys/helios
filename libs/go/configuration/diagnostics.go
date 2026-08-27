package configuration

import (
	"slices"
	"sort"
)

// Diagnostics is the accumulating sink a Validator writes into and the edge
// reports. It has value semantics on copy; Append is the only mutator. The
// zero Diagnostics is an empty, usable sink: HasError() is false, All() is nil.
type Diagnostics struct {
	// owner is a self-referential copy-detection sentinel (the strings.Builder
	// idiom). It points at the Diagnostics that exclusively owns findings'
	// backing array. A struct value copy does NOT update it, so a copied
	// Diagnostics observes owner != &copy and clones-on-write before its first
	// in-place append — that is what preserves value semantics on copy WITHOUT a
	// clone on every Append (the prior implementation cloned the whole backing
	// slice each call, making an accumulate-all parse O(n^2)). The pointer is
	// never dereferenced; only its identity is compared. nil before first Append.
	owner    *Diagnostics
	findings []Diagnostic
}

// Append adds findings to the sink.
//
// Growth is amortized O(1) within a single owner: an ordinary append reuses
// spare capacity instead of re-cloning the whole backing array on every call.
// Value semantics on copy are preserved by the copy-detection sentinel: the
// FIRST append after a struct copy (owner no longer points at this receiver)
// clones the backing slice into a fresh array this receiver exclusively owns, so
// a copy and its original never write into shared storage. All() additionally
// returns a clone, so an externally retained slice is never aliased either.
func (d *Diagnostics) Append(findings ...Diagnostic) {
	if len(findings) == 0 {
		return
	}
	if d.owner != d {
		// First append, or first append after a value copy: take exclusive
		// ownership of an independent backing array. slices.Clone gives a fresh
		// array (nil findings clones to nil, then append allocates), so a sibling
		// copy that still references the old array is never mutated.
		d.findings = slices.Clone(d.findings)
		d.owner = d
	}
	d.findings = append(d.findings, findings...)
}

// HasError reports whether any appended finding is SeverityError.
func (d *Diagnostics) HasError() bool {
	for i := range d.findings {
		if d.findings[i].Severity == SeverityError {
			return true
		}
	}
	return false
}

// All returns a copy of every finding, ordered by At.Source then At.Position.
// Callers may freely retain or mutate the returned slice.
func (d *Diagnostics) All() []Diagnostic {
	if len(d.findings) == 0 {
		return nil
	}
	out := slices.Clone(d.findings)
	sort.SliceStable(out, func(i, j int) bool {
		return lessByPosition(out[i].At, out[j].At)
	})
	return out
}

// lessByPosition orders by Source, then Line, then Column.
func lessByPosition(a, b Position) bool {
	if a.Source != b.Source {
		return a.Source < b.Source
	}
	if a.Line != b.Line {
		return a.Line < b.Line
	}
	return a.Column < b.Column
}
