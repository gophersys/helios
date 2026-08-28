package orchestrator

import (
	"strconv"

	"github.com/gophersys/libs/go/errors"
)

// The error taxonomy is a set of distinct types, each carrying the offending id/ref —
// NEVER a secret value — and each mapping to a stable errors.Kind so the transport
// boundary needs no per-port table (errors.md §5, 10 §9). Inspected via errors.AsType;
// classified via errors.KindOf after the library wraps them with wrapKind.

type (
	// TemplateNotFoundError reports an unknown TemplateRef at Spawn. Kind=NotFound.
	TemplateNotFoundError struct{ Ref TemplateRef }

	// NotFoundError reports no such agent in the caller's tenancy (Get/Stop/Resume for
	// an unknown id). Kind=NotFound.
	NotFoundError struct{ ID AgentID }

	// LimitError reports a Spawn rejected by the (Tenant, Template) MaxConcurrent ceiling
	// — checked at admission, BEFORE any pod (fail cheap). It carries Max + Current so the
	// UI shows "5 of 8 running". Kind=Exhausted.
	LimitError struct {
		Tenant   Tenancy
		Template TemplateRef
		Max      int
		Current  int
	}

	// InvalidRequestError reports a malformed SpawnRequest or a widening override (a
	// budget larger than the template ceiling, a missing tenant/template). Kind=Invalid.
	InvalidRequestError struct{ Reason string }

	// ConflictError reports a Resume on an agent that is not in a resumable Status.
	// Kind=Conflict.
	ConflictError struct {
		ID     AgentID
		Status Status
	}

	// UnsupportedError reports a Resume but the bound adapter declares CapResume absent.
	// Kind=Invalid.
	UnsupportedError struct {
		ID         AgentID
		Capability string
	}

	// ProvisionError reports a workspace provisioning fault the reconcile loop could not
	// recover within ProvisionTimeout (often retryable). Kind=Unavailable.
	ProvisionError struct {
		Tenant  Tenancy
		Cluster ClusterRef
		Message string
	}

	// ConfigError reports an invalid Config or a nil required Dep at New. Kind=Invalid.
	ConfigError struct{ Reason string }
)

// Error renders an operator-safe message; none of these ever interpolates a secret
// value (the records carry only loggable ids/refs, never a credential).

func (e *TemplateNotFoundError) Error() string {
	return "orchestrator: template not found: " + e.Ref.String()
}

func (e *NotFoundError) Error() string {
	return "orchestrator: agent not found: " + strconv.Quote(string(e.ID))
}

func (e *LimitError) Error() string {
	return "orchestrator: max concurrent reached for tenant " +
		strconv.Quote(e.Tenant.OrganizationID+"/"+e.Tenant.ProjectID) +
		" template " + e.Template.String() + ": " +
		strconv.Itoa(e.Current) + " of " + strconv.Itoa(e.Max) + " running"
}

func (e *InvalidRequestError) Error() string {
	return "orchestrator: invalid spawn request: " + e.Reason
}

func (e *ConflictError) Error() string {
	return "orchestrator: agent " + strconv.Quote(string(e.ID)) +
		" not resumable in status " + e.Status.String()
}

func (e *UnsupportedError) Error() string {
	return "orchestrator: agent " + strconv.Quote(string(e.ID)) +
		" unsupported: capability " + strconv.Quote(e.Capability) + " absent"
}

func (e *ProvisionError) Error() string {
	return "orchestrator: provision failed for tenant " +
		strconv.Quote(e.Tenant.OrganizationID+"/"+e.Tenant.ProjectID) +
		" cluster " + strconv.Quote(e.Cluster.ID) + ": " + e.Message
}

func (e *ConfigError) Error() string {
	return "orchestrator: invalid configuration: " + e.Reason
}

// kindOf maps a typed orchestrator error to its stable errors.Kind (the single mapping
// the transport boundary relies on). Unknown types are KindUnknown so the wrap is a
// no-op classification rather than a wrong one. It classifies an UNWRAPPED leaf the
// library just minted (the wrapped-chain path is errors.KindOf via errors.AsType), so the
// type switch is the right tool.
//
//nolint:errorlint // kindOf classifies an unwrapped leaf the library just minted; the wrapped-chain path is errors.KindOf via AsType.
func kindOf(err error) errors.Kind {
	switch err.(type) {
	case *TemplateNotFoundError, *NotFoundError:
		return errors.KindNotFound
	case *LimitError:
		return errors.KindExhausted
	case *InvalidRequestError, *UnsupportedError, *ConfigError:
		return errors.KindInvalid
	case *ConflictError:
		return errors.KindConflict
	case *ProvisionError:
		return errors.KindUnavailable
	default:
		return errors.KindUnknown
	}
}

// wrapKind wraps a typed orchestrator error with its stable errors.Kind so the transport
// boundary maps it without a per-port table (10 §9). Returns nil for a nil error (the
// happy path reads linearly).
func wrapKind(err error) error {
	if err == nil {
		return nil
	}
	return errors.Wrap(kindOf(err), err.Error(), err)
}
