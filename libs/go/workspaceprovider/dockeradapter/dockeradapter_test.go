package dockeradapter_test

import (
	stderrors "errors"
	"testing"

	"github.com/gophersys/libs/go/workspaceprovider"
	"github.com/gophersys/libs/go/workspaceprovider/dockeradapter"
)

func TestNew_IsPure(t *testing.T) {
	t.Parallel()
	// New constructs the client but performs NO daemon I/O — it must not error on a
	// machine without a running daemon (the first daemon call is Create/Dial/List/Destroy).
	adapter, err := dockeradapter.New(dockeradapter.Config{LabelNamespace: "unit"})
	if err != nil {
		t.Fatalf("New must be pure (no daemon dial): %v", err)
	}
	if adapter == nil {
		t.Fatalf("New returned a nil *Adapter with a nil error")
	}
}

func TestManifest_IsTruthful(t *testing.T) {
	t.Parallel()
	adapter, err := dockeradapter.New(dockeradapter.Config{})
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	m := adapter.Manifest()
	if m.Distro == "" {
		t.Errorf("Manifest.Distro is empty")
	}
	// docker has full bind mounts, resource limits, exec PTY, log streaming, re-attach.
	for _, capFull := range []workspaceprovider.Capability{
		workspaceprovider.CapBindMount,
		workspaceprovider.CapResourceLimits,
		workspaceprovider.CapExecPTY,
		workspaceprovider.CapLogStream,
		workspaceprovider.CapReattach,
	} {
		if m.Status(capFull) != workspaceprovider.CapFull {
			t.Errorf("docker Manifest.Status(%v) = %v, want CapFull", capFull, m.Status(capFull))
		}
	}
	// docker has NO native persistent volume / multi-tenant quota plane.
	for _, capAbsent := range []workspaceprovider.Capability{
		workspaceprovider.CapPersistentVolume,
		workspaceprovider.CapMultiTenant,
	} {
		if m.Status(capAbsent) != workspaceprovider.CapAbsent {
			t.Errorf("docker Manifest.Status(%v) = %v, want CapAbsent", capAbsent, m.Status(capAbsent))
		}
	}
	// Egress is partial (docker has no NetworkPolicy CRD).
	if m.Status(workspaceprovider.CapEgressPolicy) != workspaceprovider.CapPartial {
		t.Errorf("docker CapEgressPolicy = %v, want CapPartial", m.Status(workspaceprovider.CapEgressPolicy))
	}
}

func TestSanitizeNamespace(t *testing.T) {
	t.Parallel()
	cases := map[string]string{
		"edentest-TestFoo/Bar": "edentest-testfoo-bar",
		"Already.Valid_name-1": "already.valid_name-1",
		"  weird **chars!!  ":  "weird-chars",
		"":                     "eden",
		"/////":                "eden",
	}
	for in, want := range cases {
		in, want := in, want
		t.Run(in, func(t *testing.T) {
			t.Parallel()
			if got := dockeradapter.SanitizeNamespace(in); got != want {
				t.Errorf("SanitizeNamespace(%q) = %q, want %q", in, got, want)
			}
		})
	}
}

func TestIsDaemonUnavailable(t *testing.T) {
	t.Parallel()
	if dockeradapter.IsDaemonUnavailable(nil) {
		t.Errorf("IsDaemonUnavailable(nil) = true, want false")
	}
	if !dockeradapter.IsDaemonUnavailable(stderrors.New("Cannot connect to the Docker daemon at unix:///var/run/docker.sock")) {
		t.Errorf("IsDaemonUnavailable(daemon-down) = false, want true")
	}
	if dockeradapter.IsDaemonUnavailable(stderrors.New("some unrelated error")) {
		t.Errorf("IsDaemonUnavailable(unrelated) = true, want false")
	}
}
