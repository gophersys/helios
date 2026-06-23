package workspaceprovider

import (
	"strconv"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// The error taxonomy is a set of distinct types, each carrying the offending
// handle/field/substrate/ref — NEVER a secret value — and each mapping to a stable
// errors.Kind so the transport boundary needs no per-port table (errors.md §5, 10 §9).
// Inspected via errors.AsType; classified via errors.KindOf after the library wraps
// them with wrapKind.

type (
	// InvalidSpecError reports a malformed WorkspaceSpec (no Image, unknown Substrate,
	// bad mount path). Kind=Invalid.
	InvalidSpecError struct{ Field, Reason string }

	// ImageError reports an unpullable/missing image (bad ref, ImagePull credential
	// denied — carries the secrets.Reference, NEVER the value). Kind=Invalid.
	ImageError struct {
		Image string
		Ref   secrets.Reference
	}

	// NotFoundError reports no such workspace/path in the caller's tenancy (Open/
	// Teardown/Files.Get for an absent workspace or path). Kind=NotFound.
	NotFoundError struct {
		Handle Handle
		Path   string
	}

	// ConflictError reports a non-idempotent name/state collision (a Provision whose
	// Name exists with an INCOMPATIBLE spec). Kind=Conflict.
	ConflictError struct{ Name string }

	// QuotaExceededError reports a provision/run that would breach the tenant's bound
	// limits (07 §6) — the central-cluster cross-tenant defense made a typed signal.
	// Kind=Exhausted (retry after reclaim, not immediately).
	QuotaExceededError struct {
		Handle   Handle
		Resource string // "cpu" | "memory" | "workspaces"
	}

	// IsolationError reports a failure to apply the declared isolation/egress guarantees
	// (NetworkPolicy rejected, namespace creation denied) — a HARD, fail-closed failure:
	// a workspace without its declared isolation is NEVER returned Ready (07 §3).
	// Kind=Permission.
	IsolationError struct {
		Handle Handle
		Detail string
	}

	// SubstrateUnavailableError reports the daemon/apiserver is unreachable or returned
	// a transient fault — the one retryable signal the reconcile loop backs off on.
	// Kind=Unavailable.
	SubstrateUnavailableError struct {
		Substrate Substrate
		Op        string
	}

	// NotReadyError reports a Run/Exec/Files-write called in an illegal State (Exec
	// before Ready, a second Run while Running, a write under a read-only Inputs mount).
	// Kind=Invalid.
	NotReadyError struct {
		Handle Handle
		State  State
		Op     string
	}

	// DeadlineError reports an Exec/provision that exceeded its timeout. Kind=Deadline.
	DeadlineError struct{ Op string }

	// UnsupportedError reports a verb needing a Capability the adapter declares absent
	// (MountVolume without CapPersistentVolume; PTY exec without CapExecPTY). Kind=Invalid.
	UnsupportedError struct{ Cap Capability }

	// InvalidHandleError reports a malformed/zero Handle. Kind=Invalid.
	InvalidHandleError struct{ Raw string }

	// IllegalStateTransitionError reports an adapter Probe that read a State the library's
	// State machine forbids transitioning INTO from the last-observed State (a move OUT of the
	// terminal Gone, or any edge not in the documented graph Provisioning → Ready → {Degraded →
	// Ready | Evicted} → Gone). The library — not the adapter — owns the legal-transition set
	// (types.go State doc), so a substrate reporting an impossible transition surfaces here
	// rather than corrupting the observed lifecycle. Kind=Conflict (the observed state conflicts
	// with the enforced machine; the reconcile loop branches on it like any other drift signal).
	IllegalStateTransitionError struct {
		Handle Handle
		From   State
		To     State
	}
)

// Error renders an operator-safe message; none of these ever interpolates a secret
// value (the Ref's canonical form is loggable by design, the value is not present).

func (e *InvalidSpecError) Error() string {
	return "workspaceprovider: invalid spec: field " + strconv.Quote(e.Field) + ": " + e.Reason
}

func (e *ImageError) Error() string {
	msg := "workspaceprovider: image " + strconv.Quote(e.Image) + " unavailable"
	if !e.Ref.IsZero() {
		msg += " (pull-secret " + strconv.Quote(e.Ref.String()) + ")"
	}
	return msg
}

func (e *NotFoundError) Error() string {
	if e.Path != "" {
		return "workspaceprovider: path " + strconv.Quote(e.Path) + " not found in workspace " + strconv.Quote(e.Handle.String())
	}
	return "workspaceprovider: workspace " + strconv.Quote(e.Handle.String()) + " not found"
}

func (e *ConflictError) Error() string {
	return "workspaceprovider: workspace " + strconv.Quote(e.Name) + " exists with an incompatible spec"
}

func (e *QuotaExceededError) Error() string {
	return "workspaceprovider: quota exceeded for " + strconv.Quote(e.Resource) + " (workspace " + strconv.Quote(e.Handle.String()) + ")"
}

func (e *IsolationError) Error() string {
	return "workspaceprovider: isolation not applied for workspace " + strconv.Quote(e.Handle.String()) + ": " + e.Detail
}

func (e *SubstrateUnavailableError) Error() string {
	return "workspaceprovider: substrate " + strconv.Quote(string(e.Substrate)) + " unavailable during " + strconv.Quote(e.Op)
}

func (e *NotReadyError) Error() string {
	return "workspaceprovider: " + strconv.Quote(e.Op) + " not legal in state " + e.State.String() + " (workspace " + strconv.Quote(e.Handle.String()) + ")"
}

func (e *DeadlineError) Error() string {
	return "workspaceprovider: operation " + strconv.Quote(e.Op) + " exceeded its deadline"
}

func (e *UnsupportedError) Error() string {
	return "workspaceprovider: capability " + e.Cap.String() + " is not supported by this substrate"
}

func (e *InvalidHandleError) Error() string {
	return "workspaceprovider: malformed handle " + strconv.Quote(e.Raw)
}

func (e *IllegalStateTransitionError) Error() string {
	return "workspaceprovider: illegal State transition " + e.From.String() + " -> " + e.To.String() +
		" (workspace " + strconv.Quote(e.Handle.String()) + ")"
}

// String renders a Capability for diagnostics (used by UnsupportedError).
func (c Capability) String() string {
	switch c {
	case CapExecPTY:
		return "exec-pty"
	case CapPersistentVolume:
		return "persistent-volume"
	case CapBindMount:
		return "bind-mount"
	case CapEgressPolicy:
		return "egress-policy"
	case CapResourceLimits:
		return "resource-limits"
	case CapLogStream:
		return "log-stream"
	case CapMultiTenant:
		return "multi-tenant"
	case CapReattach:
		return "reattach"
	case CapHibernate:
		return "hibernate"
	case CapSupervise:
		return "supervise"
	case CapWorkloadPod:
		return "workload-pod"
	case CapEditorSidecar:
		return "editor-sidecar"
	default:
		return "unknown"
	}
}

// kindOf is the TOTAL classifier mapping each workspaceprovider error type to its stable
// errors.Kind (design rationale 6). Every type maps; an unknown error is KindUnknown.
// This is the single table the library wraps with (wrapKind), so the transport boundary
// reads errors.KindOf without a workspaceprovider-specific switch.
//
// The switch is on the CONCRETE leaf type ON PURPOSE: kindOf is only ever called by
// wrapKind on a freshly-minted, UNWRAPPED workspaceprovider error the library is about to
// wrap; classification of an already-WRAPPED chain is classifyTyped (which uses
// errors.AsType). A type switch is the right tool for the unwrapped-leaf case.
//
//nolint:errorlint // kindOf classifies an unwrapped leaf the library just minted; the wrapped-chain path is classifyTyped via errors.AsType.
func kindOf(err error) errors.Kind {
	switch err.(type) {
	case *InvalidSpecError, *ImageError, *NotReadyError, *UnsupportedError, *InvalidHandleError:
		return errors.KindInvalid
	case *NotFoundError:
		return errors.KindNotFound
	case *ConflictError, *IllegalStateTransitionError:
		return errors.KindConflict
	case *QuotaExceededError:
		return errors.KindExhausted
	case *IsolationError:
		return errors.KindPermission
	case *SubstrateUnavailableError:
		return errors.KindUnavailable
	case *DeadlineError:
		return errors.KindDeadline
	default:
		return errors.KindUnknown
	}
}
