package workspaceprovider

import (
	"context"
	"path"
	"strings"

	"github.com/gophersys/libs/go/dependencies"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// Tenancy label keys (07 §6). The library reads these from a spec's Labels to stamp the
// Handle's organization/project, so List/Open enforce cross-tenant isolation by
// construction.
const (
	LabelOrganization = "eden.org"
	LabelProject      = "eden.project"
)

// Config is the immutable, fully-resolved input (the configuration pattern: parsed at
// the edge, frozen). It holds the substrate-routing default and the tenancy namespace;
// it reads NO env, NO clock, NO secret value.
type Config struct {
	// Default routes a WorkspaceSpec that names no Substrate (the common single-
	// substrate app). Empty means "require an explicit Substrate" (a substrate-less spec
	// then yields InvalidSpecError). The central/local/BYO posture selects WHICH adapter
	// this default binds at the composition root (ADR-0012's "zero special code paths").
	Default Substrate
	// Namespace is the workspace-id / k8s-namespace / docker-label prefix that scopes
	// THIS Provider's ownership domain (05 §5) and keeps tenancies disjoint
	// (namespace-per-project on the multi-tenant central cluster, 07 §6); empty for
	// single-tenant local/BYO.
	Namespace string
}

// Deps is the injected hexagon. New constructs no ports.
type Deps struct {
	// Adapters maps a Substrate to its Adapter (the lower substrate seam). At least one
	// is required; New errors otherwise. The docker adapter and the kubernetes adapter
	// are the two v1 entries (05 §2); a managed kubernetes (EKS/GKE/AKS/DO) is the SAME
	// kubernetes adapter with a different client config — not a new adapter.
	Adapters map[Substrate]Adapter
	// Secrets resolves the opaque secrets.Reference in a spec (registry pull-secret,
	// workload token, TLS material) to a short-lived *secrets.Secret at Provision/Run
	// time, server-side, so the value reaches the substrate per the credential seam and
	// NEVER enters the spec, a Handle, a Status, a log, or an Event (07 §2). The library
	// resolves; the adapter injects.
	Secrets secrets.Provider
	// Clock stamps Descriptor/Status timestamps and bounds graceful-drain waits. Injected
	// so New stays pure and the fake is deterministic (dependencies.Clock).
	Clock dependencies.Clock
}

// Provisioner is the concrete Provider returned by New (the contract's "concrete
// *Substrate", renamed to Provisioner because Go cannot name both the substrate-selector
// string type and the concrete routing type "Substrate" — see the contract-ambiguity
// note in the package's conformance test). It routes each Provision/Open/List/Teardown
// to the Deps.Adapters entry for the spec's (or Config.Default's) Substrate, resolves
// secrets.References server-side before handing control to the adapter, assigns/validates
// Handles and stamps them with tenancy keys, wraps adapter HandleData as Workspaces, and
// enforces the ownership-domain labeling. Safe for concurrent use. Zero value unusable;
// construct via New.
type Provisioner struct {
	defaultSubstrate Substrate
	namespace        string
	adapters         map[Substrate]Adapter
	secrets          secrets.Provider
	clock            dependencies.Clock
}

// Static assertion: the concrete *Provisioner satisfies the Provider port.
var _ Provider = (*Provisioner)(nil)

// New is the pure constructor spine: no I/O, no clock read, no env read, no daemon
// dial, no apiserver call. It validates Config + Deps and returns the concrete
// *Provisioner. The first substrate I/O happens only at Provider.Provision/Open/List.
//
//nolint:gocritic // importShadow: the spine name New(configuration, dependencies) is the canon constructor signature (10 §4 / HNS-1); the parameter shadow is intentional and matches every Eden library.
func New(configuration Config, dependencies Deps) (*Provisioner, error) {
	if len(dependencies.Adapters) == 0 {
		return nil, errors.New(errors.KindInvalid, "workspaceprovider.New: Deps.Adapters requires at least one entry")
	}
	adapters := make(map[Substrate]Adapter, len(dependencies.Adapters))
	for substrate, adapter := range dependencies.Adapters {
		if adapter == nil {
			return nil, errors.New(errors.KindInvalid, "workspaceprovider.New: a Deps.Adapters entry is nil").
				WithField("substrate", string(substrate))
		}
		adapters[substrate] = adapter
	}
	if dependencies.Secrets == nil {
		return nil, errors.New(errors.KindInvalid, "workspaceprovider.New: Deps.Secrets is required")
	}
	if dependencies.Clock == nil {
		return nil, errors.New(errors.KindInvalid, "workspaceprovider.New: Deps.Clock is required")
	}
	if configuration.Default != "" {
		if _, ok := adapters[configuration.Default]; !ok {
			return nil, errors.New(errors.KindInvalid, "workspaceprovider.New: Config.Default names a substrate with no adapter").
				WithField("substrate", string(configuration.Default))
		}
	}
	return &Provisioner{
		defaultSubstrate: configuration.Default,
		namespace:        configuration.Namespace,
		adapters:         adapters,
		secrets:          dependencies.Secrets,
		clock:            dependencies.Clock,
	}, nil
}

// Provision creates a fresh isolated Workspace from spec and returns a live handle once
// it is Ready. ALL-OR-NOTHING and idempotent on spec.Name within a tenancy (the
// adapter's Create rolls back on partial failure; the library checks idempotency by
// listing the ownership domain first). Never returns a non-nil Workspace with a non-nil
// error.
//
//nolint:gocritic,ireturn // contract §2: Provision takes spec by value AND returns the Workspace port; the surface is frozen.
func (s *Provisioner) Provision(ctx context.Context, spec WorkspaceSpec) (Workspace, error) {
	substrate, adapter, err := s.route(spec.Substrate)
	if err != nil {
		return nil, err
	}
	if verr := validateSpec(&spec); verr != nil {
		return nil, verr
	}
	spec.Substrate = substrate

	// Stamp the spec fingerprint into the labels the adapter persists, so a later
	// same-Name Provision can decide COMPATIBLE (re-dial) vs INCOMPATIBLE (ConflictError)
	// by comparing fingerprints read back from List (idempotency is LIBRARY-owned).
	spec.Labels = withFingerprint(spec.Labels, specFingerprint(&spec))

	// Idempotency: a re-Provision of an existing, compatible workspace returns its
	// handle (the level-based reconcile contract). List the ownership domain by the
	// tenancy keys + name; an existing workspace with the SAME fingerprint is the
	// idempotent hit (re-dial it); a DIFFERENT fingerprint is a ConflictError.
	if existing, found, ierr := s.findExisting(ctx, adapter, &spec); ierr != nil {
		return nil, ierr
	} else if found {
		return existing, nil
	}

	resolved, cleanup, rerr := s.resolveForProvision(ctx, &spec)
	if rerr != nil {
		return nil, rerr
	}
	defer cleanup()

	data, cerr := adapter.Create(ctx, spec, resolved)
	if cerr != nil {
		return nil, classify(cerr)
	}
	handle := s.stampHandle(data.Handle, substrate, &spec)
	return s.wrap(handle, data.Connection, readOnlyTargets(&spec)), nil
}

// Open re-attaches to an already-provisioned workspace by Handle. PURELY a re-dial.
//
//nolint:ireturn // contract §2: Open returns the Workspace port; the surface is frozen.
func (s *Provisioner) Open(ctx context.Context, handle Handle) (Workspace, error) {
	if handle.IsZero() {
		return nil, wrapKind(&InvalidHandleError{Raw: handle.String()})
	}
	_, adapter, err := s.route(handle.Substrate())
	if err != nil {
		return nil, err
	}
	data, derr := adapter.Dial(ctx, handle)
	if derr != nil {
		return nil, classify(derr)
	}
	// Open is a pure re-dial: the spec (and thus its read-only mount targets) is not
	// known here, so the library enforces no read-only Files guard on a re-dialed
	// workspace (the clean-room flow provisions fresh and never re-dials).
	return s.wrap(handle, data.Connection, nil), nil
}

// List enumerates the workspaces Eden authored within a tenancy that match selector. It
// scopes the selector to this Provider's namespace and fans out to every routable
// adapter (the default substrate first, else all), returning the merged ownership domain.
func (s *Provisioner) List(ctx context.Context, selector Selector) ([]Descriptor, error) {
	out := make([]Descriptor, 0)
	for substrate, adapter := range s.adapters {
		descriptors, err := adapter.List(ctx, selector)
		if err != nil {
			return nil, classify(err)
		}
		for i := range descriptors {
			if descriptors[i].Substrate == "" {
				descriptors[i].Substrate = substrate
			}
		}
		out = append(out, descriptors...)
	}
	return out, nil
}

// Teardown destroys the workspace named by handle and reclaims its resources. IDEMPOTENT
// (an already-gone workspace is nil, not an error).
func (s *Provisioner) Teardown(ctx context.Context, handle Handle) error {
	if handle.IsZero() {
		return wrapKind(&InvalidHandleError{Raw: handle.String()})
	}
	_, adapter, err := s.route(handle.Substrate())
	if err != nil {
		return err
	}
	if derr := adapter.Destroy(ctx, handle); derr != nil {
		return classify(derr)
	}
	return nil
}

// route resolves the adapter for a substrate selector, applying Config.Default for an
// empty selector. An unknown substrate is an InvalidSpecError; an empty selector with no
// default is an InvalidSpecError.
//
//nolint:ireturn // route yields the adapter port internally so the public Provider methods can return the frozen ports.
func (s *Provisioner) route(selector Substrate) (Substrate, Adapter, error) {
	substrate := selector
	if substrate == "" {
		substrate = s.defaultSubstrate
	}
	if substrate == "" {
		return "", nil, wrapKind(&InvalidSpecError{Field: "Substrate", Reason: "no substrate and no Config.Default"})
	}
	adapter, ok := s.adapters[substrate]
	if !ok {
		return "", nil, wrapKind(&InvalidSpecError{Field: "Substrate", Reason: "no adapter for substrate " + string(substrate)})
	}
	return substrate, adapter, nil
}

// findExisting implements idempotency: it lists the ownership domain by the spec's
// tenancy keys + name and, on a same-Name match, compares the stored spec fingerprint to
// the incoming spec's. A COMPATIBLE match (same fingerprint) re-dials the existing
// workspace (the level-based reconcile contract); an INCOMPATIBLE match (different
// fingerprint — a re-Provision with a changed Image/Resources/Egress/Mounts/Env) is a
// ConflictError (Kind=Conflict), NEVER a silent return of the stale workspace.
//
//nolint:ireturn // findExisting returns the Workspace port (re-dialed) feeding Provision's frozen return.
func (s *Provisioner) findExisting(ctx context.Context, adapter Adapter, spec *WorkspaceSpec) (Workspace, bool, error) {
	selector := Selector{Labels: tenancyLabels(spec.Labels)}
	descriptors, err := adapter.List(ctx, selector)
	if err != nil {
		return nil, false, classify(err)
	}
	want := spec.Labels[SpecFingerprintLabel]
	for i := range descriptors {
		if descriptors[i].Name != spec.Name {
			continue
		}
		// A workspace with this Name exists in the tenancy. Compare fingerprints: a
		// changed Image/Resources/Egress/Mounts/Env is an INCOMPATIBLE re-Provision and
		// must surface a ConflictError rather than silently returning the old workspace.
		if got := descriptors[i].Labels[SpecFingerprintLabel]; got != "" && want != "" && got != want {
			return nil, false, wrapKind(&ConflictError{Name: spec.Name})
		}
		// Compatible (or a legacy workspace without a recorded fingerprint): re-dial it.
		ws, oerr := s.Open(ctx, descriptors[i].Handle)
		if oerr != nil {
			return nil, false, oerr
		}
		return ws, true, nil
	}
	return nil, false, nil
}

// resolveForProvision resolves every secrets.Reference in the spec to an un-printable
// *secrets.Secret, server-side, BEFORE handing control to the adapter (the credential
// seam, 07 §2). It returns the Resolved bundle and a cleanup that Zeroizes every
// resolved Secret after the adapter's Create returns. A failed resolution is mapped to
// an ImageError (for the pull-secret) or surfaced with its secrets Kind.
func (s *Provisioner) resolveForProvision(ctx context.Context, spec *WorkspaceSpec) (Resolved, func(), error) {
	resolved := Resolved{
		Mounts: map[string]*secrets.Secret{},
		Egress: map[string]*secrets.Secret{},
	}
	var minted []*secrets.Secret
	cleanup := func() {
		for _, sec := range minted {
			sec.Zeroize()
		}
	}

	if !spec.ImagePull.IsZero() {
		sec, err := s.secrets.Resolve(ctx, spec.ImagePull)
		if err != nil {
			cleanup()
			return Resolved{}, func() {}, wrapKind(&ImageError{Image: spec.Image, Ref: spec.ImagePull})
		}
		minted = append(minted, sec)
		resolved.PullSecret = sec
	}

	for i := range spec.Mounts {
		mount := spec.Mounts[i]
		if mount.Kind != MountSecret || mount.Ref.IsZero() {
			continue
		}
		sec, err := s.secrets.Resolve(ctx, mount.Ref)
		if err != nil {
			cleanup()
			return Resolved{}, func() {}, classifySecret(err)
		}
		minted = append(minted, sec)
		resolved.Mounts[mount.Target] = sec
	}

	for i := range spec.Egress {
		rule := spec.Egress[i]
		if rule.Ref.IsZero() {
			continue
		}
		sec, err := s.secrets.Resolve(ctx, rule.Ref)
		if err != nil {
			cleanup()
			return Resolved{}, func() {}, classifySecret(err)
		}
		minted = append(minted, sec)
		resolved.Egress[rule.Host] = sec
	}

	return resolved, cleanup, nil
}

// stampHandle re-derives the canonical Handle from the adapter's assigned identity plus the
// tenancy keys the LIBRARY owns (the adapter never invents tenancy). It uses the
// adapter-assigned Handle's Name()/WorkDir() (the substrate object identity) when present,
// else the spec values. The NAMESPACE is the adapter's when it assigned one (the native
// object physically lives there, so Open/Teardown must route to it), else the Provisioner's
// Config.Namespace — so a stateless re-dial addresses the right ownership domain.
func (s *Provisioner) stampHandle(assigned Handle, substrate Substrate, spec *WorkspaceSpec) Handle {
	name := assigned.Name()
	if name == "" {
		name = spec.Name
	}
	workDir := assigned.WorkDir()
	if workDir == "" {
		workDir = defaultWorkDir(spec)
	}
	namespace := assigned.Namespace()
	if namespace == "" {
		namespace = s.namespace
	}
	return newHandle(
		substrate,
		namespace,
		spec.Labels[LabelOrganization],
		spec.Labels[LabelProject],
		name,
		workDir,
	)
}

// wrap binds a Handle + a live adapter Connection + the read-only mount targets into the
// concrete *workspace the library hands the consumer as the Workspace port (returned
// concrete per accept-interfaces/return-concrete, 10 §9).
//
//nolint:ireturn // wrap constructs the Workspace port the frozen Provider methods return.
func (s *Provisioner) wrap(handle Handle, conn Connection, readOnly []string) *workspace {
	return &workspace{
		handle:          handle,
		conn:            conn,
		clock:           s.clock,
		secrets:         s.secrets,
		readOnlyTargets: readOnly,
	}
}

// readOnlyTargets extracts the absolute targets of read-only mounts from a spec — a
// MountInputs target (always read-only by the clean-room contract) or any mount flagged
// ReadOnly. The library guards Files.Put under these on every substrate (07 §4).
func readOnlyTargets(spec *WorkspaceSpec) []string {
	var targets []string
	for i := range spec.Mounts {
		if spec.Mounts[i].ReadOnly || spec.Mounts[i].Kind == MountInputs {
			targets = append(targets, spec.Mounts[i].Target)
		}
	}
	return targets
}

// validateSpec enforces the spec invariants the library owns before any adapter call.
func validateSpec(spec *WorkspaceSpec) error {
	if strings.TrimSpace(spec.Name) == "" {
		return wrapKind(&InvalidSpecError{Field: "Name", Reason: "must be non-empty"})
	}
	if strings.TrimSpace(spec.Image) == "" {
		return wrapKind(&InvalidSpecError{Field: "Image", Reason: "must be non-empty"})
	}
	for i := range spec.Mounts {
		if !path.IsAbs(spec.Mounts[i].Target) {
			return wrapKind(&InvalidSpecError{Field: "Mounts.Target", Reason: "mount target must be an absolute path"})
		}
		if spec.Mounts[i].Kind == MountSecret && spec.Mounts[i].Ref.IsZero() {
			return wrapKind(&InvalidSpecError{Field: "Mounts.Ref", Reason: "MountSecret requires a secrets.Reference"})
		}
	}
	return nil
}

// defaultWorkDir picks the path the harness runs in: the first Bind/Inputs mount target,
// else "/workspace".
func defaultWorkDir(spec *WorkspaceSpec) string {
	for i := range spec.Mounts {
		if spec.Mounts[i].Kind == MountBind || spec.Mounts[i].Kind == MountInputs {
			return spec.Mounts[i].Target
		}
	}
	return "/workspace"
}

// withFingerprint returns a copy of labels with the spec fingerprint stamped under
// SpecFingerprintLabel (so the original caller-supplied map is never mutated). The
// adapter persists this label; List reads it back for the idempotency/conflict check.
func withFingerprint(labels map[string]string, fingerprint string) map[string]string {
	out := make(map[string]string, len(labels)+1)
	for k, v := range labels {
		out[k] = v
	}
	out[SpecFingerprintLabel] = fingerprint
	return out
}

// tenancyLabels narrows a spec's Labels to the tenancy keys the Selector enforces (so a
// List never crosses a tenant boundary, 07 §6).
func tenancyLabels(labels map[string]string) map[string]string {
	out := map[string]string{}
	if org, ok := labels[LabelOrganization]; ok {
		out[LabelOrganization] = org
	}
	if proj, ok := labels[LabelProject]; ok {
		out[LabelProject] = proj
	}
	return out
}

// classify wraps an adapter-returned error with its stable Kind. An already-typed
// workspaceprovider error is re-wrapped through kindOf; a foreign error is surfaced as a
// SubstrateUnavailableError-equivalent only if it is genuinely unclassified — here it is
// passed through with KindUnknown so the caller still sees the cause.
func classify(err error) error {
	if err == nil {
		return nil
	}
	// If the adapter already returned a typed workspaceprovider error, wrap it with its
	// Kind. AsType walks the chain, so a wrapped typed error is still classified.
	if kind := classifyTyped(err); kind != errors.KindUnknown {
		return errors.Wrap(kind, "workspaceprovider: adapter call failed", err)
	}
	return errors.Wrap(errors.KindUnknown, "workspaceprovider: adapter call failed", err)
}

// classifyTyped reports the Kind for a chain that carries a known workspaceprovider error
// type, else KindUnknown.
func classifyTyped(err error) errors.Kind { //nolint:cyclop // a flat one-type-per-arm dispatch over the closed error set; splitting it would obscure the 1:1 mapping.
	switch {
	case asType[*InvalidSpecError](err), asType[*ImageError](err),
		asType[*NotReadyError](err), asType[*UnsupportedError](err),
		asType[*InvalidHandleError](err):
		return errors.KindInvalid
	case asType[*NotFoundError](err):
		return errors.KindNotFound
	case asType[*ConflictError](err):
		return errors.KindConflict
	case asType[*QuotaExceededError](err):
		return errors.KindExhausted
	case asType[*IsolationError](err):
		return errors.KindPermission
	case asType[*SubstrateUnavailableError](err):
		return errors.KindUnavailable
	case asType[*DeadlineError](err):
		return errors.KindDeadline
	default:
		// A foreign error may already carry an Eden Kind (e.g. a secrets error) — inherit it.
		return errors.KindOf(err)
	}
}

// asType is a boolean convenience over errors.AsType for the classify dispatch.
func asType[E error](err error) bool {
	_, ok := errors.AsType[E](err)
	return ok
}

// classifySecret maps a secrets resolution failure into the workspaceprovider error
// space, preserving the secrets Kind (NotFound/Denied/Unavailable/Invalid) so the
// reconcile loop still branches correctly. The Reference is loggable; the value is not
// present.
func classifySecret(err error) error {
	return errors.Wrap(errors.KindOf(err), "workspaceprovider: resolve credential", err)
}
