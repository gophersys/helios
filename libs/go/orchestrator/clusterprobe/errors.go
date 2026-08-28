package clusterprobe

import (
	"github.com/gophersys/libs/go/errors"
)

// The error taxonomy: a distinct type per fault, each mapping to a stable errors.Kind so
// the transport boundary needs no per-package table (10 §9). Inspected via errors.AsType;
// classified via errors.KindOf after the package wraps with wrapKind. None ever embeds a
// secret value (a heartbeat / a Descriptor carries only loggable ids — never a credential).

type (
	// ConfigError reports an invalid Config or a nil required Dep at New (the only place this
	// package validates wiring). Kind=Invalid.
	ConfigError struct{ Reason string }

	// WorkspaceQueryError reports the list-by-label of live workspaces failed — the
	// project namespace could not be observed, so the workspace half of Actual is unknown
	// (the reconcile pass treats the whole Observe as failed rather than reporting a
	// fabricated "no workspaces live"). Kind=Unavailable.
	WorkspaceQueryError struct {
		Organization string
		Project      string
		Cause        error
	}

	// HealthQueryError reports the most-recent-heartbeat read failed — the session half of
	// Actual is unknown for the requested ids. Kind=Unavailable.
	HealthQueryError struct{ Cause error }
)

func (e *ConfigError) Error() string {
	return "clusterprobe: invalid configuration: " + e.Reason
}

func (e *WorkspaceQueryError) Error() string {
	return "clusterprobe: workspace list-by-label failed for project " +
		quote(e.Organization+"/"+e.Project) + ": " + causeMessage(e.Cause)
}

func (e *WorkspaceQueryError) Unwrap() error { return e.Cause }

func (e *HealthQueryError) Error() string {
	return "clusterprobe: health heartbeat read failed: " + causeMessage(e.Cause)
}

func (e *HealthQueryError) Unwrap() error { return e.Cause }

// kindOf maps a typed clusterprobe error to its stable errors.Kind. It classifies an
// UNWRAPPED leaf the package just minted (the wrapped-chain path is errors.KindOf via
// AsType), so the type switch is the right tool.
//
//nolint:errorlint // kindOf classifies an unwrapped leaf this package just minted; the wrapped-chain path is errors.KindOf via AsType.
func kindOf(err error) errors.Kind {
	switch err.(type) {
	case *ConfigError:
		return errors.KindInvalid
	case *WorkspaceQueryError, *HealthQueryError:
		return errors.KindUnavailable
	default:
		return errors.KindUnknown
	}
}

// wrapKind wraps a typed clusterprobe error with its stable errors.Kind so the transport
// boundary maps it without a per-package table (10 §9). Returns nil for a nil error (the
// happy path reads linearly).
func wrapKind(err error) error {
	if err == nil {
		return nil
	}
	return errors.Wrap(kindOf(err), err.Error(), err)
}

// causeMessage renders a wrapped cause's message, or a fixed token for a nil cause (so the
// operator-safe Error() never prints "<nil>"). It never interpolates a secret (the cause is
// a substrate/bus transport error, redaction-eligible).
func causeMessage(cause error) string {
	if cause == nil {
		return "unknown cause"
	}
	return cause.Error()
}

// quote renders s with surrounding quotes for an operator-safe error message without
// pulling strconv into the error path twice; it mirrors strconv.Quote's intent for the
// loggable project key (never a secret).
func quote(s string) string { return "\"" + s + "\"" }
