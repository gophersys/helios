package configuration

import (
	"slices"
	"sort"
)

// Diagnostics is the accumulating sink a Validator writes into and the edge
// reports. It has value semantics on copy; Append is the only mutator. The
// zero Diagnostics is an empty, usable sink: HasError() is false, All() is nil.
type Diagnostics struct {
	// unexported slice; never an exported mutable field (immutability of a
	// reported set is structural).
	findings []Diagnostic
}

// Append adds findings to the sink.
//
// Value semantics on copy are preserved by never aliasing the caller's backing
// array: a fresh slice is grown so that appending to a copy of a Diagnostics
// cannot reach back into the original (and vice versa).
func (d *Diagnostics) Append(findings ...Diagnostic) {
	if len(findings) == 0 {
		return
	}
	next := make([]Diagnostic, 0, len(d.findings)+len(findings))
	next = append(next, d.findings...)
	next = append(next, findings...)
	d.findings = next
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
