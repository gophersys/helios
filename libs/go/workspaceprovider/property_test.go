package workspaceprovider_test

import (
	"context"
	"testing"

	"pgregory.net/rapid"

	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// The `property` ctl.sh verb runs `go test` with RAPID_CHECKS in the process environment
// (default 1000 iterations/property, ADR-0020 dimension (a)); rapid reads it directly. These
// properties drive the REAL Provisioner/workspace/idempotency/fingerprint machinery over the
// in-memory fake adapter — the fake is the conformance two-binding partner (08 §2), NOT a mock
// of the library under test.

// drawSpec draws a random-but-valid WorkspaceSpec: a non-empty Name+Image, a random mount/egress/
// env/resource shape, and the tenancy labels. The mount targets are always absolute (the library
// rejects relative targets), so a drawn spec always passes validateSpec.
func drawSpec(rt *rapid.T) workspaceprovider.WorkspaceSpec {
	name := "ws-" + rapid.StringMatching(`[a-z][a-z0-9]{0,11}`).Draw(rt, "name")
	image := "img-" + rapid.StringMatching(`[a-z0-9]{1,8}`).Draw(rt, "image") + ":1"

	nMounts := rapid.IntRange(0, 3).Draw(rt, "nMounts")
	mounts := make([]workspaceprovider.Mount, 0, nMounts)
	for i := range nMounts {
		mounts = append(mounts, workspaceprovider.Mount{
			Kind:     workspaceprovider.MountBind,
			Target:   "/m" + rapid.StringMatching(`[a-z]{1,6}`).Draw(rt, "mtarget"),
			ReadOnly: rapid.Bool().Draw(rt, "ro"),
		})
		_ = i
	}

	nEgress := rapid.IntRange(0, 3).Draw(rt, "nEgress")
	egress := make([]workspaceprovider.EgressRule, 0, nEgress)
	for range nEgress {
		egress = append(egress, workspaceprovider.EgressRule{
			Host:  rapid.StringMatching(`[a-z]{1,6}\.example\.com`).Draw(rt, "host"),
			Ports: rapid.SliceOfN(rapid.IntRange(1, 65535), 0, 3).Draw(rt, "ports"),
		})
	}

	nEnv := rapid.IntRange(0, 3).Draw(rt, "nEnv")
	env := make([]workspaceprovider.EnvVar, 0, nEnv)
	for range nEnv {
		env = append(env, workspaceprovider.EnvVar{
			Name:  rapid.StringMatching(`[A-Z]{1,6}`).Draw(rt, "envk"),
			Value: rapid.StringMatching(`[a-z0-9]{0,8}`).Draw(rt, "envv"),
		})
	}

	return workspaceprovider.WorkspaceSpec{
		Name:   name,
		Image:  image,
		Mounts: mounts,
		Egress: egress,
		Env:    env,
		Resources: workspaceprovider.Resources{
			CPUMilli:    rapid.Int64Range(0, 4000).Draw(rt, "cpu"),
			MemoryBytes: rapid.Int64Range(0, 1<<30).Draw(rt, "mem"),
			PIDs:        rapid.Int64Range(0, 4096).Draw(rt, "pids"),
		},
		Labels: map[string]string{
			workspaceprovider.LabelOrganization: "org-" + rapid.StringMatching(`[a-z0-9]{1,6}`).Draw(rt, "org"),
			workspaceprovider.LabelProject:      "proj-" + rapid.StringMatching(`[a-z0-9]{1,6}`).Draw(rt, "proj"),
		},
	}
}

// TestProperty_ProvisionDeterministicAndIdempotent asserts the level-based reconcile contract:
// for ANY valid spec, re-Provisioning the SAME spec returns the SAME Handle (idempotent on
// spec.Name within a tenancy) and the Handle is stable across the two calls (spec->workspace
// determinism). A drift here would make the reconcile loop create a duplicate workspace on every
// pass — a runaway.
func TestProperty_ProvisionDeterministicAndIdempotent(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		prov := workspaceprovidertest.FakeProvider(nil)
		spec := drawSpec(rt)
		ctx := context.Background()

		a, err := prov.Provision(ctx, spec)
		if err != nil {
			rt.Fatalf("first Provision: %v", err)
		}
		b, err := prov.Provision(ctx, spec)
		if err != nil {
			rt.Fatalf("re-Provision (idempotent): %v", err)
		}
		if a.Handle().String() != b.Handle().String() {
			rt.Fatalf("idempotent re-Provision drifted: %q != %q", a.Handle().String(), b.Handle().String())
		}
		// The Handle carries the tenancy keys it was provisioned under (cross-tenant isolation by
		// construction).
		if a.Handle().Organization() != spec.Labels[workspaceprovider.LabelOrganization] {
			rt.Fatalf("Handle.Organization = %q, want %q", a.Handle().Organization(), spec.Labels[workspaceprovider.LabelOrganization])
		}
		if a.Handle().Project() != spec.Labels[workspaceprovider.LabelProject] {
			rt.Fatalf("Handle.Project = %q, want %q", a.Handle().Project(), spec.Labels[workspaceprovider.LabelProject])
		}
	})
}

// TestProperty_HandleRoundTrips asserts that for ANY valid spec, the provisioned Handle survives
// a ParseHandle round-trip byte-for-byte and its accessors decode the same values — the
// orchestrator persists Handle.String() and re-hydrates it across restarts, so a lossy round-trip
// would orphan the workspace (Open could never re-dial it).
func TestProperty_HandleRoundTrips(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		prov := workspaceprovidertest.FakeProvider(nil)
		spec := drawSpec(rt)
		ws, err := prov.Provision(context.Background(), spec)
		if err != nil {
			rt.Fatalf("Provision: %v", err)
		}
		h := ws.Handle()
		parsed, perr := workspaceprovider.ParseHandle(h.String())
		if perr != nil {
			rt.Fatalf("ParseHandle(%q): %v", h.String(), perr)
		}
		if parsed.String() != h.String() {
			rt.Fatalf("Handle round-trip drifted: %q != %q", parsed.String(), h.String())
		}
		if parsed.Name() != h.Name() || parsed.WorkDir() != h.WorkDir() ||
			parsed.Substrate() != h.Substrate() || parsed.Namespace() != h.Namespace() {
			rt.Fatalf("Handle accessor drift after round-trip: %+v vs %+v", parsed, h)
		}
	})
}

// TestProperty_MountEgressReorderIsNotAConflict asserts the fingerprint is order-insensitive over
// Mounts and Egress: a re-Provision with the SAME mounts/egress in a DIFFERENT order is the SAME
// workspace (idempotent re-dial), NEVER a false ConflictError. A consumer builds these slices in
// any order; an order-sensitive fingerprint would spuriously conflict on a benign re-order.
func TestProperty_MountEgressReorderIsNotAConflict(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		prov := workspaceprovidertest.FakeProvider(nil)
		ctx := context.Background()
		spec := drawSpec(rt)
		if len(spec.Mounts) < 2 && len(spec.Egress) < 2 {
			return // nothing to reorder; not a counterexample
		}

		first, err := prov.Provision(ctx, spec)
		if err != nil {
			rt.Fatalf("first Provision: %v", err)
		}

		reordered := spec
		reordered.Mounts = reverseMounts(spec.Mounts)
		reordered.Egress = reverseEgress(spec.Egress)

		second, rerr := prov.Provision(ctx, reordered)
		if rerr != nil {
			rt.Fatalf("re-Provision with reordered mounts/egress must be idempotent, got: %v", rerr)
		}
		if first.Handle().String() != second.Handle().String() {
			rt.Fatalf("a benign mount/egress re-order produced a different workspace: %q != %q",
				first.Handle().String(), second.Handle().String())
		}
	})
}

// TestProperty_IncompatibleRespecIsConflict asserts the OTHER half of the idempotency contract:
// re-Provisioning the SAME Name with an INCOMPATIBLE spec (a changed Image) is a ConflictError
// (Kind=Conflict), NEVER a silent return of the stale workspace. This is the guard that keeps a
// reconcile loop from silently running a workload against an out-of-date image.
func TestProperty_IncompatibleRespecIsConflict(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		prov := workspaceprovidertest.FakeProvider(nil)
		ctx := context.Background()
		spec := drawSpec(rt)

		if _, err := prov.Provision(ctx, spec); err != nil {
			rt.Fatalf("first Provision: %v", err)
		}
		// Same Name + tenancy, a genuinely different image -> incompatible.
		changed := spec
		changed.Image = spec.Image + "-changed"
		_, cerr := prov.Provision(ctx, changed)
		if cerr == nil {
			rt.Fatalf("re-Provision with a changed Image must conflict, got nil")
		}
		if errors.KindOf(cerr) != errors.KindConflict {
			rt.Fatalf("incompatible re-Provision Kind = %v, want Conflict", errors.KindOf(cerr))
		}
		if typed, ok := errors.AsType[*workspaceprovider.ConflictError](cerr); !ok || typed == nil {
			rt.Fatalf("incompatible re-Provision: want *ConflictError in the chain, got %v", cerr)
		}
	})
}

// TestProperty_TeardownIsIdempotentAndConverges asserts the GC/reconcile convergence invariant:
// for ANY provisioned workspace, Teardown is idempotent (the second is nil, not an error) and
// after teardown Open yields NotFound — so a reconcile loop converges without special-casing the
// already-gone race.
func TestProperty_TeardownIsIdempotentAndConverges(t *testing.T) {
	t.Parallel()
	rapid.Check(t, func(rt *rapid.T) {
		prov := workspaceprovidertest.FakeProvider(nil)
		ctx := context.Background()
		ws, err := prov.Provision(ctx, drawSpec(rt))
		if err != nil {
			rt.Fatalf("Provision: %v", err)
		}
		handle := ws.Handle()
		if terr := prov.Teardown(ctx, handle); terr != nil {
			rt.Fatalf("first Teardown: %v", terr)
		}
		if terr := prov.Teardown(ctx, handle); terr != nil {
			rt.Fatalf("second Teardown must be idempotent (nil), got: %v", terr)
		}
		if _, oerr := prov.Open(ctx, handle); errors.KindOf(oerr) != errors.KindNotFound {
			rt.Fatalf("Open after Teardown Kind = %v, want NotFound", errors.KindOf(oerr))
		}
	})
}

// TestProperty_ErrorKindRoundTrip asserts the error-taxonomy contract: every workspaceprovider
// error type maps to its stable errors.Kind when wrapped (the transport boundary reads KindOf with
// no per-port table, 10 §9) and is recoverable from the chain via AsType. A drift here breaks every
// caller that branches on Kind.
func TestProperty_ErrorKindRoundTrip(t *testing.T) {
	t.Parallel()
	type errCase struct {
		err  error
		kind errors.Kind
	}
	rapid.Check(t, func(rt *rapid.T) {
		field := rapid.StringMatching(`[a-zA-Z]{1,10}`).Draw(rt, "field")
		cases := []errCase{
			{&workspaceprovider.InvalidSpecError{Field: field, Reason: field}, errors.KindInvalid},
			{&workspaceprovider.ImageError{Image: field}, errors.KindInvalid},
			{&workspaceprovider.NotFoundError{Path: field}, errors.KindNotFound},
			{&workspaceprovider.ConflictError{Name: field}, errors.KindConflict},
			{&workspaceprovider.QuotaExceededError{Resource: field}, errors.KindExhausted},
			{&workspaceprovider.IsolationError{Detail: field}, errors.KindPermission},
			{&workspaceprovider.SubstrateUnavailableError{Substrate: workspaceprovider.SubstrateDocker, Op: field}, errors.KindUnavailable},
			{&workspaceprovider.NotReadyError{Op: field}, errors.KindInvalid},
			{&workspaceprovider.DeadlineError{Op: field}, errors.KindDeadline},
			{&workspaceprovider.UnsupportedError{Cap: workspaceprovider.CapExecPTY}, errors.KindInvalid},
			{&workspaceprovider.InvalidHandleError{Raw: field}, errors.KindInvalid},
		}
		for _, c := range cases {
			if c.err.Error() == "" {
				rt.Fatalf("%T renders an empty Error()", c.err)
			}
			wrapped := errors.Wrap(c.kind, "property: "+field, c.err)
			if errors.KindOf(wrapped) != c.kind {
				rt.Fatalf("%T wrapped Kind = %v, want %v", c.err, errors.KindOf(wrapped), c.kind)
			}
		}
	})
}

// reverseMounts returns a reversed copy of the mounts slice.
func reverseMounts(in []workspaceprovider.Mount) []workspaceprovider.Mount {
	out := make([]workspaceprovider.Mount, len(in))
	for i := range in {
		out[len(in)-1-i] = in[i]
	}
	return out
}

// reverseEgress returns a reversed copy of the egress slice.
func reverseEgress(in []workspaceprovider.EgressRule) []workspaceprovider.EgressRule {
	out := make([]workspaceprovider.EgressRule, len(in))
	for i := range in {
		out[len(in)-1-i] = in[i]
	}
	return out
}
