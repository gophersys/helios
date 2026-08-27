package kubernetesadapter_test

import (
	stderrors "errors"
	"os"
	"path/filepath"
	"testing"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/kubernetesadapter"
)

// minimalKubeconfig is a syntactically-valid kubeconfig pointing at an UNREACHABLE apiserver.
// It lets New build a client WITHOUT any apiserver dial (the first apiserver call is
// Create/Dial/List/Destroy) — the construction-is-pure proof.
const minimalKubeconfig = `apiVersion: v1
kind: Config
clusters:
- name: unreachable
  cluster:
    server: https://127.0.0.1:1
contexts:
- name: unreachable
  context:
    cluster: unreachable
    user: none
current-context: unreachable
users:
- name: none
  user: {}
`

// writeKubeconfig writes the minimal kubeconfig to a temp file and returns its path.
func writeKubeconfig(t *testing.T) string {
	t.Helper()
	path := filepath.Join(t.TempDir(), "kubeconfig")
	if err := os.WriteFile(path, []byte(minimalKubeconfig), 0o600); err != nil {
		t.Fatalf("write kubeconfig: %v", err)
	}
	return path
}

func TestNew_IsPure(t *testing.T) {
	t.Parallel()
	// New builds the client from a kubeconfig but performs NO apiserver I/O — it must not
	// error merely because the cluster is unreachable. The first apiserver call is
	// Create/Dial/List/Destroy; the kubeconfig points at an unreachable server to prove no
	// dial happens at construction.
	adapter, err := kubernetesadapter.New(kubernetesadapter.Config{Kubeconfig: writeKubeconfig(t), LabelNamespace: "unit"})
	if err != nil {
		t.Fatalf("New must be pure (no apiserver dial): %v", err)
	}
	if adapter == nil {
		t.Fatalf("New returned a nil *Adapter with a nil error")
	}
}

func TestManifest_IsTruthful(t *testing.T) {
	t.Parallel()
	adapter, err := kubernetesadapter.New(kubernetesadapter.Config{Kubeconfig: writeKubeconfig(t)})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	m := adapter.WithDistro("k3d v5.9 / k3s").Manifest()
	if m.Distro != "k3d v5.9 / k3s" {
		t.Errorf("Manifest.Distro = %q, want the WithDistro value", m.Distro)
	}
	// kubernetes has full resource limits, exec PTY, log streaming, re-attach, multi-tenancy.
	for _, capFull := range []workspaceprovider.Capability{
		workspaceprovider.CapResourceLimits,
		workspaceprovider.CapExecPTY,
		workspaceprovider.CapLogStream,
		workspaceprovider.CapReattach,
		workspaceprovider.CapMultiTenant,
	} {
		if m.Status(capFull) != workspaceprovider.CapFull {
			t.Errorf("kubernetes Manifest.Status(%v) = %v, want CapFull", capFull, m.Status(capFull))
		}
	}
	// Hibernate is the deferred verb (Q4) — absent.
	if m.Status(workspaceprovider.CapHibernate) != workspaceprovider.CapAbsent {
		t.Errorf("CapHibernate = %v, want CapAbsent", m.Status(workspaceprovider.CapHibernate))
	}
}

func TestSanitizeName_IsExportedAndStable(t *testing.T) {
	t.Parallel()
	if got := kubernetesadapter.SanitizeName("Eden WS/1"); got != "eden-ws-1" {
		t.Errorf("SanitizeName = %q, want eden-ws-1", got)
	}
}

func TestIsClusterUnavailable(t *testing.T) {
	t.Parallel()
	if kubernetesadapter.IsClusterUnavailable(nil) {
		t.Errorf("IsClusterUnavailable(nil) = true, want false")
	}
	if !kubernetesadapter.IsClusterUnavailable(stderrors.New("dial tcp 127.0.0.1:6443: connection refused")) {
		t.Errorf("IsClusterUnavailable(apiserver-down) = false, want true")
	}
	if kubernetesadapter.IsClusterUnavailable(stderrors.New("some unrelated error")) {
		t.Errorf("IsClusterUnavailable(unrelated) = true, want false")
	}
}
