package workspaceprovidertest

import (
	"testing"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/dockeradapter"
	"github.com/gophersys/libs/go/workspaceprovider/kubernetesadapter"
)

// harnessConfig is the resolved option set the real-substrate spinners read.
type harnessConfig struct {
	perTest             bool
	prePullImages       []string
	keepOnFailure       bool
	editorIngressDomain string
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

// WithEditorIngressDomain configures the kubernetes adapter the cluster harness binds with a
// wildcard editor ingress domain, so a spec.Editor authors the host-per-agent editor Ingress
// "<agent-id>.editor.<domain>" (ADR-0027 §3) — the editor-sidecar integration test asserts that
// Ingress OBJECT exists on the live cluster. No effect on the docker harness (docker has no Ingress).
func WithEditorIngressDomain(domain string) HarnessOption {
	return func(c *harnessConfig) { c.editorIngressDomain = domain }
}

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

	adapter, cleanup, err := dockeradapter.NewEphemeral(t.Context(), dockeradapter.EphemeralDaemonConfig{
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
	adapter, _ := K3dClusterNamed(t, opts...)
	return adapter
}

// K3dClusterNamed is K3dCluster plus the cluster's name (so a test that must reach the cluster's
// node containers — e.g. joining a private registry's docker network for an in-cluster
// authenticated pull, B7 — can identify them via ClusterNodes(name)). The name is empty when the
// harness Skipped.
//
//nolint:ireturn // the C23 harness vends the workspaceprovider.Adapter port; returning the port IS the contract.
func K3dClusterNamed(t *testing.T, opts ...HarnessOption) (adapter workspaceprovider.Adapter, clusterName string) {
	t.Helper()
	configuration := resolveOptions(opts...)
	if !k3dAvailable() {
		t.Skip("k3d or docker unavailable, skipping real-cluster conformance (the k3d binding needs both)")
	}
	cluster, err := createK3dCluster(t.Context(), configuration.prePullImages)
	if err != nil {
		t.Skipf("k3d cluster create unavailable, skipping: %v", err)
	}
	return bindCluster(t, cluster, configuration), cluster.Name
}

// K3dClusterWithRegistry is the B7 (pull-secret) harness: it stands up an ephemeral k3d cluster
// configured to reach a freshly-spun PRIVATE authenticated registry over HTTP (a registries.yaml
// endpoint, NO baked-in auth — credentials come from the Pod's ImagePullSecret, the B7 fix under
// test), joins the cluster's nodes to the registry network, pre-pushes a private image, and
// returns the kubernetesadapter bound to the cluster plus the live registry. Both the cluster and
// the registry are reaped on t.Cleanup. It SKIPS when k3d/docker/htpasswd is unavailable. baseImage
// is the public image the private one is derived FROM.
//
//nolint:ireturn // the harness vends the workspaceprovider.Adapter port; returning the port IS the contract.
func K3dClusterWithRegistry(t *testing.T, baseImage string, opts ...HarnessOption) (workspaceprovider.Adapter, *LocalRegistry) {
	t.Helper()
	configuration := resolveOptions(opts...)
	if !k3dAvailable() {
		t.Skip("k3d or docker unavailable, skipping pull-secret conformance (needs both)")
	}

	registry, rerr := NewLocalRegistry(t.Context(), baseImage)
	if rerr != nil {
		t.Skipf("local authenticated registry unavailable, skipping pull-secret test: %v", rerr)
	}
	t.Cleanup(registry.Delete)

	registriesYAML, werr := registry.WriteRegistriesYAML()
	if werr != nil {
		t.Skipf("write k3d registries.yaml: %v", werr)
	}
	cluster, cerr := createK3dCluster(t.Context(), configuration.prePullImages, "--registry-config", registriesYAML)
	if cerr != nil {
		t.Skipf("k3d cluster create (with registry) unavailable, skipping: %v", cerr)
	}

	// Join the cluster nodes to the registry network so the container hostname resolves in-cluster.
	registry.JoinCluster(t.Context(), ClusterNodes(t.Context(), cluster.Name))
	return bindCluster(t, cluster, configuration), registry
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

// ClusterAccess carries the raw handles a test needs to reach a just-spun ephemeral cluster
// OUTSIDE the Adapter port — the isolated Kubeconfig path (so a `kubectl exec` lands on THIS
// cluster, never the developer's ~/.kube/config) and the cluster Name (for diagnostics). The
// editor-sidecar integration test (ADR-0027) uses it to `kubectl exec` into the read-only editor
// CONTAINER (which the Connection.Exec port intentionally cannot target — it only execs the
// workspace container) to reach the editor over the pod-localhost and to prove the read-only mount
// STRUCTURALLY (a write from the editor side fails EROFS).
type ClusterAccess struct {
	Kubeconfig string
	Name       string
}

// K3dClusterForEditor is K3dCluster plus the cluster's ClusterAccess (kubeconfig + name), so the
// editor-sidecar integration test can `kubectl exec` into the editor container — the one reach the
// Adapter's Connection.Exec port does not offer (it execs the workspace container only). The
// cluster + its namespaces are reaped on t.Cleanup exactly as K3dCluster. SKIPS when k3d/docker is
// unavailable.
//
//nolint:ireturn // the harness vends the workspaceprovider.Adapter port; returning the port IS the contract.
func K3dClusterForEditor(t *testing.T, opts ...HarnessOption) (workspaceprovider.Adapter, ClusterAccess) {
	t.Helper()
	configuration := resolveOptions(opts...)
	if !k3dAvailable() {
		t.Skip("k3d or docker unavailable, skipping editor-sidecar conformance (the k3d binding needs both)")
	}
	cluster, err := createK3dCluster(t.Context(), configuration.prePullImages)
	if err != nil {
		t.Skipf("k3d cluster create unavailable, skipping: %v", err)
	}
	return bindCluster(t, cluster, configuration), ClusterAccess{Kubeconfig: cluster.Kubeconfig, Name: cluster.Name}
}

// KindClusterForEditor is KindCluster plus the cluster's ClusterAccess. kind ships NO ingress
// controller, so the editor test asserts at the Service / pod-exec layer on kind (never the
// Ingress) and encodes that divergence honestly (ADR-0012 CapStatus), never a silent skip. SKIPS
// when kind/docker is unavailable.
//
//nolint:ireturn // the harness vends the workspaceprovider.Adapter port; returning the port IS the contract.
func KindClusterForEditor(t *testing.T, opts ...HarnessOption) (workspaceprovider.Adapter, ClusterAccess) {
	t.Helper()
	configuration := resolveOptions(opts...)
	if !kindAvailable() {
		t.Skip("kind or docker unavailable, skipping editor-sidecar conformance (the kind binding needs both)")
	}
	cluster, err := createKindCluster(t.Context(), configuration.prePullImages)
	if err != nil {
		t.Skipf("kind cluster create unavailable, skipping: %v", err)
	}
	return bindCluster(t, cluster, configuration), ClusterAccess{Kubeconfig: cluster.Kubeconfig, Name: cluster.Name}
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

	adapter, reap, err := kubernetesadapter.NewEphemeral(t.Context(), kubernetesadapter.EphemeralClusterConfig{
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
	// Post-New setter (the ephemeral test seam): when the harness was given an editor ingress domain,
	// a spec.Editor then authors the host-per-agent Ingress (ADR-0027 §3) — kept off the frozen
	// EphemeralClusterConfig (by-value) so its size stays small.
	adapter.WithEditorIngressDomain(configuration.editorIngressDomain)
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
