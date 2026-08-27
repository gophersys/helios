package agentsession_test

import (
	"strings"
	"testing"

	"github.com/gophersys/libs/go/agentsession"
	"github.com/gophersys/libs/go/errors"
	"github.com/gophersys/libs/go/secrets"
)

// kinder is the typed-error contract (errors.md): every agentsession error classifies to a
// stable errors.Kind so the transport boundary and the engine branch on Kind, never on a string.
type kinder interface {
	error
	Kind() errors.Kind
}

// TestTypedErrors_MessageAndKind covers every typed error's operator-safe Error() (no secret
// value) and its stable Kind(). It also asserts the AuthError carries the loggable
// secrets.Reference, never a value, and exercises both RouteError message branches.
func TestTypedErrors_MessageAndKind(t *testing.T) {
	t.Parallel()
	cases := []struct {
		name     string
		err      kinder
		kind     errors.Kind
		contains string
	}{
		{"Unsupported", agentsession.UnsupportedError{Cap: agentsession.CapSteer}, errors.KindInvalid, "capability not supported"},
		{"Spawn", agentsession.SpawnError{Harness: "claude"}, errors.KindUnavailable, "harness spawn failed: claude"},
		{"Auth", agentsession.AuthError{Reference: secrets.Ref("vault://eden/anthropic#setup-token")}, errors.KindUnauthenticated, "vault://eden/anthropic#setup-token"},
		{"State", agentsession.StateError{From: agentsession.StateReady, Op: "Prompt"}, errors.KindConflict, "operation Prompt is illegal in state"},
		{"UnknownPermission", agentsession.UnknownPermissionError{RequestID: "req-7"}, errors.KindNotFound, "req-7"},
		{"Config", agentsession.ConfigError{Field: "Adapters", Message: "empty"}, errors.KindInvalid, "invalid configuration: Adapters: empty"},
		{"RouteHarness", agentsession.RouteError{Harness: "omp"}, errors.KindInvalid, "no adapter registered for harness omp"},
		{"RoutePhaseRole", agentsession.RouteError{Phase: "implement", Role: "assistant"}, errors.KindInvalid, "no route for phase=implement role=assistant"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			t.Parallel()
			if got := tc.err.Error(); !strings.Contains(got, tc.contains) {
				t.Fatalf("Error() = %q, want substring %q", got, tc.contains)
			}
			if got := tc.err.Kind(); got != tc.kind {
				t.Fatalf("Kind() = %v, want %v", got, tc.kind)
			}
		})
	}
}

// TestCapabilityManifest_Status covers the manifest lookup: an unset map and an unlisted
// capability both report CapAbsent (the safe default), and a listed capability reports its value.
func TestCapabilityManifest_Status(t *testing.T) {
	t.Parallel()

	var zero agentsession.CapabilityManifest
	if got := zero.Status(agentsession.CapSteer); got != agentsession.CapAbsent {
		t.Fatalf("nil-map Status(CapSteer) = %v, want CapAbsent", got)
	}

	m := agentsession.CapabilityManifest{Capabilities: map[agentsession.Capability]agentsession.CapStatus{
		agentsession.CapSteer:  agentsession.CapFull,
		agentsession.CapResume: agentsession.CapPartial,
	}}
	if got := m.Status(agentsession.CapSteer); got != agentsession.CapFull {
		t.Fatalf("Status(CapSteer) = %v, want CapFull", got)
	}
	if got := m.Status(agentsession.CapResume); got != agentsession.CapPartial {
		t.Fatalf("Status(CapResume) = %v, want CapPartial", got)
	}
	if got := m.Status(agentsession.CapHostTools); got != agentsession.CapAbsent {
		t.Fatalf("unlisted Status(CapHostTools) = %v, want CapAbsent", got)
	}
}
