package workspaceprovidertest

import (
	"context"
	"io"
	"slices"
	"strings"
	"testing"

	"github.com/gophersys/libs/go/dependencies/dependenciestest"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
	"github.com/gophersys/libs/go/secrets/secretstest"
	edentesting "github.com/gophersys/libs/go/testing"
	"github.com/gophersys/libs/go/workspaceprovider"
)

// SeededCanary is the credential plaintext the suite seeds so the no-leak assertions have
// a concrete needle. A workspace's ImagePull/MountSecret/RunSpec.Credential resolves to
// it, yet it must appear in NO Spec/Handle/Descriptor/Status/log/error.
const SeededCanary = "S3CR3T-canary-do-not-leak"

// canaryRef is the secrets.Reference the seeded canary resolves under.
const canaryRef = "test-pull-secret"

// ProviderSuite is THE one Suite (05 §6, ADR-0016), exported per the testing pattern. It
// runs the SAME cases over every Adapter binding — the in-memory fake AND a real docker/
// k3d/kind substrate — so substitutability is EXECUTED, not asserted. Capability-gated
// cases Skip (not fail) where the substrate's manifest declares a capability absent (05 §3
// graceful degradation). newAdapter (the Factory) builds a fresh Adapter bound to its
// substrate; the harnesses in this package supply the docker/k3d/kind ones, NewAdapter
// supplies the in-memory one.
//
// NOTE ON THE ADAPTER SEAM: the conformance subject is the high-level workspaceprovider
// Provider behavior, exercised THROUGH a freshly-constructed Provisioner wired over the
// Adapter the factory yields. The factory's S is workspaceprovider.Adapter (the contract's
// §4 signature); each case wraps it in a real *Provisioner via the library's New so the
// state machine, idempotency, Handle stamping, and the credential seam — all LIBRARY-owned
// — are under test exactly as a consumer sees them.
func ProviderSuite() edentesting.Suite[workspaceprovider.Adapter] {
	return edentesting.Suite[workspaceprovider.Adapter]{
		Name:  "workspaceprovider.Provider",
		Cases: slices.Values(providerCases()),
	}
}

// RunProviderSuite drives the ProviderSuite over factory against a *testing.T, mapping the
// structured testing.Result onto t (one subtest per case; Skip ≠ Fail). It is the single
// call site the four bindings share (fake + real docker + real k3d + real kind). It probes
// the factory's adapter once to read its CapabilityManifest, then configures the runner's
// RequireCapabilities so a capability-gated case Skips (not fails) where the substrate
// declares it absent (05 §3).
func RunProviderSuite(t *testing.T, factory func(ctx context.Context, h edentesting.Harness) (workspaceprovider.Adapter, error)) {
	t.Helper()
	probe, perr := factory(context.Background(), probeHarness{})
	if perr != nil {
		t.Fatalf("probe factory for capability manifest: %v", perr)
	}
	runner, err := edentesting.New(
		edentesting.Config{RequireCapabilities: declaredCapabilityNames(probe.Manifest())},
		edentesting.Deps{},
	)
	if err != nil {
		t.Fatalf("build conformance runner: %v", err)
	}
	result := edentesting.RunSuite(runner, ProviderSuite(), factory)
	for _, cr := range result.Cases {
		cr := cr
		t.Run(cr.Name, func(t *testing.T) {
			switch cr.Outcome {
			case edentesting.Skip:
				t.Skip(strings.Join(cr.Messages, "; "))
			case edentesting.Fail:
				t.Errorf("%s", strings.Join(cr.Messages, "; "))
			case edentesting.Pass:
			}
			if cr.Panic != "" {
				t.Errorf("case panicked: %s", cr.Panic)
			}
		})
	}
}

// FakeProvider returns a ready-to-use in-memory workspaceprovider.Provider (a Provisioner
// wired over the in-memory Adapter + a fake secrets.Provider seeded from seed + a fake
// Clock) for consumer unit tests that just need a working Provider in one call.
//
//nolint:ireturn // contract §3: FakeProvider returns the workspaceprovider.Provider port; the surface is frozen.
func FakeProvider(seed map[string]string) workspaceprovider.Provider {
	set, _, _, _ := dependenciestest.Fakes()
	prov, err := workspaceprovider.New(
		workspaceprovider.Config{Default: workspaceprovider.SubstrateDocker},
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{
				workspaceprovider.SubstrateDocker: NewAdapter(defaultCaps()...),
			},
			Secrets: secretstest.New(seed),
			Clock:   set.Clock,
		},
	)
	if err != nil {
		// New is pure and the wiring above is statically valid, so this only fires on a
		// programming error in this helper.
		panic("workspaceprovidertest.FakeProvider: " + err.Error())
	}
	return prov
}

// providerOver builds a real *Provisioner wired over adapter + a canary-seeded fake
// secrets.Provider + a deterministic Clock, so a case exercises the LIBRARY-owned behavior
// against the given substrate. It returns the Provider and the fake secrets.Provider (for
// the no-leak resolution assertions).
func providerOver(adapter workspaceprovider.Adapter) (provider *workspaceprovider.Provisioner, secretsProvider *secretstest.Provider) {
	set, _, _, _ := dependenciestest.Fakes()
	sec := secretstest.New(map[string]string{canaryRef: SeededCanary})
	substrate := substrateOf(adapter)
	prov, err := workspaceprovider.New(
		workspaceprovider.Config{Default: substrate},
		workspaceprovider.Deps{
			Adapters: map[workspaceprovider.Substrate]workspaceprovider.Adapter{substrate: adapter},
			Secrets:  sec,
			Clock:    set.Clock,
		},
	)
	if err != nil {
		panic("workspaceprovidertest.providerOver: " + err.Error())
	}
	return prov, sec
}

// substrateOf reports which Substrate an adapter serves, read from its manifest's Distro
// hint (docker adapters tag "docker …"; kubernetes adapters tag a distro). The fake tags
// "in-memory fake" and is treated as docker. This keeps the factory's S a plain Adapter
// per the contract while letting providerOver route correctly.
func substrateOf(adapter workspaceprovider.Adapter) workspaceprovider.Substrate {
	distro := strings.ToLower(adapter.Manifest().Distro)
	switch {
	case strings.Contains(distro, "k3d"), strings.Contains(distro, "k3s"),
		strings.Contains(distro, "kind"), strings.Contains(distro, "kubernetes"):
		return workspaceprovider.SubstrateKubernetes
	default:
		return workspaceprovider.SubstrateDocker
	}
}

// readAllClose reads rc to EOF and closes it, returning the bytes.
func readAllClose(rc io.ReadCloser) ([]byte, error) {
	defer func() { _ = rc.Close() }() //nolint:errcheck // closing a fully-read stream has no actionable error.
	data, err := io.ReadAll(rc)
	if err != nil {
		return nil, errors.Wrap(errors.KindInternal, "workspaceprovidertest: read stream", err)
	}
	return data, nil
}

// drainToTerminal ranges a Run.Status to its terminal transition and returns the last
// RunStatus seen, exercising the workload's real exit signal.
func drainToTerminal(ctx context.Context, run workspaceprovider.Run) workspaceprovider.RunStatus {
	var last workspaceprovider.RunStatus
	for {
		status, ok := run.Status(ctx)
		last = status
		if !ok || status.Phase.IsTerminal() {
			return last
		}
	}
}

// pullSecretRef is the canary-bearing reference a spec uses to drive the credential seam.
func pullSecretRef() secrets.Reference { return secrets.Ref(canaryRef) }

// declaredCapabilityNames maps the manifest's CapPartial/CapFull capabilities to the
// gate names the conformance cases check via h.Has(...). A CapAbsent capability is omitted
// so its gated case Skips.
func declaredCapabilityNames(manifest workspaceprovider.CapabilityManifest) []string {
	all := []workspaceprovider.Capability{
		workspaceprovider.CapExecPTY,
		workspaceprovider.CapPersistentVolume,
		workspaceprovider.CapBindMount,
		workspaceprovider.CapEgressPolicy,
		workspaceprovider.CapResourceLimits,
		workspaceprovider.CapLogStream,
		workspaceprovider.CapMultiTenant,
		workspaceprovider.CapReattach,
		workspaceprovider.CapHibernate,
	}
	var names []string
	for _, c := range all {
		if manifest.Supports(c) {
			names = append(names, c.String())
		}
	}
	return names
}

// probeHarness is a no-op Harness used only to invoke the factory once for its manifest
// (no case runs against it). Its Context is the background context; the deterministic
// sources are never read.
type probeHarness struct{}

//nolint:ireturn // implements the testing.Harness interface; these methods MUST return the port types.
func (probeHarness) Clock() edentesting.Clock { return nil }

//nolint:ireturn // implements the testing.Harness interface; these methods MUST return the port types.
func (probeHarness) RandomSource() edentesting.RandomSource { return nil }
func (probeHarness) Has(string) bool                        { return false }
func (probeHarness) Cleanup(func())                         {}
func (probeHarness) Context() context.Context               { return context.Background() }
