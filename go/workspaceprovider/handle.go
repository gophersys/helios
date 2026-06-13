package workspaceprovider

import (
	"strings"

	"github.com/gophersys/libs/go/errors"
)

// schemeSeparator delimits the substrate scheme from the path in a Handle's canonical
// form, e.g. "docker://ws-9f3a".
const schemeSeparator = "://"

// Handle is the durable, loggable identity of a provisioned workspace — the join key
// between Eden's records and substrate state, and the ONLY durable per-workspace state
// the orchestrator keeps (Open re-dials from it across restarts). Comparable (a map key
// for the reconcile loop), loggable by contract (carries no secret), and tenancy-bearing.
// Constructed by the library at Provision (never by a consumer); ParseHandle round-trips
// its canonical string for persistence. Zero value: invalid (IsZero true).
//
// Canonical form:
//
//	docker://<workdir-encoded>/<name>            (single-tenant: no org/project)
//	kubernetes://<namespace>/<org>/<project>/<name>
//
// The unexported field forces every Handle through the library / ParseHandle, mirroring
// the frozen secrets.Reference decision (Q2).
type Handle struct {
	raw string // canonical, e.g. "kubernetes://eden/org-7/proj-42/ws-9f3a" or "docker://ws-9f3a"
}

// newHandle builds a canonical Handle from its parts. It is the library's sole
// constructor (a consumer never builds one). substrate routes Open/Teardown; namespace
// scopes the ownership domain; organization/project are the tenancy keys ("" for
// single-tenant local/BYO); name is the tenancy-scoped logical workspace name; workDir
// is the path the harness runs in. The parts are joined into the canonical scheme form.
func newHandle(substrate Substrate, namespace, organization, project, name, workDir string) Handle {
	segments := []string{
		encodeSegment(namespace),
		encodeSegment(organization),
		encodeSegment(project),
		encodeSegment(name),
		encodeSegment(workDir),
	}
	return Handle{raw: string(substrate) + schemeSeparator + strings.Join(segments, "/")}
}

// ParseHandle reconstructs a Handle from its persisted canonical form. PURE;
// shape-validated; InvalidHandleError (Kind=Invalid) on malformed input. The
// orchestrator stores Handle.String() and re-hydrates with this across restarts.
func ParseHandle(s string) (Handle, error) {
	if s == "" {
		return Handle{}, wrapKind(&InvalidHandleError{Raw: s})
	}
	scheme, rest, ok := strings.Cut(s, schemeSeparator)
	if !ok || scheme == "" {
		return Handle{}, wrapKind(&InvalidHandleError{Raw: s})
	}
	if scheme != string(SubstrateDocker) && scheme != string(SubstrateKubernetes) {
		return Handle{}, wrapKind(&InvalidHandleError{Raw: s})
	}
	// Five segments: namespace/organization/project/name/workdir. A missing name
	// segment is malformed; empty tenancy/namespace/workdir segments are legal
	// (single-tenant local).
	segments := strings.Split(rest, "/")
	if len(segments) != handleSegmentCount {
		return Handle{}, wrapKind(&InvalidHandleError{Raw: s})
	}
	if segments[handleNameIndex] == "" {
		return Handle{}, wrapKind(&InvalidHandleError{Raw: s})
	}
	return Handle{raw: s}, nil
}

// handleSegmentCount / the segment indices index the canonical path's parts.
const (
	handleNamespaceIndex = iota
	handleOrganizationIndex
	handleProjectIndex
	handleNameIndex
	handleWorkDirIndex
	handleSegmentCount
)

// String returns the canonical form. A Handle is loggable by design.
func (h Handle) String() string { return h.raw }

// Substrate reports which substrate authored the workspace — it routes Open/Teardown.
func (h Handle) Substrate() Substrate {
	scheme, _, ok := strings.Cut(h.raw, schemeSeparator)
	if !ok {
		return ""
	}
	return Substrate(scheme)
}

// WorkDir is the path the harness runs in → agentsession.Spec.Workspace (02 §1).
func (h Handle) WorkDir() string { return h.segment(handleWorkDirIndex) }

// Organization is the tenancy key (07 §6); "" for single-tenant local/BYO.
func (h Handle) Organization() string { return h.segment(handleOrganizationIndex) }

// Project is the tenancy key (07 §6).
func (h Handle) Project() string { return h.segment(handleProjectIndex) }

// Name is the tenancy-scoped logical workspace name (the Provision idempotency key).
func (h Handle) Name() string { return h.segment(handleNameIndex) }

// Namespace is the ownership-domain prefix this workspace lives under (05 §5).
func (h Handle) Namespace() string { return h.segment(handleNamespaceIndex) }

// IsZero reports whether h is the invalid zero Handle.
func (h Handle) IsZero() bool { return h.raw == "" }

// segment decodes the nth path segment of a well-formed Handle ("" out of range).
func (h Handle) segment(n int) string {
	_, rest, ok := strings.Cut(h.raw, schemeSeparator)
	if !ok {
		return ""
	}
	segments := strings.Split(rest, "/")
	if n < 0 || n >= len(segments) {
		return ""
	}
	return decodeSegment(segments[n])
}

// encodeSegment makes a path segment safe for the "/"-joined canonical form by
// percent-encoding the only two bytes that would corrupt parsing ("/" and "%"). It
// keeps the Handle a single flat, comparable, loggable string while letting a WorkDir
// like "/workspace" round-trip exactly.
func encodeSegment(s string) string {
	if !strings.ContainsAny(s, "/%") {
		return s
	}
	var b strings.Builder
	b.Grow(len(s) + 2)
	for i := 0; i < len(s); i++ {
		switch s[i] {
		case '%':
			b.WriteString("%25")
		case '/':
			b.WriteString("%2F")
		default:
			b.WriteByte(s[i])
		}
	}
	return b.String()
}

// decodeSegment reverses encodeSegment.
func decodeSegment(s string) string {
	if !strings.Contains(s, "%") {
		return s
	}
	r := strings.NewReplacer("%2F", "/", "%2f", "/", "%25", "%")
	return r.Replace(s)
}

// wrapKind wraps a typed workspaceprovider error with its stable errors.Kind so the
// transport boundary maps it without a per-port table (10 §9). Returns nil for a nil
// error (the happy path reads linearly).
func wrapKind(err error) error {
	if err == nil {
		return nil
	}
	return errors.Wrap(kindOf(err), err.Error(), err)
}
