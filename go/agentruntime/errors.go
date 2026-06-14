package agentruntime

import "github.com/gophersys/libs/go/errors"

// TerminationReason is the typed reason the PID-1 run loop exited — the graceful-shutdown state
// machine's verdict (ADR-0022 Consequences: "signal.NotifyContext → typed termination reason →
// cancel → drain → cleanup → OTel flush"). Run returns it so main() maps it to a process exit code.
// Closed taxonomy, append-only (10 §9).
type TerminationReason uint8

// The PID-1 termination reasons.
const (
	TerminationUnknown     TerminationReason = iota // unset/zero — never returned by a clean Run
	TerminationSignal                               // a SIGTERM/SIGINT (the parent ctx) drove a graceful drain
	TerminationControlStop                          // a control STOP verb drove a graceful drain
	TerminationControlKill                          // a control KILL verb canceled the agent immediately
	TerminationSessionEnd                           // the harness session reached its own terminal (Result/Failed/Aborted)
	TerminationFault                                // the run loop hit an unrecoverable fault (spawn/transport)
)

// terminationTokens holds the stable lower-kebab token for each TerminationReason, indexed by value.
var terminationTokens = [...]string{
	TerminationUnknown:     "unknown",
	TerminationSignal:      "signal",
	TerminationControlStop: "control-stop",
	TerminationControlKill: "control-kill",
	TerminationSessionEnd:  "session-end",
	TerminationFault:       "fault",
}

// String returns the stable lower-kebab token (e.g. "control-stop"). Total: returns "unknown" for
// any out-of-range value.
func (r TerminationReason) String() string {
	if int(r) < len(terminationTokens) {
		return terminationTokens[r]
	}
	return terminationTokens[TerminationUnknown]
}

// IsGraceful reports whether this reason ended the loop through a clean drain (signal/stop/
// session-end) rather than a hard cancel/fault. main() maps a graceful reason to exit 0.
func (r TerminationReason) IsGraceful() bool {
	return r == TerminationSignal || r == TerminationControlStop || r == TerminationSessionEnd
}

// ConfigError is the typed New-time error: a Configuration/Dependencies invariant was violated (a
// missing required port, an empty AgentID). It is inspected by type via errors.AsType, never by
// string (the errors contract). It carries NO secret.
type ConfigError struct {
	field string
	cause error
}

// Error renders the field whose invariant was violated. Lowercase, no trailing punctuation (the
// errors contract / revive error-strings).
func (e *ConfigError) Error() string {
	if e.cause != nil {
		return "agentruntime configuration invalid: " + e.field + ": " + e.cause.Error()
	}
	return "agentruntime configuration invalid: " + e.field
}

// Unwrap exposes the wrapped cause so the error chain stays inspectable (errors.Is/AsType).
func (e *ConfigError) Unwrap() error { return e.cause }

// newConfigError builds a *ConfigError wrapped on the Eden errors seam (KindInvalid) so a caller
// branches on KindOf == KindInvalid OR AsType[*ConfigError].
func newConfigError(field string) error {
	return errors.Wrap(errors.KindInvalid, "agentruntime: construct runtime", &ConfigError{field: field})
}
