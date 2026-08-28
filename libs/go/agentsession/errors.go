package agentsession

import (
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// The typed error set is errors.AsType-first (errors.md): each carries the offending
// ref/cap/state, never a secret value, and classifies to a stable errors.Kind so the
// transport boundary and the engine branch on Kind, never on a message string.

// UnsupportedError is returned by a control verb whose Capability the adapter
// declares absent (Steer/Resume on a harness that cannot). The UI consulted the
// manifest first; this is the belt-and-suspenders runtime guard. Kind: invalid.
type UnsupportedError struct{ Cap Capability }

// Error renders the operator-safe message (no secret).
func (e UnsupportedError) Error() string {
	return "agentsession: capability not supported by this adapter: " + e.Cap.String()
}

// Kind classifies UnsupportedError as an invalid-argument failure.
func (e UnsupportedError) Kind() errors.Kind { return errors.KindInvalid }

// SpawnError reports a failed process launch (binary missing, workspace gone, pod
// not ready). Kind: unavailable (a retry against a healthy pod may succeed).
type SpawnError struct{ Harness string }

// Error renders the operator-safe message (no secret).
func (e SpawnError) Error() string {
	return "agentsession: harness spawn failed: " + e.Harness
}

// Kind classifies SpawnError as a transient unavailability.
func (e SpawnError) Kind() errors.Kind { return errors.KindUnavailable }

// AuthError reports a credential failure AT OPEN — including the silent-bad-token
// trap: the library requires an init/ready event and converts its ABSENCE into an
// AuthError rather than trusting the harness exit code. It is the Unauthenticated
// outcome the chat renders as the setup-token card (C22). It carries the
// secrets.Reference (loggable), NEVER the value. Kind: unauthenticated.
type AuthError struct{ Reference secrets.Reference }

// Error renders the operator-safe message carrying the loggable Reference (never the
// secret value).
func (e AuthError) Error() string {
	return "agentsession: authentication failed for credential reference " + e.Reference.String()
}

// Kind classifies AuthError as an unauthenticated failure.
func (e AuthError) Kind() errors.Kind { return errors.KindUnauthenticated }

// StateError reports a control verb called in an illegal State (e.g. Prompt while
// Running, Abort on a terminal session). Kind: conflict (the call raced the session
// state; a retry from the right phase succeeds).
type StateError struct {
	From State
	Op   string
}

// Error renders the operator-safe message (no secret).
func (e StateError) Error() string {
	return "agentsession: operation " + e.Op + " is illegal in state " + e.From.String()
}

// Kind classifies StateError as a state conflict.
func (e StateError) Kind() errors.Kind { return errors.KindConflict }

// UnknownPermissionError reports a Resolve for a RequestID that is already resolved,
// expired, or never existed (multi-client races resolve to "first decision wins").
// Kind: not-found.
type UnknownPermissionError struct{ RequestID string }

// Error renders the operator-safe message (no secret).
func (e UnknownPermissionError) Error() string {
	return "agentsession: unknown or already-resolved permission request: " + e.RequestID
}

// Kind classifies UnknownPermissionError as a not-found failure.
func (e UnknownPermissionError) Kind() errors.Kind { return errors.KindNotFound }

// ConfigError reports an invalid Config or Deps at New (a nil required dependency, an
// empty adapter map). The pure constructor returns it before any I/O. Kind: invalid.
type ConfigError struct {
	Field   string
	Message string
}

// Error renders the operator-safe message (no secret).
func (e ConfigError) Error() string {
	return "agentsession: invalid configuration: " + e.Field + ": " + e.Message
}

// Kind classifies ConfigError as an invalid-argument failure.
func (e ConfigError) Kind() errors.Kind { return errors.KindInvalid }

// RouteError reports that no Adapter is registered for the harness a Spec's RouteKey
// resolves to, or that the RouteKey is unknown to the routing table. Kind: invalid.
type RouteError struct {
	Phase   string
	Role    string
	Harness string
}

// Error renders the operator-safe message (no secret).
func (e RouteError) Error() string {
	if e.Harness != "" {
		return "agentsession: no adapter registered for harness " + e.Harness
	}
	return "agentsession: no route for phase=" + e.Phase + " role=" + e.Role
}

// Kind classifies RouteError as an invalid-argument failure.
func (e RouteError) Kind() errors.Kind { return errors.KindInvalid }

// Compile-time assertions that every typed error satisfies the error interface and
// carries a stable Kind (the errors.md contract).
var (
	_ error = UnsupportedError{}
	_ error = SpawnError{}
	_ error = AuthError{}
	_ error = StateError{}
	_ error = UnknownPermissionError{}
	_ error = ConfigError{}
	_ error = RouteError{}
)
