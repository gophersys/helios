package workspaceprovidertest_test

import (
	"context"
	"testing"

	edentesting "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/workspaceprovidertest"
)

// TestFake_Conforms runs THE one ProviderSuite over the in-memory fake Adapter — the
// fake ≡ adapter closure (08 §2). The same suite runs over a REAL docker daemon in the
// dockeradapter integration test (//go:build integration) and, when the kubernetes adapter
// lands, over k3d and kind. Four bindings, one suite (ADR-0016 §4).
func TestFake_Conforms(t *testing.T) {
	t.Parallel()
	workspaceprovidertest.RunProviderSuite(t, func(_ context.Context, _ edentesting.Harness) (workspaceprovider.Adapter, error) {
		return workspaceprovidertest.NewAdapter(fullCapabilities()...), nil
	})
}

// TestFake_PartialAdapter_SkipsGatedCases proves graceful degradation (05 §3): a fake that
// declares CapEgressPolicy/CapResourceLimits/CapMultiTenant absent makes those gated cases
// SKIP, not FAIL — a partial adapter looks partial, not broken.
func TestFake_PartialAdapter_SkipsGatedCases(t *testing.T) {
	t.Parallel()
	workspaceprovidertest.RunProviderSuite(t, func(_ context.Context, _ edentesting.Harness) (workspaceprovider.Adapter, error) {
		// Only the always-present capabilities; the egress/limits/multi-tenant/reattach
		// gated cases must skip.
		return workspaceprovidertest.NewAdapter(
			workspaceprovider.CapExecPTY,
			workspaceprovider.CapBindMount,
			workspaceprovider.CapLogStream,
		), nil
	})
}

// fullCapabilities is the complete capability set the vanilla fake declares so every gated
// conformance case runs against it.
func fullCapabilities() []workspaceprovider.Capability {
	return []workspaceprovider.Capability{
		workspaceprovider.CapExecPTY,
		workspaceprovider.CapPersistentVolume,
		workspaceprovider.CapBindMount,
		workspaceprovider.CapEgressPolicy,
		workspaceprovider.CapResourceLimits,
		workspaceprovider.CapLogStream,
		workspaceprovider.CapMultiTenant,
		workspaceprovider.CapReattach,
		workspaceprovider.CapSupervise,
		workspaceprovider.CapWorkloadPod,
	}
}
