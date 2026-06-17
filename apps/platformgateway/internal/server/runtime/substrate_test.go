package runtime_test

import (
	"testing"

	"github.com/gophersys/eden/apps/platformgateway/internal/server/runtime"
)

// TestDetectSubstrate_HintWins asserts the EDEN_SUBSTRATE override is honored outright, before any
// host detection — a docker or kubernetes hint pins the substrate regardless of the environment.
func TestDetectSubstrate_HintWins(t *testing.T) {
	t.Parallel()
	cases := []struct {
		hint           string
		wantKubernetes bool
		wantString     string
	}{
		{"kubernetes", true, "kubernetes"},
		{"docker", false, "docker"},
	}
	for _, tc := range cases {
		got := runtime.DetectSubstrate(tc.hint)
		if got.IsKubernetes() != tc.wantKubernetes {
			t.Errorf("DetectSubstrate(%q).IsKubernetes() = %v, want %v", tc.hint, got.IsKubernetes(), tc.wantKubernetes)
		}
		if got.String() != tc.wantString {
			t.Errorf("DetectSubstrate(%q).String() = %q, want %q", tc.hint, got.String(), tc.wantString)
		}
		// An explicit docker hint is a container, not a bare process.
		if tc.hint == "docker" && got.IsBareProcess() {
			t.Errorf("DetectSubstrate(%q).IsBareProcess() = true, want false (explicit docker hint)", tc.hint)
		}
	}
}

// TestDetectSubstrate_UnknownHintFallsThrough asserts an unrecognized hint does not pin a substrate;
// detection falls through to the host signals, and on a CI/devcontainer host with no kubernetes
// signal it resolves to the non-kubernetes adapter (never silently kubernetes from a typo).
func TestDetectSubstrate_UnknownHintFallsThrough(t *testing.T) {
	t.Parallel()
	got := runtime.DetectSubstrate("not-a-real-substrate")
	if got.IsKubernetes() {
		t.Errorf("an unknown hint resolved to kubernetes; want host detection (non-kubernetes here)")
	}
	// String renders one of the non-kubernetes labels.
	if s := got.String(); s != "docker" && s != "bare-process" {
		t.Errorf("String() = %q, want docker or bare-process for a non-kubernetes host", s)
	}
}
