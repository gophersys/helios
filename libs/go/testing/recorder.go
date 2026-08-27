package testing

import "fmt"

// recorder is the internal Report the core hands each Case. It accumulates messages
// and a terminal outcome without importing stdlib "testing": Errorf records a
// failure and continues; Fatalf records a failure and aborts THIS case via a
// fatalSignal panic caught in runCase; Skipf marks the case skipped.
//
// Outcome precedence after the case body runs:
//   - if any Errorf/Fatalf fired      → Fail
//   - else if a Skipf fired           → Skip
//   - else                            → Pass
//
// A Skipf does not un-fail a prior Errorf: a case that asserted a real failure then
// tried to skip is still a Fail (a failure is never silently downgraded).
type recorder struct {
	messages []string
	failed   bool
	skipped  bool
}

func newRecorder() *recorder { return &recorder{} }

// fatalSignal is the sentinel a Fatalf panics with so runCase can abort only the
// current case body without treating it as an uncontained panic.
type fatalSignal struct{}

func (r *recorder) Errorf(format string, args ...any) {
	r.messages = append(r.messages, fmt.Sprintf(format, args...))
	r.failed = true
}

func (r *recorder) Fatalf(format string, args ...any) {
	r.messages = append(r.messages, fmt.Sprintf(format, args...))
	r.failed = true
	panic(fatalSignal{})
}

func (r *recorder) Skipf(format string, args ...any) {
	r.messages = append(r.messages, fmt.Sprintf(format, args...))
	r.skipped = true
}

// outcome resolves the recorded state into the tri-state Outcome.
func (r *recorder) outcome() Outcome {
	switch {
	case r.failed:
		return Fail
	case r.skipped:
		return Skip
	default:
		return Pass
	}
}
