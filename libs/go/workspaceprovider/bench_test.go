package workspaceprovider_test

import (
	"context"
	"testing"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// sink keeps the benchmarked work observable so the compiler cannot prove the result dead and
// elide it (a package-level `any` per ADR-0020 dimension (g); kept off any sentinel path).
//
//nolint:gochecknoglobals // benchmark sink must be package-level so the compiler cannot elide the work.
var sink any

// benchSpec is a representative provision request the hot-path benchmarks drive: an image, two
// mounts, resource ceilings, an egress allow, non-secret env, and the tenancy labels — the shape
// the orchestrator's reconcile loop hands Provision per workspace.
var benchSpec = workspaceprovider.WorkspaceSpec{
	Name:  "ws-bench",
	Image: "busybox:1.36",
	Mounts: []workspaceprovider.Mount{
		{Kind: workspaceprovider.MountBind, Target: "/workspace"},
		{Kind: workspaceprovider.MountInputs, Target: "/inputs", ReadOnly: true},
	},
	Resources: workspaceprovider.Resources{CPUMilli: 500, MemoryBytes: 256 << 20, PIDs: 256},
	Egress:    []workspaceprovider.EgressRule{{Host: "api.anthropic.com", Note: "anthropic api"}},
	Env:       []workspaceprovider.EnvVar{{Name: "EDEN_STAGE", Value: "test"}},
	Labels: map[string]string{
		workspaceprovider.LabelOrganization: "org-bench",
		workspaceprovider.LabelProject:      "proj-bench",
	},
}

// BenchmarkProvision measures the Provision hot path over the in-memory fake (spec validation +
// fingerprint hash + idempotency List + Handle stamping + Connection wrap — every LIBRARY-owned
// step a real provision pays before the substrate I/O). It is the per-workspace cost the reconcile
// loop pays on every desired-but-absent workspace.
func BenchmarkProvision(b *testing.B) {
	prov := workspaceprovidertest.FakeProvider(nil)
	ctx := context.Background()
	b.ReportAllocs()
	var ws workspaceprovider.Workspace
	for i := 0; b.Loop(); i++ {
		spec := benchSpec
		spec.Name = "ws-bench" // stable name so the idempotency path is exercised after the first
		var err error
		ws, err = prov.Provision(ctx, spec)
		if err != nil {
			b.Fatalf("Provision: %v", err)
		}
	}
	sink = ws
}

// BenchmarkProvisionTeardown measures one full provision→teardown cycle (the create + reclaim the
// reconcile/GC loop pays per ephemeral workspace), so the fingerprint + Handle parse + Destroy
// routing are all on the measured path.
func BenchmarkProvisionTeardown(b *testing.B) {
	prov := workspaceprovidertest.FakeProvider(nil)
	ctx := context.Background()
	b.ReportAllocs()
	for i := 0; b.Loop(); i++ {
		spec := benchSpec
		spec.Name = "ws-bench-cycle"
		ws, err := prov.Provision(ctx, spec)
		if err != nil {
			b.Fatalf("Provision: %v", err)
		}
		if terr := prov.Teardown(ctx, ws.Handle()); terr != nil {
			b.Fatalf("Teardown: %v", terr)
		}
		sink = ws
	}
}

// BenchmarkParseHandle measures the durable-Handle round-trip — the hot path the orchestrator
// pays re-hydrating its only per-workspace persisted state on every Open across a control-plane
// restart (the statelessness guarantee).
func BenchmarkParseHandle(b *testing.B) {
	const raw = "kubernetes://eden/org-7/proj-42/ws-9f3a/%2Fworkspace%2Feden"
	b.ReportAllocs()
	var h workspaceprovider.Handle
	for b.Loop() {
		var err error
		h, err = workspaceprovider.ParseHandle(raw)
		if err != nil {
			b.Fatalf("ParseHandle: %v", err)
		}
	}
	sink = h
}

// BenchmarkHandleAccessors measures the Handle's pure decode accessors (Substrate/WorkDir/
// Organization/Project/Name) — read on every routing + tenancy decision the library makes.
func BenchmarkHandleAccessors(b *testing.B) {
	h, err := workspaceprovider.ParseHandle("kubernetes://eden/org-7/proj-42/ws-9f3a/%2Fworkspace")
	if err != nil {
		b.Fatalf("ParseHandle: %v", err)
	}
	b.ReportAllocs()
	var s string
	for b.Loop() {
		s = string(h.Substrate()) + h.WorkDir() + h.Organization() + h.Project() + h.Name()
	}
	sink = s
}

// BenchmarkStatus measures the Status normalization path over the fake Connection (Probe ->
// State/Condition/Usage + Clock-stamped Since) — the read the reconcile loop, dashboard, and
// usage meter poll per workspace.
func BenchmarkStatus(b *testing.B) {
	prov := workspaceprovidertest.FakeProvider(nil)
	ctx := context.Background()
	ws, err := prov.Provision(ctx, benchSpec)
	if err != nil {
		b.Fatalf("Provision: %v", err)
	}
	b.ReportAllocs()
	var st workspaceprovider.Status
	for b.Loop() {
		st, err = ws.Status(ctx)
		if err != nil {
			b.Fatalf("Status: %v", err)
		}
	}
	sink = st
}
