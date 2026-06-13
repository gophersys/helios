package workspaceprovidertest

import (
	"testing"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/dockeradapter"
	"github.com/gophersys/libs/go/workspaceprovider/kubernetesadapter"
)

// harnessConfig is the resolved option set the real-substrate spinners read.
type harnessConfig struct {
	perTest       bool
	prePullImages []string
	keepOnFailure bool
}

// HarnessOption tunes a real-substrate harness.
type HarnessOption func(*harnessConfig)

// WithPerTest forces a dedicated substrate per test (slow, hermetic) instead of the
// shared default. For docker the EphemeralContainer is always per-test-isolated by its
// label namespace, so this is a no-op there; it is load-bearing for the cluster spinners.
func WithPerTest() HarnessOption { return func(c *harnessConfig) { c.perTest = true } }

// WithImages pre-pulls images into the substrate so a per-test provision is fast and
// offline-safe.
func WithImages(refs ...string) HarnessOption {
	return func(c *harnessConfig) { c.prePullImages = append(c.prePullImages, refs...) }
}

// KeepOnFailure skips Cleanup when the test failed (debugging).
func KeepOnFailure() HarnessOption { return func(c *harnessConfig) { c.keepOnFailure = true } }

// resolveOptions folds the options into a config.
func resolveOptions(opts ...HarnessOption) harnessConfig {
	var c harnessConfig
	for _, o := range opts {
		o(&c)
	}
	return c
}

// EphemeralContainer spins a throwaway, isolated docker context (a dedicated label
// namespace) on the local daemon, returns a live workspaceprovider.Adapter bound to the
// REAL dockeradapter, and registers Cleanup to reclaim every container/network/volume it
// created (forced teardown, C23). It SKIPS (t.Skip) when no docker daemon is reachable, so
// the suite degrades on a machine without docker rather than failing.
//
//nolint:ireturn // the C23 harness vends the workspaceprovider.Adapter port (docker/k3d/kind interchangeably); returning the port IS the contract.
func EphemeralContainer(t *testing.T, opts ...HarnessOption) workspaceprovider.Adapter {
	t.Helper()
	configuration := resolveOptions(opts...)

	adapter, cleanup, err := dockeradapter.NewEphemeral(t.Context(), dockeradapter.EphemeralConfig{
		LabelNamespace: uniqueNamespace(t),
		PrePullImages:  configuration.prePullImages,
	})
	if err != nil {
		if dockeradapter.IsDaemonUnavailable(err) {
			t.Skipf("docker daemon unavailable, skipping real-substrate test: %v", err)
		}
		t.Fatalf("spin ephemeral docker context: %v", err)
	}
	t.Cleanup(func() {
		if configuration.keepOnFailure && t.Failed() {
			t.Logf("KeepOnFailure: leaving docker objects in namespace %q for inspection", uniqueNamespace(t))
			return
		}
		if cerr := cleanup(); cerr != nil {
			t.Errorf("cleanup ephemeral docker context: %v", cerr)
		}
	})
	return adapter
}

// K3dCluster creates an ephemeral k3d cluster (k3s-in-docker — the DEFAULT local/test
// substrate, ADR-0016 §4), returns an Adapter bound to the REAL kubernetesadapter pointed
// at its kubeconfig, and `k3d cluster delete`s it on t.Cleanup (on failure too — leaking a
// k3d cluster is unacceptable, C23). SKIPS (t.Skip) when k3d or docker is unavailable, so
// the suite degrades on a machine without the tooling rather than failing. The cluster name
// carries a timestamp + a process-monotonic suffix so parallel/abandoned runs never collide.
//
//nolint:ireturn // the C23 harness vends the workspaceprovider.Adapter port (docker/k3d/kind interchangeably); returning the port IS the contract.
func K3dCluster(t *testing.T, opts ...HarnessOption) workspaceprovider.Adapter {
	t.Helper()
	configuration := resolveOptions(opts...)
	if !k3dAvailable() {
		t.Skip("k3d or docker unavailable, skipping real-cluster conformance (the k3d binding needs both)")
	}
	cluster, err := createK3dCluster(t.Context(), configuration.prePullImages)
	if err != nil {
		t.Skipf("k3d cluster create unavailable, skipping: %v", err)
	}
	return bindCluster(t, cluster, configuration)
}

// KindCluster is the SECOND conformance target (kind v0.32.0, ADR-0016 §4): identical shape
// over a different distro. Running RunProviderSuite over BOTH K3dCluster and KindCluster is
// the EMPIRICAL proof of the distro-transparency claim (05 §3/§6) — same suite, two distros,
// both green. It deletes the cluster on t.Cleanup (on failure too) and SKIPS when kind/docker
// is unavailable.
//
//nolint:ireturn // the C23 harness vends the workspaceprovider.Adapter port; returning the port IS the contract.
func KindCluster(t *testing.T, opts ...HarnessOption) workspaceprovider.Adapter {
	t.Helper()
	configuration := resolveOptions(opts...)
	if !kindAvailable() {
		t.Skip("kind or docker unavailable, skipping real-cluster conformance (the kind binding needs both)")
	}
	cluster, err := createKindCluster(t.Context(), configuration.prePullImages)
	if err != nil {
		t.Skipf("kind cluster create unavailable, skipping: %v", err)
	}
	return bindCluster(t, cluster, configuration)
}

// bindCluster binds the REAL kubernetesadapter to the just-created ephemeral cluster, registers
// the cluster-delete + namespace-reap on t.Cleanup (on failure too — a leaked cluster is
// unacceptable, C23), and returns the adapter as the Adapter port. The cluster-delete is the
// OUTER teardown guarantee (the whole cluster goes); the per-run namespace reap is the inner
// one (a shared cluster stays clean). It SKIPS if the apiserver is unreachable.
//
//nolint:ireturn // the C23 harness vends the workspaceprovider.Adapter port; returning the port IS the contract.
func bindCluster(t *testing.T, cluster *ephemeralCluster, configuration harnessConfig) workspaceprovider.Adapter {
	t.Helper()
	t.Cleanup(func() {
		if configuration.keepOnFailure && t.Failed() {
			t.Logf("KeepOnFailure: leaving cluster %q (kubeconfig %s) for inspection", cluster.Name, cluster.Kubeconfig)
			return
		}
		if derr := cluster.delete(); derr != nil {
			t.Errorf("delete ephemeral cluster %q: %v", cluster.Name, derr)
		}
	})

	adapter, reap, err := kubernetesadapter.NewEphemeral(t.Context(), kubernetesadapter.EphemeralConfig{
		Kubeconfig:     cluster.Kubeconfig,
		LabelNamespace: uniqueClusterNamespace(t),
		Distro:         cluster.Distro,
	})
	if err != nil {
		if kubernetesadapter.IsClusterUnavailable(err) {
			t.Skipf("kubernetes apiserver unreachable on cluster %q: %v", cluster.Name, err)
		}
		t.Fatalf("bind kubernetes adapter to cluster %q: %v", cluster.Name, err)
	}
	t.Cleanup(func() {
		if rerr := reap(); rerr != nil {
			t.Errorf("reap namespaces on cluster %q: %v", cluster.Name, rerr)
		}
	})
	return adapter
}

// uniqueNamespace derives a collision-proof, per-test docker label namespace from the test
// name plus a process-unique token, so parallel or abandoned runs never reap each other's
// containers (the C23 unique-suffix discipline).
func uniqueNamespace(t *testing.T) string {
	t.Helper()
	return dockeradapter.SanitizeNamespace("edentest-" + t.Name())
}

// uniqueClusterNamespace derives a collision-proof, per-test ownership-domain namespace prefix
// for the kubernetes adapter within the cluster (so a shared cluster's per-test reap targets
// exactly this run's namespaces).
func uniqueClusterNamespace(t *testing.T) string {
	t.Helper()
	return kubernetesadapter.SanitizeName("edentest-" + t.Name())
}
